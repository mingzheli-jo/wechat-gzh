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
