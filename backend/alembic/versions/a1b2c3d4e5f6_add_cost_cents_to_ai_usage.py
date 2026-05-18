"""add cost_cents to ai_usage

Revision ID: a1b2c3d4e5f6
Revises: 6cc8d75955ec
Create Date: 2026-05-18 10:00:00.000000

"""
from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = 'a1b2c3d4e5f6'
down_revision: str | Sequence[str] | None = '6cc8d75955ec'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "ai_usage",
        sa.Column("cost_cents", sa.Integer(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("ai_usage", "cost_cents")
