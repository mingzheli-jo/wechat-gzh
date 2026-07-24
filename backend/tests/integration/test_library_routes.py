import pytest
from httpx import ASGITransport, AsyncClient

from app.api.deps import get_db
from app.main import create_app


@pytest.fixture
def app(db_session, monkeypatch):
    from app.tasks import crawl

    monkeypatch.setattr(
        crawl.crawl_library_item, "delay", lambda *a, **k: None, raising=False
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


async def test_ingest_creates_pending_items(auth_client):
    r = await auth_client.post(
        "/api/library",
        json={
            "urls": [
                "https://mp.weixin.qq.com/s/abc",
                "https://mp.weixin.qq.com/s/def",
            ],
            "tags": ["职场"],
        },
    )
    assert r.status_code == 201
    assert len(r.json()) == 2
    assert all(item["status"] == "pending" for item in r.json())


async def test_list_filtered_by_tag(auth_client):
    await auth_client.post(
        "/api/library", json={"urls": ["https://x/1"], "tags": ["a"]}
    )
    await auth_client.post(
        "/api/library", json={"urls": ["https://x/2"], "tags": ["b"]}
    )
    r = await auth_client.get("/api/library?tag=a")
    assert len(r.json()) == 1


async def test_update_tags_and_delete(auth_client):
    create = await auth_client.post(
        "/api/library", json={"urls": ["https://x/3"], "tags": []}
    )
    item_id = create.json()[0]["id"]
    upd = await auth_client.patch(
        f"/api/library/{item_id}/tags", json={"tags": ["养生"]}
    )
    assert upd.json()["tags"] == ["养生"]
    delete = await auth_client.delete(f"/api/library/{item_id}")
    assert delete.status_code == 204


async def test_ingest_same_url_twice_is_idempotent(auth_client):
    """自动出稿每天按热榜搜素材，撞到已入库链接是常态，不能 500。"""
    url = "https://news.qq.com/rain/a/20260724A01"
    first = await auth_client.post("/api/library", json={"urls": [url]})
    assert first.status_code == 201
    second = await auth_client.post("/api/library", json={"urls": [url]})
    assert second.status_code == 201
    assert second.json()[0]["id"] == first.json()[0]["id"]

    listing = await auth_client.get("/api/library")
    assert [i["source_url"] for i in listing.json()].count(url) == 1


async def test_reingest_failed_item_redispatches_crawl(auth_client, db_session):
    """抓失败过的条目重新提交要能再抓一次，否则失败的素材永远救不回来。"""
    from sqlalchemy import select

    from app.library.models import LibraryItem, LibraryStatus

    url = "https://news.qq.com/rain/a/20260724A02"
    created = await auth_client.post("/api/library", json={"urls": [url]})
    item_id = created.json()[0]["id"]

    item = (
        await db_session.execute(
            select(LibraryItem).where(LibraryItem.source_url == url)
        )
    ).scalar_one()
    item.status = LibraryStatus.failed
    item.error_msg = "parse error: 正文过短"
    await db_session.commit()

    again = await auth_client.post("/api/library", json={"urls": [url]})
    assert again.status_code == 201
    assert again.json()[0]["id"] == item_id
    assert again.json()[0]["status"] == "pending"


async def test_reingest_pending_item_redispatches_crawl(auth_client, db_session):
    """派发本身失败过的条目会一直停在 pending，重新提交必须再派一次，否则永远卡住。"""
    calls = []
    from app.tasks import crawl

    crawl.crawl_library_item.delay = lambda *a, **k: calls.append(a)  # type: ignore[method-assign]

    url = "https://news.qq.com/rain/a/20260724A05"
    first = await auth_client.post("/api/library", json={"urls": [url]})
    assert first.json()[0]["status"] == "pending"
    again = await auth_client.post("/api/library", json={"urls": [url]})
    assert again.json()[0]["id"] == first.json()[0]["id"]
    assert len(calls) == 2


async def test_reingest_merges_tags(auth_client):
    """同一篇报道被不同热榜话题命中时，新 tag 不能被无声吞掉。"""
    url = "https://news.qq.com/rain/a/20260724A06"
    await auth_client.post("/api/library", json={"urls": [url], "tags": ["养老金"]})
    await auth_client.post("/api/library", json={"urls": [url], "tags": ["退休"]})
    r = await auth_client.get("/api/library?tag=退休")
    assert [i["source_url"] for i in r.json()] == [url]
    assert set(r.json()[0]["tags"]) == {"养老金", "退休"}
