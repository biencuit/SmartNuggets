"""Ajoute door_schedules : planning hebdomadaire de la porte (#70).

Revision ID: 0006
Revises: 0005
Create Date: 2026-11-17

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0006"
down_revision: str | None = "0005"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

BigIntPK = sa.BigInteger().with_variant(sa.Integer(), "sqlite")


def upgrade() -> None:
    op.create_table(
        "door_schedules",
        sa.Column("id", BigIntPK, primary_key=True, autoincrement=True),
        sa.Column(
            "coop_id",
            sa.String(length=64),
            sa.ForeignKey("coops.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("weekday", sa.Integer(), nullable=False),
        sa.Column("open_from", sa.Time(), nullable=False),
        sa.Column("close_at", sa.Time(), nullable=False),
        sa.UniqueConstraint("coop_id", "weekday", name="uq_door_schedules_coop_weekday"),
    )
    op.create_index("ix_door_schedules_coop_id", "door_schedules", ["coop_id"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_door_schedules_coop_id", table_name="door_schedules")
    op.drop_table("door_schedules")
