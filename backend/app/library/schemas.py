import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from app.library.models import LibraryStatus


class IngestRequest(BaseModel):
    urls: list[str] = Field(min_length=1, max_length=100)
    tags: list[str] = []


class LibraryItemOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    source_url: str
    original_title: str | None
    original_author: str | None
    status: LibraryStatus
    tags: list[str] | None
    error_msg: str | None
    crawled_at: datetime | None
    created_at: datetime
    rewrite_count: int = 0


class LibraryItemDetail(LibraryItemOut):
    original_content_html: str | None
    original_content_text: str | None
    images: list[dict[str, Any]] | None


class TagsUpdate(BaseModel):
    tags: list[str]
