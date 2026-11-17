"""US-APP-4 (#27) : historique de démonstration (deux semaines de passages, renard avec photo)."""

from datetime import UTC, datetime, time, timedelta

from fastapi import FastAPI
from httpx import AsyncClient
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.demo_history import (
    DEMO_TIMEZONE,
    PHOTO,
    TOTAL_HENS,
    add_demo_history,
    build_demo_history,
)
from app.models import Alert, AlertType, Coop, DoorState, Event, EventType, TriggerSource

NOW = datetime(2026, 11, 10, 10, 40, tzinfo=UTC)  # mardi 10/11, 11:40 à Bruxelles


def local(at: datetime) -> datetime:
    return at.astimezone(DEMO_TIMEZONE)


def test_deux_semaines_completes_jusqu_a_hier() -> None:
    history = build_demo_history(NOW)

    days = sorted({local(e.at).date() for e in history.events})
    today = local(NOW).date()
    assert len(days) == 14
    assert days[0] == today - timedelta(days=14) and days[-1] == today - timedelta(days=1)
    assert [e.at for e in history.events] == sorted(e.at for e in history.events)


def test_toujours_la_meme_demo() -> None:
    assert build_demo_history(NOW) == build_demo_history(NOW)


def test_compteur_et_porte_coherents() -> None:
    history = build_demo_history(NOW)

    assert all(0 <= e.inside_after <= TOTAL_HENS for e in history.events)
    # Le soir, tout le monde est rentré et la porte est fermée.
    assert history.inside_count == TOTAL_HENS
    assert history.door_state == DoorState.CLOSED
    # La porte alterne ouverture / fermeture, sans deux ouvertures de suite.
    doors = [
        e.event_type
        for e in history.events
        if e.event_type in (EventType.DOOR_OPEN, EventType.DOOR_CLOSE)
    ]
    assert all(a != b for a, b in zip(doors, doors[1:], strict=False))
    # Le compteur suit les passages : +1 pour une entrée, -1 pour une sortie.
    inside = TOTAL_HENS
    for event in history.events:
        if event.event_type == EventType.HEN_ENTRY:
            inside += 1
        elif event.event_type == EventType.HEN_EXIT:
            inside -= 1
        assert event.inside_after == inside


def test_journees_realistes() -> None:
    history = build_demo_history(NOW)
    first_exits: dict = {}
    for event in history.events:
        if event.event_type == EventType.HEN_EXIT:
            first_exits.setdefault(local(event.at).date(), local(event.at).time())

    assert len(first_exits) == 14
    assert all(time(6, 40) <= t <= time(8, 15) for t in first_exits.values())
    # Fermetures à l'horaire du soir (21:30) les jours où une poule rentre tard.
    schedule = [e for e in history.events if e.trigger_source == TriggerSource.SCHEDULE]
    assert len(schedule) == 2
    assert all(local(e.at).time() == time(21, 30) for e in schedule)


def test_renard_avec_photo_et_porte_fermee_par_securite() -> None:
    history = build_demo_history(NOW)
    predators = [a for a in history.alerts if a.alert_type == AlertType.PREDATOR_DETECTED]

    assert len(predators) == 1
    fox = predators[0]
    assert fox.with_photo and not fox.acknowledged
    assert local(fox.at).date() == local(NOW).date() - timedelta(days=3)
    assert local(fox.at).time() == time(14, 12)
    failsafe = [e for e in history.events if e.trigger_source == TriggerSource.FAILSAFE]
    assert [(e.event_type, e.at) for e in failsafe] == [(EventType.DOOR_CLOSE, fox.at)]
    # Verrouillage de 5 minutes : aucune ouverture juste après le renard.
    assert not any(
        e.event_type == EventType.DOOR_OPEN and fox.at <= e.at < fox.at + timedelta(minutes=5)
        for e in history.events
    )


async def test_enregistre_en_base_et_visible_dans_l_api(
    app: FastAPI, client: AsyncClient, session: AsyncSession, coop: Coop
) -> None:
    history = await add_demo_history(session, coop, app.state.settings.media_dir)
    await session.commit()

    page = (await client.get("/api/v1/coops/coop_01/history")).json()
    assert page["total"] == len(history.events) + len(history.alerts)
    assert page["total"] > 100  # assez pour la pagination

    alerts = (await client.get("/api/v1/coops/coop_01/history?category=alerts")).json()
    fox = next(a for a in alerts["items"] if a["type"] == "PREDATOR_DETECTED")
    image = await client.get(fox["image_url"])
    assert image.status_code == 200
    assert image.headers["content-type"] == "image/jpeg"
    assert image.content == PHOTO.read_bytes()

    habits = (await client.get("/api/v1/coops/coop_01/habits")).json()
    assert habits["active_days"] == 6  # hier et les 5 jours d'avant ; aujourd'hui est vide
    assert 8 <= habits["exits_per_day"] <= 20

    status = (await client.get("/api/v1/coops/coop_01/status")).json()
    assert (status["inside_count"], status["door_state"]) == (10, "CLOSED")


async def test_regenerer_sans_doublon(app: FastAPI, session: AsyncSession, coop: Coop) -> None:
    media_dir = app.state.settings.media_dir
    await add_demo_history(session, coop, media_dir, NOW)
    await session.commit()
    history = await add_demo_history(session, coop, media_dir, NOW, replace=True)
    await session.commit()

    events = (await session.execute(select(func.count()).select_from(Event))).scalar_one()
    alerts = (await session.execute(select(func.count()).select_from(Alert))).scalar_one()
    assert (events, alerts) == (len(history.events), len(history.alerts))
