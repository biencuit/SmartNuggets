from collections.abc import Sequence

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Event


class EventRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def list_for_coop(
        self,
        coop_id: str,
        *,
        event_type: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> Sequence[Event]:
        """Historique du plus récent au plus ancien."""
        query = select(Event).where(Event.coop_id == coop_id)
        if event_type is not None:
            query = query.where(Event.event_type == event_type)
        query = (
            query.order_by(Event.occurred_at.desc(), Event.id.desc()).limit(limit).offset(offset)
        )
        result = await self.session.execute(query)
        return result.scalars().all()

    async def add(self, event: Event) -> Event:
        self.session.add(event)
        await self.session.flush()
        return event
