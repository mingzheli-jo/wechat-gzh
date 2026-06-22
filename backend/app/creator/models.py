import enum
import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import DateTime, Enum, ForeignKey, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class CreationInputMode(enum.StrEnum):
    link = "link"
    manual = "manual"


class CreationStatus(enum.StrEnum):
    pending = "pending"
    extracting = "extracting"
    retrieving = "retrieving"
    generating = "generating"
    reviewing = "reviewing"
    done = "done"
    failed = "failed"


class ThemeCreation(Base):
    """An AI-authored article grounded in the existing crawled article library.

    Pipeline: (optional crawl) -> extract ~100 char theme -> retrieve real
    related articles from the library -> generate a divergent article grounded
    in those sources -> fact-consistency review. Retrieved source ids are kept
    so the output stays traceable.
    """

    __tablename__ = "theme_creations"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    input_mode: Mapped[CreationInputMode] = mapped_column(
        Enum(CreationInputMode), nullable=False, default=CreationInputMode.link
    )
    # Source article (link mode): crawled snapshot for traceability.
    source_url: Mapped[str | None] = mapped_column(String(2048), nullable=True)
    source_title: Mapped[str | None] = mapped_column(String(500), nullable=True)
    source_text_snapshot: Mapped[str | None] = mapped_column(Text, nullable=True)
    # The distilled ~100 char theme that drives retrieval + generation.
    extracted_theme: Mapped[str | None] = mapped_column(Text, nullable=True)
    keywords: Mapped[list[str] | None] = mapped_column(JSONB, nullable=True)
    # Retrieved real articles used as grounding material. Each entry:
    # {library_item_id, title, source_url, relevance, excerpt}.
    retrieved_sources: Mapped[list[dict[str, Any]] | None] = mapped_column(
        JSONB, nullable=True
    )
    generated_title: Mapped[str | None] = mapped_column(String(500), nullable=True)
    generated_content_md: Mapped[str | None] = mapped_column(Text, nullable=True)
    generated_content_html: Mapped[str | None] = mapped_column(Text, nullable=True)
    # Fact-consistency review: {score, unsupported_claims, issues, note?}.
    fact_check: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    account_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("accounts.id"),
        nullable=True,
        index=True,
    )
    status: Mapped[CreationStatus] = mapped_column(
        Enum(CreationStatus), nullable=False, default=CreationStatus.pending
    )
    error_msg: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
