"""Format des messages JSON envoyés par le Raspberry Pi."""

from typing import Literal

from pydantic import BaseModel, Field

from app.models import AlertType, DoorState, EventType, Severity, TriggerSource
from app.schemas import UtcDatetime


class EventPayload(BaseModel):
    event_type: EventType
    trigger_source: TriggerSource | None = None
    inside_count_after: int | None = Field(default=None, ge=0)
    ai_confidence: float | None = Field(default=None, ge=0, le=1)
    occurred_at: UtcDatetime


class TelemetryMessage(BaseModel):
    """Envoyé à chaque changement d'état et périodiquement (battement de cœur)."""

    sent_at: UtcDatetime
    door_state: DoorState | None = None
    inside_count: int | None = Field(default=None, ge=0)
    battery_level: int | None = Field(default=None, ge=0, le=100)
    event: EventPayload | None = None


class AlertMessage(BaseModel):
    sent_at: UtcDatetime
    alert_type: AlertType
    severity: Severity
    ai_confidence: float | None = Field(default=None, ge=0, le=1)
    image_base64: str | None = None
    image_format: Literal["jpeg", "webp"] = "jpeg"


def parse_status(payload: bytes) -> bool | None:
    """Topic status : "online" / "offline" (texte brut). None si la valeur est inconnue."""
    value = payload.decode("utf-8", errors="replace").strip().lower()
    if value == "online":
        return True
    if value == "offline":
        return False
    return None
