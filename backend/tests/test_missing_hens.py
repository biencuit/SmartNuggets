"""US perso de Sébastien : nombre total de poules (US-COMPT-3, #18) et alerte quand des
poules sont encore dehors à la fermeture de la porte (US-COMPT-4, #19)."""

import json

from fastapi import FastAPI
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Alert, Coop
from app.services.broadcaster import Broadcaster

from .test_ingestion import SENT_AT, make_worker, refreshed_coop
from .test_ownership import other_client

# ---------------------------------------------------------------- US-COMPT-3 : le total


async def test_regler_le_nombre_total_de_poules(
    app: FastAPI, client: AsyncClient, session: AsyncSession, coop: Coop
) -> None:
    broadcaster: Broadcaster = app.state.broadcaster
    async with broadcaster.subscribe("coop_01") as queue:
        response = await client.patch("/api/v1/coops/coop_01", json={"total_hens": 12})
        messages = [queue.get_nowait() for _ in range(queue.qsize())]

    assert response.status_code == 200
    assert response.json() == {"id": "coop_01", "name": "Poulailler de Marc", "total_hens": 12}
    assert (await refreshed_coop(session)).total_hens == 12
    # La page ouverte reçoit le nouvel état : 7 dedans, donc 5 dehors.
    assert messages[0]["event"] == "status"
    assert messages[0]["data"]["outside_count"] == 5


async def test_nombre_de_poules_invalide_refuse(client: AsyncClient, coop: Coop) -> None:
    for value in (-1, 1001, "dix"):
        response = await client.patch("/api/v1/coops/coop_01", json={"total_hens": value})
        assert response.status_code == 422


async def test_impossible_de_regler_le_poulailler_d_un_autre(
    app: FastAPI, session: AsyncSession, coop: Coop
) -> None:
    async with await other_client(app, session) as voisin:
        response = await voisin.patch("/api/v1/coops/coop_01", json={"total_hens": 3})
    assert response.status_code == 404
    assert (await refreshed_coop(session)).total_hens == 10


# ---------------------------------------------------------------- US-COMPT-4 : l'alerte


async def porte_fermee(
    app: FastAPI, inside: int, event_type: str = "DOOR_CLOSE", source: str = "SCHEDULE"
) -> list:
    """Simule le Raspberry Pi qui annonce une fermeture de porte avec `inside` poules."""
    payload = {
        "sent_at": SENT_AT,
        "door_state": "CLOSED",
        "inside_count": inside,
        "event": {"event_type": event_type, "trigger_source": source, "occurred_at": SENT_AT},
    }
    broadcaster: Broadcaster = app.state.broadcaster
    async with broadcaster.subscribe("coop_01") as queue:
        await make_worker(app).handle_message(
            "smartnuggets/coop_01/telemetry", json.dumps(payload).encode()
        )
        return [queue.get_nowait() for _ in range(queue.qsize())]


async def alertes(session: AsyncSession) -> list[Alert]:
    session.expire_all()
    return list((await session.execute(select(Alert))).scalars())


async def test_alerte_si_des_poules_sont_dehors_a_la_fermeture(
    app: FastAPI, session: AsyncSession, coop: Coop
) -> None:
    messages = await porte_fermee(app, inside=8)  # 10 poules au total

    [alerte] = await alertes(session)
    assert alerte.alert_type == "MISSING_HEN"
    assert alerte.severity == "WARNING"
    assert alerte.missing_count == 2
    # L'application reçoit l'état (2 dehors), l'événement, puis l'alerte en direct.
    assert [m["event"] for m in messages] == ["status", "event", "alert"]
    assert messages[0]["data"]["outside_count"] == 2
    assert messages[2]["data"]["missing_count"] == 2


async def test_pas_d_alerte_si_toutes_les_poules_sont_rentrees(
    app: FastAPI, session: AsyncSession, coop: Coop
) -> None:
    await porte_fermee(app, inside=10)
    assert await alertes(session) == []


async def test_pas_d_alerte_si_le_total_n_est_pas_regle(
    app: FastAPI, session: AsyncSession, coop: Coop
) -> None:
    coop.total_hens = 0
    await session.commit()
    await porte_fermee(app, inside=0)
    assert await alertes(session) == []


async def test_pas_d_alerte_pour_une_ouverture_ou_un_passage(
    app: FastAPI, session: AsyncSession, coop: Coop
) -> None:
    await porte_fermee(app, inside=3, event_type="DOOR_OPEN")
    await porte_fermee(app, inside=3, event_type="HEN_EXIT")
    assert await alertes(session) == []


async def test_pas_d_alerte_pour_une_fermeture_en_journee(
    app: FastAPI, session: AsyncSession, coop: Coop
) -> None:
    # En journée, des poules dehors sont normales : la porte se referme après un passage
    # (caméra) ou devant un prédateur (sécurité), ou l'éleveur la ferme depuis l'application.
    for source in ("AI_AUTO", "FAILSAFE", "MANUAL_APP"):
        await porte_fermee(app, inside=6, source=source)
    assert await alertes(session) == []
