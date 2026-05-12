import pytest
from httpx import ASGITransport, AsyncClient

from app.api.deps import get_db
from app.main import create_app


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


async def test_create_and_list(auth_client):
    payload = {
        "name": "测试号",
        "wechat_appid": "wx12345",
        "wechat_secret": "super-secret",
        "category": "职场",
        "title_prompt": "改写更吸引",
        "content_prompt": "保持原意",
        "style_desc": "专业克制",
    }
    r = await auth_client.post("/api/accounts", json=payload)
    assert r.status_code == 201
    body = r.json()
    assert body["name"] == "测试号"
    assert "wechat_secret" not in body

    r = await auth_client.get("/api/accounts")
    assert len(r.json()) == 1


async def test_get_update_delete(auth_client):
    create = await auth_client.post(
        "/api/accounts",
        json={
            "name": "A",
            "wechat_appid": "wx",
            "wechat_secret": "s",
            "category": "职场",
        },
    )
    account_id = create.json()["id"]
    assert (await auth_client.get(f"/api/accounts/{account_id}")).status_code == 200
    upd = await auth_client.patch(
        f"/api/accounts/{account_id}", json={"name": "B"}
    )
    assert upd.json()["name"] == "B"
    assert (await auth_client.delete(f"/api/accounts/{account_id}")).status_code == 204
    assert (await auth_client.get(f"/api/accounts/{account_id}")).status_code == 404


async def test_routes_require_auth(app):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        assert (await client.get("/api/accounts")).status_code == 401


async def test_account_response_exposes_default_thumb_media_id(auth_client):
    r = await auth_client.post(
        "/api/accounts",
        json={
            "name": "default-cover-test",
            "wechat_appid": "wx_dc",
            "wechat_secret": "s",
            "category": "职场",
        },
    )
    assert r.status_code == 201
    body = r.json()
    assert "default_thumb_media_id" in body
    assert body["default_thumb_media_id"] is None
