"""Modèles de la base de données (voir le schéma du wiki, page 8.C).

Les valeurs « énumérées » sont stockées en VARCHAR : ajouter une valeur ne demande
pas de migration. La validation se fait côté Python (enums ci-dessous + schémas Pydantic).
"""

import uuid
from datetime import datetime, time
from enum import StrEnum

from sqlalchemy import (
    BigInteger,
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Time,
    Uuid,
    false,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base

# BIGSERIAL sous PostgreSQL ; SQLite n'auto-incrémente que les colonnes INTEGER.
BigIntPK = BigInteger().with_variant(Integer(), "sqlite")


class DoorState(StrEnum):
    OPEN = "OPEN"
    CLOSED = "CLOSED"
    OPENING = "OPENING"
    CLOSING = "CLOSING"
    ERROR = "ERROR"


class EventType(StrEnum):
    HEN_ENTRY = "HEN_ENTRY"
    HEN_EXIT = "HEN_EXIT"
    DOOR_OPEN = "DOOR_OPEN"
    DOOR_CLOSE = "DOOR_CLOSE"
    OBSTACLE = "OBSTACLE"


class TriggerSource(StrEnum):
    AI_AUTO = "AI_AUTO"
    MANUAL_APP = "MANUAL_APP"
    SCHEDULE = "SCHEDULE"
    FAILSAFE = "FAILSAFE"


class AlertType(StrEnum):
    PREDATOR_DETECTED = "PREDATOR_DETECTED"
    MISSING_HEN = "MISSING_HEN"
    DOOR_BLOCKED = "DOOR_BLOCKED"
    LOW_BATTERY = "LOW_BATTERY"
    DEVICE_OFFLINE = "DEVICE_OFFLINE"


class Severity(StrEnum):
    WARNING = "WARNING"
    CRITICAL = "CRITICAL"


class User(Base):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    email: Mapped[str] = mapped_column(String(255), unique=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    telegram_chat_id: Mapped[str | None] = mapped_column(String(64))
    push_enabled: Mapped[bool] = mapped_column(Boolean, default=False, server_default=false())
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    coops: Mapped[list["Coop"]] = relationship(back_populates="owner")


class Coop(Base):
    __tablename__ = "coops"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)  # ex. "coop_01"
    owner_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    name: Mapped[str] = mapped_column(String(100))
    total_hens: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    inside_count: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    door_state: Mapped[str] = mapped_column(
        String(16), default=DoorState.CLOSED, server_default=DoorState.CLOSED
    )
    auto_close_time: Mapped[time | None] = mapped_column(Time)
    battery_level: Mapped[int | None] = mapped_column(Integer)
    last_seen_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    # Connexion MQTT du Raspberry Pi (topic status, alimenté par le Last Will).
    is_online: Mapped[bool] = mapped_column(Boolean, default=False, server_default=false())
    # État de la caméra signalé par le Pi (None : jamais signalé).
    camera_ok: Mapped[bool | None] = mapped_column(Boolean)

    owner: Mapped[User] = relationship(back_populates="coops")


class Event(Base):
    __tablename__ = "events"
    __table_args__ = (Index("ix_events_coop_id_occurred_at", "coop_id", "occurred_at"),)

    id: Mapped[int] = mapped_column(BigIntPK, primary_key=True, autoincrement=True)
    coop_id: Mapped[str] = mapped_column(ForeignKey("coops.id", ondelete="CASCADE"))
    event_type: Mapped[str] = mapped_column(String(32))
    trigger_source: Mapped[str | None] = mapped_column(String(32))
    inside_count_after: Mapped[int | None] = mapped_column(Integer)
    ai_confidence: Mapped[float | None] = mapped_column(Float)
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))  # horloge du Pi


class Alert(Base):
    __tablename__ = "alerts"
    __table_args__ = (Index("ix_alerts_coop_id_created_at", "coop_id", "created_at"),)

    id: Mapped[int] = mapped_column(BigIntPK, primary_key=True, autoincrement=True)
    coop_id: Mapped[str] = mapped_column(ForeignKey("coops.id", ondelete="CASCADE"))
    alert_type: Mapped[str] = mapped_column(String(32))
    severity: Mapped[str] = mapped_column(String(16))
    ai_confidence: Mapped[float | None] = mapped_column(Float)
    image_url: Mapped[str | None] = mapped_column(String(255))
    acknowledged: Mapped[bool] = mapped_column(Boolean, default=False, server_default=false())
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
