"""add image role to role enum

Revision ID: 4b31cd6708db
Revises: 54b57cb28235
Create Date: 2026-05-18 20:58:34.664548

"""
from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "4b31cd6708db"
down_revision: str | Sequence[str] | None = "54b57cb28235"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # PG 12+ allows ADD VALUE in a transaction when the new value is not
    # referenced in the same transaction. We only add the label here;
    # usage comes later through normal role_bindings inserts.
    op.execute("ALTER TYPE role ADD VALUE IF NOT EXISTS 'image'")


def downgrade() -> None:
    # PG does not support removing enum values. No-op.
    pass
