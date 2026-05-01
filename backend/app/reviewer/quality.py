from typing import Any

from app.ai_providers.base import BaseProvider, Message
from app.reviewer.compliance import _parse_json_safe

PROMPT = """你是一名内容质量审核员，评估文章的通顺度、逻辑连贯、可读性，以及是否有明显 AI 生成痕迹。
输出严格 JSON：{"score": 0-100, "issues": [...]}。"""


async def review_quality(
    *,
    provider: BaseProvider,
    model: str,
    title: str,
    content: str,
) -> dict[str, Any]:
    user = f"【标题】{title}\n【正文】{content[:6000]}"
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
