import json
from typing import Any

import pytest

from app.ai_providers.base import BaseProvider, ChatResult, Message, TokenUsage
from app.reviewer.aggregator import aggregate
from app.reviewer.clickbait import review_clickbait
from app.reviewer.compliance import _parse_json_safe, review_compliance
from app.reviewer.originality import review_originality
from app.reviewer.quality import review_quality
from app.reviewer.sensitive_words import SensitiveWordChecker


class StubProvider(BaseProvider):
    name = "stub"

    def __init__(self, response: str) -> None:
        self.response = response

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
        return ChatResult(content=self.response, model=model, usage=TokenUsage())


def test_parse_json_safe_extracts_block_from_noisy_text():
    assert _parse_json_safe('noise{"score":80,"issues":[]}trail') == {
        "score": 80,
        "issues": [],
    }


def test_parse_json_safe_returns_default_on_garbage():
    out = _parse_json_safe("不是 JSON")
    assert out["score"] == 0
    assert "非法 JSON" in out["issues"][0]


@pytest.mark.asyncio
async def test_compliance_includes_local_blacklist_hits(tmp_path):
    words_file = tmp_path / "w.txt"
    words_file.write_text("最佳\n", encoding="utf-8")
    checker = SensitiveWordChecker.from_file(words_file)
    provider = StubProvider(json.dumps({"score": 90, "issues": []}))
    out = await review_compliance(
        provider=provider,
        model="m",
        title="最佳产品",
        content="...",
        sensitive_checker=checker,
    )
    assert out["score"] <= 60
    assert any("最佳" in i for i in out["issues"])


@pytest.mark.asyncio
async def test_originality_returns_dict():
    provider = StubProvider(
        json.dumps({"score": 70, "similarity": 0.3, "issues": []})
    )
    out = await review_originality(
        provider=provider, model="m", original_text="x", rewritten_text="y"
    )
    assert out["score"] == 70
    assert out["similarity"] == 0.3


@pytest.mark.asyncio
async def test_quality_and_clickbait_run():
    provider = StubProvider(json.dumps({"score": 85, "issues": ["小问题"]}))
    q = await review_quality(provider=provider, model="m", title="t", content="c")
    cb = await review_clickbait(
        provider=provider, model="m", title="t", content_excerpt="c"
    )
    assert q["score"] == 85
    assert cb["score"] == 85


def test_aggregate_overall_score():
    reports = {
        "compliance": {"score": 80},
        "originality": {"score": 60},
        "quality": {"score": 90},
        "clickbait": {"score": 70},
    }
    overall = aggregate(reports)
    assert 0 <= overall <= 100
    assert overall == int(80 * 0.35 + 60 * 0.25 + 90 * 0.25 + 70 * 0.15)
