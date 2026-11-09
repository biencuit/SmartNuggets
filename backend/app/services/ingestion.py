"""Traitement des messages reçus du Raspberry Pi : mise à jour de la base + diffusion SSE."""

import asyncio
import base64
import binascii
import logging
from pathlib import Path

from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Alert, AlertType, Coop, Event, EventType, Severity, TriggerSource
from app.mqtt.messages import AlertMessage, TelemetryMessage
from app.repositories import AlertRepository, CoopRepository, EventRepository
from app.schemas import AlertRead, EventRead
from app.services.broadcaster import Broadcaster
from app.services.coop_service import DEFAULT_OFFLINE_AFTER_S, build_status
from app.timeutils import utcnow

logger = logging.getLogger(__name__)

IMAGE_SIGNATURES = {"jpeg": (b"\xff\xd8\xff",), "webp": (b"RIFF",)}


class IngestionService:
    def __init__(
        self,
        session: AsyncSession,
        broadcaster: Broadcaster,
        media_dir: Path,
        max_image_bytes: int = 2_000_000,
        offline_after_s: int = DEFAULT_OFFLINE_AFTER_S,
        low_battery_threshold: int = 20,
    ) -> None:
        self.session = session
        self.broadcaster = broadcaster
        self.media_dir = media_dir
        self.max_image_bytes = max_image_bytes
        self.offline_after_s = offline_after_s
        self.low_battery_threshold = low_battery_threshold
        self.coops = CoopRepository(session)
        self.events = EventRepository(session)
        self.alerts = AlertRepository(session)

    async def _get_coop(self, coop_id: str) -> Coop | None:
        coop = await self.coops.get(coop_id)
        if coop is None:
            logger.warning("Message ignoré : poulailler %r inconnu", coop_id)
        return coop

    async def handle_telemetry(self, coop_id: str, message: TelemetryMessage) -> None:
        coop = await self._get_coop(coop_id)
        if coop is None:
            return
        if message.door_state is not None:
            coop.door_state = message.door_state
        if message.inside_count is not None:
            coop.inside_count = message.inside_count
        low_battery_alert = None
        if message.battery_level is not None:
            if self._crosses_low_battery(coop.battery_level, message.battery_level):
                low_battery_alert = await self.alerts.add(
                    Alert(
                        coop_id=coop_id,
                        alert_type=AlertType.LOW_BATTERY,
                        severity=Severity.WARNING,
                        created_at=utcnow(),
                    )
                )
            coop.battery_level = message.battery_level
        if message.camera_ok is not None:
            coop.camera_ok = message.camera_ok
        coop.last_seen_at = utcnow()
        coop.is_online = True

        event = None
        if message.event is not None:
            payload = message.event
            inside_after = payload.inside_count_after
            if inside_after is None:
                inside_after = message.inside_count
            event = await self.events.add(
                Event(
                    coop_id=coop_id,
                    event_type=payload.event_type,
                    trigger_source=payload.trigger_source,
                    inside_count_after=inside_after,
                    ai_confidence=payload.ai_confidence,
                    occurred_at=payload.occurred_at,
                )
            )
        missing_hen_alert = None
        if (
            event is not None
            and event.event_type == EventType.DOOR_CLOSE
            and event.trigger_source == TriggerSource.SCHEDULE
        ):
            missing_hen_alert = await self._check_missing_hens(coop)
        await self.session.commit()

        self._publish_status(coop)
        if event is not None:
            self.broadcaster.publish(
                coop_id, "event", EventRead.model_validate(event).model_dump(mode="json")
            )
        if low_battery_alert is not None:
            self._publish_alert(low_battery_alert)
        if missing_hen_alert is not None:
            self._publish_alert(missing_hen_alert)

    async def _check_missing_hens(self, coop: Coop) -> Alert | None:
        """US-COMPT-4 : porte fermée pour la nuit, toutes les poules sont-elles rentrées ?

        Seulement pour la fermeture du soir (SCHEDULE) : en journée, la porte se ferme aussi
        après le passage d'une poule ou devant un prédateur, et les poules dehors sont normales.
        Pas d'alerte si le total n'est pas réglé (0) ou si le compte est bon.
        """
        if coop.total_hens <= 0 or coop.inside_count >= coop.total_hens:
            return None
        return await self.alerts.add(
            Alert(
                coop_id=coop.id,
                alert_type=AlertType.MISSING_HEN,
                severity=Severity.WARNING,
                created_at=utcnow(),
            )
        )

    async def handle_alert(self, coop_id: str, message: AlertMessage) -> None:
        coop = await self._get_coop(coop_id)
        if coop is None:
            return
        coop.last_seen_at = utcnow()
        coop.is_online = True
        alert = await self.alerts.add(
            Alert(
                coop_id=coop_id,
                alert_type=message.alert_type,
                severity=message.severity,
                ai_confidence=message.ai_confidence,
                created_at=utcnow(),
            )
        )
        if message.image_base64:
            image = self._decode_image(message.image_base64, message.image_format)
            if image is not None:
                path = self.media_dir / coop_id / f"{alert.id}.{message.image_format}"
                await asyncio.to_thread(_write_file, path, image)
                alert.image_url = f"/api/v1/coops/{coop_id}/alerts/{alert.id}/image"
        await self.session.commit()
        self._publish_alert(alert)

    async def handle_status(self, coop_id: str, online: bool) -> None:
        coop = await self._get_coop(coop_id)
        if coop is None:
            return
        coop.is_online = online
        if online:
            coop.last_seen_at = utcnow()
        await self.session.commit()
        self._publish_status(coop)

    def _crosses_low_battery(self, previous: int | None, current: int) -> bool:
        """Alerte une seule fois, au passage sous le seuil (pas à chaque télémétrie)."""
        was_ok = previous is None or previous >= self.low_battery_threshold
        return was_ok and current < self.low_battery_threshold

    def _publish_status(self, coop: Coop) -> None:
        status = build_status(coop, self.offline_after_s)
        self.broadcaster.publish(coop.id, "status", status.model_dump(mode="json"))

    def _publish_alert(self, alert: Alert) -> None:
        self.broadcaster.publish(
            alert.coop_id, "alert", AlertRead.model_validate(alert).model_dump(mode="json")
        )

    def _decode_image(self, data: str, image_format: str) -> bytes | None:
        try:
            image = base64.b64decode(data, validate=True)
        except (binascii.Error, ValueError):
            logger.warning("Photo d'alerte ignorée : base64 invalide")
            return None
        if len(image) > self.max_image_bytes:
            logger.warning(
                "Photo d'alerte ignorée : %d octets (max %d)", len(image), self.max_image_bytes
            )
            return None
        if not image.startswith(IMAGE_SIGNATURES[image_format]):
            logger.warning("Photo d'alerte ignorée : ce n'est pas un fichier %s", image_format)
            return None
        return image


def _write_file(path: Path, content: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(content)
