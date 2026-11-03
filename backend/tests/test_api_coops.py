from datetime import timedelta

from fastapi import FastAPI
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Alert, AlertType, Coop, Event, EventType, Severity
from app.timeutils import utcnow


async def test_health(client: AsyncClient) -> None:
    response = await client.get("/api/v1/health")
    assert response.json() == {"status": "ok"}


async def test_liste_des_poulaillers(client: AsyncClient, coop: Coop) -> None:
    response = await client.get("/api/v1/coops")
    assert response.status_code == 200
    assert response.json() == [{"id": "coop_01", "name": "Poulailler de Marc", "total_hens": 10}]


async def test_etat_du_poulailler(client: AsyncClient, coop: Coop) -> None:
    response = await client.get("/api/v1/coops/coop_01/status")

    assert response.status_code == 200
    body = response.json()
    assert body["door_state"] == "OPEN"
    assert body["inside_count"] == 7
    assert body["outside_count"] == 3
    assert body["battery"] == 88
    assert body["auto_close_time"] == "21:30:00"
    assert body["last_seen_at"] is None


async def test_poulailler_inconnu_renvoie_404(client: AsyncClient) -> None:
    response = await client.get("/api/v1/coops/inconnu/status")
    assert response.status_code == 404


async def test_historique_filtre_et_pagine(
    client: AsyncClient, session: AsyncSession, coop: Coop
) -> None:
    now = utcnow()
    for minutes in range(5):
        session.add(
            Event(
                coop_id=coop.id,
                event_type=EventType.HEN_EXIT if minutes % 2 else EventType.HEN_ENTRY,
                occurred_at=now - timedelta(minutes=minutes),
            )
        )
    await session.commit()

    response = await client.get("/api/v1/coops/coop_01/events", params={"limit": 2})
    assert response.status_code == 200
    assert len(response.json()) == 2

    response = await client.get("/api/v1/coops/coop_01/events", params={"type": "HEN_EXIT"})
    body = response.json()
    assert {e["event_type"] for e in body} == {"HEN_EXIT"}
    assert len(body) == 2
    assert body[0]["occurred_at"].endswith("Z") or body[0]["occurred_at"].endswith("+00:00")

    response = await client.get("/api/v1/coops/coop_01/events", params={"type": "PAS_UN_TYPE"})
    assert response.status_code == 422


async def test_alertes_et_acquittement(
    client: AsyncClient, session: AsyncSession, coop: Coop
) -> None:
    alert = Alert(
        coop_id=coop.id,
        alert_type=AlertType.PREDATOR_DETECTED,
        severity=Severity.CRITICAL,
        ai_confidence=0.9,
    )
    session.add(alert)
    await session.commit()

    response = await client.get("/api/v1/coops/coop_01/alerts")
    assert [a["alert_type"] for a in response.json()] == ["PREDATOR_DETECTED"]

    response = await client.post(f"/api/v1/coops/coop_01/alerts/{alert.id}/ack")
    assert response.status_code == 200
    assert response.json()["acknowledged"] is True

    response = await client.get("/api/v1/coops/coop_01/alerts", params={"acknowledged": False})
    assert response.json() == []

    response = await client.post("/api/v1/coops/coop_01/alerts/9999/ack")
    assert response.status_code == 404


async def test_commande_manuelle_transmise(app: FastAPI, client: AsyncClient, coop: Coop) -> None:
    response = await client.post("/api/v1/coops/coop_01/command", json={"action": "OPEN"})

    assert response.status_code == 202
    body = response.json()
    assert body["action"] == "OPEN"
    sent = app.state.command_publisher.sent
    assert len(sent) == 1
    assert str(sent[0].command_id) == body["command_id"]


async def test_calibrage_exige_le_nombre_de_poules(client: AsyncClient, coop: Coop) -> None:
    response = await client.post("/api/v1/coops/coop_01/command", json={"action": "CALIBRATE"})
    assert response.status_code == 422

    response = await client.post(
        "/api/v1/coops/coop_01/command", json={"action": "OPEN", "inside_count": 3}
    )
    assert response.status_code == 422

    response = await client.post(
        "/api/v1/coops/coop_01/command", json={"action": "CALIBRATE", "inside_count": 9}
    )
    assert response.status_code == 202


async def test_commande_vers_poulailler_inconnu(app: FastAPI, client: AsyncClient) -> None:
    response = await client.post("/api/v1/coops/inconnu/command", json={"action": "CLOSE"})
    assert response.status_code == 404
    assert app.state.command_publisher.sent == []
