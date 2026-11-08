"""Enregistrer un nouveau Raspberry Pi : `python -m app.new_coop coop_02`.

Sur le VPS, on passe par `scripts/new-coop.sh`, qui crée aussi le compte MQTT du Pi.

Affiche le code d'appairage à écrire sur l'étiquette du boîtier. L'éleveur en a besoin pour
ajouter le poulailler à son compte. Seul le hash du code est gardé en base : si le code est
perdu avant d'avoir servi, on en crée un nouveau avec `--new-code`.
"""

import argparse
import asyncio
import sys

from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.db import create_engine, create_sessionmaker
from app.models import Device
from app.mqtt.topics import COOP_ID_PATTERN
from app.repositories import DeviceRepository
from app.security import generate_claim_code, hash_password, normalize_claim_code


class NewCoopError(Exception):
    pass


async def register_device(session: AsyncSession, coop_id: str, *, new_code: bool = False) -> str:
    """Enregistre le Pi (ou lui donne un nouveau code) et renvoie le code en clair."""
    if not COOP_ID_PATTERN.fullmatch(coop_id):
        raise NewCoopError(
            "L'identifiant ne peut contenir que des lettres sans accent, des chiffres, _ et - "
            "(64 caractères au maximum)."
        )
    devices = DeviceRepository(session)
    device = await devices.get(coop_id)
    if device is not None and device.claimed_at is not None:
        raise NewCoopError(f"{coop_id} est déjà ajouté à un compte : son code a déjà servi.")
    if device is not None and not new_code:
        raise NewCoopError(f"{coop_id} existe déjà. Code perdu ? Relancer avec --new-code.")

    code = generate_claim_code()
    code_hash = hash_password(normalize_claim_code(code))
    if device is None:
        await devices.add(Device(id=coop_id, claim_code_hash=code_hash))
    else:
        device.claim_code_hash = code_hash
    await session.commit()
    return code


async def run(coop_id: str, new_code: bool) -> str:
    engine = create_engine(get_settings().database_url)
    try:
        async with create_sessionmaker(engine)() as session:
            return await register_device(session, coop_id, new_code=new_code)
    finally:
        await engine.dispose()


def main() -> None:
    parser = argparse.ArgumentParser(description="Enregistrer un nouveau Raspberry Pi.")
    parser.add_argument("coop_id", help="identifiant du poulailler (= compte MQTT du Pi)")
    parser.add_argument(
        "--new-code",
        action="store_true",
        help="nouveau code pour un Pi déjà enregistré mais pas encore ajouté à un compte",
    )
    args = parser.parse_args()
    try:
        code = asyncio.run(run(args.coop_id, args.new_code))
    except NewCoopError as exc:
        print(f"Erreur : {exc}", file=sys.stderr)
        sys.exit(1)
    if args.new_code:
        print(f"Nouveau code pour le poulailler {args.coop_id} (l'ancien ne marche plus).")
    else:
        print(f"Poulailler {args.coop_id} enregistré.")
    print(f"Code d'appairage : {code}")
    print("À écrire sur l'étiquette du boîtier : il ne sera plus affiché.")


if __name__ == "__main__":
    main()
