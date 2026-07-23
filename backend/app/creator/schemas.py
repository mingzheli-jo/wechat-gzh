import uuid
from datetime import datetime
from typing import Any
from urllib.parse import urlparse

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.creator.models import CreationInputMode, CreationStatus


class CreationCreateRequest(BaseModel):
    """Create a theme creation. Provide a source_url (link mode) and/or a
    theme (manual mode). At least one is required; if both are given the
    crawled article is used and the manual theme is ignored."""

    # max_length matches ThemeCreation.source_url (String(2048)); reject
    # oversized input at the boundary rather than leaking a DB length error.
    source_url: str | None = Field(default=None, max_length=2048)
    theme: str | None = Field(default=None, max_length=2000)
    account_id: uuid.UUID | None = None

    @field_validator("source_url", mode="before")
    @classmethod
    def _validate_url_scheme(cls, v: str | None) -> str | None:
        # Reject non-http(s) schemes (file://, internal addresses, ...) at the
        # boundary. The worker's SSRF allowlist is the real guard, but storing
        # only well-formed http(s) URLs keeps the persisted/echoed value clean.
        if v is None:
            return v
        stripped = v.strip()
        if not stripped:
            return None
        if urlparse(stripped).scheme not in ("http", "https"):
            raise ValueError("source_url 必须以 http:// 或 https:// 开头")
        return stripped

    @model_validator(mode="after")
    def _require_input(self) -> "CreationCreateRequest":
        if not (self.source_url and self.source_url.strip()) and not (
            self.theme and self.theme.strip()
        ):
            raise ValueError("必须提供 source_url 或 theme 之一")
        return self


class CreationOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    input_mode: CreationInputMode
    source_url: str | None
    source_title: str | None
    extracted_theme: str | None
    generated_title: str | None
    status: CreationStatus
    error_msg: str | None
    account_id: uuid.UUID | None
    created_at: datetime


class CreationDetail(CreationOut):
    source_text_snapshot: str | None
    keywords: list[str] | None
    retrieved_sources: list[dict[str, Any]] | None
    generated_content_md: str | None
    generated_content_html: str | None
    fact_check: dict[str, Any] | None


class CreationEdit(BaseModel):
    generated_title: str | None = None
    generated_content_html: str | None = None


class CreationPublishRequest(BaseModel):
    account_id: uuid.UUID | None = None


class CreationListPage(BaseModel):
    items: list[CreationOut]
    total: int
