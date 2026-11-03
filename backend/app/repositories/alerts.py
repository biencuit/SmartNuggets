from collections.abc import Sequence
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Alert


class AlertRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get(self, coop_id: str, alert_id: int) -> Alert | None:
        result = await self.session.execute(
            select(Alert).where(Alert.id == alert_id, Alert.coop_id == coop_id)
        )
        return result.scalar_one_or_none()

    async def list_for_coop(
        self,
        coop_id: str,
        *,
        acknowledged: bool | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> Sequence[Alert]:
        """Alertes de la plus récente à la plus ancienne."""
        query = select(Alert).where(Alert.coop_id == coop_id)
        if acknowledged is not None:
            query = query.where(Alert.acknowledged == acknowledged)
        query = query.order_by(Alert.created_at.desc(), Alert.id.desc()).limit(limit).offset(offset)
        result = await self.session.execute(query)
        return result.scalars().all()

    async def add(self, alert: Alert) -> Alert:
        self.session.add(alert)
        await self.session.flush()
        return alert

    async def exists_since(self, coop_id: str, alert_type: str, since: datetime) -> bool:
        result = await self.session.execute(
            select(Alert.id)
            .where(
                Alert.coop_id == coop_id,
                Alert.alert_type == alert_type,
                Alert.created_at >= since,
            )
            .limit(1)
        )
        return result.first() is not None
