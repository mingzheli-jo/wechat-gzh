# ruff: noqa: E501
import json
from typing import Any

from app.ai_providers.base import BaseProvider, Message
from app.reviewer.sensitive_words import SensitiveWordChecker

PROMPT = """你是一名公众号合规审核员。请评估以下文章是否存在违规风险（政治敏感、广告法违禁词、医疗保健夸大、虚假宣传）。
输出严格 JSON：{"score": 0-100 整数，越高越合规, "issues": ["问题1", "问题2", ...]}。
没有问题时 issues 为空数组。score 与 issues 必须保持一致：100 表示完全合规、issues 必须为空；越多/越严重的问题对应越低 score。"""


def _parse_json_safe(text: str) -> dict[str, Any]:
    try:
        return json.loads(text)  # type: ignore[no-any-return]
    except json.JSONDecodeError:
        start = text.find("{")
        end = text.rfind("}")
        if start >= 0 and end > start:
            try:
                return json.loads(text[start : end + 1])  # type: ignore[no-any-return]
            except json.JSONDecodeError:
                pass
        return {"score": 0, "issues": [f"AI 返回非法 JSON: {text[:200]}"]}


async def review_compliance(
    *,
    provider: BaseProvider,
    model: str,
    title: str,
    content: str,
    sensitive_checker: SensitiveWordChecker | None = None,
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
    score = int(parsed.get("score", 0))
    issues = list(parsed.get("issues") or [])
    if sensitive_checker is not None:
        local_hits = sensitive_checker.check(title + "\n" + content)
        if local_hits:
            issues.append("本地黑名单命中：" + "、".join(local_hits))
            score = min(score, 60)
    return {"score": score, "issues": issues, "model": model}
