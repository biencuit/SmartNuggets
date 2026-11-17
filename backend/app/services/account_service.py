"""Données personnelles de l'éleveur : export et suppression du compte (RGPD, #64).

- Export (droit à la portabilité, art. 20) : le compte, ses poulaillers, leurs passages et
  leurs alertes, en JSON. Les photos sont données par leur adresse dans l'API.
- Suppression (droit à l'effacement, art. 17) : tout ce qui appartient au compte, photos
  comprises. Les suppressions sont faites une par une, sans compter sur les ON DELETE
  CASCADE : SQLite ne les applique pas. Le Raspberry Pi est libéré : l'installateur peut lui
  donner un nouveau code d'appairage (`scripts/new-coop.sh <id> --code-only`).
"""

import asyncio
import shutil
from pathlib import Path
from typing import Any

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import Settings
from app.errors import UnauthorizedError
from app.models import Alert, Coop, Device, Event, User
from app.schemas import AlertRead, EventRead, UserRead
from app.security import verify_password
from app.timeutils import ensure_utc, utcnow


class AccountService:
    def __init__(self, session: AsyncSession, settings: Settings) -> None:
        self.session = session
        self.settings = settings

    async def export(self, user: User) -> dict[str, Any]:
        coops = []
        for coop in await self._coops_of(user):
            events = await self.session.scalars(
                select(Event).where(Event.coop_id == coop.id).order_by(Event.occurred_at)
            )
            alerts = await self.session.scalars(
                select(Alert).where(Alert.coop_id == coop.id).order_by(Alert.created_at)
            )
            coops.append(
                {
                    "id": coop.id,
                    "name": coop.name,
                    "total_hens": coop.total_hens,
                    "inside_count": coop.inside_count,
                    "door_state": coop.door_state,
                    "auto_close_time": (
                        coop.auto_close_time.isoformat() if coop.auto_close_time else None
                    ),
                    "battery_level": coop.battery_level,
                    "last_seen_at": (
                        ensure_utc(coop.last_seen_at).isoformat() if coop.last_seen_at else None
                    ),
                    "events": [EventRead.model_validate(e).model_dump(mode="json") for e in events],
                    "alerts": [AlertRead.model_validate(a).model_dump(mode="json") for a in alerts],
                }
            )
        account = UserRead.model_validate(user).model_dump(mode="json")
        return {"exported_at": utcnow().isoformat(), "account": account, "coops": coops}

    async def delete(self, user: User, password: str) -> None:
        if not verify_password(user.password_hash, password):
            raise UnauthorizedError("Mot de passe incorrect")
        folders = []
        for coop in await self._coops_of(user):
            await self.session.execute(delete(Event).where(Event.coop_id == coop.id))
            await self.session.execute(delete(Alert).where(Alert.coop_id == coop.id))
            device = await self.session.get(Device, coop.id)
            if device is not None:
                device.claimed_at = None  # le Pi peut être ajouté à un autre compte
            await self.session.delete(coop)
            folders.append(Path(self.settings.media_dir) / coop.id)
        await self.session.flush()  # poulaillers supprimés avant le compte (clé étrangère)
        await self.session.delete(user)
        await self.session.commit()
        # Les photos partent après le commit : si la base refuse, rien n'est perdu.
        for folder in folders:
            await asyncio.to_thread(shutil.rmtree, folder, True)  # True : dossier absent toléré

    async def _coops_of(self, user: User) -> list[Coop]:
        result = await self.session.scalars(
            select(Coop).where(Coop.owner_id == user.id).order_by(Coop.id)
        )
        return list(result)
