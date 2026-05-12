"""add regenerate count to drafts

Revision ID: aa119e18bb5f
Revises: b3a7f1c2e8d9
Create Date: 2026-05-11 23:40:29.414582

"""
from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = 'aa119e18bb5f'
down_revision: str | Sequence[str] | None = 'b3a7f1c2e8d9'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "drafts",
        sa.Column(
            "regenerate_count",
            sa.Integer(),
            nullable=False,
            server_default="0",
        ),
    )


def downgrade() -> None:
    op.drop_column("drafts", "regenerate_count")
