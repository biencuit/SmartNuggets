from datetime import timedelta

from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Alert, AlertType, Coop, Event, EventType, Severity, User
from app.repositories import AlertRepository, CoopRepository, EventRepository, UserRepository
from app.timeutils import utcnow


async def test_email_utilisateur_normalise_en_minuscules(session: AsyncSession) -> None:
    users = UserRepository(session)
    await users.add(User(email="Marc@Example.COM", password_hash="!"))
    await session.commit()

    assert (await users.get_by_email("MARC@example.com")) is not None


async def test_coop_filtre_par_proprietaire(session: AsyncSession, coop: Coop) -> None:
    other = User(email="voisin@example.com", password_hash="!")
    session.add(other)
    await session.commit()
    coops = CoopRepository(session)

    assert await coops.get("coop_01", owner_id=coop.owner_id) is not None
    assert await coops.get("coop_01", owner_id=other.id) is None
    assert await coops.list(owner_id=other.id) == []


async def test_evenements_du_plus_recent_au_plus_ancien(session: AsyncSession, coop: Coop) -> None:
    now = utcnow()
    events = EventRepository(session)
    for minutes, event_type in [(30, EventType.HEN_EXIT), (5, EventType.HEN_ENTRY)]:
        await events.add(
            Event(
                coop_id=coop.id, event_type=event_type, occurred_at=now - timedelta(minutes=minutes)
            )
        )
    await session.commit()

    result = await events.list_for_coop(coop.id)
    assert [e.event_type for e in result] == [EventType.HEN_ENTRY, EventType.HEN_EXIT]

    only_exits = await events.list_for_coop(coop.id, event_type=EventType.HEN_EXIT)
    assert len(only_exits) == 1


async def test_alertes_filtrees_par_etat_de_lecture(session: AsyncSession, coop: Coop) -> None:
    alerts = AlertRepository(session)
    await alerts.add(
        Alert(coop_id=coop.id, alert_type=AlertType.LOW_BATTERY, severity=Severity.WARNING)
    )
    await alerts.add(
        Alert(
            coop_id=coop.id,
            alert_type=AlertType.PREDATOR_DETECTED,
            severity=Severity.CRITICAL,
            acknowledged=True,
        )
    )
    await session.commit()

    unread = await alerts.list_for_coop(coop.id, acknowledged=False)
    assert [a.alert_type for a in unread] == [AlertType.LOW_BATTERY]
