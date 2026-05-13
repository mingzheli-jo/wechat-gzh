"""Image provider factory."""
from app.config import get_settings
from app.image_generator.base import BaseImageProvider
from app.image_generator.doubao import DoubaoImageProvider


def get_image_provider() -> BaseImageProvider:
    settings = get_settings()
    return DoubaoImageProvider(
        api_key=settings.doubao_api_key,
        base_url=settings.doubao_base_url,
        model=settings.doubao_image_model,
    )
