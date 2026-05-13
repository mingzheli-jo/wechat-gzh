import enum
import uuid
from datetime import datetime

from sqlalchemy import (
    DateTime,
    Enum,
    ForeignKey,
    Integer,
    String,
    Text,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class ImagePostTemplate(enum.StrEnum):
    two_panel_contrast = "two_panel_contrast"
    single_panel_caption = "single_panel_caption"


class ImagePostStatus(enum.StrEnum):
    pending = "pending"
    generating = "generating"
    generated = "generated"
    composing = "composing"
    pushing = "pushing"
    pushed = "pushed"
    failed = "failed"


class ImageAssetSource(enum.StrEnum):
    ai_generated = "ai_generated"
    manual_upload = "manual_upload"


class ImagePost(Base):
    __tablename__ = "image_posts"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    account_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("accounts.id", ondelete="CASCADE"),
        nullable=False,
    )
    template: Mapped[ImagePostTemplate] = mapped_column(
        Enum(ImagePostTemplate, name="image_post_template"), nullable=False
    )
    topic: Mapped[str] = mapped_column(Text, nullable=False)
    tone: Mapped[str | None] = mapped_column(String(50), nullable=True)
    status: Mapped[ImagePostStatus] = mapped_column(
        Enum(ImagePostStatus, name="image_post_status"),
        nullable=False,
        default=ImagePostStatus.pending,
    )
    captions: Mapped[list[str] | None] = mapped_column(JSONB, nullable=True)
    panel_prompts: Mapped[list[str] | None] = mapped_column(JSONB, nullable=True)
    asset_ids: Mapped[list[str] | None] = mapped_column(JSONB, nullable=True)
    panel_asset_ids: Mapped[list[str] | None] = mapped_column(JSONB, nullable=True)
    composed_image_path: Mapped[str | None] = mapped_column(Text, nullable=True)
    wechat_thumb_media_id: Mapped[str | None] = mapped_column(String(200), nullable=True)
    wechat_draft_media_id: Mapped[str | None] = mapped_column(String(200), nullable=True)
    wechat_pushed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    error_msg: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class ImageAsset(Base):
    __tablename__ = "image_assets"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    account_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("accounts.id", ondelete="CASCADE"),
        nullable=False,
    )
    image_path: Mapped[str] = mapped_column(Text, nullable=False)
    scene_prompt: Mapped[str | None] = mapped_column(Text, nullable=True)
    tags: Mapped[list[str] | None] = mapped_column(JSONB, nullable=True)
    source: Mapped[ImageAssetSource] = mapped_column(
        Enum(ImageAssetSource, name="image_asset_source"),
        nullable=False,
        default=ImageAssetSource.ai_generated,
    )
    used_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
