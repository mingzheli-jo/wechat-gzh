import uuid

import pytest

from app.accounts.models import Account
from app.stats import service
from app.tasks import stats as stats_task


async def _seed_account(db_session) -> Account:
    account = Account(
        name="测试号",
        wechat_appid="wx12345",
        wechat_secret="secret",
        category="职场",
        title_prompt="",
        content_prompt="",
    )
    db_session.add(account)
    await db_session.commit()
    await db_session.refresh(account)
    return account


@pytest.fixture
def stub_clients(monkeypatch):
    async def fake_token(*a, **kw):
        return "tok"

    async def fake_user_summary(*a, **kw):
        return [{"ref_date": "2026-05-17", "new_user": 12, "cancel_user": 3}]

    async def fake_user_cumulate(*a, **kw):
        return [{"ref_date": "2026-05-17", "cumulate_user": 1234}]

    async def fake_article_total(*a, **kw):
        return [
            {
                "msgid": "100_0",
                "title": "标题 A",
                "ref_date": "2026-05-17",
                "details": [
                    {
                        "stat_date": "2026-05-17",
                        "int_page_read_count": 200,
                        "share_count": 5,
                        "like_count": 8,
                    }
                ],
            }
        ]

    async def fake_comment_count(*a, **kw):
        return 7

    monkeypatch.setattr("app.wechat.token.get_access_token", fake_token)
    monkeypatch.setattr("app.wechat.stats.fetch_user_summary", fake_user_summary)
    monkeypatch.setattr("app.wechat.stats.fetch_user_cumulate", fake_user_cumulate)
    monkeypatch.setattr("app.wechat.stats.fetch_article_total", fake_article_total)
    monkeypatch.setattr("app.wechat.stats.fetch_comment_count", fake_comment_count)


@pytest.mark.asyncio
async def test_sync_one_account_updates_follower_fields(db_session, stub_clients):
    account = await _seed_account(db_session)
    await stats_task._sync_one_account(db_session, account)
    await db_session.refresh(account)
    assert account.follower_count == 1234
    assert account.new_follow_yesterday == 12
    assert account.cancel_follow_yesterday == 3
    assert account.stats_synced_at is not None


@pytest.mark.asyncio
async def test_sync_one_account_upserts_articles(db_session, stub_clients):
    account = await _seed_account(db_session)
    await stats_task._sync_one_account(db_session, account)
    rows = await service.list_articles(db_session, account.id)
    assert len(rows) == 1
    assert rows[0].msgid == 100
    assert rows[0].article_idx == 0
    assert rows[0].title == "标题 A"
    assert rows[0].read_count == 200
    assert rows[0].share_count == 5
    assert rows[0].like_count == 8
    assert rows[0].comment_count == 7


@pytest.mark.asyncio
async def test_sync_one_account_keeps_old_comment_count_when_comment_fails(
    db_session, stub_clients, monkeypatch
):
    account = await _seed_account(db_session)
    await stats_task._sync_one_account(db_session, account)
    rows = await service.list_articles(db_session, account.id)
    assert rows[0].comment_count == 7

    async def boom(*a, **kw):
        raise RuntimeError("comment api down")

    monkeypatch.setattr("app.wechat.stats.fetch_comment_count", boom)
    await stats_task._sync_one_account(db_session, account)

    rows = await service.list_articles(db_session, account.id)
    assert rows[0].comment_count == 7
    assert rows[0].read_count == 200


@pytest.mark.asyncio
async def test_sync_all_accounts_continues_after_per_account_error(
    db_session, monkeypatch
):
    a1 = Account(
        name="A1",
        wechat_appid="wx_a1",
        wechat_secret="s",
        category="x",
        title_prompt="",
        content_prompt="",
    )
    a2 = Account(
        name="A2",
        wechat_appid="wx_a2",
        wechat_secret="s",
        category="x",
        title_prompt="",
        content_prompt="",
    )
    db_session.add_all([a1, a2])
    await db_session.commit()
    await db_session.refresh(a1)
    await db_session.refresh(a2)

    visited: list[uuid.UUID] = []

    async def maybe_fail(db, account):
        visited.append(account.id)
        if account.name == "A1":
            raise RuntimeError("boom A1")

    monkeypatch.setattr(stats_task, "_sync_one_account", maybe_fail)
    await stats_task._sync_all(db_session)

    assert set(visited) == {a1.id, a2.id}
