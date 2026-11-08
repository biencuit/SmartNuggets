from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Alert, AlertType, Coop, Severity, User
from app.security import hash_password

from .conftest import token_for


async def other_client(app, session: AsyncSession) -> AsyncClient:
    voisin = User(email="voisin@example.com", password_hash=hash_password("voisin-123"))
    session.add(voisin)
    await session.commit()
    return AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
        headers={"Authorization": f"Bearer {token_for(voisin)}"},
    )


async def test_un_eleveur_ne_voit_pas_le_poulailler_d_un_autre(
    app, session: AsyncSession, coop: Coop
) -> None:
    alert = Alert(coop_id=coop.id, alert_type=AlertType.LOW_BATTERY, severity=Severity.WARNING)
    session.add(alert)
    await session.commit()

    async with await other_client(app, session) as voisin:
        assert (await voisin.get("/api/v1/coops")).json() == []
        for method, url in [
            ("GET", "/api/v1/coops/coop_01/status"),
            ("GET", "/api/v1/coops/coop_01/events"),
            ("GET", "/api/v1/coops/coop_01/alerts"),
            ("POST", f"/api/v1/coops/coop_01/alerts/{alert.id}/ack"),
            ("GET", f"/api/v1/coops/coop_01/alerts/{alert.id}/image"),
            ("GET", "/api/v1/coops/coop_01/stream"),
        ]:
            response = await voisin.request(method, url)
            assert response.status_code == 404, url

        response = await voisin.post("/api/v1/coops/coop_01/command", json={"action": "OPEN"})
        assert response.status_code == 404
    assert app.state.command_publisher.sent == []
