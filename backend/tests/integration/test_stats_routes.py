import uuid
from datetime import UTC, datetime, timedelta

import pytest
from httpx import ASGITransport, AsyncClient

from app.accounts.models import Account
from app.api.deps import get_db
from app.main import create_app
from app.stats.models import WechatArticle


@pytest.fixture
def app(db_session):
    app = create_app()

    async def _override():
        yield db_session

    app.dependency_overrides[get_db] = _override
    return app


@pytest.fixture
async def auth_client(app):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        login = await client.post(
            "/api/auth/login",
            data={"username": "admin", "password": "hunter2"},
        )
        token = login.json()["access_token"]
        client.headers["Authorization"] = f"Bearer {token}"
        yield client


@pytest.fixture(autouse=True)
def stub_celery(monkeypatch):
    from app.tasks import stats as stats_task

    monkeypatch.setattr(
        stats_task.sync_one_account_stats,
        "delay",
        lambda *a, **k: type("R", (), {"id": "fake-job-id"})(),
        raising=False,
    )
    monkeypatch.setattr(
        stats_task.sync_all_accounts_stats,
        "delay",
        lambda *a, **k: type("R", (), {"id": "fake-job-id"})(),
        raising=False,
    )


async def _seed(db_session) -> tuple[Account, WechatArticle]:
    account = Account(
        name="测试号",
        wechat_appid="wx_test",
        wechat_secret="s",
        category="x",
        title_prompt="",
        content_prompt="",
        follower_count=1234,
        new_follow_yesterday=12,
        cancel_follow_yesterday=3,
        stats_synced_at=datetime.now(UTC),
    )
    db_session.add(account)
    await db_session.commit()
    await db_session.refresh(account)

    article = WechatArticle(
        account_id=account.id,
        msgid=100,
        article_idx=0,
        title="标题",
        publish_time=datetime.now(UTC) - timedelta(days=5),
        read_count=200,
        like_count=10,
        share_count=5,
        comment_count=7,
        last_synced_at=datetime.now(UTC),
    )
    db_session.add(article)
    await db_session.commit()
    await db_session.refresh(article)
    return account, article


async def test_list_accounts_returns_stats(auth_client, db_session):
    account, _ = await _seed(db_session)
    r = await auth_client.get("/api/stats/accounts")
    assert r.status_code == 200
    body = r.json()
    assert len(body) >= 1
    row = next(x for x in body if x["account_id"] == str(account.id))
    assert row["follower_count"] == 1234
    assert row["new_follow_yesterday"] == 12
    assert row["articles_count_30d"] == 1
    assert row["total_read_30d"] == 200


async def test_list_articles_filters_and_sorts(auth_client, db_session):
    account, _ = await _seed(db_session)
    r = await auth_client.get(
        f"/api/stats/accounts/{account.id}/articles?days=30&sort=read_count&order=desc"
    )
    assert r.status_code == 200
    body = r.json()
    assert len(body) == 1
    assert body[0]["msgid"] == 100
    assert body[0]["read_count"] == 200


async def test_list_articles_404_when_account_missing(auth_client):
    fake = uuid.uuid4()
    r = await auth_client.get(f"/api/stats/accounts/{fake}/articles")
    assert r.status_code == 404


async def test_refresh_all_enqueues(auth_client, db_session):
    r = await auth_client.post("/api/stats/refresh")
    assert r.status_code == 202
    body = r.json()
    assert body["status"] == "queued"
    assert body["job_id"] == "fake-job-id"


async def test_refresh_one_enqueues(auth_client, db_session):
    account, _ = await _seed(db_session)
    r = await auth_client.post(f"/api/stats/refresh?account_id={account.id}")
    assert r.status_code == 202
    assert r.json()["status"] == "queued"


async def test_refresh_one_404_when_account_missing(auth_client):
    fake = uuid.uuid4()
    r = await auth_client.post(f"/api/stats/refresh?account_id={fake}")
    assert r.status_code == 404


async def test_endpoints_require_auth(app):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        r = await client.get("/api/stats/accounts")
        assert r.status_code in (401, 403)
