import json
from typing import Any

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker

from app.ai_providers.base import BaseProvider, ChatResult, Message, TokenUsage
from app.ai_providers.registry import get_registry
from app.creator.models import CreationInputMode, CreationStatus, ThemeCreation
from app.library.models import LibraryItem, LibraryStatus
from app.tasks.create import _do_create


class StubProvider(BaseProvider):
    """Branches on the system prompt to return the right shape per stage."""

    name = "stub"

    def __init__(self) -> None:
        self.calls: list[str] = []

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
        system = messages[0].content
        self.calls.append(system[:24])
        usage = TokenUsage(prompt_tokens=10, completion_tokens=5)
        if json_mode:
            if "关键词" in system:
                content = json.dumps({"keywords": ["新能源", "电池"]})
            elif "资料筛选员" in system:
                content = json.dumps({"selected": [{"index": 0, "relevance": 92}]})
            elif "事实核查" in system:
                content = json.dumps(
                    {"score": 85, "unsupported_claims": [], "issues": []}
                )
            else:
                content = json.dumps({"score": 0})
            return ChatResult(content=content, model=model, usage=usage)
        if "标题编辑" in system:
            return ChatResult(content="生成的标题", model=model, usage=usage)
        # content generation
        return ChatResult(
            content="## 一、引子\n基于素材的正文[1]。", model=model, usage=usage
        )


@pytest.fixture
def stub_registry(monkeypatch):
    reg = get_registry()
    reg.reset()
    p = StubProvider()
    reg.register(p)
    reg.bind_role("writer", provider="stub", model="m")
    reg.bind_role("reviewer", provider="stub", model="m")
    reg.bind_role("lite", provider="stub", model="m")

    async def noop(_session):
        return None

    monkeypatch.setattr("app.tasks.create.load_from_db", noop)
    return p


@pytest.mark.asyncio
async def test_creation_pipeline_manual_mode_grounded(
    db_engine, db_session, stub_registry
):
    # Seed a library item that the keyword "新能源" will match.
    item = LibraryItem(
        source_url="https://mp.weixin.qq.com/s/seed1",
        original_title="新能源汽车销量创新高",
        original_content_text="2025 年新能源汽车销量同比增长，电池产能提升。" * 5,
        status=LibraryStatus.done,
    )
    db_session.add(item)
    await db_session.commit()

    creation = ThemeCreation(
        input_mode=CreationInputMode.manual,
        extracted_theme="围绕新能源汽车与电池产业的发展主题。",
        status=CreationStatus.pending,
    )
    db_session.add(creation)
    await db_session.commit()

    await _do_create(creation.id)

    fresh_sm = async_sessionmaker(db_engine, expire_on_commit=False)
    async with fresh_sm() as fresh:
        refreshed = (
            await fresh.execute(
                select(ThemeCreation).where(ThemeCreation.id == creation.id)
            )
        ).scalar_one()
        assert refreshed.status == CreationStatus.done
        assert refreshed.generated_title == "生成的标题"
        assert refreshed.generated_content_html
        assert "正文" in (refreshed.generated_content_md or "")
        # Retrieval found the seeded real article and stored it as a source.
        assert refreshed.retrieved_sources
        assert refreshed.retrieved_sources[0]["library_item_id"] == str(item.id)
        # Excerpt is the real article text, not model-invented.
        assert "新能源汽车" in refreshed.retrieved_sources[0]["excerpt"]
        # Fact-consistency review ran.
        assert refreshed.fact_check is not None
        assert refreshed.fact_check["score"] == 85
