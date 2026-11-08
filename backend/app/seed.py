"""Données de démonstration : `python -m app.seed` (après `alembic upgrade head`).

Crée un éleveur de démo et le poulailler `coop_01` avec quelques événements et une alerte,
pour pouvoir développer l'application sans le Raspberry Pi. Enregistre aussi un Pi `coop_02`
qui n'est encore sur aucun compte, pour tester « Ajouter un poulailler » avec son code.
"""

import asyncio
from datetime import time, timedelta

from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.db import create_engine, create_sessionmaker
from app.models import (
    Alert,
    AlertType,
    Coop,
    Device,
    DoorState,
    Event,
    EventType,
    Severity,
    TriggerSource,
    User,
)
from app.repositories import CoopRepository, DeviceRepository, UserRepository
from app.security import hash_password, normalize_claim_code
from app.timeutils import utcnow

DEMO_EMAIL = "demo@smartnuggets.be"
# Compte de démonstration pour le développement local uniquement (jamais en production).
DEMO_PASSWORD = "poulailler"  # nosec B105
DEMO_COOP_ID = "coop_01"
# Pi de démo pas encore ajouté à un compte, avec un code connu (local uniquement).
DEMO_FREE_COOP_ID = "coop_02"
DEMO_CLAIM_CODE = "DEMO-DEMO-0002"


async def reset_free_device(session: AsyncSession) -> None:
    """Enregistre `coop_02` ou remet son code de démo, tant qu'il n'est sur aucun compte."""
    devices = DeviceRepository(session)
    device = await devices.get(DEMO_FREE_COOP_ID)
    code_hash = hash_password(normalize_claim_code(DEMO_CLAIM_CODE))
    if device is None:
        await devices.add(Device(id=DEMO_FREE_COOP_ID, claim_code_hash=code_hash))
    elif device.claimed_at is None:
        device.claim_code_hash = code_hash


async def seed() -> None:
    engine = create_engine(get_settings().database_url)
    sessionmaker = create_sessionmaker(engine)
    async with sessionmaker() as session:
        users = UserRepository(session)
        existing = await users.get_by_email(DEMO_EMAIL)
        if existing is not None:
            existing.password_hash = hash_password(DEMO_PASSWORD)
            await reset_free_device(session)
            await session.commit()
            await engine.dispose()
            print(f"Données de démo déjà présentes ({DEMO_EMAIL} / {DEMO_PASSWORD}).")
            print(f"Poulailler à ajouter : {DEMO_FREE_COOP_ID}, code {DEMO_CLAIM_CODE}.")
            return

        user = await users.add(User(email=DEMO_EMAIL, password_hash=hash_password(DEMO_PASSWORD)))
        await DeviceRepository(session).add(Device(id=DEMO_COOP_ID, claimed_at=utcnow()))
        await reset_free_device(session)
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
    print(
        f"Compte {DEMO_EMAIL} (mot de passe : {DEMO_PASSWORD}) et poulailler {DEMO_COOP_ID} créés."
    )
    print(f"Poulailler à ajouter : {DEMO_FREE_COOP_ID}, code {DEMO_CLAIM_CODE}.")


if __name__ == "__main__":
    asyncio.run(seed())
