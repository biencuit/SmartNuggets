"""Données de démonstration : `python -m app.seed` (après `alembic upgrade head`).

Crée un éleveur de démo et le poulailler `coop_01` avec quelques événements et une alerte,
pour pouvoir développer l'application sans le Raspberry Pi.
"""

import asyncio
from datetime import time, timedelta

from app.config import get_settings
from app.db import create_engine, create_sessionmaker
from app.models import (
    Alert,
    AlertType,
    Coop,
    DoorState,
    Event,
    EventType,
    Severity,
    TriggerSource,
    User,
)
from app.repositories import CoopRepository, UserRepository
from app.timeutils import utcnow

DEMO_EMAIL = "demo@smartnuggets.be"
DEMO_COOP_ID = "coop_01"


async def seed() -> None:
    engine = create_engine(get_settings().database_url)
    sessionmaker = create_sessionmaker(engine)
    async with sessionmaker() as session:
        users = UserRepository(session)
        if await users.get_by_email(DEMO_EMAIL) is not None:
            print("Données de démo déjà présentes.")
            await engine.dispose()
            return

        # "!" = aucun mot de passe valide (la connexion arrive avec l'issue #25).
        user = await users.add(User(email=DEMO_EMAIL, password_hash="!"))  # nosec B106
        await CoopRepository(session).add(
            Coop(
                id=DEMO_COOP_ID,
                owner_id=user.id,
                name="Poulailler de Marc",
                total_hens=10,
                inside_count=8,
                door_state=DoorState.OPEN,
                auto_close_time=time(21, 30),
                battery_level=87,
                last_seen_at=utcnow(),
            )
        )
        now = utcnow()
        session.add_all(
            [
                Event(
                    coop_id=DEMO_COOP_ID,
                    event_type=EventType.DOOR_OPEN,
                    trigger_source=TriggerSource.AI_AUTO,
                    inside_count_after=10,
                    ai_confidence=0.94,
                    occurred_at=now - timedelta(minutes=30),
                ),
                Event(
                    coop_id=DEMO_COOP_ID,
                    event_type=EventType.HEN_EXIT,
                    trigger_source=TriggerSource.AI_AUTO,
                    inside_count_after=9,
                    ai_confidence=0.91,
                    occurred_at=now - timedelta(minutes=29),
                ),
                Event(
                    coop_id=DEMO_COOP_ID,
                    event_type=EventType.HEN_EXIT,
                    trigger_source=TriggerSource.AI_AUTO,
                    inside_count_after=8,
                    ai_confidence=0.89,
                    occurred_at=now - timedelta(minutes=12),
                ),
                Alert(
                    coop_id=DEMO_COOP_ID,
                    alert_type=AlertType.PREDATOR_DETECTED,
                    severity=Severity.CRITICAL,
                    ai_confidence=0.87,
                    created_at=now - timedelta(hours=10),
                ),
            ]
        )
        await session.commit()
    await engine.dispose()
    print(f"Utilisateur {DEMO_EMAIL} et poulailler {DEMO_COOP_ID} créés.")


if __name__ == "__main__":
    asyncio.run(seed())
