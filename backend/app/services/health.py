"""Surveillance des Raspberry Pi : alerte quand un poulailler ne donne plus de nouvelles."""

import asyncio
import logging
from datetime import datetime, timedelta

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.models import Alert, AlertType, Severity
from app.repositories import AlertRepository, CoopRepository
from app.schemas import AlertRead
from app.services.broadcaster import Broadcaster
from app.services.coop_service import build_status
from app.timeutils import ensure_utc, utcnow

logger = logging.getLogger(__name__)


class DeviceWatchdog:
    """Crée une alerte DEVICE_OFFLINE par coupure (pas une par vérification).

    Une coupure courte (redémarrage, câble débranché une minute) ne déclenche rien : l'état
    "hors ligne" s'affiche tout de suite, mais l'alerte n'arrive qu'après `offline_after_s`.
    """

    def __init__(
        self,
        sessionmaker: async_sessionmaker[AsyncSession],
        broadcaster: Broadcaster,
        offline_after_s: int,
        interval_s: float = 60.0,
    ) -> None:
        self.sessionmaker = sessionmaker
        self.broadcaster = broadcaster
        self.offline_after_s = offline_after_s
        self.interval_s = interval_s

    async def run(self) -> None:
        while True:
            try:
                await self.check_once()
            except Exception:
                logger.exception("Erreur pendant la vérification des poulaillers")
            await asyncio.sleep(self.interval_s)

    async def check_once(self, now: datetime | None = None) -> list[str]:
        """Renvoie les identifiants des poulaillers pour lesquels une alerte a été créée."""
        now = now or utcnow()
        limit = now - timedelta(seconds=self.offline_after_s)
        alerted: list[str] = []
        async with self.sessionmaker() as session:
            alerts = AlertRepository(session)
            for coop in await CoopRepository(session).list_silent_since(limit):
                last_seen = ensure_utc(coop.last_seen_at) if coop.last_seen_at else limit
                if await alerts.exists_since(coop.id, AlertType.DEVICE_OFFLINE, last_seen):
                    continue  # déjà signalé pour cette coupure
                alert = await alerts.add(
                    Alert(
                        coop_id=coop.id,
                        alert_type=AlertType.DEVICE_OFFLINE,
                        severity=Severity.WARNING,
                        created_at=now,
                    )
                )
                alerted.append(coop.id)
                await session.commit()
                logger.warning("Poulailler %s sans nouvelles depuis %s", coop.id, last_seen)
                self.broadcaster.publish(
                    coop.id, "alert", AlertRead.model_validate(alert).model_dump(mode="json")
                )
                status = build_status(coop, self.offline_after_s, now)
                self.broadcaster.publish(coop.id, "status", status.model_dump(mode="json"))
        return alerted
