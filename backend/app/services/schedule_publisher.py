"""Transmission du planning hebdomadaire au Raspberry Pi (#70).

Contrairement aux commandes (OPEN/CLOSE/CALIBRATE, ponctuelles, avec une fenêtre de
validité de 60 s), le planning est de la configuration persistante : il part en message
MQTT *retained*, gardé par le broker et livré au Pi dès qu'il se (re)connecte, même s'il
était hors ligne au moment de l'enregistrement.
"""

import logging
from datetime import time
from typing import Protocol

logger = logging.getLogger(__name__)

ScheduleDays = list[tuple[int, time, time]]


class SchedulePublisher(Protocol):
    async def publish_schedule(self, coop_id: str, days: ScheduleDays) -> None: ...


class InMemorySchedulePublisher:
    """Garde le dernier planning envoyé en mémoire (développement sans broker, tests)."""

    def __init__(self) -> None:
        self.sent: dict[str, ScheduleDays] = {}

    async def publish_schedule(self, coop_id: str, days: ScheduleDays) -> None:
        logger.info("Planning de %s (non transmis : pas de broker)", coop_id)
        self.sent[coop_id] = days
