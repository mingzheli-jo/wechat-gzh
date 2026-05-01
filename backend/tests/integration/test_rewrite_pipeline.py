import json
from typing import Any

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker

from app.accounts.models import Account
from app.ai_providers.base import BaseProvider, ChatResult, Message, TokenUsage
from app.ai_providers.registry import get_registry
from app.drafts.models import Draft, DraftStatus, ReviewReport
from app.library.models import LibraryItem, LibraryStatus
from app.tasks.rewrite import _do_rewrite


class StubProvider(BaseProvider):
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
        last = messages[-1].content
        self.calls.append(last[:50])
        if json_mode:
            return ChatResult(
                content=json.dumps(
                    {"score": 88, "issues": [], "similarity": 0.2}
                ),
                model=model,
                usage=TokenUsage(prompt_tokens=10, completion_tokens=5),
            )
        if "标题" in last and "改写" in last:
            return ChatResult(
                content="新标题", model=model, usage=TokenUsage(10, 5)
            )
        return ChatResult(
            content="<p>改写正文</p>", model=model, usage=TokenUsage(10, 5)
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

    monkeypatch.setattr("app.tasks.rewrite._ensure_registry", noop)
    return p


@pytest.mark.asyncio
async def test_rewrite_pipeline_produces_draft_and_report(db_engine, db_session, stub_registry):
    item = LibraryItem(
        source_url="https://x/1",
        original_title="原标题",
        original_content_text="原文 " * 50,
        status=LibraryStatus.done,
    )
    account = Account(
        name="A",
        wechat_appid="wx",
        wechat_secret="s",
        category="职场",
        title_prompt="改写",
        content_prompt="改写",
        style_desc="",
    )
    db_session.add_all([item, account])
    await db_session.commit()
    draft = Draft(
        library_item_id=item.id,
        account_id=account.id,
        status=DraftStatus.draft,
    )
    db_session.add(draft)
    await db_session.commit()

    await _do_rewrite(draft.id, None, None)

    fresh_sm = async_sessionmaker(db_engine, expire_on_commit=False)
    async with fresh_sm() as fresh:
        refreshed = (
            await fresh.execute(select(Draft).where(Draft.id == draft.id))
        ).scalar_one()
        assert refreshed.status == DraftStatus.reviewed
        assert refreshed.title == "新标题"
        assert "改写正文" in refreshed.content_html
        assert refreshed.review_report_id is not None
        report = (
            await fresh.execute(
                select(ReviewReport).where(
                    ReviewReport.id == refreshed.review_report_id
                )
            )
        ).scalar_one()
        assert report.overall_score is not None
        assert report.compliance["score"] == 88
