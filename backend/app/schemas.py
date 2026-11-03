"""Schémas Pydantic exposés par l'API (entrées validées, sorties documentées dans OpenAPI)."""

import uuid
from datetime import datetime, time
from enum import StrEnum
from typing import Annotated, Self

from pydantic import AfterValidator, BaseModel, ConfigDict, Field, model_validator

from app.models import AlertType, DoorState, EventType, Severity, TriggerSource
from app.timeutils import ensure_utc

UtcDatetime = Annotated[datetime, AfterValidator(ensure_utc)]


class ORMModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class CoopRead(ORMModel):
    id: str
    name: str
    total_hens: int


class CoopStatus(BaseModel):
    """État complet actuel d'un poulailler (`GET /coops/{id}/status`)."""

    coop_id: str
    name: str
    door_state: DoorState
    inside_count: int
    total_hens: int
    outside_count: int
    battery: int | None = Field(description="Niveau de batterie en %")
    auto_close_time: time | None
    last_seen_at: UtcDatetime | None = Field(description="Dernier message reçu du Raspberry Pi")


class EventRead(ORMModel):
    id: int
    event_type: EventType
    trigger_source: TriggerSource | None
    inside_count_after: int | None
    ai_confidence: float | None
    occurred_at: UtcDatetime


class AlertRead(ORMModel):
    id: int
    alert_type: AlertType
    severity: Severity
    ai_confidence: float | None
    image_url: str | None
    acknowledged: bool
    created_at: UtcDatetime


class CommandAction(StrEnum):
    OPEN = "OPEN"
    CLOSE = "CLOSE"
    CALIBRATE = "CALIBRATE"


class CommandRequest(BaseModel):
    """Commande manuelle envoyée au poulailler."""

    action: CommandAction
    inside_count: int | None = Field(
        default=None, ge=0, description="Obligatoire pour CALIBRATE : nombre réel de poules dedans"
    )

    @model_validator(mode="after")
    def check_inside_count(self) -> Self:
        if self.action is CommandAction.CALIBRATE and self.inside_count is None:
            raise ValueError("inside_count est obligatoire pour l'action CALIBRATE")
        if self.action is not CommandAction.CALIBRATE and self.inside_count is not None:
            raise ValueError("inside_count n'est accepté que pour l'action CALIBRATE")
        return self


class CommandAccepted(BaseModel):
    command_id: uuid.UUID
    coop_id: str
    action: CommandAction
    inside_count: int | None
    issued_at: UtcDatetime
