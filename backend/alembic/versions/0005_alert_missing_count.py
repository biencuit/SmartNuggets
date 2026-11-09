"""Ajoute alerts.missing_count (nombre de poules encore dehors, alerte MISSING_HEN).

Revision ID: 0005
Revises: 0004
Create Date: 2026-11-09

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0005"
down_revision: str | None = "0004"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("alerts") as batch_op:
        batch_op.add_column(sa.Column("missing_count", sa.Integer(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("alerts") as batch_op:
        batch_op.drop_column("missing_count")
