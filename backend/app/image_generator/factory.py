"""Image provider factory.

Lookup order:
1. role_bindings row with role=image → use that AIProvider's api_key/base_url + binding model
2. Fallback to settings.doubao_* (env-based config, kept for backward compat)
"""
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai_providers.models import AIProvider, Role, RoleBinding
from app.config import get_settings
from app.image_generator.base import BaseImageProvider
from app.image_generator.doubao import DoubaoImageProvider


async def get_image_provider(db: AsyncSession) -> BaseImageProvider:
    """Resolve current image provider from DB role binding, falling back to env settings."""
    binding_row = (
        await db.execute(
            select(RoleBinding, AIProvider)
            .join(AIProvider, AIProvider.id == RoleBinding.provider_id)
            .where(RoleBinding.role == Role.image)
            .where(AIProvider.enabled.is_(True))
        )
    ).first()

    if binding_row is not None:
        binding, provider = binding_row
        return DoubaoImageProvider(
            api_key=provider.api_key,
            base_url=provider.base_url,
            model=binding.model,
        )

    settings = get_settings()
    return DoubaoImageProvider(
        api_key=settings.doubao_api_key,
        base_url=settings.doubao_base_url,
        model=settings.doubao_image_model,
    )
