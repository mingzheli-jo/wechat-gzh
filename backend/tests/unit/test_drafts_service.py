import uuid

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.accounts.models import Account
from app.drafts import service
from app.drafts.models import Draft, DraftStatus
from app.library.models import LibraryItem, LibraryStatus


async def _seed_draft(db_session: AsyncSession, *, regenerate_count: int = 0) -> Draft:
    item = LibraryItem(
        source_url=f"https://x/{uuid.uuid4()}",
        original_title="原标题",
        original_content_text="原文 " * 30,
        status=LibraryStatus.done,
    )
    account = Account(
        name="A",
        wechat_appid="wx",
        wechat_secret="s",
        category="职场",
        title_prompt="t",
        content_prompt="c",
    )
    db_session.add_all([item, account])
    await db_session.commit()
    await db_session.refresh(item)
    await db_session.refresh(account)

    draft = Draft(
        library_item_id=item.id,
        account_id=account.id,
        status=DraftStatus.reviewed,
        title="旧标题",
        content_html="<p>旧正文</p>",
        regenerate_count=regenerate_count,
    )
    db_session.add(draft)
    await db_session.commit()
    await db_session.refresh(draft)
    return draft


@pytest.mark.asyncio
async def test_reset_for_rewrite_increments_regenerate_count(db_session: AsyncSession) -> None:
    draft = await _seed_draft(db_session, regenerate_count=2)
    reset = await service.reset_for_rewrite(db_session, draft)
    assert reset.regenerate_count == 3


@pytest.mark.asyncio
async def test_reset_for_rewrite_clears_generated_fields(db_session: AsyncSession) -> None:
    draft = await _seed_draft(db_session, regenerate_count=0)
    reset = await service.reset_for_rewrite(db_session, draft)
    assert reset.title is None
    assert reset.content_html is None
    assert reset.status == DraftStatus.draft
    assert reset.regenerate_count == 1
