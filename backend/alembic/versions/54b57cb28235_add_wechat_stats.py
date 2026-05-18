"""add wechat stats

Revision ID: 54b57cb28235
Revises: a1b2c3d4e5f6
Create Date: 2026-05-18 19:23:49.402591

"""
from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "54b57cb28235"
down_revision: str | Sequence[str] | None = "a1b2c3d4e5f6"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "accounts",
        sa.Column(
            "follower_count",
            sa.Integer(),
            nullable=False,
            server_default="0",
        ),
    )
    op.add_column(
        "accounts",
        sa.Column(
            "new_follow_yesterday",
            sa.Integer(),
            nullable=False,
            server_default="0",
        ),
    )
    op.add_column(
        "accounts",
        sa.Column(
            "cancel_follow_yesterday",
            sa.Integer(),
            nullable=False,
            server_default="0",
        ),
    )
    op.add_column(
        "accounts",
        sa.Column(
            "stats_synced_at",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
    )

    op.create_table(
        "wechat_articles",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("account_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("msgid", sa.BigInteger(), nullable=False),
        sa.Column("article_idx", sa.Integer(), nullable=False),
        sa.Column("title", sa.String(length=200), nullable=False),
        sa.Column("publish_time", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "read_count",
            sa.Integer(),
            nullable=False,
            server_default="0",
        ),
        sa.Column(
            "like_count",
            sa.Integer(),
            nullable=False,
            server_default="0",
        ),
        sa.Column(
            "share_count",
            sa.Integer(),
            nullable=False,
            server_default="0",
        ),
        sa.Column(
            "comment_count",
            sa.Integer(),
            nullable=False,
            server_default="0",
        ),
        sa.Column("last_synced_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["account_id"], ["accounts.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "account_id", "msgid", "article_idx", name="uq_wechat_article"
        ),
    )
    op.create_index(
        "ix_wechat_articles_account_id",
        "wechat_articles",
        ["account_id"],
    )
    op.create_index(
        "ix_wechat_article_publish",
        "wechat_articles",
        ["account_id", "publish_time"],
    )


def downgrade() -> None:
    op.drop_index("ix_wechat_article_publish", table_name="wechat_articles")
    op.drop_index("ix_wechat_articles_account_id", table_name="wechat_articles")
    op.drop_table("wechat_articles")
    op.drop_column("accounts", "stats_synced_at")
    op.drop_column("accounts", "cancel_follow_yesterday")
    op.drop_column("accounts", "new_follow_yesterday")
    op.drop_column("accounts", "follower_count")
