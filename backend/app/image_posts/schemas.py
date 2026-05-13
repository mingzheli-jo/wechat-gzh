"""Pydantic schemas for image posts."""
import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.image_posts.models import ImagePostStatus, ImagePostTemplate


class ImagePostCreate(BaseModel):
    account_id: uuid.UUID
    template: ImagePostTemplate
    topic: str = Field(min_length=1, max_length=500)
    tone: str | None = None
    panel_asset_ids: list[uuid.UUID] | None = None  # 阶段 2 复用图库


class ImagePostUpdate(BaseModel):
    captions: list[str] | None = None


class ImagePostOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    account_id: uuid.UUID
    template: ImagePostTemplate
    topic: str
    tone: str | None
    status: ImagePostStatus
    error_msg: str | None
    wechat_pushed_at: datetime | None
    created_at: datetime


class ImagePostDetail(ImagePostOut):
    captions: list[str] | None
    panel_prompts: list[str] | None
    asset_ids: list[uuid.UUID] | None
    panel_asset_ids: list[uuid.UUID] | None
    composed_image_path: str | None
    wechat_thumb_media_id: str | None
    wechat_draft_media_id: str | None


class ImagePostListPage(BaseModel):
    items: list[ImagePostOut]
    total: int


class ImageAssetOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    account_id: uuid.UUID
    image_path: str
    scene_prompt: str | None
    tags: list[str] | None
    source: str
    used_count: int
    created_at: datetime


class ImageAssetListPage(BaseModel):
    items: list[ImageAssetOut]
    total: int
