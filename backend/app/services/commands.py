"""Envoi des commandes manuelles (OPEN / CLOSE / CALIBRATE) vers le poulailler.

Le service ne connaît que l'interface `CommandPublisher` : l'implémentation en mémoire
sert au développement et aux tests, l'implémentation MQTT est branchée par l'application.
"""

import logging
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from typing import Protocol

from app.timeutils import utcnow

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class DoorCommand:
    coop_id: str
    action: str
    inside_count: int | None = None
    command_id: uuid.UUID = field(default_factory=uuid.uuid4)
    issued_at: datetime = field(default_factory=utcnow)

    def to_payload(self) -> dict[str, object]:
        return {
            "command_id": str(self.command_id),
            "action": self.action,
            "inside_count": self.inside_count,
            "issued_at": self.issued_at.isoformat(),
        }


class CommandPublisher(Protocol):
    async def publish(self, command: DoorCommand) -> None: ...


class InMemoryCommandPublisher:
    """Garde les commandes en mémoire (développement sans broker, tests)."""

    def __init__(self) -> None:
        self.sent: list[DoorCommand] = []

    async def publish(self, command: DoorCommand) -> None:
        logger.info(
            "Commande %s pour %s (non transmise : pas de broker)", command.action, command.coop_id
        )
        self.sent.append(command)
