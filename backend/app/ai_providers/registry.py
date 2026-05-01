from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai_providers.base import BaseProvider
from app.ai_providers.models import AIProvider, RoleBinding
from app.ai_providers.openai_compat import OpenAICompatProvider


class RegistryError(Exception):
    pass


class ProviderRegistry:
    def __init__(self) -> None:
        self._providers: dict[str, BaseProvider] = {}
        self._role_to_pair: dict[str, tuple[str, str]] = {}

    def register(self, provider: BaseProvider) -> None:
        self._providers[provider.name] = provider

    def bind_role(self, role: str, *, provider: str, model: str) -> None:
        if provider not in self._providers:
            raise RegistryError(f"unknown provider: {provider}")
        self._role_to_pair[role] = (provider, model)

    def role(self, role: str) -> tuple[BaseProvider, str]:
        if role not in self._role_to_pair:
            raise RegistryError(f"role not bound: {role}")
        provider_name, model = self._role_to_pair[role]
        return self._providers[provider_name], model

    def reset(self) -> None:
        self._providers.clear()
        self._role_to_pair.clear()


_registry = ProviderRegistry()


def get_registry() -> ProviderRegistry:
    return _registry


async def load_from_db(db: AsyncSession) -> None:
    """Reload providers and role bindings from DB.

    Called at app startup and after config changes.
    """
    _registry.reset()
    providers = (
        await db.execute(select(AIProvider).where(AIProvider.enabled.is_(True)))
    ).scalars().all()
    by_id = {p.id: p for p in providers}
    for p in providers:
        _registry.register(
            OpenAICompatProvider(
                name=p.name, api_key=p.api_key, base_url=p.base_url
            )
        )
    bindings = (await db.execute(select(RoleBinding))).scalars().all()
    for b in bindings:
        provider = by_id.get(b.provider_id)
        if provider is None:
            continue
        _registry.bind_role(b.role.value, provider=provider.name, model=b.model)
