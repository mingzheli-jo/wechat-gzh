"""add performance indexes

Revision ID: b3a7f1c2e8d9
Revises: d04b636b2aab
Create Date: 2026-05-06 14:30:00.000000

Adds three indexes to keep list/grouping queries fast as data grows:

  ix_library_items_created_at
      Library list orders by created_at DESC (default newest-first).
      PG can use an ASC index in reverse, so a plain b-tree on
      created_at suffices.

  ix_drafts_status_created_at
      Drafts paginated list filters by status (group→IN(...)) and
      orders by created_at DESC. Composite (status, created_at) lets
      PG do an index scan per status value and feed results into the
      sort already pre-ordered.

  ix_drafts_library_item_id_active  (partial)
      The Library page's rewrite_count column does
        LEFT JOIN drafts WHERE status != 'failed' GROUP BY library_item_id.
      Partial index keyed on library_item_id, restricted to non-failed
      rows, makes that subquery a cheap index scan instead of a full
      drafts seq scan.
"""
from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "b3a7f1c2e8d9"
down_revision: str | Sequence[str] | None = "d04b636b2aab"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_index(
        "ix_library_items_created_at",
        "library_items",
        ["created_at"],
    )
    op.create_index(
        "ix_drafts_status_created_at",
        "drafts",
        ["status", "created_at"],
    )
    op.create_index(
        "ix_drafts_library_item_id_active",
        "drafts",
        ["library_item_id"],
        postgresql_where=sa.text("status != 'failed'"),
    )


def downgrade() -> None:
    op.drop_index("ix_drafts_library_item_id_active", table_name="drafts")
    op.drop_index("ix_drafts_status_created_at", table_name="drafts")
    op.drop_index("ix_library_items_created_at", table_name="library_items")
