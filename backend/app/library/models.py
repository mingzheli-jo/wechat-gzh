import enum
import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import DateTime, Enum, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class LibraryStatus(enum.StrEnum):
    pending = "pending"
    processing = "processing"
    done = "done"
    failed = "failed"


class LibraryItem(Base):
    __tablename__ = "library_items"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    source_url: Mapped[str] = mapped_column(String(2048), nullable=False, unique=True)
    original_title: Mapped[str | None] = mapped_column(String(500), nullable=True)
    original_author: Mapped[str | None] = mapped_column(String(200), nullable=True)
    original_content_html: Mapped[str | None] = mapped_column(Text, nullable=True)
    original_content_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    images: Mapped[list[dict[str, Any]] | None] = mapped_column(JSONB, nullable=True)
    status: Mapped[LibraryStatus] = mapped_column(
        Enum(LibraryStatus), nullable=False, default=LibraryStatus.pending
    )
    tags: Mapped[list[str] | None] = mapped_column(JSONB, nullable=True, default=list)
    crawled_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    error_msg: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
