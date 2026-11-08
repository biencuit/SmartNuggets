from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Device


class DeviceRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get(self, device_id: str, *, for_update: bool = False) -> Device | None:
        """`for_update` verrouille la ligne : deux comptes ne peuvent pas utiliser le même
        code en même temps (ignoré par SQLite, qui n'a qu'un seul écrivain à la fois)."""
        query = select(Device).where(Device.id == device_id)
        if for_update:
            query = query.with_for_update()
        result = await self.session.execute(query)
        return result.scalar_one_or_none()

    async def add(self, device: Device) -> Device:
        self.session.add(device)
        await self.session.flush()
        return device
