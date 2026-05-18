import uuid
from datetime import datetime

from sqlalchemy import (
    BigInteger,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class WechatArticle(Base):
    __tablename__ = "wechat_articles"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    account_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("accounts.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    msgid: Mapped[int] = mapped_column(BigInteger, nullable=False)
    article_idx: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    publish_time: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    read_count: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default="0"
    )
    like_count: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default="0"
    )
    share_count: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default="0"
    )
    comment_count: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default="0"
    )
    last_synced_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )

    __table_args__ = (
        UniqueConstraint(
            "account_id", "msgid", "article_idx", name="uq_wechat_article"
        ),
        Index(
            "ix_wechat_article_publish", "account_id", "publish_time"
        ),
    )
