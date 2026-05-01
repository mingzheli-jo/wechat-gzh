import httpx
import pytest
import respx

from app.ai_providers.base import Message
from app.ai_providers.openai_compat import OpenAICompatProvider


@pytest.mark.asyncio
async def test_chat_returns_content_and_usage():
    body = {
        "id": "x",
        "model": "deepseek-chat",
        "choices": [
            {
                "index": 0,
                "message": {"role": "assistant", "content": "hello"},
                "finish_reason": "stop",
            }
        ],
        "usage": {
            "prompt_tokens": 10,
            "completion_tokens": 5,
            "total_tokens": 15,
        },
    }
    async with respx.mock(base_url="https://api.deepseek.com/v1") as mock:
        mock.post("/chat/completions").mock(
            return_value=httpx.Response(200, json=body)
        )
        provider = OpenAICompatProvider(
            name="deepseek",
            api_key="sk-x",
            base_url="https://api.deepseek.com/v1",
        )
        result = await provider.chat(
            [Message(role="user", content="hi")],
            model="deepseek-chat",
        )
    assert result.content == "hello"
    assert result.usage.prompt_tokens == 10
    assert result.usage.completion_tokens == 5
