"""Planning hebdomadaire de la porte (#70)."""

from fastapi import FastAPI
from httpx import AsyncClient

from app.models import Coop

SCHEDULE = "/api/v1/coops/coop_01/schedule"

DEFAULT_WEEK = [
    {"weekday": weekday, "open_from": "07:00:00", "close_at": "21:00:00"} for weekday in range(7)
]


def custom_week(saturday_close: str = "22:00:00") -> list[dict]:
    days = [dict(day) for day in DEFAULT_WEEK]
    days[5]["close_at"] = saturday_close  # 5 = samedi
    return days


async def test_planning_par_defaut_sans_personnalisation(
    client: AsyncClient, coop: Coop
) -> None:
    response = await client.get(SCHEDULE)

    assert response.status_code == 200
    assert response.json() == {"days": DEFAULT_WEEK}


async def test_regler_le_planning_le_sauvegarde_et_le_transmet(
    app: FastAPI, client: AsyncClient, coop: Coop
) -> None:
    response = await client.put(SCHEDULE, json={"days": custom_week()})

    assert response.status_code == 200
    assert response.json() == {"days": custom_week()}
    # Relu depuis la base (pas seulement renvoyé par l'appel précédent).
    assert (await client.get(SCHEDULE)).json() == {"days": custom_week()}
    # Transmis tout de suite au Raspberry Pi (message retenu, publisher en mémoire pour les tests).
    sent = app.state.schedule_publisher.sent["coop_01"]
    assert sent[5][0] == 5  # samedi
    assert sent[5][2].isoformat() == "22:00:00"


async def test_planning_refuse_sauf_exactement_sept_jours(
    client: AsyncClient, coop: Coop
) -> None:
    response = await client.put(SCHEDULE, json={"days": DEFAULT_WEEK[:6]})  # il en manque un
    assert response.status_code == 422

    with_doublon = DEFAULT_WEEK[:6] + [DEFAULT_WEEK[0]]  # lundi en double, dimanche absent
    response = await client.put(SCHEDULE, json={"days": with_doublon})
    assert response.status_code == 422


async def test_planning_exige_une_connexion(anon_client: AsyncClient) -> None:
    assert (await anon_client.get(SCHEDULE)).status_code == 401
    assert (await anon_client.put(SCHEDULE, json={"days": DEFAULT_WEEK})).status_code == 401


async def test_planning_d_un_poulailler_inconnu_renvoie_404(client: AsyncClient) -> None:
    url = "/api/v1/coops/inconnu/schedule"
    assert (await client.get(url)).status_code == 404
    assert (await client.put(url, json={"days": DEFAULT_WEEK})).status_code == 404
