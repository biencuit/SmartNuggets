import uuid
from collections.abc import Sequence

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Coop


class CoopRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get(self, coop_id: str, owner_id: uuid.UUID | None = None) -> Coop | None:
        """Renvoie le poulailler ; si `owner_id` est donné, seulement s'il lui appartient."""
        query = select(Coop).where(Coop.id == coop_id)
        if owner_id is not None:
            query = query.where(Coop.owner_id == owner_id)
        result = await self.session.execute(query)
        return result.scalar_one_or_none()

    async def list(self, owner_id: uuid.UUID | None = None) -> Sequence[Coop]:
        query = select(Coop).order_by(Coop.id)
        if owner_id is not None:
            query = query.where(Coop.owner_id == owner_id)
        result = await self.session.execute(query)
        return result.scalars().all()

    async def add(self, coop: Coop) -> Coop:
        self.session.add(coop)
        await self.session.flush()
        return coop
