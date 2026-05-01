from typing import Any

from app.ai_providers.base import BaseProvider, Message
from app.reviewer.compliance import _parse_json_safe

PROMPT = """你是一名标题审核员，评估【标题】是否标题党：是否过度夸张、是否与【正文】不符。
输出严格 JSON：{"score": 0-100，越高越克制，越好, "issues": [...]}。"""


async def review_clickbait(
    *,
    provider: BaseProvider,
    model: str,
    title: str,
    content_excerpt: str,
) -> dict[str, Any]:
    user = f"【标题】{title}\n【正文摘要】{content_excerpt[:1500]}"
    result = await provider.chat(
        [
            Message(role="system", content=PROMPT),
            Message(role="user", content=user),
        ],
        model=model,
        json_mode=True,
        temperature=0.1,
    )
    parsed = _parse_json_safe(result.content)
    return {
        "score": int(parsed.get("score", 0)),
        "issues": list(parsed.get("issues") or []),
        "model": model,
    }
