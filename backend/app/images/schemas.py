import uuid

from pydantic import BaseModel, ConfigDict

from app.images.models import ImageStatus


class ImageOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    draft_id: uuid.UUID
    original_url: str
    wechat_url: str | None
    status: ImageStatus
    position: int
    is_cover: bool
    error_msg: str | None
