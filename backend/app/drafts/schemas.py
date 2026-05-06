import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from app.drafts.models import DraftStatus


class RewriteTriggerRequest(BaseModel):
    library_item_ids: list[uuid.UUID] = Field(min_length=1, max_length=200)
    account_id: uuid.UUID
    override_title_prompt: str | None = None
    override_content_prompt: str | None = None


class DraftOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    library_item_id: uuid.UUID
    account_id: uuid.UUID
    title: str | None
    status: DraftStatus
    error_msg: str | None
    review_report_id: uuid.UUID | None
    wechat_pushed_at: datetime | None
    created_at: datetime


class DraftDetail(DraftOut):
    content_html: str | None
    cover_image_id: uuid.UUID | None


class ReviewReportOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    draft_id: uuid.UUID
    compliance: dict[str, Any] | None
    originality: dict[str, Any] | None
    quality: dict[str, Any] | None
    clickbait: dict[str, Any] | None
    overall_score: int | None


class DraftEdit(BaseModel):
    title: str | None = None
    content_html: str | None = None


class DraftListPage(BaseModel):
    items: list[DraftOut]
    total: int
