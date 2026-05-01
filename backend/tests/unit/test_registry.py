from typing import Any

import pytest

from app.ai_providers.base import BaseProvider, ChatResult, Message, TokenUsage
from app.ai_providers.registry import ProviderRegistry, RegistryError


class StubProvider(BaseProvider):
    def __init__(self, name: str) -> None:
        self.name = name

    async def chat(
        self,
        messages: list[Message],
        *,
        model: str,
        temperature: float = 0.7,
        max_tokens: int | None = None,
        json_mode: bool = False,
        **kwargs: Any,
    ) -> ChatResult:
        return ChatResult(content="ok", model=model, usage=TokenUsage())


def test_register_and_bind():
    reg = ProviderRegistry()
    reg.register(StubProvider("a"))
    reg.bind_role("writer", provider="a", model="m1")
    p, m = reg.role("writer")
    assert p.name == "a"
    assert m == "m1"


def test_bind_unknown_provider_raises():
    reg = ProviderRegistry()
    with pytest.raises(RegistryError):
        reg.bind_role("writer", provider="missing", model="m")


def test_unbound_role_raises():
    reg = ProviderRegistry()
    reg.register(StubProvider("a"))
    with pytest.raises(RegistryError):
        reg.role("writer")
