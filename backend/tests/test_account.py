"""Données personnelles : export et suppression du compte (RGPD, #64)."""

from datetime import timedelta
from pathlib import Path

import pytest
from httpx import AsyncClient
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import Settings
from app.models import Alert, AlertType, Coop, Device, Event, EventType, Severity, User
from app.new_coop import NewCoopError, register_device
from app.security import hash_password
from app.timeutils import utcnow
from tests.conftest import OWNER_PASSWORD, token_for

EXPORT = "/api/v1/auth/me/export"
ME = "/api/v1/auth/me"
COOP = "coop_01"  # fixture `coop` (ne pas relire coop.id après expire_all)


async def add_history(session: AsyncSession, coop_id: str) -> Alert:
    """Deux passages et une alerte avec photo pour ce poulailler."""
    now = utcnow()
    session.add_all(
        [
            Event(coop_id=coop_id, event_type=EventType.HEN_EXIT, occurred_at=now),
            Event(coop_id=coop_id, event_type=EventType.HEN_ENTRY, occurred_at=now),
        ]
    )
    alert = Alert(
        coop_id=coop_id,
        alert_type=AlertType.PREDATOR_DETECTED,
        severity=Severity.CRITICAL,
        created_at=now - timedelta(hours=1),
    )
    session.add(alert)
    await session.flush()
    alert.image_url = f"/api/v1/coops/{coop_id}/alerts/{alert.id}/image"
    await session.commit()
    return alert


def write_photo(settings: Settings, coop_id: str, alert_id: int) -> Path:
    path = Path(settings.media_dir) / coop_id / f"{alert_id}.jpeg"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(b"\xff\xd8\xff photo")
    return path


@pytest.fixture
async def neighbour(session: AsyncSession) -> User:
    """Un autre éleveur, avec son propre poulailler et son historique."""
    user = User(email="voisin@example.com", password_hash=hash_password("mot-de-passe-voisin"))
    session.add_all([user, Device(id="coop_09", claimed_at=utcnow())])
    await session.flush()
    session.add(Coop(id="coop_09", owner_id=user.id, name="Chez le voisin"))
    await session.commit()
    await add_history(session, "coop_09")
    return user


async def count(session: AsyncSession, model, **where) -> int:
    session.expire_all()
    query = select(func.count()).select_from(model)
    for column, value in where.items():
        query = query.where(getattr(model, column) == value)
    return (await session.execute(query)).scalar_one()


async def test_export_contient_mes_donnees_et_seulement_les_miennes(
    client: AsyncClient, session: AsyncSession, coop: Coop, neighbour: User
) -> None:
    alert = await add_history(session, COOP)

    response = await client.get(EXPORT)

    assert response.status_code == 200
    assert "attachment" in response.headers["content-disposition"]
    data = response.json()
    assert data["account"]["email"] == "marc@example.com"
    assert [c["id"] for c in data["coops"]] == ["coop_01"]  # pas le poulailler du voisin
    mine = data["coops"][0]
    assert mine["name"] == "Poulailler de Marc" and mine["auto_close_time"] == "21:30:00"
    assert sorted(e["event_type"] for e in mine["events"]) == ["HEN_ENTRY", "HEN_EXIT"]
    assert mine["alerts"][0]["image_url"] == alert.image_url
    assert "password_hash" not in str(data)


async def test_export_et_suppression_exigent_une_connexion(anon_client: AsyncClient) -> None:
    assert (await anon_client.get(EXPORT)).status_code == 401
    assert (
        await anon_client.request("DELETE", ME, json={"password": OWNER_PASSWORD})
    ).status_code == 401


async def test_suppression_refusee_avec_un_mauvais_mot_de_passe(
    client: AsyncClient, session: AsyncSession, settings: Settings, coop: Coop
) -> None:
    alert = await add_history(session, COOP)
    photo = write_photo(settings, COOP, alert.id)

    response = await client.request("DELETE", ME, json={"password": "pas-le-bon"})

    assert response.status_code == 401
    assert response.json()["detail"] == "Mot de passe incorrect"
    assert await count(session, User) == 1
    assert await count(session, Event, coop_id=COOP) == 2
    assert photo.is_file()


async def test_suppression_efface_tout_et_libere_le_raspberry_pi(
    client: AsyncClient,
    anon_client: AsyncClient,
    session: AsyncSession,
    settings: Settings,
    owner: User,
    coop: Coop,
    neighbour: User,
) -> None:
    alert = await add_history(session, COOP)
    photo = write_photo(settings, COOP, alert.id)
    with pytest.raises(NewCoopError):
        await register_device(session, COOP, new_code=True)  # Pi déjà sur un compte
    token, voisin = token_for(owner), token_for(neighbour)  # avant expire_all

    response = await client.request("DELETE", ME, json={"password": OWNER_PASSWORD})

    assert response.status_code == 204
    assert await count(session, User, email="marc@example.com") == 0
    assert await count(session, Coop, id=COOP) == 0
    assert await count(session, Event, coop_id=COOP) == 0
    assert await count(session, Alert, coop_id=COOP) == 0
    assert not photo.parent.exists()
    # L'ancien jeton ne sert plus à rien.
    gone = await anon_client.get(ME, headers={"Authorization": f"Bearer {token}"})
    assert gone.status_code == 401
    # Le voisin n'a rien perdu.
    assert await count(session, Coop, id="coop_09") == 1
    assert await count(session, Event, coop_id="coop_09") == 2
    # Le Pi est libre : l'installateur lui donne un nouveau code, un autre éleveur l'ajoute.
    code = await register_device(session, COOP, new_code=True)
    claimed = await anon_client.post(
        "/api/v1/coops",
        json={"id": COOP, "claim_code": code, "name": "Repris"},
        headers={"Authorization": f"Bearer {voisin}"},
    )
    assert claimed.status_code == 201


async def test_suppression_d_un_compte_sans_poulailler(
    client: AsyncClient, session: AsyncSession
) -> None:
    response = await client.request("DELETE", ME, json={"password": OWNER_PASSWORD})
    assert response.status_code == 204
    assert await count(session, User) == 0
