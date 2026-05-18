import uuid
from datetime import UTC, datetime, timedelta

import pytest

from app.accounts.models import Account
from app.stats import service


async def _seed_account(db_session, *, name: str = "A") -> Account:
    account = Account(
        name=name,
        wechat_appid=f"wx{uuid.uuid4().hex[:8]}",
        wechat_secret="s",
        category="职场",
        title_prompt="t",
        content_prompt="c",
    )
    db_session.add(account)
    await db_session.commit()
    await db_session.refresh(account)
    return account


@pytest.mark.asyncio
async def test_upsert_account_stats_sets_fields(db_session):
    account = await _seed_account(db_session)
    now = datetime.now(UTC)
    await service.upsert_account_stats(
        db_session,
        account.id,
        follower_count=1234,
        new_follow=12,
        cancel_follow=3,
        synced_at=now,
    )
    await db_session.refresh(account)
    assert account.follower_count == 1234
    assert account.new_follow_yesterday == 12
    assert account.cancel_follow_yesterday == 3
    assert account.stats_synced_at == now


@pytest.mark.asyncio
async def test_upsert_article_creates_then_updates(db_session):
    account = await _seed_account(db_session)
    pub = datetime.now(UTC) - timedelta(days=5)
    synced = datetime.now(UTC)

    await service.upsert_article(
        db_session,
        account.id,
        msgid=100,
        article_idx=0,
        title="标题",
        publish_time=pub,
        read_count=100,
        like_count=10,
        share_count=5,
        last_synced_at=synced,
    )
    await service.upsert_article(
        db_session,
        account.id,
        msgid=100,
        article_idx=0,
        title="标题改",
        publish_time=pub,
        read_count=200,
        like_count=20,
        share_count=10,
        last_synced_at=synced,
    )
    rows = await service.list_articles(db_session, account.id)
    assert len(rows) == 1
    assert rows[0].read_count == 200
    assert rows[0].title == "标题改"
    assert rows[0].comment_count == 0


@pytest.mark.asyncio
async def test_update_comment_count_only_touches_comment_column(db_session):
    account = await _seed_account(db_session)
    pub = datetime.now(UTC) - timedelta(days=5)
    synced = datetime.now(UTC)

    await service.upsert_article(
        db_session,
        account.id,
        msgid=100,
        article_idx=0,
        title="标题",
        publish_time=pub,
        read_count=100,
        like_count=10,
        share_count=5,
        last_synced_at=synced,
    )
    await service.update_comment_count(db_session, account.id, 100, 0, 42)

    rows = await service.list_articles(db_session, account.id)
    assert rows[0].comment_count == 42
    assert rows[0].read_count == 100


@pytest.mark.asyncio
async def test_list_account_stats_derives_30d_window(db_session):
    account = await _seed_account(db_session)
    now = datetime.now(UTC)
    synced = now

    await service.upsert_article(
        db_session,
        account.id,
        msgid=100,
        article_idx=0,
        title="新",
        publish_time=now - timedelta(days=10),
        read_count=100,
        like_count=10,
        share_count=5,
        last_synced_at=synced,
    )
    await service.upsert_article(
        db_session,
        account.id,
        msgid=200,
        article_idx=0,
        title="旧",
        publish_time=now - timedelta(days=40),
        read_count=999,
        like_count=99,
        share_count=99,
        last_synced_at=synced,
    )
    rows = await service.list_account_stats(db_session)
    assert len(rows) == 1
    row = rows[0]
    assert row.account_id == account.id
    assert row.articles_count_30d == 1
    assert row.total_read_30d == 100


@pytest.mark.asyncio
async def test_list_articles_filters_by_days_and_sorts(db_session):
    account = await _seed_account(db_session)
    now = datetime.now(UTC)
    synced = now

    await service.upsert_article(
        db_session,
        account.id,
        msgid=100,
        article_idx=0,
        title="低阅读",
        publish_time=now - timedelta(days=2),
        read_count=50,
        like_count=1,
        share_count=1,
        last_synced_at=synced,
    )
    await service.upsert_article(
        db_session,
        account.id,
        msgid=200,
        article_idx=0,
        title="高阅读",
        publish_time=now - timedelta(days=5),
        read_count=500,
        like_count=1,
        share_count=1,
        last_synced_at=synced,
    )
    await service.upsert_article(
        db_session,
        account.id,
        msgid=300,
        article_idx=0,
        title="窗口外",
        publish_time=now - timedelta(days=40),
        read_count=9999,
        like_count=1,
        share_count=1,
        last_synced_at=synced,
    )

    rows = await service.list_articles(db_session, account.id)
    assert [r.title for r in rows] == ["低阅读", "高阅读"]

    rows = await service.list_articles(
        db_session, account.id, sort="read_count", order="desc"
    )
    assert [r.title for r in rows] == ["高阅读", "低阅读"]

    rows = await service.list_articles(db_session, account.id, days=7)
    assert [r.title for r in rows] == ["低阅读", "高阅读"]


@pytest.mark.asyncio
async def test_get_account_stats_returns_none_for_missing(db_session):
    fake_id = uuid.uuid4()
    row = await service.get_account_stats(db_session, fake_id)
    assert row is None
