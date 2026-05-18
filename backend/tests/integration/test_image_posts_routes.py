import pytest
from httpx import ASGITransport, AsyncClient

from app.accounts.models import Account
from app.api.deps import get_db
from app.main import create_app


@pytest.fixture
def app(db_session, monkeypatch, tmp_path):
    from app.tasks import image_pipeline

    monkeypatch.setattr(
        image_pipeline.generate_image_post, "delay",
        lambda *a, **k: None, raising=False,
    )
    monkeypatch.setattr(
        image_pipeline.compose_and_push_image_post, "delay",
        lambda *a, **k: None, raising=False,
    )
    monkeypatch.setenv("IMAGE_STORAGE_DIR", str(tmp_path))
    from app.config import get_settings
    get_settings.cache_clear()

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


async def _seed_account_with_ref(db_session, tmp_path) -> Account:
    ref_path = tmp_path / "accounts" / "char.png"
    ref_path.parent.mkdir(parents=True, exist_ok=True)
    ref_path.write_bytes(b"fake_png")
    account = Account(
        name="A",
        wechat_appid="wx",
        wechat_secret="s",
        category="职场",
        character_reference_path=str(ref_path),
    )
    db_session.add(account)
    await db_session.commit()
    await db_session.refresh(account)
    return account


async def test_create_image_post(auth_client, db_session, tmp_path):
    account = await _seed_account_with_ref(db_session, tmp_path)
    r = await auth_client.post(
        "/api/image-posts",
        json={
            "account_id": str(account.id),
            "template": "two_panel_contrast",
            "topic": "测试主题",
            "tone": "self_mockery",
        },
    )
    assert r.status_code == 202, r.text
    body = r.json()
    assert body["topic"] == "测试主题"
    assert body["status"] == "pending"


async def test_create_image_post_requires_character_reference(
    auth_client, db_session
):
    account = Account(
        name="NoRef",
        wechat_appid="wx",
        wechat_secret="s",
        category="x",
        # no character_reference_path
    )
    db_session.add(account)
    await db_session.commit()
    r = await auth_client.post(
        "/api/image-posts",
        json={
            "account_id": str(account.id),
            "template": "two_panel_contrast",
            "topic": "x",
        },
    )
    assert r.status_code == 400
    assert "角色参考图" in r.json()["detail"]


async def test_list_image_posts(auth_client, db_session, tmp_path):
    account = await _seed_account_with_ref(db_session, tmp_path)
    for i in range(3):
        await auth_client.post(
            "/api/image-posts",
            json={
                "account_id": str(account.id),
                "template": "single_panel_caption",
                "topic": f"t{i}",
            },
        )
    r = await auth_client.get("/api/image-posts")
    assert r.status_code == 200
    body = r.json()
    assert body["total"] == 3
    assert len(body["items"]) == 3


async def test_get_image_post_detail(auth_client, db_session, tmp_path):
    account = await _seed_account_with_ref(db_session, tmp_path)
    create = await auth_client.post(
        "/api/image-posts",
        json={
            "account_id": str(account.id),
            "template": "two_panel_contrast",
            "topic": "t",
        },
    )
    post_id = create.json()["id"]
    r = await auth_client.get(f"/api/image-posts/{post_id}")
    assert r.status_code == 200
    body = r.json()
    assert body["id"] == post_id
    assert "captions" in body  # detail-only field


async def test_patch_image_post_updates_captions(auth_client, db_session, tmp_path):
    account = await _seed_account_with_ref(db_session, tmp_path)
    create = await auth_client.post(
        "/api/image-posts",
        json={
            "account_id": str(account.id),
            "template": "two_panel_contrast",
            "topic": "t",
        },
    )
    post_id = create.json()["id"]
    r = await auth_client.patch(
        f"/api/image-posts/{post_id}",
        json={"captions": ["新上文案", "新下文案"]},
    )
    assert r.status_code == 200
    assert r.json()["captions"] == ["新上文案", "新下文案"]


async def test_delete_image_post(auth_client, db_session, tmp_path):
    account = await _seed_account_with_ref(db_session, tmp_path)
    create = await auth_client.post(
        "/api/image-posts",
        json={
            "account_id": str(account.id),
            "template": "two_panel_contrast",
            "topic": "t",
        },
    )
    post_id = create.json()["id"]
    r = await auth_client.delete(f"/api/image-posts/{post_id}")
    assert r.status_code == 204
    r2 = await auth_client.get(f"/api/image-posts/{post_id}")
    assert r2.status_code == 404
