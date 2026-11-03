"""Schéma initial : users, coops, events, alerts (wiki 8.C, sans lora_rssi).

Revision ID: 0001
Revises:
Create Date: 2026-11-03

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

BigIntPK = sa.BigInteger().with_variant(sa.Integer(), "sqlite")


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("email", sa.String(length=255), nullable=False),
        sa.Column("password_hash", sa.String(length=255), nullable=False),
        sa.Column("telegram_chat_id", sa.String(length=64), nullable=True),
        sa.Column("push_enabled", sa.Boolean(), server_default=sa.false(), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_users")),
        sa.UniqueConstraint("email", name=op.f("uq_users_email")),
    )
    op.create_table(
        "coops",
        sa.Column("id", sa.String(length=64), nullable=False),
        sa.Column("owner_id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("total_hens", sa.Integer(), server_default="0", nullable=False),
        sa.Column("inside_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column("door_state", sa.String(length=16), server_default="CLOSED", nullable=False),
        sa.Column("auto_close_time", sa.Time(), nullable=True),
        sa.Column("battery_level", sa.Integer(), nullable=True),
        sa.Column("last_seen_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(
            ["owner_id"],
            ["users.id"],
            name=op.f("fk_coops_owner_id_users"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_coops")),
    )
    op.create_index(op.f("ix_coops_owner_id"), "coops", ["owner_id"])

    op.create_table(
        "events",
        sa.Column("id", BigIntPK, autoincrement=True, nullable=False),
        sa.Column("coop_id", sa.String(length=64), nullable=False),
        sa.Column("event_type", sa.String(length=32), nullable=False),
        sa.Column("trigger_source", sa.String(length=32), nullable=True),
        sa.Column("inside_count_after", sa.Integer(), nullable=True),
        sa.Column("ai_confidence", sa.Float(), nullable=True),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["coop_id"], ["coops.id"], name=op.f("fk_events_coop_id_coops"), ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_events")),
    )
    op.create_index("ix_events_coop_id_occurred_at", "events", ["coop_id", "occurred_at"])

    op.create_table(
        "alerts",
        sa.Column("id", BigIntPK, autoincrement=True, nullable=False),
        sa.Column("coop_id", sa.String(length=64), nullable=False),
        sa.Column("alert_type", sa.String(length=32), nullable=False),
        sa.Column("severity", sa.String(length=16), nullable=False),
        sa.Column("ai_confidence", sa.Float(), nullable=True),
        sa.Column("image_url", sa.String(length=255), nullable=True),
        sa.Column("acknowledged", sa.Boolean(), server_default=sa.false(), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.ForeignKeyConstraint(
            ["coop_id"], ["coops.id"], name=op.f("fk_alerts_coop_id_coops"), ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_alerts")),
    )
    op.create_index("ix_alerts_coop_id_created_at", "alerts", ["coop_id", "created_at"])


def downgrade() -> None:
    op.drop_index("ix_alerts_coop_id_created_at", table_name="alerts")
    op.drop_table("alerts")
    op.drop_index("ix_events_coop_id_occurred_at", table_name="events")
    op.drop_table("events")
    op.drop_index(op.f("ix_coops_owner_id"), table_name="coops")
    op.drop_table("coops")
    op.drop_table("users")
