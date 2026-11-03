import json
from datetime import timedelta

from fastapi import FastAPI
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Alert, Coop
from app.mqtt.worker import MqttWorker
from app.services.coop_service import build_status
from app.services.health import DeviceWatchdog
from app.timeutils import utcnow

OFFLINE_AFTER_S = 900


def watchdog(app: FastAPI) -> DeviceWatchdog:
    return DeviceWatchdog(app.state.sessionmaker, app.state.broadcaster, OFFLINE_AFTER_S)


async def set_last_seen(session: AsyncSession, coop: Coop, minutes_ago: float, online=True):
    coop.last_seen_at = utcnow() - timedelta(minutes=minutes_ago)
    coop.is_online = online
    await session.commit()


async def offline_alerts(session: AsyncSession) -> list[Alert]:
    session.expire_all()
    result = await session.execute(select(Alert).where(Alert.alert_type == "DEVICE_OFFLINE"))
    return list(result.scalars().all())


def test_online_exige_connexion_et_nouvelles_recentes(coop: Coop) -> None:
    now = utcnow()
    coop.is_online = True
    coop.last_seen_at = now - timedelta(minutes=2)
    assert build_status(coop, OFFLINE_AFTER_S, now).online is True

    coop.last_seen_at = now - timedelta(minutes=20)  # connecté mais muet : programme bloqué ?
    assert build_status(coop, OFFLINE_AFTER_S, now).online is False

    coop.last_seen_at = now - timedelta(minutes=2)
    coop.is_online = False  # Last Will reçu
    assert build_status(coop, OFFLINE_AFTER_S, now).online is False

    coop.last_seen_at = None
    coop.is_online = True
    assert build_status(coop, OFFLINE_AFTER_S, now).online is False


async def test_alerte_si_le_poulailler_ne_repond_plus(
    app: FastAPI, session: AsyncSession, coop: Coop
) -> None:
    await set_last_seen(session, coop, minutes_ago=20, online=False)

    async with app.state.broadcaster.subscribe("coop_01") as queue:
        assert await watchdog(app).check_once() == ["coop_01"]
        messages = [queue.get_nowait() for _ in range(queue.qsize())]

    alerts = await offline_alerts(session)
    assert len(alerts) == 1
    assert alerts[0].severity == "WARNING"
    assert [m["event"] for m in messages] == ["alert", "status"]
    assert messages[1]["data"]["online"] is False


async def test_une_seule_alerte_par_coupure(
    app: FastAPI, session: AsyncSession, coop: Coop
) -> None:
    await set_last_seen(session, coop, minutes_ago=20)
    dog = watchdog(app)
    await dog.check_once()
    assert await dog.check_once() == []
    assert len(await offline_alerts(session)) == 1

    # Le Pi revient, puis retombe en panne : nouvelle coupure, nouvelle alerte.
    later = utcnow() + timedelta(hours=1)
    coop.last_seen_at = utcnow() + timedelta(minutes=30)
    await session.commit()
    assert await dog.check_once(now=later) == ["coop_01"]
    assert len(await offline_alerts(session)) == 2


async def test_pas_d_alerte_si_recent_ou_jamais_vu(
    app: FastAPI, session: AsyncSession, coop: Coop
) -> None:
    dog = watchdog(app)
    assert await dog.check_once() == []  # jamais vu (Pi pas encore installé)

    await set_last_seen(session, coop, minutes_ago=5, online=False)
    assert await dog.check_once() == []  # coupure courte : pas encore d'alerte
    assert await offline_alerts(session) == []


async def test_etat_du_systeme_dans_l_api(
    client: AsyncClient, session: AsyncSession, coop: Coop
) -> None:
    await set_last_seen(session, coop, minutes_ago=1)
    coop.camera_ok = False
    await session.commit()

    body = (await client.get("/api/v1/coops/coop_01/status")).json()

    assert body["online"] is True
    assert body["camera_ok"] is False
    assert body["battery"] == 88


async def test_camera_et_batterie_faible_depuis_la_telemetrie(
    app: FastAPI, session: AsyncSession, coop: Coop
) -> None:
    worker = MqttWorker(app.state.settings, app.state.sessionmaker, app.state.broadcaster)

    async def telemetry(**values) -> None:
        payload = {"sent_at": "2026-11-03T08:00:00Z", **values}
        await worker.handle_message("smartnuggets/coop_01/telemetry", json.dumps(payload))

    await telemetry(battery_level=25, camera_ok=True)
    await telemetry(battery_level=19)  # passage sous 20 % : alerte
    await telemetry(battery_level=15)  # toujours faible : pas de nouvelle alerte
    await telemetry(battery_level=80)  # rechargée
    await telemetry(battery_level=10)  # de nouveau faible : nouvelle alerte

    session.expire_all()
    updated = (await session.execute(select(Coop))).scalar_one()
    assert updated.camera_ok is True
    assert updated.battery_level == 10
    low = (await session.execute(select(Alert).where(Alert.alert_type == "LOW_BATTERY"))).all()
    assert len(low) == 2
