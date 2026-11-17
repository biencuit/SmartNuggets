"""Préférences de notification et envoi des alertes sur Telegram (#68)."""

import httpx
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Alert, AlertType, Coop, Severity, User
from app.services.notifications import NotificationService
from app.timeutils import utcnow

PREFS = "/api/v1/auth/me/notifications"


async def refreshed_user(session: AsyncSession, user_id) -> User:
    session.expire_all()
    return (await session.execute(select(User).where(User.id == user_id))).scalar_one()


async def test_preferences_par_defaut(client: AsyncClient) -> None:
    response = await client.get(PREFS)

    assert response.status_code == 200
    assert response.json() == {
        "push_enabled": False,
        "telegram_chat_id": None,
        "notify_critical_only": False,
    }


async def test_activer_les_notifications_telegram(
    client: AsyncClient, session: AsyncSession, owner: User
) -> None:
    response = await client.patch(
        PREFS,
        json={"push_enabled": True, "telegram_chat_id": "123456", "notify_critical_only": True},
    )

    assert response.status_code == 200
    assert response.json() == {
        "push_enabled": True,
        "telegram_chat_id": "123456",
        "notify_critical_only": True,
    }
    stored = await refreshed_user(session, owner.id)
    assert stored.push_enabled is True
    assert stored.telegram_chat_id == "123456"


async def test_desactiver_garde_l_identifiant_telegram_enregistre(
    client: AsyncClient, session: AsyncSession, owner: User
) -> None:
    await client.patch(PREFS, json={"push_enabled": True, "telegram_chat_id": "123456"})

    response = await client.patch(PREFS, json={"push_enabled": False, "telegram_chat_id": "123456"})

    assert response.status_code == 200
    assert response.json()["push_enabled"] is False
    assert response.json()["telegram_chat_id"] == "123456"


async def test_notifications_exigent_une_connexion(anon_client: AsyncClient) -> None:
    assert (await anon_client.get(PREFS)).status_code == 401
    assert (await anon_client.patch(PREFS, json={"push_enabled": True})).status_code == 401


def make_alert(coop_id: str, severity: Severity = Severity.WARNING) -> Alert:
    return Alert(
        coop_id=coop_id,
        alert_type=AlertType.LOW_BATTERY,
        severity=severity,
        created_at=utcnow(),
    )


class RecordingTransport(httpx.MockTransport):
    """Transport Telegram factice : garde les requêtes envoyées, répond 200 par défaut."""

    def __init__(self, status_code: int = 200) -> None:
        self.requests: list[httpx.Request] = []
        super().__init__(lambda request: self._handle(request, status_code))

    def _handle(self, request: httpx.Request, status_code: int) -> httpx.Response:
        self.requests.append(request)
        return httpx.Response(status_code)


async def test_envoie_sur_telegram_si_actif(session: AsyncSession, owner: User, coop: Coop) -> None:
    owner.push_enabled = True
    owner.telegram_chat_id = "123456"
    await session.commit()
    transport = RecordingTransport()
    service = NotificationService(session, "fake-token", transport=transport)

    await service.notify_alert(owner.id, make_alert(coop.id))

    assert len(transport.requests) == 1
    body = transport.requests[0].content
    assert b"123456" in body


async def test_rien_envoye_si_les_notifications_sont_desactivees(
    session: AsyncSession, owner: User, coop: Coop
) -> None:
    owner.push_enabled = False
    owner.telegram_chat_id = "123456"
    await session.commit()
    transport = RecordingTransport()
    service = NotificationService(session, "fake-token", transport=transport)

    await service.notify_alert(owner.id, make_alert(coop.id))

    assert transport.requests == []


async def test_rien_envoye_sans_jeton_telegram_configure(
    session: AsyncSession, owner: User, coop: Coop
) -> None:
    owner.push_enabled = True
    owner.telegram_chat_id = "123456"
    await session.commit()
    transport = RecordingTransport()
    service = NotificationService(session, None, transport=transport)

    await service.notify_alert(owner.id, make_alert(coop.id))

    assert transport.requests == []


async def test_uniquement_les_alertes_critiques_si_demande(
    session: AsyncSession, owner: User, coop: Coop
) -> None:
    owner.push_enabled = True
    owner.telegram_chat_id = "123456"
    owner.notify_critical_only = True
    await session.commit()
    transport = RecordingTransport()
    service = NotificationService(session, "fake-token", transport=transport)

    await service.notify_alert(owner.id, make_alert(coop.id, Severity.WARNING))
    assert transport.requests == []

    await service.notify_alert(owner.id, make_alert(coop.id, Severity.CRITICAL))
    assert len(transport.requests) == 1


async def test_echec_d_envoi_ne_leve_pas_d_exception(
    session: AsyncSession, owner: User, coop: Coop
) -> None:
    owner.push_enabled = True
    owner.telegram_chat_id = "123456"
    await session.commit()
    transport = RecordingTransport(status_code=500)
    service = NotificationService(session, "fake-token", transport=transport)

    await service.notify_alert(owner.id, make_alert(coop.id))  # ne doit pas lever

    assert len(transport.requests) == 1
