"""create theme_creations table

Revision ID: e1f2a3b4c5d6
Revises: f1a2b3c4d5e6
Create Date: 2026-06-22 00:00:00.000000

"""
from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "e1f2a3b4c5d6"
down_revision: str | Sequence[str] | None = "f1a2b3c4d5e6"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    # Create the enum types explicitly with checkfirst=True so a re-run after a
    # mid-migration failure (types created, table not) doesn't abort with
    # DuplicateObject. create_type=False on the columns then prevents
    # create_table from emitting a second CREATE TYPE.
    input_mode_enum = postgresql.ENUM(
        "link", "manual", name="creationinputmode", create_type=False
    )
    status_enum = postgresql.ENUM(
        "pending",
        "extracting",
        "retrieving",
        "generating",
        "reviewing",
        "done",
        "failed",
        name="creationstatus",
        create_type=False,
    )
    input_mode_enum.create(op.get_bind(), checkfirst=True)
    status_enum.create(op.get_bind(), checkfirst=True)

    op.create_table(
        "theme_creations",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column(
            "input_mode",
            input_mode_enum,
            nullable=False,
        ),
        sa.Column("source_url", sa.String(length=2048), nullable=True),
        sa.Column("source_title", sa.String(length=500), nullable=True),
        sa.Column("source_text_snapshot", sa.Text(), nullable=True),
        sa.Column("extracted_theme", sa.Text(), nullable=True),
        sa.Column(
            "keywords", postgresql.JSONB(astext_type=sa.Text()), nullable=True
        ),
        sa.Column(
            "retrieved_sources",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=True,
        ),
        sa.Column("generated_title", sa.String(length=500), nullable=True),
        sa.Column("generated_content_md", sa.Text(), nullable=True),
        sa.Column("generated_content_html", sa.Text(), nullable=True),
        sa.Column(
            "fact_check", postgresql.JSONB(astext_type=sa.Text()), nullable=True
        ),
        sa.Column("account_id", sa.UUID(), nullable=True),
        sa.Column(
            "status",
            status_enum,
            nullable=False,
        ),
        sa.Column("error_msg", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["account_id"],
            ["accounts.id"],
            name=op.f("fk_theme_creations_account_id_accounts"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_theme_creations")),
    )
    op.create_index(
        op.f("ix_theme_creations_account_id"),
        "theme_creations",
        ["account_id"],
        unique=False,
    )
    op.create_index(
        "ix_theme_creations_status_created_at",
        "theme_creations",
        ["status", "created_at"],
        unique=False,
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index("ix_theme_creations_status_created_at", table_name="theme_creations")
    op.drop_index(
        op.f("ix_theme_creations_account_id"), table_name="theme_creations"
    )
    op.drop_table("theme_creations")
    sa.Enum(name="creationstatus").drop(op.get_bind(), checkfirst=True)
    sa.Enum(name="creationinputmode").drop(op.get_bind(), checkfirst=True)
