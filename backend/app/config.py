from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/wechat_rewriter"
    redis_url: str = "redis://localhost:6379/0"

    admin_username: str = "admin"
    admin_password_hash: str = ""
    jwt_secret: str = "change-me"
    jwt_algorithm: str = "HS256"
    jwt_expire_minutes: int = 60 * 24

    encryption_key: str = ""

    default_writer_provider: str = "deepseek"
    default_reviewer_provider: str = "kimi"
    default_lite_provider: str = "deepseek"

    crawler_timeout: int = 30
    crawler_max_retry: int = 3
    celery_worker_concurrency: int = 4
    image_storage_dir: str = "/data/images"
    rewrite_batch_max: int = Field(default=20, ge=1, le=200)
    draft_max_regenerations: int = Field(default=5, ge=1, le=50)


@lru_cache
def get_settings() -> Settings:
    return Settings()
