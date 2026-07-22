# ruff: noqa: E501
import json
from typing import Any

from app.ai_providers.base import BaseProvider, Message
from app.reviewer.sensitive_words import SensitiveWordChecker

PROMPT = """你是一名公众号合规审核员。请评估以下文章是否存在违规风险（政治敏感、广告法违禁词、医疗保健夸大、虚假宣传）。
输出严格 JSON：{"score": 0-100 整数，越高越合规, "issues": ["问题1", "问题2", ...]}。
没有问题时 issues 为空数组。score 与 issues 必须保持一致：100 表示完全合规、issues 必须为空；越多/越严重的问题对应越低 score。"""

ACCOUNT_RULES_TEMPLATE = """

此外，该公众号有自己的红线要求。以下是该号的写作规范，
你只需从中提取"禁止/不许/不得/红线"类的条款，逐条检查正文是否违反，
写作风格类要求（节奏、口吻、结构）不属于你的职责，一律忽略。
违反账号红线的，按严重程度计入 issues 并扣分，issue 前缀写"账号红线："。

【该号写作规范】
{rules}"""


def _strip_surrogates(value: Any) -> Any:
    """Recursively replace lone-surrogate code points inside strings.

    Some LLMs (notably DeepSeek as reviewer) emit JSON with lone surrogates
    inside string values; downstream consumers (Postgres JSONB, UI, JSON
    serialization) choke on them. Round-tripping through UTF-8 with
    errors='replace' substitutes each one with U+FFFD.
    """
    if isinstance(value, str):
        return value.encode("utf-8", errors="replace").decode("utf-8")
    if isinstance(value, list):
        return [_strip_surrogates(v) for v in value]
    if isinstance(value, dict):
        return {k: _strip_surrogates(v) for k, v in value.items()}
    return value


def _parse_json_safe(text: str) -> dict[str, Any]:
    parsed: Any
    try:
        parsed = json.loads(text)
    except json.JSONDecodeError:
        start = text.find("{")
        end = text.rfind("}")
        if start >= 0 and end > start:
            try:
                parsed = json.loads(text[start : end + 1])
            except json.JSONDecodeError:
                return {
                    "score": 0,
                    "issues": [f"AI 返回非法 JSON: {text[:200]}"],
                }
        else:
            return {
                "score": 0,
                "issues": [f"AI 返回非法 JSON: {text[:200]}"],
            }
    sanitized = _strip_surrogates(parsed)
    if isinstance(sanitized, dict):
        return sanitized
    return {"score": 0, "issues": [f"AI 返回非 dict JSON: {text[:200]}"]}


async def review_compliance(
    *,
    provider: BaseProvider,
    model: str,
    title: str,
    content: str,
    sensitive_checker: SensitiveWordChecker | None = None,
    account_rules: str = "",
) -> dict[str, Any]:
    system = PROMPT
    if account_rules.strip():
        system += ACCOUNT_RULES_TEMPLATE.format(rules=account_rules.strip()[:3000])
    user = f"【标题】{title}\n【正文】{content[:6000]}"
    result = await provider.chat(
        [
            Message(role="system", content=system),
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
