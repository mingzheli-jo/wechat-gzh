from typing import Any

from openai import AsyncOpenAI

from app.ai_providers.base import BaseProvider, ChatResult, Message, TokenUsage
from app.config import get_settings


class OpenAICompatProvider(BaseProvider):
    def __init__(self, *, name: str, api_key: str, base_url: str) -> None:
        self.name = name
        # 设置请求超时，避免外部 AI 服务无响应时任务长期挂起
        self._client = AsyncOpenAI(
            api_key=api_key,
            base_url=base_url,
            timeout=get_settings().llm_timeout_seconds,
        )

    async def chat(
        self,
        messages: list[Message],
        *,
        model: str,
        temperature: float = 0.7,
        max_tokens: int | None = None,
        json_mode: bool = False,
    ) -> ChatResult:
        kwargs: dict[str, Any] = {
            "model": model,
            "messages": [{"role": m.role, "content": m.content} for m in messages],
            "temperature": temperature,
        }
        if max_tokens is not None:
            kwargs["max_tokens"] = max_tokens
        if json_mode:
            kwargs["response_format"] = {"type": "json_object"}
        resp = await self._client.chat.completions.create(**kwargs)
        choice = resp.choices[0]
        usage = TokenUsage(
            prompt_tokens=resp.usage.prompt_tokens if resp.usage else 0,
            completion_tokens=resp.usage.completion_tokens if resp.usage else 0,
        )
        return ChatResult(
            content=choice.message.content or "",
            model=resp.model,
            usage=usage,
            raw=resp.model_dump(),
        )
