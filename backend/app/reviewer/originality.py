from typing import Any

from app.ai_providers.base import BaseProvider, Message
from app.reviewer.compliance import _parse_json_safe

PROMPT = """你是一名公众号原创度审核员。比较【原文】与【改写】的相似度并指出明显抄袭点。
输出严格 JSON：{"score": 0-100，越高越原创, "similarity": 0.0-1.0, "issues": [...]}。
similarity 是与原文的相似度估计；score 与 (1-similarity) 应大致正相关。"""


async def review_originality(
    *,
    provider: BaseProvider,
    model: str,
    original_text: str,
    rewritten_text: str,
) -> dict[str, Any]:
    user = f"【原文】{original_text[:4000]}\n【改写】{rewritten_text[:4000]}"
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
        "similarity": float(parsed.get("similarity", 1.0)),
        "issues": list(parsed.get("issues") or []),
        "model": model,
    }
