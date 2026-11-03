import base64
import json
from pathlib import Path

from fastapi import FastAPI
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Alert, Coop, Event
from app.mqtt.worker import MqttWorker
from app.services.broadcaster import Broadcaster

JPEG = b"\xff\xd8\xff\xe0" + b"\x00" * 64
SENT_AT = "2026-11-03T08:00:00Z"


def make_worker(app: FastAPI) -> MqttWorker:
    return MqttWorker(app.state.settings, app.state.sessionmaker, app.state.broadcaster)


async def refreshed_coop(session: AsyncSession, coop_id: str = "coop_01") -> Coop:
    session.expire_all()
    return (await session.execute(select(Coop).where(Coop.id == coop_id))).scalar_one()


async def test_telemetrie_met_a_jour_le_poulailler(
    app: FastAPI, session: AsyncSession, coop: Coop
) -> None:
    broadcaster: Broadcaster = app.state.broadcaster
    payload = {
        "sent_at": SENT_AT,
        "door_state": "CLOSED",
        "inside_count": 8,
        "battery_level": 64,
        "event": {
            "event_type": "HEN_ENTRY",
            "trigger_source": "AI_AUTO",
            "ai_confidence": 0.93,
            "occurred_at": SENT_AT,
        },
    }
    async with broadcaster.subscribe("coop_01") as queue:
        await make_worker(app).handle_message(
            "smartnuggets/coop_01/telemetry", json.dumps(payload).encode()
        )
        messages = [queue.get_nowait() for _ in range(queue.qsize())]

    updated = await refreshed_coop(session)
    assert updated.door_state == "CLOSED"
    assert updated.inside_count == 8
    assert updated.battery_level == 64
    assert updated.is_online is True
    assert updated.last_seen_at is not None

    events = (await session.execute(select(Event))).scalars().all()
    assert len(events) == 1
    assert events[0].inside_count_after == 8  # repris du compteur de la télémétrie

    assert [m["event"] for m in messages] == ["status", "event"]
    assert messages[0]["data"]["inside_count"] == 8
    assert messages[1]["data"]["event_type"] == "HEN_ENTRY"


async def test_telemetrie_partielle_ne_touche_pas_au_reste(
    app: FastAPI, session: AsyncSession, coop: Coop
) -> None:
    await make_worker(app).handle_message(
        "smartnuggets/coop_01/telemetry", json.dumps({"sent_at": SENT_AT}).encode()
    )
    updated = await refreshed_coop(session)
    assert updated.inside_count == 7
    assert updated.door_state == "OPEN"
    assert updated.last_seen_at is not None


async def test_message_invalide_ou_inconnu_ignore(
    app: FastAPI, session: AsyncSession, coop: Coop
) -> None:
    worker = make_worker(app)
    await worker.handle_message("smartnuggets/coop_01/telemetry", b"pas du json")
    await worker.handle_message(
        "smartnuggets/coop_01/telemetry", json.dumps({"sent_at": SENT_AT, "inside_count": -3})
    )
    await worker.handle_message("smartnuggets/coop_99/telemetry", json.dumps({"sent_at": SENT_AT}))
    await worker.handle_message("autre/topic", b"{}")
    await worker.handle_message("smartnuggets/coop_01/status", b"peut-etre")

    updated = await refreshed_coop(session)
    assert updated.inside_count == 7
    assert updated.last_seen_at is None


async def test_alerte_avec_photo(
    app: FastAPI, client: AsyncClient, session: AsyncSession, coop: Coop
) -> None:
    payload = {
        "sent_at": SENT_AT,
        "alert_type": "PREDATOR_DETECTED",
        "severity": "CRITICAL",
        "ai_confidence": 0.88,
        "image_base64": base64.b64encode(JPEG).decode(),
        "image_format": "jpeg",
    }
    async with app.state.broadcaster.subscribe("coop_01") as queue:
        await make_worker(app).handle_message(
            "smartnuggets/coop_01/alerts", json.dumps(payload).encode()
        )
        message = queue.get_nowait()

    alert = (await session.execute(select(Alert))).scalar_one()
    assert alert.image_url == f"/api/v1/coops/coop_01/alerts/{alert.id}/image"
    assert (
        Path(app.state.settings.media_dir) / "coop_01" / f"{alert.id}.jpeg"
    ).read_bytes() == JPEG
    assert message["event"] == "alert"
    assert message["data"]["alert_type"] == "PREDATOR_DETECTED"

    response = await client.get(alert.image_url)
    assert response.status_code == 200
    assert response.headers["content-type"] == "image/jpeg"
    assert response.content == JPEG


async def test_alerte_avec_photo_invalide_est_gardee_sans_photo(
    app: FastAPI, client: AsyncClient, session: AsyncSession, coop: Coop
) -> None:
    worker = make_worker(app)
    base = {"sent_at": SENT_AT, "alert_type": "DOOR_BLOCKED", "severity": "WARNING"}
    await worker.handle_message(
        "smartnuggets/coop_01/alerts", json.dumps({**base, "image_base64": "%%%"}).encode()
    )
    not_a_jpeg = base64.b64encode(b"GIF89a....").decode()
    await worker.handle_message(
        "smartnuggets/coop_01/alerts", json.dumps({**base, "image_base64": not_a_jpeg}).encode()
    )

    alerts = (await session.execute(select(Alert))).scalars().all()
    assert len(alerts) == 2
    assert all(alert.image_url is None for alert in alerts)

    response = await client.get(f"/api/v1/coops/coop_01/alerts/{alerts[0].id}/image")
    assert response.status_code == 404


async def test_statut_online_offline(app: FastAPI, session: AsyncSession, coop: Coop) -> None:
    worker = make_worker(app)
    await worker.handle_message("smartnuggets/coop_01/status", b"online")
    assert (await refreshed_coop(session)).is_online is True

    await worker.handle_message("smartnuggets/coop_01/status", b"offline")
    updated = await refreshed_coop(session)
    assert updated.is_online is False
    assert updated.last_seen_at is not None  # garde l'heure de la dernière communication
