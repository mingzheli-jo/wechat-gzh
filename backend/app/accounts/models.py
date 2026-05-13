import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, String, Text, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.db.encryption import EncryptedString


class Account(Base):
    __tablename__ = "accounts"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    wechat_appid: Mapped[str] = mapped_column(String(100), nullable=False)
    wechat_secret: Mapped[str] = mapped_column(
        EncryptedString(length=2048), nullable=False
    )
    category: Mapped[str] = mapped_column(String(50), nullable=False)
    title_prompt: Mapped[str] = mapped_column(Text, nullable=False, default="")
    content_prompt: Mapped[str] = mapped_column(Text, nullable=False, default="")
    style_desc: Mapped[str] = mapped_column(Text, nullable=False, default="")
    default_thumb_media_id: Mapped[str | None] = mapped_column(
        String(200), nullable=True
    )
    character_reference_path: Mapped[str | None] = mapped_column(
        String(500), nullable=True
    )
    character_reference_updated_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
