"""Durées de conservation (RGPD, art. 5 ; #64) : une purge passe une fois par jour.

- Photo d'alerte : supprimée après `photo_retention_days` (30 jours). L'alerte reste, sans photo.
- Passages, mouvements de porte et alertes : supprimés après `data_retention_days` (1 an),
  avec leur photo s'il en reste une.
"""

import asyncio
import logging
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.models import Alert, Event
from app.timeutils import utcnow

logger = logging.getLogger(__name__)

PHOTO_EXTENSIONS = ("jpeg", "webp")


@dataclass(frozen=True)
class PurgeResult:
    photos: int = 0
    events: int = 0
    alerts: int = 0


class RetentionJob:
    def __init__(
        self,
        sessionmaker: async_sessionmaker[AsyncSession],
        media_dir: str,
        photo_retention_days: int,
        data_retention_days: int,
        interval_s: float = 86_400.0,
    ) -> None:
        self.sessionmaker = sessionmaker
        self.media_dir = Path(media_dir)
        self.photo_retention_days = photo_retention_days
        self.data_retention_days = data_retention_days
        self.interval_s = interval_s

    async def run(self) -> None:
        while True:
            try:
                await self.purge_once()
            except Exception:
                logger.exception("Erreur pendant la purge des anciennes données")
            await asyncio.sleep(self.interval_s)

    async def purge_once(self, now: datetime | None = None) -> PurgeResult:
        now = now or utcnow()
        photo_limit = now - timedelta(days=self.photo_retention_days)
        data_limit = now - timedelta(days=self.data_retention_days)
        files: list[Path] = []
        async with self.sessionmaker() as session:
            old_photos = await session.scalars(
                select(Alert).where(Alert.image_url.is_not(None), Alert.created_at < photo_limit)
            )
            photos = 0
            for alert in old_photos:
                files.extend(self._photo_files(alert))
                alert.image_url = None
                photos += 1
            old_alerts = await session.scalars(select(Alert).where(Alert.created_at < data_limit))
            for alert in old_alerts:
                files.extend(self._photo_files(alert))
            # synchronize_session=False : SQLite rend des dates sans fuseau, que SQLAlchemy ne
            # sait pas comparer en Python à `data_limit`. La session est fermée juste après.
            alerts = await session.execute(
                delete(Alert)
                .where(Alert.created_at < data_limit)
                .execution_options(synchronize_session=False)
            )
            events = await session.execute(
                delete(Event)
                .where(Event.occurred_at < data_limit)
                .execution_options(synchronize_session=False)
            )
            await session.commit()
        # Les fichiers partent après le commit : si la base refuse, aucune photo n'est perdue.
        await asyncio.to_thread(_unlink_all, files)
        result = PurgeResult(photos=photos, events=events.rowcount, alerts=alerts.rowcount)
        if result != PurgeResult():
            logger.info(
                "Purge : %d photo(s), %d passage(s), %d alerte(s) supprimés",
                result.photos,
                result.events,
                result.alerts,
            )
        return result

    def _photo_files(self, alert: Alert) -> list[Path]:
        folder = self.media_dir / alert.coop_id
        return [folder / f"{alert.id}.{extension}" for extension in PHOTO_EXTENSIONS]


def _unlink_all(files: list[Path]) -> None:
    for path in files:
        path.unlink(missing_ok=True)
