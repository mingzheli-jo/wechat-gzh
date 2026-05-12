"""add default_thumb_media_id to accounts

Revision ID: 83497ef013ba
Revises: aa119e18bb5f
Create Date: 2026-05-12 15:05:05.723168

"""
from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = '83497ef013ba'
down_revision: str | Sequence[str] | None = 'aa119e18bb5f'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "accounts",
        sa.Column("default_thumb_media_id", sa.String(length=200), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("accounts", "default_thumb_media_id")
