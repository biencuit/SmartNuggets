"""Données de démonstration : `python -m app.seed` (après `alembic upgrade head`).

Crée un éleveur de démo et le poulailler `coop_01` avec deux semaines d'historique (passages,
porte, alertes dont un renard avec photo, voir `app/demo_history.py`), pour pouvoir développer
l'application sans le Raspberry Pi. Enregistre aussi un Pi `coop_02` qui n'est encore sur aucun
compte, pour tester « Ajouter un poulailler » avec son code.

`python -m app.seed --historique` régénère l'historique d'une base existante.
"""

import argparse
import asyncio
from datetime import time

from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.db import create_engine, create_sessionmaker
from app.demo_history import add_demo_history
from app.models import Coop, Device, DoorState, User
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


async def seed(regenerate_history: bool = False) -> None:
    settings = get_settings()
    engine = create_engine(settings.database_url)
    sessionmaker = create_sessionmaker(engine)
    async with sessionmaker() as session:
        users = UserRepository(session)
        existing = await users.get_by_email(DEMO_EMAIL)
        if existing is not None:
            existing.password_hash = hash_password(DEMO_PASSWORD)
            await reset_free_device(session)
            coop = await CoopRepository(session).get(DEMO_COOP_ID, owner_id=existing.id)
            if regenerate_history and coop is not None:
                history = await add_demo_history(session, coop, settings.media_dir, replace=True)
                print(f"Historique de démo régénéré : {len(history.events)} événements.")
            await session.commit()
            await engine.dispose()
            print(f"Données de démo déjà présentes ({DEMO_EMAIL} / {DEMO_PASSWORD}).")
            print(f"Poulailler à ajouter : {DEMO_FREE_COOP_ID}, code {DEMO_CLAIM_CODE}.")
            return

        user = await users.add(User(email=DEMO_EMAIL, password_hash=hash_password(DEMO_PASSWORD)))
        await DeviceRepository(session).add(Device(id=DEMO_COOP_ID, claimed_at=utcnow()))
        await reset_free_device(session)
        coop = await CoopRepository(session).add(
            Coop(
                id=DEMO_COOP_ID,
                owner_id=user.id,
                name="Poulailler de Marc",
                total_hens=10,
                inside_count=10,
                door_state=DoorState.CLOSED,
                auto_close_time=time(21, 30),
                battery_level=87,
                last_seen_at=utcnow(),
            )
        )
        history = await add_demo_history(session, coop, settings.media_dir)
        print(f"Historique de démo : {len(history.events)} événements sur deux semaines.")
        await session.commit()
    await engine.dispose()
    print(
        f"Compte {DEMO_EMAIL} (mot de passe : {DEMO_PASSWORD}) et poulailler {DEMO_COOP_ID} créés."
    )
    print(f"Poulailler à ajouter : {DEMO_FREE_COOP_ID}, code {DEMO_CLAIM_CODE}.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Données de démonstration (local uniquement)")
    parser.add_argument(
        "--historique",
        action="store_true",
        help="efface et régénère l'historique de démo du poulailler coop_01",
    )
    asyncio.run(seed(regenerate_history=parser.parse_args().historique))
