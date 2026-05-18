import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict


class AccountStatsRow(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    account_id: uuid.UUID
    name: str
    follower_count: int
    new_follow_yesterday: int
    cancel_follow_yesterday: int
    articles_count_30d: int
    total_read_30d: int
    stats_synced_at: datetime | None


class ArticleStatsRow(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    msgid: int
    article_idx: int
    title: str
    publish_time: datetime
    read_count: int
    like_count: int
    share_count: int
    comment_count: int
    last_synced_at: datetime


class RefreshTriggerResponse(BaseModel):
    job_id: str
    status: Literal["queued"]
