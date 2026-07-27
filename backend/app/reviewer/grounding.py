# ruff: noqa: E501
"""Fact-consistency review: does the generated article stay grounded in the
retrieved source material, or did the model invent facts/data?"""
from typing import Any

from app.ai_providers.base import BaseProvider, Message
from app.config import get_settings
from app.reviewer.compliance import _parse_json_safe

PROMPT = """你是一名事实核查员。下面给出【参考素材】和一篇【待核查文章】。
请判断文章中出现的具体事实、数据、时间、机构、人物、事件是否都能在参考素材中找到依据。
找出那些在素材中找不到支撑、疑似编造的具体陈述。
输出严格 JSON：{"score": 0-100 整数（越高表示越忠于素材、越少杜撰）, "unsupported_claims": ["疑似无依据的具体陈述1", ...], "issues": ["其他问题", ...]}。
若所有具体事实都有素材支撑，unsupported_claims 为空数组、score 接近 100。"""

MAX_SOURCES_CHARS = 8000
MAX_ARTICLE_CHARS = 6000


async def review_grounding(
    *,
    provider: BaseProvider,
    model: str,
    article: str,
    sources_text: str,
) -> dict[str, Any]:
    user = (
        f"【参考素材】\n{sources_text[:MAX_SOURCES_CHARS]}\n\n"
        f"【待核查文章】\n{article[:MAX_ARTICLE_CHARS]}"
    )
    result = await provider.chat(
        [
            Message(role="system", content=PROMPT),
            Message(role="user", content=user),
        ],
        model=model,
        json_mode=True,
        temperature=0.1,
        max_tokens=get_settings().reviewer_max_tokens,
    )
    parsed = _parse_json_safe(result.content)
    out: dict[str, Any] = {
        "score": int(parsed.get("score", 0)),
        "unsupported_claims": list(parsed.get("unsupported_claims") or []),
        "issues": list(parsed.get("issues") or []),
        "model": model,
    }
    # Surface parse trouble so a 0 caused by a mangled response is
    # distinguishable from a 0 the reviewer genuinely awarded.
    if parsed.get("parse_error"):
        out["parse_error"] = True
        out["score_recovered"] = bool(parsed.get("score_recovered"))
    return out
