"""Topics MQTT : smartnuggets/{coop_id}/{telemetry|alerts|status|commands}.

- telemetry (Pi -> serveur, QoS 1) : état de la porte, compteur, batterie, événement éventuel
- alerts    (Pi -> serveur, QoS 1) : prédateur détecté, porte bloquée... (+ photo)
- status    (Pi -> serveur, retenu) : "online" à la connexion, "offline" via le Last Will
- commands  (serveur -> Pi, QoS 1) : OPEN, CLOSE, CALIBRATE
"""

import re
from enum import StrEnum

ROOT = "smartnuggets"
COOP_ID_PATTERN = re.compile(r"^[A-Za-z0-9_-]{1,64}$")


class Channel(StrEnum):
    TELEMETRY = "telemetry"
    ALERTS = "alerts"
    STATUS = "status"
    COMMANDS = "commands"


INCOMING = (Channel.TELEMETRY, Channel.ALERTS, Channel.STATUS)


def topic(coop_id: str, channel: Channel) -> str:
    return f"{ROOT}/{coop_id}/{channel}"


def subscription(channel: Channel) -> str:
    return f"{ROOT}/+/{channel}"


def parse(value: str) -> tuple[str, Channel] | None:
    """Renvoie (coop_id, canal) ou None si le topic n'est pas un topic SmartNuggets."""
    parts = value.split("/")
    if len(parts) != 3 or parts[0] != ROOT or not COOP_ID_PATTERN.fullmatch(parts[1]):
        return None
    try:
        return parts[1], Channel(parts[2])
    except ValueError:
        return None
