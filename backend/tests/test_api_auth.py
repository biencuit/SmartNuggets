from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Coop, User

from .conftest import OWNER_PASSWORD, token_for


async def login(client: AsyncClient, email: str, password: str):
    return await client.post("/api/v1/auth/login", data={"username": email, "password": password})


async def test_inscription_puis_connexion(anon_client: AsyncClient) -> None:
    response = await anon_client.post(
        "/api/v1/auth/register", json={"email": "Marc@Example.com", "password": "poulailler42"}
    )
    assert response.status_code == 201
    body = response.json()
    assert body["email"] == "marc@example.com"
    assert "password" not in body and "password_hash" not in body

    response = await login(anon_client, "marc@example.com", "poulailler42")
    assert response.status_code == 200
    token = response.json()["access_token"]
    assert response.json()["token_type"] == "bearer"

    response = await anon_client.get(
        "/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"}
    )
    assert response.json()["email"] == "marc@example.com"


async def test_inscription_email_deja_utilise(anon_client: AsyncClient, owner: User) -> None:
    response = await anon_client.post(
        "/api/v1/auth/register", json={"email": "MARC@example.com", "password": "poulailler42"}
    )
    assert response.status_code == 409


async def test_inscription_donnees_invalides(anon_client: AsyncClient) -> None:
    for payload in (
        {"email": "pas-un-email", "password": "poulailler42"},
        {"email": "marc@example.com", "password": "court"},
    ):
        response = await anon_client.post("/api/v1/auth/register", json=payload)
        assert response.status_code == 422


async def test_connexion_refusee(anon_client: AsyncClient, owner: User) -> None:
    wrong_password = await login(anon_client, "marc@example.com", "renard")
    unknown_email = await login(anon_client, "inconnu@example.com", OWNER_PASSWORD)

    for response in (wrong_password, unknown_email):
        assert response.status_code == 401
        assert response.json()["detail"] == "Email ou mot de passe incorrect"
        assert response.headers["www-authenticate"] == "Bearer"


async def test_connexion_insensible_a_la_casse_de_l_email(
    anon_client: AsyncClient, owner: User
) -> None:
    response = await login(anon_client, "MARC@EXAMPLE.COM", OWNER_PASSWORD)
    assert response.status_code == 200


async def test_routes_protegees(anon_client: AsyncClient, coop: Coop) -> None:
    for method, url in [
        ("GET", "/api/v1/auth/me"),
        ("GET", "/api/v1/coops"),
        ("POST", "/api/v1/coops"),
        ("GET", "/api/v1/coops/coop_01/status"),
        ("GET", "/api/v1/coops/coop_01/events"),
        ("GET", "/api/v1/coops/coop_01/alerts"),
        ("POST", "/api/v1/coops/coop_01/command"),
        ("GET", "/api/v1/coops/coop_01/stream"),
    ]:
        response = await anon_client.request(method, url)
        assert response.status_code == 401, url

    response = await anon_client.get(
        "/api/v1/coops", headers={"Authorization": "Bearer jeton-bidon"}
    )
    assert response.status_code == 401


async def test_jeton_d_un_compte_supprime(anon_client: AsyncClient, session: AsyncSession) -> None:
    ghost = User(email="ghost@example.com", password_hash="!")
    session.add(ghost)
    await session.commit()
    token = token_for(ghost)
    await session.delete(ghost)
    await session.commit()

    response = await anon_client.get(
        "/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"}
    )
    assert response.status_code == 401


async def test_jeton_en_parametre_uniquement_pour_flux_et_photos(
    anon_client: AsyncClient, owner: User, coop: Coop
) -> None:
    token = token_for(owner)
    response = await anon_client.get(f"/api/v1/coops/coop_01/status?token={token}")
    assert response.status_code == 401

    response = await anon_client.get(f"/api/v1/coops/coop_01/alerts/1/image?token={token}")
    assert response.status_code == 404  # authentifié, mais l'alerte n'existe pas
