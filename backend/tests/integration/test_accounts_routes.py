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


async def test_upload_default_cover_success(auth_client, monkeypatch):
    from app.accounts import routes as accounts_routes

    async def fake_token(*, account_id, appid, secret, force_refresh=False):
        return "fake_token"

    async def fake_upload(*, access_token, file_path):
        return {"media_id": "test_media_xyz", "url": "https://x/y.jpg"}

    monkeypatch.setattr(accounts_routes, "get_access_token", fake_token)
    monkeypatch.setattr(accounts_routes, "upload_image", fake_upload)

    create = await auth_client.post(
        "/api/accounts",
        json={
            "name": "uploader",
            "wechat_appid": "wx_up",
            "wechat_secret": "s",
            "category": "职场",
        },
    )
    account_id = create.json()["id"]
    files = {"file": ("cover.jpg", b"\xff\xd8\xff\xe0fake_jpeg", "image/jpeg")}
    r = await auth_client.post(
        f"/api/accounts/{account_id}/default-cover", files=files
    )
    assert r.status_code == 200, r.text
    assert r.json()["default_thumb_media_id"] == "test_media_xyz"


async def test_upload_default_cover_rejects_oversize(auth_client):
    create = await auth_client.post(
        "/api/accounts",
        json={
            "name": "big",
            "wechat_appid": "wx_big",
            "wechat_secret": "s",
            "category": "职场",
        },
    )
    account_id = create.json()["id"]
    files = {
        "file": ("big.jpg", b"x" * (11 * 1024 * 1024), "image/jpeg"),
    }
    r = await auth_client.post(
        f"/api/accounts/{account_id}/default-cover", files=files
    )
    assert r.status_code == 413


async def test_upload_default_cover_rejects_non_image(auth_client):
    create = await auth_client.post(
        "/api/accounts",
        json={
            "name": "txt",
            "wechat_appid": "wx_txt",
            "wechat_secret": "s",
            "category": "职场",
        },
    )
    account_id = create.json()["id"]
    files = {"file": ("evil.txt", b"hello", "text/plain")}
    r = await auth_client.post(
        f"/api/accounts/{account_id}/default-cover", files=files
    )
    assert r.status_code == 415


async def test_upload_default_cover_404_when_account_missing(auth_client):
    import uuid as _uuid

    files = {"file": ("cover.jpg", b"data", "image/jpeg")}
    r = await auth_client.post(
        f"/api/accounts/{_uuid.uuid4()}/default-cover", files=files
    )
    assert r.status_code == 404


async def test_clear_default_cover(auth_client, monkeypatch):
    from app.accounts import routes as accounts_routes

    async def fake_token(*, account_id, appid, secret, force_refresh=False):
        return "fake_token"

    async def fake_upload(*, access_token, file_path):
        return {"media_id": "abc123", "url": ""}

    monkeypatch.setattr(accounts_routes, "get_access_token", fake_token)
    monkeypatch.setattr(accounts_routes, "upload_image", fake_upload)

    create = await auth_client.post(
        "/api/accounts",
        json={
            "name": "clearable",
            "wechat_appid": "wx_cl",
            "wechat_secret": "s",
            "category": "职场",
        },
    )
    account_id = create.json()["id"]
    files = {"file": ("c.jpg", b"\xff\xd8\xff\xe0", "image/jpeg")}
    up = await auth_client.post(
        f"/api/accounts/{account_id}/default-cover", files=files
    )
    assert up.json()["default_thumb_media_id"] == "abc123"

    r = await auth_client.delete(f"/api/accounts/{account_id}/default-cover")
    assert r.status_code == 200
    assert r.json()["default_thumb_media_id"] is None


async def test_upload_character_reference_success(auth_client, tmp_path, monkeypatch):
    monkeypatch.setenv("IMAGE_STORAGE_DIR", str(tmp_path))
    from app.config import get_settings
    get_settings.cache_clear()

    create = await auth_client.post(
        "/api/accounts",
        json={
            "name": "char-test",
            "wechat_appid": "wx_ch",
            "wechat_secret": "s",
            "category": "职场",
        },
    )
    account_id = create.json()["id"]
    files = {"file": ("char.png", b"\x89PNG\r\n\x1a\nfake", "image/png")}
    r = await auth_client.post(
        f"/api/accounts/{account_id}/character-reference", files=files
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["character_reference_path"]
    assert body["character_reference_updated_at"]


async def test_upload_character_reference_rejects_oversize(auth_client):
    create = await auth_client.post(
        "/api/accounts",
        json={"name": "big", "wechat_appid": "wx", "wechat_secret": "s", "category": "x"},
    )
    account_id = create.json()["id"]
    files = {"file": ("big.png", b"x" * (11 * 1024 * 1024), "image/png")}
    r = await auth_client.post(
        f"/api/accounts/{account_id}/character-reference", files=files
    )
    assert r.status_code == 413


async def test_upload_character_reference_rejects_non_image(auth_client):
    create = await auth_client.post(
        "/api/accounts",
        json={"name": "txt", "wechat_appid": "wx", "wechat_secret": "s", "category": "x"},
    )
    account_id = create.json()["id"]
    files = {"file": ("evil.txt", b"hello", "text/plain")}
    r = await auth_client.post(
        f"/api/accounts/{account_id}/character-reference", files=files
    )
    assert r.status_code == 415


async def test_clear_character_reference(auth_client, tmp_path, monkeypatch):
    monkeypatch.setenv("IMAGE_STORAGE_DIR", str(tmp_path))
    from app.config import get_settings
    get_settings.cache_clear()

    create = await auth_client.post(
        "/api/accounts",
        json={"name": "clear", "wechat_appid": "wx", "wechat_secret": "s", "category": "x"},
    )
    account_id = create.json()["id"]
    files = {"file": ("c.png", b"\x89PNG\r\n\x1a\nfake", "image/png")}
    await auth_client.post(
        f"/api/accounts/{account_id}/character-reference", files=files
    )
    r = await auth_client.delete(f"/api/accounts/{account_id}/character-reference")
    assert r.status_code == 200
    assert r.json()["character_reference_path"] is None
