"""US-APP-4 (#27) : historique complet du poulailler (passages, porte et alertes).

Les dates sont fixes (le 09/11/2026, heure de Bruxelles = UTC+1) pour que chaque test
décrive un scénario précis, indépendant du jour où il tourne.
"""

from datetime import UTC, datetime, timedelta

from fastapi import FastAPI
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import (
    Alert,
    AlertType,
    Coop,
    Event,
    EventType,
    Severity,
    TriggerSource,
)

from .test_ownership import other_client

URL = "/api/v1/coops/coop_01/history"
# 09/11/2026 à Bruxelles : de 00:00 à 24:00 heure locale = de 23:00 la veille à 23:00 UTC.
YESTERDAY_START = "2026-11-08T23:00:00Z"
YESTERDAY_END = "2026-11-09T23:00:00Z"


def utc(day: int, hour: int, minute: int = 0) -> datetime:
    return datetime(2026, 11, day, hour, minute, tzinfo=UTC)


async def add_day_of_history(session: AsyncSession, coop: Coop) -> None:
    """Le 09/11 : porte ouverte, 2 sorties, 1 entrée, renard (avec photo), porte fermée.

    Plus une entrée le 08/11 et une le 10/11, qui ne sont pas « hier ».
    """
    events = [
        (utc(9, 6, 30), EventType.DOOR_OPEN, TriggerSource.AI_AUTO, 10),
        (utc(9, 6, 31), EventType.HEN_EXIT, TriggerSource.AI_AUTO, 9),
        (utc(9, 6, 40), EventType.HEN_EXIT, TriggerSource.AI_AUTO, 8),
        (utc(9, 11, 5), EventType.HEN_ENTRY, TriggerSource.AI_AUTO, 9),
        (utc(9, 13, 12), EventType.DOOR_CLOSE, TriggerSource.FAILSAFE, 9),
        # Le 08/11 à 22:30 UTC, il est déjà 23:30 à Bruxelles : c'est encore le 08/11.
        (utc(8, 22, 30), EventType.HEN_ENTRY, TriggerSource.AI_AUTO, 10),
        # Le 09/11 à 23:15 UTC, il est 00:15 le 10/11 à Bruxelles : ce n'est plus « hier ».
        (utc(9, 23, 15), EventType.HEN_ENTRY, TriggerSource.AI_AUTO, 10),
    ]
    for at, event_type, source, inside in events:
        session.add(
            Event(
                coop_id=coop.id,
                event_type=event_type,
                trigger_source=source,
                inside_count_after=inside,
                occurred_at=at,
            )
        )
    session.add(
        Alert(
            coop_id=coop.id,
            alert_type=AlertType.PREDATOR_DETECTED,
            severity=Severity.CRITICAL,
            ai_confidence=0.87,
            image_url="/api/v1/coops/coop_01/alerts/1/image",
            created_at=utc(9, 13, 12),
        )
    )
    await session.commit()


async def test_sans_filtre_tout_est_melange_du_plus_recent_au_plus_ancien(
    client: AsyncClient, session: AsyncSession, coop: Coop
) -> None:
    await add_day_of_history(session, coop)

    response = await client.get(URL)

    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 8
    kinds_and_types = [(item["kind"], item["type"]) for item in body["items"]]
    assert kinds_and_types == [
        ("event", "HEN_ENTRY"),  # 10/11 00:15 (heure de Bruxelles)
        # Même seconde : l'alerte passe avant l'événement (ordre stable entre deux pages).
        ("alert", "PREDATOR_DETECTED"),
        ("event", "DOOR_CLOSE"),
        ("event", "HEN_ENTRY"),
        ("event", "HEN_EXIT"),
        ("event", "HEN_EXIT"),
        ("event", "DOOR_OPEN"),
        ("event", "HEN_ENTRY"),  # 08/11
    ]
    times = [item["occurred_at"] for item in body["items"]]
    assert times == sorted(times, reverse=True)


async def test_les_champs_dependent_du_genre_de_ligne(
    client: AsyncClient, session: AsyncSession, coop: Coop
) -> None:
    await add_day_of_history(session, coop)

    items = (await client.get(URL)).json()["items"]
    alert = next(item for item in items if item["kind"] == "alert")
    door = next(item for item in items if item["type"] == "DOOR_CLOSE")

    assert alert["severity"] == "CRITICAL"
    assert alert["image_url"] == "/api/v1/coops/coop_01/alerts/1/image"
    assert alert["acknowledged"] is False
    assert alert["trigger_source"] is None and alert["inside_count_after"] is None
    assert door["trigger_source"] == "FAILSAFE"
    assert door["inside_count_after"] == 9
    assert door["severity"] is None and door["image_url"] is None
    assert door["acknowledged"] is None
    assert alert["occurred_at"] in ("2026-11-09T13:12:00Z", "2026-11-09T13:12:00+00:00")


async def test_scenario_entrees_d_hier(
    client: AsyncClient, session: AsyncSession, coop: Coop
) -> None:
    """Scénario 1 de #27 : « Entrées » + « Hier » → seules les entrées d'hier."""
    await add_day_of_history(session, coop)

    response = await client.get(
        URL, params={"category": "entries", "since": YESTERDAY_START, "until": YESTERDAY_END}
    )

    body = response.json()
    assert body["total"] == 1
    assert [(item["type"], item["occurred_at"][:16]) for item in body["items"]] == [
        ("HEN_ENTRY", "2026-11-09T11:05")
    ]


async def test_plusieurs_categories_a_la_fois(
    client: AsyncClient, session: AsyncSession, coop: Coop
) -> None:
    await add_day_of_history(session, coop)

    response = await client.get(URL, params=[("category", "door"), ("category", "alerts")])
    types = [item["type"] for item in response.json()["items"]]
    assert types == ["PREDATOR_DETECTED", "DOOR_CLOSE", "DOOR_OPEN"]

    response = await client.get(URL, params={"category": "exits"})
    assert [item["type"] for item in response.json()["items"]] == ["HEN_EXIT", "HEN_EXIT"]

    response = await client.get(URL, params={"category": "alerts"})
    assert [item["kind"] for item in response.json()["items"]] == ["alert"]


async def test_obstacle_compte_dans_la_porte(
    client: AsyncClient, session: AsyncSession, coop: Coop
) -> None:
    session.add(Event(coop_id=coop.id, event_type=EventType.OBSTACLE, occurred_at=utc(9, 20)))
    await session.commit()

    response = await client.get(URL, params={"category": "door"})
    assert [item["type"] for item in response.json()["items"]] == ["OBSTACLE"]


async def test_pagination_avec_total(
    client: AsyncClient, session: AsyncSession, coop: Coop
) -> None:
    """Scénario 3 de #27 : le total ne dépend pas de la page, et les pages se suivent."""
    start = utc(9, 8)
    for i in range(120):
        event_type = EventType.HEN_EXIT if i % 2 else EventType.HEN_ENTRY
        session.add(
            Event(coop_id=coop.id, event_type=event_type, occurred_at=start + timedelta(minutes=i))
        )
    await session.commit()

    first = (await client.get(URL)).json()
    second = (await client.get(URL, params={"offset": 50})).json()
    last = (await client.get(URL, params={"offset": 100})).json()

    assert first["total"] == second["total"] == last["total"] == 120
    assert (len(first["items"]), len(second["items"]), len(last["items"])) == (50, 50, 20)
    ids = [item["id"] for page in (first, second, last) for item in page["items"]]
    assert len(set(ids)) == 120  # aucun doublon, aucun trou
    assert first["items"][-1]["occurred_at"] > second["items"][0]["occurred_at"]

    page = (await client.get(URL, params={"limit": 100})).json()
    assert len(page["items"]) == 100


async def test_periode_sans_resultat(
    client: AsyncClient, session: AsyncSession, coop: Coop
) -> None:
    await add_day_of_history(session, coop)

    response = await client.get(
        URL, params={"since": "2026-01-01T00:00:00Z", "until": "2026-01-02T00:00:00Z"}
    )
    assert response.json() == {"total": 0, "items": []}


async def test_date_avec_fuseau_ou_sans(
    client: AsyncClient, session: AsyncSession, coop: Coop
) -> None:
    """« 2026-11-09T00:00:00+01:00 » (Bruxelles) = 2026-11-08T23:00:00Z ; sans fuseau = UTC."""
    await add_day_of_history(session, coop)

    with_offset = await client.get(
        URL,
        params={"since": "2026-11-09T00:00:00+01:00", "until": "2026-11-10T00:00:00+01:00"},
    )
    naive_utc = await client.get(
        URL, params={"since": "2026-11-08T23:00:00", "until": "2026-11-09T23:00:00"}
    )
    assert with_offset.json()["total"] == naive_utc.json()["total"] == 6


async def test_parametres_invalides(client: AsyncClient, coop: Coop) -> None:
    for params in [
        {"category": "poules"},
        {"since": "2026-11-10T00:00:00Z", "until": "2026-11-09T00:00:00Z"},
        {"since": "2026-11-10T00:00:00Z", "until": "2026-11-10T00:00:00Z"},
        {"since": "hier"},
        {"limit": 0},
        {"limit": 101},
        {"offset": -1},
    ]:
        response = await client.get(URL, params=params)
        assert response.status_code == 422, params


async def test_historique_d_un_autre_poulailler(
    app: FastAPI, session: AsyncSession, coop: Coop
) -> None:
    await add_day_of_history(session, coop)

    async with await other_client(app, session) as voisin:
        response = await voisin.get(URL)

    assert response.status_code == 404


async def test_historique_sans_connexion(anon_client: AsyncClient, coop: Coop) -> None:
    response = await anon_client.get(URL)
    assert response.status_code == 401


async def test_poulailler_inconnu(client: AsyncClient) -> None:
    response = await client.get("/api/v1/coops/inconnu/history")
    assert response.status_code == 404
