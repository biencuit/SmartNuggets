"""Notifications externes (Telegram) quand une alerte survient (#68).

Best-effort : un envoi qui échoue (jeton absent, chat_id invalide, API Telegram en panne)
est journalisé et n'empêche jamais la création ou l'affichage de l'alerte dans l'application.
"""

import logging
import uuid

import httpx
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Alert, Severity, User
from app.repositories import UserRepository

logger = logging.getLogger(__name__)

TELEGRAM_API_URL = "https://api.telegram.org/bot{token}/sendMessage"

ALERT_LABELS = {
    "PREDATOR_DETECTED": "Prédateur détecté",
    "MISSING_HEN": "Poule manquante à la fermeture",
    "DOOR_BLOCKED": "Porte bloquée",
    "LOW_BATTERY": "Batterie faible",
    "DEVICE_OFFLINE": "Poulailler hors ligne",
}


class NotificationService:
    def __init__(self, session: AsyncSession, telegram_bot_token: str | None) -> None:
        self.session = session
        self.telegram_bot_token = telegram_bot_token
        self.users = UserRepository(session)

    async def notify_alert(self, owner_id: uuid.UUID, alert: Alert) -> None:
        if not self.telegram_bot_token:
            return
        user = await self.users.get(owner_id)
        if user is None or not self._wants_notification(user, alert):
            return
        await self._send_telegram(user, alert)

    def _wants_notification(self, user: User, alert: Alert) -> bool:
        if not user.push_enabled or not user.telegram_chat_id:
            return False
        if user.notify_critical_only and alert.severity != Severity.CRITICAL:
            return False
        return True

    async def _send_telegram(self, user: User, alert: Alert) -> None:
        label = ALERT_LABELS.get(alert.alert_type, alert.alert_type)
        text = f"🐔 SmartNuggets ({alert.coop_id}) — {label}"
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                response = await client.post(
                    TELEGRAM_API_URL.format(token=self.telegram_bot_token),
                    json={"chat_id": user.telegram_chat_id, "text": text},
                )
                response.raise_for_status()
        except httpx.HTTPError:
            logger.warning(
                "Envoi Telegram échoué pour l'utilisateur %s (alerte %s)",
                user.id,
                alert.alert_type,
                exc_info=True,
            )
