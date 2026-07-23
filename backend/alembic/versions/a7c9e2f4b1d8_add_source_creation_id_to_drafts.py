"""add source_creation_id to drafts

Revision ID: a7c9e2f4b1d8
Revises: e1f2a3b4c5d6
Create Date: 2026-07-23 00:00:00.000000

"""
from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "a7c9e2f4b1d8"
down_revision: str | Sequence[str] | None = "e1f2a3b4c5d6"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    # Drafts can now originate from a ThemeCreation instead of a LibraryItem,
    # so library_item_id becomes optional and a new nullable FK is added.
    op.alter_column("drafts", "library_item_id", existing_type=sa.UUID(), nullable=True)
    op.add_column(
        "drafts",
        sa.Column("source_creation_id", sa.UUID(), nullable=True),
    )
    op.create_foreign_key(
        op.f("fk_drafts_source_creation_id_theme_creations"),
        "drafts",
        "theme_creations",
        ["source_creation_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_index(
        op.f("ix_drafts_source_creation_id"),
        "drafts",
        ["source_creation_id"],
        unique=False,
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(op.f("ix_drafts_source_creation_id"), table_name="drafts")
    op.drop_constraint(
        op.f("fk_drafts_source_creation_id_theme_creations"),
        "drafts",
        type_="foreignkey",
    )
    op.drop_column("drafts", "source_creation_id")
    op.alter_column(
        "drafts", "library_item_id", existing_type=sa.UUID(), nullable=False
    )
