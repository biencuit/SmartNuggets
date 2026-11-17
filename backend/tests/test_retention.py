"""Durées de conservation : photos après 30 jours, données après un an (RGPD, #64)."""

from datetime import timedelta
from pathlib import Path

from fastapi import FastAPI
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import Settings
from app.models import Alert, AlertType, Coop, Event, EventType, Severity
from app.services.retention import PurgeResult, RetentionJob
from app.timeutils import utcnow


def job(app: FastAPI, settings: Settings) -> RetentionJob:
    return RetentionJob(app.state.sessionmaker, settings.media_dir, 30, 365)


async def alert_with_photo(
    session: AsyncSession, settings: Settings, coop: Coop, days_ago: float
) -> tuple[Alert, Path]:
    alert = Alert(
        coop_id=coop.id,
        alert_type=AlertType.PREDATOR_DETECTED,
        severity=Severity.CRITICAL,
        created_at=utcnow() - timedelta(days=days_ago),
    )
    session.add(alert)
    await session.flush()
    alert.image_url = f"/api/v1/coops/{coop.id}/alerts/{alert.id}/image"
    await session.commit()
    path = Path(settings.media_dir) / coop.id / f"{alert.id}.jpeg"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(b"\xff\xd8\xff photo")
    return alert, path


async def reload(session: AsyncSession, alert_id: int) -> Alert | None:
    session.expire_all()
    return await session.get(Alert, alert_id)


async def test_photo_de_plus_de_30_jours_supprimee_l_alerte_reste(
    app: FastAPI, session: AsyncSession, settings: Settings, coop: Coop
) -> None:
    old, old_photo = await alert_with_photo(session, settings, coop, days_ago=31)
    recent, recent_photo = await alert_with_photo(session, settings, coop, days_ago=29)

    old_id, recent_id = old.id, recent.id

    result = await job(app, settings).purge_once()

    assert result == PurgeResult(photos=1)
    assert not old_photo.exists() and recent_photo.is_file()
    kept = await reload(session, old_id)
    assert kept is not None and kept.image_url is None
    assert (await reload(session, recent_id)).image_url is not None


async def test_donnees_de_plus_d_un_an_supprimees(
    app: FastAPI, session: AsyncSession, settings: Settings, coop: Coop
) -> None:
    now = utcnow()
    session.add_all(
        [
            Event(
                coop_id=coop.id,
                event_type=EventType.HEN_EXIT,
                occurred_at=now - timedelta(days=400),
            ),
            Event(
                coop_id=coop.id,
                event_type=EventType.HEN_ENTRY,
                occurred_at=now - timedelta(days=10),
            ),
        ]
    )
    await session.commit()
    very_old, photo = await alert_with_photo(session, settings, coop, days_ago=366)
    very_old_id = very_old.id

    result = await job(app, settings).purge_once()

    assert result.events == 1 and result.alerts == 1
    assert await reload(session, very_old_id) is None
    assert not photo.exists()
    remaining = (await session.execute(select(Event.event_type))).scalars().all()
    assert remaining == [EventType.HEN_ENTRY]


async def test_rien_a_purger(app: FastAPI, settings: Settings, coop: Coop) -> None:
    assert await job(app, settings).purge_once() == PurgeResult()


async def test_durees_de_conservation_par_defaut(app: FastAPI) -> None:
    settings: Settings = app.state.settings
    assert settings.photo_retention_days == 30 and settings.data_retention_days == 365
    assert settings.retention_interval_s == 86_400
