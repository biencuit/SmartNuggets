"""Ajoute la table devices (Raspberry Pi enregistrés et leur code d'appairage).

Les poulaillers qui existent déjà sont considérés comme déjà ajoutés à un compte : leur Pi
est enregistré sans code, on ne peut donc plus le réclamer.

Revision ID: 0004
Revises: 0003
Create Date: 2026-11-08

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0004"
down_revision: str | None = "0003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "devices",
        sa.Column("id", sa.String(length=64), nullable=False),
        sa.Column("claim_code_hash", sa.String(length=255), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column("claimed_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_devices")),
    )
    op.execute("INSERT INTO devices (id, claimed_at) SELECT id, CURRENT_TIMESTAMP FROM coops")
    with op.batch_alter_table("coops") as batch_op:
        batch_op.create_foreign_key(
            op.f("fk_coops_id_devices"), "devices", ["id"], ["id"], ondelete="CASCADE"
        )


def downgrade() -> None:
    with op.batch_alter_table("coops") as batch_op:
        batch_op.drop_constraint(op.f("fk_coops_id_devices"), type_="foreignkey")
    op.drop_table("devices")
