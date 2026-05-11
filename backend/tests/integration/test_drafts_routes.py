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
