from collections.abc import Sequence
from datetime import time

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import DoorSchedule


class ScheduleRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def list_for_coop(self, coop_id: str) -> Sequence[DoorSchedule]:
        result = await self.session.execute(
            select(DoorSchedule)
            .where(DoorSchedule.coop_id == coop_id)
            .order_by(DoorSchedule.weekday)
        )
        return result.scalars().all()

    async def replace(self, coop_id: str, days: list[tuple[int, time, time]]) -> list[DoorSchedule]:
        """Remplace tout le planning du poulailler par les 7 jours donnés."""
        await self.session.execute(delete(DoorSchedule).where(DoorSchedule.coop_id == coop_id))
        rows = [
            DoorSchedule(coop_id=coop_id, weekday=weekday, open_from=open_from, close_at=close_at)
            for weekday, open_from, close_at in days
        ]
        self.session.add_all(rows)
        await self.session.flush()
        return rows
