"""US-APP-4 (#27) : habitudes des poules (sorties et retours par jour et par heure).

Les premiers tests vérifient le calcul seul (`compute_habits`, sans base de données), y compris
les jours de changement d'heure. Les suivants passent par l'API.
"""

from dataclasses import dataclass
from datetime import UTC, date, datetime, time, timedelta

import pytest
from fastapi import FastAPI
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Coop, Event, EventType, User
from app.services.coop_service import CoopService
from app.services.habits import (
    UnknownTimezoneError,
    compute_habits,
    load_timezone,
    period_start,
    utc_bounds,
)
from app.timeutils import utcnow

from .test_ownership import other_client

BRUXELLES = load_timezone("Europe/Brussels")
URL = "/api/v1/coops/coop_01/habits"


@dataclass
class P:
    """Un passage, comme un `Event` de la base."""

    event_type: str
    occurred_at: datetime


def brussels(day: date, hour: int, minute: int = 0) -> datetime:
    return datetime(day.year, day.month, day.day, hour, minute, tzinfo=BRUXELLES)


def exit_at(at: datetime) -> P:
    return P(EventType.HEN_EXIT, at)


def entry_at(at: datetime) -> P:
    return P(EventType.HEN_ENTRY, at)


# ---------- Calcul seul ----------


def test_resume_par_jour_et_par_heure() -> None:
    d1, d2, d3 = date(2026, 11, 6), date(2026, 11, 7), date(2026, 11, 8)
    passages = [
        exit_at(brussels(d1, 7, 10)),
        exit_at(brussels(d1, 7, 40)),
        entry_at(brussels(d1, 12, 5)),
        entry_at(brussels(d1, 18, 20)),
        exit_at(brussels(d2, 7, 50)),
        entry_at(brussels(d2, 17, 40)),
        # Le 08/11 : aucune sortie (porte restée fermée), mais la journée apparaît.
    ]

    habits = compute_habits(passages, BRUXELLES, d1, 3)

    assert habits.timezone == "Europe/Brussels"
    assert [(d.day, d.exits, d.entries) for d in habits.days] == [
        (d1, 2, 2),
        (d2, 1, 1),
        (d3, 0, 0),
    ]
    assert habits.days[0].first_exit == time(7, 10)
    assert habits.days[0].last_entry == time(18, 20)
    assert habits.days[2].first_exit is None and habits.days[2].last_entry is None
    # Moyennes sur les jours qui ont une valeur : (7:10 + 7:50) / 2 et (18:20 + 17:40) / 2.
    assert habits.average_first_exit == time(7, 30)
    assert habits.average_last_entry == time(18, 0)
    assert (habits.total_exits, habits.total_entries) == (3, 3)
    # 3 sorties sur les 2 jours avec des passages : le 08/11 ne fait pas baisser la moyenne.
    assert habits.active_days == 2
    assert habits.exits_per_day == 1.5
    assert len(habits.hours) == 24
    assert (habits.hours[7].exits, habits.hours[7].entries) == (3, 0)
    assert (habits.hours[12].entries, habits.hours[17].entries, habits.hours[18].entries) == (
        1,
        1,
        1,
    )
    assert sum(h.exits for h in habits.hours) == 3


def test_jour_et_heure_locales_et_non_utc() -> None:
    """Scénario 6 de #27 : 22:30 UTC en hiver = 23:30 à Bruxelles, le même jour."""
    day = date(2026, 11, 9)
    habits = compute_habits(
        [entry_at(datetime(2026, 11, 9, 22, 30, tzinfo=UTC))], BRUXELLES, day, 1
    )

    assert habits.days[0].entries == 1
    assert habits.days[0].last_entry == time(23, 30)
    assert habits.hours[23].entries == 1


def test_passages_hors_periode_et_autres_evenements_ignores() -> None:
    day = date(2026, 11, 9)
    habits = compute_habits(
        [
            exit_at(brussels(day - timedelta(days=1), 8)),
            exit_at(brussels(day + timedelta(days=1), 8)),
            P(EventType.DOOR_OPEN, brussels(day, 7)),
            P(EventType.OBSTACLE, brussels(day, 9)),
        ],
        BRUXELLES,
        day,
        1,
    )

    assert habits.total_exits == habits.total_entries == 0
    assert habits.average_first_exit is None and habits.average_last_entry is None
    assert habits.exits_per_day == 0.0 and habits.active_days == 0


def test_sans_aucun_passage() -> None:
    habits = compute_habits([], BRUXELLES, date(2026, 11, 3), 7)

    assert len(habits.days) == 7
    assert habits.days[0].day == date(2026, 11, 3) and habits.days[-1].day == date(2026, 11, 9)
    assert all(h.exits == h.entries == 0 for h in habits.hours)


def test_moyenne_arrondie_a_la_minute() -> None:
    d1, d2 = date(2026, 11, 7), date(2026, 11, 8)
    habits = compute_habits(
        [exit_at(brussels(d1, 7, 0)), exit_at(brussels(d2, 7, 1))], BRUXELLES, d1, 2
    )
    assert habits.average_first_exit == time(7, 0)  # 7:00:30 arrondi
    assert habits.exits_per_day == 1.0


def test_passage_a_l_heure_d_hiver_journee_de_25_heures() -> None:
    """Le 25/10/2026, à 3 h, l'horloge revient à 2 h : la journée dure 25 h à Bruxelles.

    Une sortie à 02:50 (heure d'été, 00:50 UTC) a lieu AVANT une sortie à 02:10 (heure
    d'hiver, 01:10 UTC). La première sortie est donc 02:50, même si 02:10 est « plus petit ».
    """
    day = date(2026, 10, 25)
    since, until = utc_bounds(day, 1, BRUXELLES)
    assert until - since == timedelta(hours=25)

    habits = compute_habits(
        [
            exit_at(datetime(2026, 10, 25, 1, 10, tzinfo=UTC)),
            exit_at(datetime(2026, 10, 25, 0, 50, tzinfo=UTC)),
            # 23:30 heure d'hiver = 22:30 UTC : encore le 25/10.
            entry_at(datetime(2026, 10, 25, 22, 30, tzinfo=UTC)),
            # 23:30 UTC = 00:30 le 26/10 à Bruxelles : hors période.
            entry_at(datetime(2026, 10, 25, 23, 30, tzinfo=UTC)),
        ],
        BRUXELLES,
        day,
        1,
    )

    assert habits.days[0].first_exit == time(2, 50)
    assert habits.hours[2].exits == 2  # les deux « 2 h » de la journée
    assert habits.days[0].last_entry == time(23, 30)
    assert habits.total_entries == 1


def test_passage_a_l_heure_d_ete_journee_de_23_heures() -> None:
    since, until = utc_bounds(date(2026, 3, 29), 1, BRUXELLES)
    assert until - since == timedelta(hours=23)
    assert since == datetime(2026, 3, 28, 23, 0, tzinfo=UTC)


def test_periode_qui_finit_aujourd_hui_en_heure_locale() -> None:
    # 23:30 UTC le 09/11 = 00:30 le 10/11 à Bruxelles : « aujourd'hui » est déjà le 10/11.
    now = datetime(2026, 11, 9, 23, 30, tzinfo=UTC)
    assert period_start(now, BRUXELLES, 7) == date(2026, 11, 4)
    assert period_start(now, BRUXELLES, 1) == date(2026, 11, 10)


@pytest.mark.parametrize("name", ["Europe/Bruxelles", "Europe", "../etc/passwd", "", "UTC+1"])
def test_fuseau_inconnu(name: str) -> None:
    with pytest.raises(UnknownTimezoneError):
        load_timezone(name)


# ---------- Par l'API ----------


async def test_habitudes_par_l_api(client: AsyncClient, session: AsyncSession, coop: Coop) -> None:
    """Scénario 5 de #27, sur les vraies dates : passages d'hier, à Bruxelles."""
    yesterday = utcnow().astimezone(BRUXELLES).date() - timedelta(days=1)
    for event_type, hour, minute in [
        (EventType.HEN_EXIT, 7, 15),
        (EventType.HEN_EXIT, 7, 25),
        (EventType.HEN_ENTRY, 18, 40),
        (EventType.DOOR_OPEN, 7, 14),
    ]:
        session.add(
            Event(
                coop_id=coop.id,
                event_type=event_type,
                occurred_at=brussels(yesterday, hour, minute).astimezone(UTC),
            )
        )
    await session.commit()

    response = await client.get(URL)

    assert response.status_code == 200
    body = response.json()
    assert body["timezone"] == "Europe/Brussels"
    assert len(body["days"]) == 7 and len(body["hours"]) == 24
    assert body["days"][-2] == {
        "day": yesterday.isoformat(),
        "exits": 2,
        "entries": 1,
        "first_exit": "07:15:00",
        "last_entry": "18:40:00",
    }
    assert body["average_first_exit"] == "07:15:00"
    assert body["hours"][7] == {"hour": 7, "exits": 2, "entries": 0}
    assert (body["total_exits"], body["total_entries"]) == (2, 1)
    assert (body["active_days"], body["exits_per_day"]) == (1, 2.0)

    response = await client.get(URL, params={"days": 30})
    assert len(response.json()["days"]) == 30


async def test_le_fuseau_change_le_jour_d_un_passage(
    app: FastAPI, session: AsyncSession, coop: Coop, owner: User
) -> None:
    """03:30 UTC le 09/11 : 04:30 le 09/11 à Bruxelles, mais 22:30 le 08/11 à New York."""
    session.add(
        Event(
            coop_id=coop.id,
            event_type=EventType.HEN_EXIT,
            occurred_at=datetime(2026, 11, 9, 3, 30, tzinfo=UTC),
        )
    )
    await session.commit()
    service = CoopService(session, app.state.command_publisher, owner.id)
    now = datetime(2026, 11, 9, 12, 0, tzinfo=UTC)

    brussels_habits = await service.get_habits(coop.id, days=2, tz=BRUXELLES, now=now)
    new_york = load_timezone("America/New_York")
    new_york_habits = await service.get_habits(coop.id, days=2, tz=new_york, now=now)

    assert [(d.day.day, d.exits) for d in brussels_habits.days] == [(8, 0), (9, 1)]
    assert brussels_habits.days[1].first_exit == time(4, 30)
    assert [(d.day.day, d.exits) for d in new_york_habits.days] == [(8, 1), (9, 0)]
    assert new_york_habits.days[0].first_exit == time(22, 30)


async def test_parametres_invalides(client: AsyncClient, coop: Coop) -> None:
    for params in [
        {"days": 0},
        {"days": 32},
        {"days": "sept"},
        {"tz": "Europe/Bruxelles"},
        {"tz": "Europe"},
        {"tz": "../../etc/passwd"},
        {"tz": "x" * 65},
    ]:
        response = await client.get(URL, params=params)
        assert response.status_code == 422, params
    detail = (await client.get(URL, params={"tz": "Europe/Bruxelles"})).json()["detail"]
    assert "Fuseau horaire inconnu" in detail


async def test_habitudes_d_un_autre_poulailler(
    app: FastAPI, session: AsyncSession, coop: Coop
) -> None:
    async with await other_client(app, session) as voisin:
        response = await voisin.get(URL)
    assert response.status_code == 404


async def test_habitudes_sans_connexion(anon_client: AsyncClient, coop: Coop) -> None:
    assert (await anon_client.get(URL)).status_code == 401
