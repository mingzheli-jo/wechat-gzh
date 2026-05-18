import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class AccountIn(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    wechat_appid: str = Field(min_length=1, max_length=100)
    wechat_secret: str = Field(min_length=1)
    category: str = Field(min_length=1, max_length=50)
    title_prompt: str = ""
    content_prompt: str = ""
    style_desc: str = ""
    is_active: bool = True


class AccountUpdate(BaseModel):
    name: str | None = None
    wechat_appid: str | None = None
    wechat_secret: str | None = None
    category: str | None = None
    title_prompt: str | None = None
    content_prompt: str | None = None
    style_desc: str | None = None
    is_active: bool | None = None


class AccountOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    name: str
    wechat_appid: str
    category: str
    title_prompt: str
    content_prompt: str
    style_desc: str
    default_thumb_media_id: str | None
    character_reference_path: str | None = None
    character_reference_updated_at: datetime | None = None
    follower_count: int
    new_follow_yesterday: int
    cancel_follow_yesterday: int
    stats_synced_at: datetime | None
    is_active: bool
    created_at: datetime
    updated_at: datetime
