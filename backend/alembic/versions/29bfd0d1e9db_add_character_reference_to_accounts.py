"""add character_reference to accounts

Revision ID: 29bfd0d1e9db
Revises: 83497ef013ba
Create Date: 2026-05-13 09:49:44.216072

"""
from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = '29bfd0d1e9db'
down_revision: str | Sequence[str] | None = '83497ef013ba'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "accounts",
        sa.Column("character_reference_path", sa.String(length=500), nullable=True),
    )
    op.add_column(
        "accounts",
        sa.Column("character_reference_updated_at", sa.DateTime(timezone=True), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("accounts", "character_reference_updated_at")
    op.drop_column("accounts", "character_reference_path")
