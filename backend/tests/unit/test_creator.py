import json
import uuid
from types import SimpleNamespace
from typing import Any

import pytest

from app.ai_providers.base import BaseProvider, ChatResult, Message, TokenUsage
from app.creator import generator, retriever, theme_extractor
from app.creator.retriever import _parse_keywords, _parse_selected
from app.reviewer.grounding import review_grounding


class StubProvider(BaseProvider):
    name = "stub"

    def __init__(self, response: str) -> None:
        self.response = response
        self.last_messages: list[Message] | None = None

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
        self.last_messages = messages
        return ChatResult(content=self.response, model=model, usage=TokenUsage())


def _item(title: str, text: str) -> SimpleNamespace:
    return SimpleNamespace(
        id=uuid.uuid4(),
        original_title=title,
        original_content_text=text,
        source_url=f"https://mp.weixin.qq.com/s/{title}",
    )


# --- theme_extractor ---


@pytest.mark.asyncio
async def test_extract_theme_returns_text_and_usage():
    provider = StubProvider("  这是一个约一百字的主题概述。  ")
    theme, usage = await theme_extractor.extract_theme(
        provider=provider, model="m", content="原文内容" * 100
    )
    assert theme == "这是一个约一百字的主题概述。"
    assert isinstance(usage, TokenUsage)


@pytest.mark.asyncio
async def test_extract_theme_raises_on_empty():
    provider = StubProvider("   ")
    with pytest.raises(ValueError):
        await theme_extractor.extract_theme(
            provider=provider, model="m", content="x"
        )


# --- retriever parsing ---


def test_parse_keywords_dedupes_and_strips():
    out = _parse_keywords('{"keywords": ["AI", " AI ", "芯片", ""]}')
    assert out == ["AI", "芯片"]


def test_parse_keywords_handles_noise_and_garbage():
    assert _parse_keywords('noise{"keywords":["x"]}tail') == ["x"]
    assert _parse_keywords("not json") == []


def test_parse_selected_filters_non_dicts():
    out = _parse_selected('{"selected": [{"index": 1, "relevance": 90}, 5]}')
    assert out == [{"index": 1, "relevance": 90}]


@pytest.mark.asyncio
async def test_extract_keywords_via_provider():
    provider = StubProvider(json.dumps({"keywords": ["新能源", "电池"]}))
    kws, usage = await retriever.extract_keywords(
        provider=provider, model="m", theme="主题"
    )
    assert kws == ["新能源", "电池"]
    assert isinstance(usage, TokenUsage)


# --- retriever.rerank ---


@pytest.mark.asyncio
async def test_rerank_maps_to_real_excerpts_and_respects_topk():
    candidates = [
        _item("电池技术突破", "真实正文A：宁德时代发布新电池，能量密度提升。"),
        _item("无关八卦", "和主题无关的内容。"),
        _item("新能源补贴", "真实正文C：2025 年新能源补贴政策调整。"),
    ]
    # Model selects index 0 and 2 (skips the irrelevant one).
    provider = StubProvider(
        json.dumps(
            {"selected": [{"index": 0, "relevance": 95}, {"index": 2, "relevance": 80}]}
        )
    )
    sources, usage = await retriever.rerank(
        provider=provider, model="m", theme="新能源电池", candidates=candidates, top_k=5
    )
    assert [s["title"] for s in sources] == ["电池技术突破", "新能源补贴"]
    # Excerpts must be sliced from the real article text, not invented.
    assert sources[0]["excerpt"] == candidates[0].original_content_text
    assert sources[0]["relevance"] == 95
    assert sources[0]["library_item_id"] == str(candidates[0].id)
    assert isinstance(usage, TokenUsage)


@pytest.mark.asyncio
async def test_rerank_skips_out_of_range_and_duplicate_indices():
    candidates = [_item("A", "aaa"), _item("B", "bbb")]
    provider = StubProvider(
        json.dumps(
            {"selected": [{"index": 9}, {"index": 0}, {"index": 0}, {"index": 1}]}
        )
    )
    sources, _ = await retriever.rerank(
        provider=provider, model="m", theme="t", candidates=candidates, top_k=5
    )
    assert [s["title"] for s in sources] == ["A", "B"]


@pytest.mark.asyncio
async def test_rerank_caps_at_topk():
    candidates = [_item(f"T{i}", f"body{i}") for i in range(6)]
    provider = StubProvider(
        json.dumps({"selected": [{"index": i, "relevance": 50} for i in range(6)]})
    )
    sources, _ = await retriever.rerank(
        provider=provider, model="m", theme="t", candidates=candidates, top_k=2
    )
    assert len(sources) == 2


# --- generator ---


def test_build_content_grounded_mode_includes_sources_and_citation_rule():
    sources = [
        {"title": "源1", "excerpt": "真实数据：增长 20%。"},
        {"title": "源2", "excerpt": "历史背景内容。"},
    ]
    msgs = generator.build_content_messages(theme="主题", sources=sources)
    system = msgs[0].content
    user = msgs[1].content
    assert "标注来源编号" in system
    assert "不得编造" in system or "不得凭空编造" in system
    assert "真实数据：增长 20%。" in user
    assert "[1]" in user and "[2]" in user


def test_build_content_no_source_mode_forbids_fabrication():
    msgs = generator.build_content_messages(theme="主题", sources=[])
    system = msgs[0].content
    assert "未检索到" in system
    assert "严禁编造" in system


def test_build_title_messages_shape():
    msgs = generator.build_title_messages(theme="主题")
    assert msgs[0].role == "system"
    assert msgs[1].role == "user"
    assert "主题" in msgs[1].content


# --- grounding review ---


@pytest.mark.asyncio
async def test_review_grounding_parses_unsupported_claims():
    provider = StubProvider(
        json.dumps(
            {
                "score": 60,
                "unsupported_claims": ["文中称增长 35%，素材无依据"],
                "issues": [],
            }
        )
    )
    out = await review_grounding(
        provider=provider, model="m", article="文章", sources_text="素材"
    )
    assert out["score"] == 60
    assert out["unsupported_claims"] == ["文中称增长 35%，素材无依据"]
    assert out["issues"] == []
