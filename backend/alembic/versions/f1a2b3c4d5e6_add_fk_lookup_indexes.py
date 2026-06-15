"""add fk lookup indexes

Revision ID: f1a2b3c4d5e6
Revises: 4b31cd6708db
Create Date: 2026-06-15 00:00:00.000000

Adds indexes on frequently-filtered foreign-key columns that Postgres does
NOT auto-index. Without these, the following queries do sequential scans as
data grows:

  ix_drafts_account_id
      drafts list/pagination and the rewrite/publish pipeline filter by
      account_id; also speeds account deletion cleanup.

  ix_images_draft_id
      Every image lookup filters `WHERE draft_id = ?` (image processing,
      publish gating, draft detail).

  ix_ai_usage_provider_id / ix_ai_usage_ref_id
      Cost/usage stats group and filter by provider_id and ref_id.
"""
from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "f1a2b3c4d5e6"
down_revision: str | Sequence[str] | None = "4b31cd6708db"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_index("ix_drafts_account_id", "drafts", ["account_id"])
    op.create_index("ix_images_draft_id", "images", ["draft_id"])
    op.create_index("ix_ai_usage_provider_id", "ai_usage", ["provider_id"])
    op.create_index("ix_ai_usage_ref_id", "ai_usage", ["ref_id"])


def downgrade() -> None:
    op.drop_index("ix_ai_usage_ref_id", table_name="ai_usage")
    op.drop_index("ix_ai_usage_provider_id", table_name="ai_usage")
    op.drop_index("ix_images_draft_id", table_name="images")
    op.drop_index("ix_drafts_account_id", table_name="drafts")
