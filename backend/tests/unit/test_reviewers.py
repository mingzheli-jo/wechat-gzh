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


def test_parse_json_safe_strips_lone_surrogates():
    """DeepSeek occasionally returns lone surrogates in JSON string values.

    json.loads accepts them but downstream consumers (DB, JSON serializers,
    UI) choke on them. We sanitize via UTF-8 round-trip with errors='replace'.
    """
    raw = '{"score": 70, "issues": ["abc\\ud800def"]}'
    out = _parse_json_safe(raw)
    assert out["score"] == 70
    assert "\ud800" not in out["issues"][0]
    out_json = json.dumps(out)
    assert "\\ud800" not in out_json


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


# --- truncated-response handling (production bug 2026-07-27) ---------------
# Moonshot's default max_tokens cut the fact-check JSON off mid-string. The
# brace-slice fallback then failed too (no closing brace survived), score
# defaulted to 0, and the auto-publish gate silently dropped articles the
# reviewer had actually scored 95.


def test_parse_json_safe_recovers_score_from_truncated_json():
    truncated = '{"score": 95, "unsupported_claims": ["某条陈述"], "issues": ["文章中提到的'
    out = _parse_json_safe(truncated)
    assert out["score"] == 95
    assert out["parse_error"] is True
    assert out["score_recovered"] is True


def test_parse_json_safe_truncated_without_score_still_fails_closed():
    out = _parse_json_safe('{"unsupported_claims": ["某条陈述"], "issues": ["文章中')
    assert out["score"] == 0
    assert out["parse_error"] is True
    assert out["score_recovered"] is False


def test_parse_json_safe_clamps_out_of_range_recovered_score():
    out = _parse_json_safe('{"score": 999, "issues": ["截断')
    assert out["score"] == 100


def test_parse_json_safe_intact_json_has_no_parse_error_flag():
    out = _parse_json_safe('{"score": 80, "issues": []}')
    assert "parse_error" not in out


@pytest.mark.asyncio
async def test_grounding_recovers_truncated_score_and_flags_it():
    from app.reviewer.grounding import review_grounding

    provider = StubProvider('{"score": 95, "unsupported_claims": [], "issues": ["文章中提到的')
    out = await review_grounding(
        provider=provider, model="m", article="正文", sources_text="素材"
    )
    assert out["score"] == 95
    assert out["parse_error"] is True
    assert out["score_recovered"] is True


@pytest.mark.asyncio
async def test_reviewers_cap_output_tokens():
    """Every reviewer must bound its own output, or long Chinese `issues`
    arrays truncate the JSON and the score is lost."""
    from app.config import get_settings
    from app.reviewer.grounding import review_grounding

    captured: dict[str, Any] = {}

    class CapturingProvider(StubProvider):
        async def chat(self, messages, *, model, temperature=0.7,
                       max_tokens=None, json_mode=False, **kwargs):
            captured["max_tokens"] = max_tokens
            return await super().chat(
                messages, model=model, temperature=temperature,
                max_tokens=max_tokens, json_mode=json_mode, **kwargs
            )

    expected = get_settings().reviewer_max_tokens
    assert expected >= 512

    calls = [
        lambda p: review_compliance(provider=p, model="m", title="t", content="c"),
        lambda p: review_originality(
            provider=p, model="m", original_text="o", rewritten_text="r"
        ),
        lambda p: review_quality(provider=p, model="m", title="t", content="c"),
        lambda p: review_clickbait(
            provider=p, model="m", title="t", content_excerpt="c"
        ),
        lambda p: review_grounding(
            provider=p, model="m", article="a", sources_text="s"
        ),
    ]
    for call in calls:
        captured.clear()
        await call(CapturingProvider('{"score": 90, "issues": []}'))
        assert captured["max_tokens"] == expected
