"""Ajouter un poulailler à son compte avec le code d'appairage du Raspberry Pi (#36)."""

import re

import pytest
from fastapi import FastAPI
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Coop, Device
from app.new_coop import NewCoopError, register_device
from app.security import CLAIM_CODE_ALPHABET, normalize_claim_code, verify_password

from .test_ownership import other_client

REFUSED = {"detail": "Identifiant ou code d'appairage incorrect"}
WRONG_CODE = "ABCD-EFGH-JKMN"


@pytest.fixture
async def code(session: AsyncSession) -> str:
    """Pi coop_02 enregistré par l'équipe, pas encore sur un compte : renvoie son code."""
    return await register_device(session, "coop_02")


def body(claim_code: str, coop_id: str = "coop_02") -> dict[str, object]:
    return {"id": coop_id, "claim_code": claim_code, "name": "Petit poulailler", "total_hens": 4}


async def test_ajout_avec_le_bon_code(client: AsyncClient, session: AsyncSession, code: str):
    response = await client.post("/api/v1/coops", json=body(code))
    assert response.status_code == 201
    assert response.json() == {"id": "coop_02", "name": "Petit poulailler", "total_hens": 4}

    status = (await client.get("/api/v1/coops/coop_02/status")).json()
    assert status["door_state"] == "CLOSED"
    assert status["outside_count"] == 4

    device = await session.get(Device, "coop_02")
    assert device is not None
    await session.refresh(device)
    assert device.claimed_at is not None
    assert device.claim_code_hash is None  # le code ne sert plus à rien


async def test_code_en_minuscules_et_sans_tirets(client: AsyncClient, code: str) -> None:
    response = await client.post("/api/v1/coops", json=body(code.replace("-", "").lower()))
    assert response.status_code == 201


async def test_meme_refus_si_code_faux_ou_identifiant_inconnu(
    client: AsyncClient, code: str
) -> None:
    for payload in (body(WRONG_CODE), body(code, coop_id="coop_99")):
        response = await client.post("/api/v1/coops", json=payload)
        assert response.status_code == 403
        assert response.json() == REFUSED
    assert (await client.get("/api/v1/coops")).json() == []


async def test_le_code_ne_marche_qu_une_fois(
    app: FastAPI, client: AsyncClient, session: AsyncSession, code: str
) -> None:
    assert (await client.post("/api/v1/coops", json=body(code))).status_code == 201

    async with await other_client(app, session) as voisin:
        response = await voisin.post("/api/v1/coops", json=body(code))
        assert response.status_code == 403
        assert response.json() == REFUSED
        assert (await voisin.get("/api/v1/coops")).json() == []
        response = await voisin.post("/api/v1/coops/coop_02/command", json={"action": "OPEN"})
        assert response.status_code == 404
    assert app.state.command_publisher.sent == []

    response = await client.post("/api/v1/coops", json=body(code))
    assert response.status_code == 403


async def test_poulailler_deja_sur_un_compte(client: AsyncClient, coop: Coop) -> None:
    """coop_01 est enregistré sans code, comme les poulaillers d'avant la migration 0004."""
    response = await client.post("/api/v1/coops", json=body(WRONG_CODE, coop_id="coop_01"))
    assert response.status_code == 403
    assert response.json() == REFUSED


async def test_identifiant_ou_code_mal_forme(client: AsyncClient) -> None:
    response = await client.post("/api/v1/coops", json=body(WRONG_CODE, coop_id="../etc"))
    assert response.status_code == 422
    response = await client.post("/api/v1/coops", json=body("court"))
    assert response.status_code == 422


async def test_ajout_sans_etre_connecte(anon_client: AsyncClient, code: str) -> None:
    response = await anon_client.post("/api/v1/coops", json=body(code))
    assert response.status_code == 401


# ---------------------------------------------------------------- python -m app.new_coop


async def test_new_coop_ne_garde_que_le_hash(session: AsyncSession) -> None:
    code = await register_device(session, "coop_03")

    assert re.fullmatch(r"[A-Z0-9]{4}-[A-Z0-9]{4}-[A-Z0-9]{4}", code)
    assert set(normalize_claim_code(code)) <= set(CLAIM_CODE_ALPHABET)
    device = await session.get(Device, "coop_03")
    assert device is not None and device.claim_code_hash is not None
    assert code not in device.claim_code_hash
    assert verify_password(device.claim_code_hash, normalize_claim_code(code))
    assert device.claimed_at is None


async def test_new_coop_nouveau_code_et_pi_deja_sur_un_compte(
    client: AsyncClient, session: AsyncSession, code: str
) -> None:
    with pytest.raises(NewCoopError, match="--new-code"):
        await register_device(session, "coop_02")

    new_code = await register_device(session, "coop_02", new_code=True)
    assert (await client.post("/api/v1/coops", json=body(code))).status_code == 403
    assert (await client.post("/api/v1/coops", json=body(new_code))).status_code == 201

    session.expire_all()
    with pytest.raises(NewCoopError, match="déjà ajouté à un compte"):
        await register_device(session, "coop_02", new_code=True)


async def test_new_coop_identifiant_invalide(session: AsyncSession) -> None:
    with pytest.raises(NewCoopError):
        await register_device(session, "../etc")
