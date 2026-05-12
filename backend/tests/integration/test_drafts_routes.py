import uuid

import pytest
from httpx import ASGITransport, AsyncClient

from app.accounts.models import Account
from app.api.deps import get_db
from app.drafts.models import Draft, DraftStatus
from app.library.models import LibraryItem, LibraryStatus
from app.main import create_app


@pytest.fixture
def app(db_session, monkeypatch):
    from app.tasks import rewrite as rewrite_module

    monkeypatch.setattr(
        rewrite_module.run_pipeline,
        "delay",
        lambda *a, **k: None,
        raising=False,
    )

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
        client.headers["Authorization"] = f"Bearer {login.json()['access_token']}"
        yield client


async def _seed(
    db_session, *, status: DraftStatus, regenerate_count: int = 0
) -> Draft:
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
        status=status,
        title="旧标题",
        content_html="<p>旧正文</p>",
        regenerate_count=regenerate_count,
    )
    db_session.add(draft)
    await db_session.commit()
    await db_session.refresh(draft)
    return draft


async def test_rewrite_again_blocked_at_cap(auth_client, db_session):
    draft = await _seed(
        db_session, status=DraftStatus.reviewed, regenerate_count=5
    )
    r = await auth_client.post(f"/api/drafts/{draft.id}/rewrite")
    assert r.status_code == 409
    assert "已达 5 次改写上限" in r.json()["detail"]

    await db_session.refresh(draft)
    assert draft.regenerate_count == 5


async def test_rewrite_again_increments_counter(auth_client, db_session):
    draft = await _seed(
        db_session, status=DraftStatus.reviewed, regenerate_count=2
    )
    r = await auth_client.post(f"/api/drafts/{draft.id}/rewrite")
    assert r.status_code == 202

    await db_session.refresh(draft)
    assert draft.regenerate_count == 3


async def test_rewrite_response_exposes_regenerate_count(auth_client, db_session):
    draft = await _seed(
        db_session, status=DraftStatus.reviewed, regenerate_count=1
    )
    r = await auth_client.post(f"/api/drafts/{draft.id}/rewrite")
    assert r.status_code == 202
    body = r.json()
    assert "regenerate_count" in body
    assert body["regenerate_count"] == 2


async def test_draft_detail_exposes_max_regenerations(auth_client, db_session):
    draft = await _seed(
        db_session, status=DraftStatus.reviewed, regenerate_count=0
    )
    r = await auth_client.get(f"/api/drafts/{draft.id}")
    assert r.status_code == 200
    body = r.json()
    assert body["regenerate_count"] == 0
    assert body["max_regenerations"] == 5


async def test_draft_detail_exposes_original_fields(auth_client, db_session):
    item = LibraryItem(
        source_url="https://mp.weixin.qq.com/s/originalUrl",
        original_title="原标题 A",
        original_author="原作者 X",
        original_content_text="第一段\n\n第二段\n\n第三段",
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
        title="改后",
        content_html="<p>改后正文</p>",
    )
    db_session.add(draft)
    await db_session.commit()

    r = await auth_client.get(f"/api/drafts/{draft.id}")
    assert r.status_code == 200
    body = r.json()
    assert body["source_url"] == "https://mp.weixin.qq.com/s/originalUrl"
    assert body["original_title"] == "原标题 A"
    assert body["original_author"] == "原作者 X"
    assert body["original_content_text"] == "第一段\n\n第二段\n\n第三段"


async def test_draft_list_exposes_source_url(auth_client, db_session):
    await _seed(db_session, status=DraftStatus.reviewed)
    r = await auth_client.get("/api/drafts")
    assert r.status_code == 200
    items = r.json()["items"]
    assert len(items) >= 1
    assert all("source_url" in d for d in items)
    assert any(d["source_url"] and d["source_url"].startswith("https://") for d in items)
