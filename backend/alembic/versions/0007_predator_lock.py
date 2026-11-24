"""Ajoute coops.predator_lock_s : durée de verrouillage de la porte après un prédateur.

Réglable dans l'application (carte Planning), transmis au Raspberry Pi avec le planning.

Revision ID: 0007
Revises: 0006
Create Date: 2026-11-24

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0007"
down_revision: str | None = "0006"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("coops") as batch_op:
        batch_op.add_column(
            sa.Column("predator_lock_s", sa.Integer(), nullable=False, server_default="300")
        )


def downgrade() -> None:
    with op.batch_alter_table("coops") as batch_op:
        batch_op.drop_column("predator_lock_s")
