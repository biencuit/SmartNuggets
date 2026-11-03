"""Ajoute coops.camera_ok (état de la caméra signalé par le Raspberry Pi).

Revision ID: 0003
Revises: 0002
Create Date: 2026-11-03

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0003"
down_revision: str | None = "0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("coops") as batch_op:
        batch_op.add_column(sa.Column("camera_ok", sa.Boolean(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("coops") as batch_op:
        batch_op.drop_column("camera_ok")
