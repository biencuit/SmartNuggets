"""Logique métier liée aux poulaillers : état, historique, alertes, commandes."""

from collections.abc import Sequence

from sqlalchemy.ext.asyncio import AsyncSession

from app.errors import NotFoundError
from app.models import Alert, Coop, Event
from app.repositories import AlertRepository, CoopRepository, EventRepository
from app.schemas import CommandRequest, CoopStatus
from app.services.commands import CommandPublisher, DoorCommand


class CoopService:
    def __init__(self, session: AsyncSession, publisher: CommandPublisher) -> None:
        self.session = session
        self.publisher = publisher
        self.coops = CoopRepository(session)
        self.events = EventRepository(session)
        self.alerts = AlertRepository(session)

    async def list_coops(self) -> Sequence[Coop]:
        return await self.coops.list()

    async def get_coop(self, coop_id: str) -> Coop:
        coop = await self.coops.get(coop_id)
        if coop is None:
            raise NotFoundError(f"Poulailler {coop_id!r} introuvable")
        return coop

    async def get_status(self, coop_id: str) -> CoopStatus:
        coop = await self.get_coop(coop_id)
        return build_status(coop)

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

    async def acknowledge_alert(self, coop_id: str, alert_id: int) -> Alert:
        await self.get_coop(coop_id)
        alert = await self.alerts.get(coop_id, alert_id)
        if alert is None:
            raise NotFoundError(f"Alerte {alert_id} introuvable")
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


def build_status(coop: Coop) -> CoopStatus:
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
    )
