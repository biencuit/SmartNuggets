"""Logique métier liée aux poulaillers : état, historique, alertes, commandes."""

import uuid
from collections.abc import Sequence
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.errors import ForbiddenError, NotFoundError
from app.models import Alert, Coop, Event, EventType
from app.repositories import (
    AlertRepository,
    CoopRepository,
    DeviceRepository,
    EventRepository,
    HistoryRepository,
)
from app.schemas import (
    CommandRequest,
    CoopCreate,
    CoopStatus,
    HabitsRead,
    HistoryCategory,
    HistoryItem,
    HistoryPage,
)
from app.security import normalize_claim_code, verify_password
from app.services.commands import CommandPublisher, DoorCommand
from app.services.habits import PASSAGE_TYPES, compute_habits, period_start, utc_bounds
from app.timeutils import ensure_utc, utcnow

DEFAULT_OFFLINE_AFTER_S = 900
CLAIM_REFUSED = "Identifiant ou code d'appairage incorrect"

# Types d'événements derrière chaque filtre de la page Historique.
CATEGORY_EVENT_TYPES: dict[HistoryCategory, tuple[EventType, ...]] = {
    HistoryCategory.ENTRIES: (EventType.HEN_ENTRY,),
    HistoryCategory.EXITS: (EventType.HEN_EXIT,),
    HistoryCategory.DOOR: (EventType.DOOR_OPEN, EventType.DOOR_CLOSE, EventType.OBSTACLE),
}


class CoopService:
    """Toutes les opérations sont limitées aux poulaillers de l'utilisateur connecté."""

    def __init__(
        self,
        session: AsyncSession,
        publisher: CommandPublisher,
        owner_id: uuid.UUID,
        offline_after_s: int = DEFAULT_OFFLINE_AFTER_S,
    ) -> None:
        self.session = session
        self.publisher = publisher
        self.owner_id = owner_id
        self.offline_after_s = offline_after_s
        self.coops = CoopRepository(session)
        self.devices = DeviceRepository(session)
        self.events = EventRepository(session)
        self.alerts = AlertRepository(session)
        self.history = HistoryRepository(session)

    async def list_coops(self) -> Sequence[Coop]:
        return await self.coops.list(owner_id=self.owner_id)

    async def create_coop(self, data: CoopCreate) -> Coop:
        """Ajoute le poulailler au compte, seulement avec le bon code d'appairage du Pi.

        Le code ne marche qu'une fois. La réponse est la même si l'identifiant n'existe pas,
        si le code est faux ou si le poulailler a déjà un propriétaire : on ne peut pas
        deviner quels identifiants existent.
        """
        device = await self.devices.get(data.id, for_update=True)
        code_hash = None
        if device is not None and device.claimed_at is None:
            code_hash = device.claim_code_hash
        # verify_password calcule toujours un hash (même sans code enregistré) : la réponse
        # prend le même temps dans tous les cas.
        valid = verify_password(code_hash, normalize_claim_code(data.claim_code))
        if device is None or not valid:
            raise ForbiddenError(CLAIM_REFUSED)
        device.claimed_at = utcnow()
        device.claim_code_hash = None
        coop = Coop(owner_id=self.owner_id, **data.model_dump(exclude={"claim_code"}))
        try:
            await self.coops.add(coop)
            await self.session.commit()
        except IntegrityError as exc:
            await self.session.rollback()
            raise ForbiddenError(CLAIM_REFUSED) from exc
        return coop

    async def get_coop(self, coop_id: str) -> Coop:
        # Le poulailler d'un autre éleveur répond "introuvable" : on ne révèle pas qu'il existe.
        coop = await self.coops.get(coop_id, owner_id=self.owner_id)
        if coop is None:
            raise NotFoundError(f"Poulailler {coop_id!r} introuvable")
        return coop

    async def get_status(self, coop_id: str) -> CoopStatus:
        coop = await self.get_coop(coop_id)
        return build_status(coop, self.offline_after_s)

    async def list_events(
        self, coop_id: str, *, event_type: str | None, limit: int, offset: int
    ) -> Sequence[Event]:
        await self.get_coop(coop_id)
        return await self.events.list_for_coop(
            coop_id, event_type=event_type, limit=limit, offset=offset
        )

    async def list_alerts(
        self, coop_id: str, *, acknowledged: bool | None, limit: int, offset: int
    ) -> Sequence[Alert]:
        await self.get_coop(coop_id)
        return await self.alerts.list_for_coop(
            coop_id, acknowledged=acknowledged, limit=limit, offset=offset
        )

    async def history_page(
        self,
        coop_id: str,
        *,
        categories: Sequence[HistoryCategory] | None,
        since: datetime | None,
        until: datetime | None,
        limit: int,
        offset: int,
    ) -> HistoryPage:
        """Historique complet (passages, porte, alertes), filtré et paginé."""
        await self.get_coop(coop_id)
        if categories:
            selected = set(categories)
            event_types: set[str] | None = {
                event_type
                for category in selected
                for event_type in CATEGORY_EVENT_TYPES.get(category, ())
            }
            include_alerts = HistoryCategory.ALERTS in selected
        else:
            # Aucun filtre : tous les événements, y compris un futur nouveau type.
            event_types, include_alerts = None, True
        rows, total = await self.history.page(
            coop_id,
            event_types=event_types,
            include_alerts=include_alerts,
            since=since,
            until=until,
            limit=limit,
            offset=offset,
        )
        return HistoryPage(
            total=total, items=[HistoryItem.model_validate(dict(row._mapping)) for row in rows]
        )

    async def get_habits(
        self, coop_id: str, *, days: int, tz: ZoneInfo, now: datetime | None = None
    ) -> HabitsRead:
        """Habitudes des `days` derniers jours, aujourd'hui compris, en heure locale `tz`."""
        await self.get_coop(coop_id)
        first_day = period_start(now or utcnow(), tz, days)
        since, until = utc_bounds(first_day, days, tz)
        passages = await self.events.list_between(
            coop_id, event_types=PASSAGE_TYPES, since=since, until=until
        )
        return compute_habits(passages, tz, first_day, days)

    async def get_alert(self, coop_id: str, alert_id: int) -> Alert:
        await self.get_coop(coop_id)
        alert = await self.alerts.get(coop_id, alert_id)
        if alert is None:
            raise NotFoundError(f"Alerte {alert_id} introuvable")
        return alert

    async def acknowledge_alert(self, coop_id: str, alert_id: int) -> Alert:
        alert = await self.get_alert(coop_id, alert_id)
        alert.acknowledged = True
        await self.session.commit()
        return alert

    async def send_command(self, coop_id: str, request: CommandRequest) -> DoorCommand:
        await self.get_coop(coop_id)
        command = DoorCommand(
            coop_id=coop_id, action=request.action, inside_count=request.inside_count
        )
        await self.publisher.publish(command)
        return command


def is_online(coop: Coop, offline_after_s: int, now: datetime | None = None) -> bool:
    """Connecté au broker (Last Will) ET dernier message il y a moins de `offline_after_s`.

    Le second critère couvre un Pi encore connecté mais bloqué (programme planté).
    """
    if not coop.is_online or coop.last_seen_at is None:
        return False
    now = now or utcnow()
    return now - ensure_utc(coop.last_seen_at) < timedelta(seconds=offline_after_s)


def build_status(
    coop: Coop, offline_after_s: int = DEFAULT_OFFLINE_AFTER_S, now: datetime | None = None
) -> CoopStatus:
    return CoopStatus(
        coop_id=coop.id,
        name=coop.name,
        door_state=coop.door_state,
        inside_count=coop.inside_count,
        total_hens=coop.total_hens,
        outside_count=max(coop.total_hens - coop.inside_count, 0),
        battery=coop.battery_level,
        auto_close_time=coop.auto_close_time,
        last_seen_at=coop.last_seen_at,
        online=is_online(coop, offline_after_s, now),
        camera_ok=coop.camera_ok,
    )
