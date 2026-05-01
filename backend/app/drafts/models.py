import enum
import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import DateTime, Enum, ForeignKey, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class DraftStatus(enum.StrEnum):
    draft = "draft"
    reviewing = "reviewing"
    reviewed = "reviewed"
    published_to_wechat = "published_to_wechat"
    failed = "failed"


class Draft(Base):
    __tablename__ = "drafts"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    library_item_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("library_items.id"),
        nullable=False,
    )
    account_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("accounts.id"), nullable=False
    )
    title: Mapped[str | None] = mapped_column(String(500), nullable=True)
    content_html: Mapped[str | None] = mapped_column(Text, nullable=True)
    cover_image_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), nullable=True
    )
    status: Mapped[DraftStatus] = mapped_column(
        Enum(DraftStatus), nullable=False, default=DraftStatus.draft
    )
    review_report_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey(
            "review_reports.id",
            use_alter=True,
            name="fk_drafts_review_report",
        ),
        nullable=True,
    )
    error_msg: Mapped[str | None] = mapped_column(Text, nullable=True)
    wechat_media_id: Mapped[str | None] = mapped_column(String(200), nullable=True)
    wechat_pushed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class ReviewReport(Base):
    __tablename__ = "review_reports"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    draft_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("drafts.id"), nullable=False
    )
    compliance: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    originality: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    quality: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    clickbait: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    overall_score: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
