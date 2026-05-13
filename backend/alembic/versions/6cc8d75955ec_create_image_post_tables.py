"""create image post tables

Revision ID: 6cc8d75955ec
Revises: 29bfd0d1e9db
Create Date: 2026-05-13 10:09:33.682651

"""
from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

# revision identifiers, used by Alembic.
revision: str = '6cc8d75955ec'
down_revision: str | Sequence[str] | None = '29bfd0d1e9db'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    image_post_template = sa.Enum(
        "two_panel_contrast", "single_panel_caption",
        name="image_post_template",
    )
    image_post_status = sa.Enum(
        "pending", "generating", "generated",
        "composing", "pushing", "pushed", "failed",
        name="image_post_status",
    )
    image_asset_source = sa.Enum(
        "ai_generated", "manual_upload",
        name="image_asset_source",
    )
    image_post_template.create(op.get_bind(), checkfirst=False)
    image_post_status.create(op.get_bind(), checkfirst=False)
    image_asset_source.create(op.get_bind(), checkfirst=False)

    op.create_table(
        "image_posts",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("account_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("accounts.id", ondelete="CASCADE"), nullable=False),
        sa.Column("template", image_post_template, nullable=False),
        sa.Column("topic", sa.Text(), nullable=False),
        sa.Column("tone", sa.String(50), nullable=True),
        sa.Column("status", image_post_status, nullable=False,
                  server_default="pending"),
        sa.Column("captions", postgresql.JSONB(), nullable=True),
        sa.Column("panel_prompts", postgresql.JSONB(), nullable=True),
        sa.Column("asset_ids", postgresql.JSONB(), nullable=True),
        sa.Column("panel_asset_ids", postgresql.JSONB(), nullable=True),
        sa.Column("composed_image_path", sa.Text(), nullable=True),
        sa.Column("wechat_thumb_media_id", sa.String(200), nullable=True),
        sa.Column("wechat_draft_media_id", sa.String(200), nullable=True),
        sa.Column("wechat_pushed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("error_msg", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True),
                  server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True),
                  server_default=sa.func.now(), nullable=False),
    )

    op.create_table(
        "image_assets",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("account_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("accounts.id", ondelete="CASCADE"), nullable=False),
        sa.Column("image_path", sa.Text(), nullable=False),
        sa.Column("scene_prompt", sa.Text(), nullable=True),
        sa.Column("tags", postgresql.JSONB(), nullable=True),
        sa.Column("source", image_asset_source, nullable=False,
                  server_default="ai_generated"),
        sa.Column("used_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True),
                  server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_image_posts_account_id", "image_posts", ["account_id"])
    op.create_index("ix_image_assets_account_id", "image_assets", ["account_id"])


def downgrade() -> None:
    op.drop_index("ix_image_assets_account_id")
    op.drop_index("ix_image_posts_account_id")
    op.drop_table("image_assets")
    op.drop_table("image_posts")
    op.execute("DROP TYPE image_asset_source")
    op.execute("DROP TYPE image_post_status")
    op.execute("DROP TYPE image_post_template")
