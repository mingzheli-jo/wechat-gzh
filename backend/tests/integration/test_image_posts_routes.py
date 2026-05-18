import uuid

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


async def test_list_filters_by_status(auth_client, db_session, tmp_path):
    """status query param actually filters; FastAPI enum-from-querystring path."""
    from app.image_posts.models import ImagePost, ImagePostStatus

    account = await _seed_account_with_ref(db_session, tmp_path)
    # Create one via API (status=pending) ...
    await auth_client.post(
        "/api/image-posts",
        json={
            "account_id": str(account.id),
            "template": "single_panel_caption",
            "topic": "pending-one",
        },
    )
    # ... and one directly with status=generated so the filter has something
    # to separate.
    generated = ImagePost(
        account_id=account.id,
        template="single_panel_caption",
        topic="generated-one",
        status=ImagePostStatus.generated,
    )
    db_session.add(generated)
    await db_session.commit()

    r_all = await auth_client.get("/api/image-posts")
    assert r_all.json()["total"] == 2

    r_pending = await auth_client.get("/api/image-posts?status=pending")
    assert r_pending.status_code == 200
    body = r_pending.json()
    assert body["total"] == 1
    assert body["items"][0]["topic"] == "pending-one"

    r_generated = await auth_client.get("/api/image-posts?status=generated")
    assert r_generated.json()["total"] == 1
    assert r_generated.json()["items"][0]["topic"] == "generated-one"


async def test_create_rejects_wrong_panel_asset_count(
    auth_client, db_session, tmp_path
):
    """two_panel_contrast.panel_count==2; passing 1 asset id must 400."""
    from app.image_posts.models import ImageAsset, ImageAssetSource

    account = await _seed_account_with_ref(db_session, tmp_path)
    asset = ImageAsset(
        account_id=account.id,
        image_path=str(tmp_path / "a.png"),
        scene_prompt="s",
        tags=[],
        source=ImageAssetSource.ai_generated,
    )
    db_session.add(asset)
    await db_session.commit()
    await db_session.refresh(asset)

    r = await auth_client.post(
        "/api/image-posts",
        json={
            "account_id": str(account.id),
            "template": "two_panel_contrast",
            "topic": "t",
            "panel_asset_ids": [str(asset.id)],
        },
    )
    assert r.status_code == 400
    assert "panel_count" in r.json()["detail"]


async def test_create_rejects_foreign_asset(auth_client, db_session, tmp_path):
    """asset belonging to another account must 400 (cross-account guard)."""
    from app.accounts.models import Account
    from app.image_posts.models import ImageAsset, ImageAssetSource

    account = await _seed_account_with_ref(db_session, tmp_path)
    other = Account(
        name="Other",
        wechat_appid="wx2",
        wechat_secret="s2",
        category="x",
        character_reference_path=str(tmp_path / "other.png"),
    )
    db_session.add(other)
    await db_session.commit()
    await db_session.refresh(other)
    foreign_asset = ImageAsset(
        account_id=other.id,
        image_path=str(tmp_path / "foreign.png"),
        scene_prompt="s",
        tags=[],
        source=ImageAssetSource.ai_generated,
    )
    db_session.add(foreign_asset)
    await db_session.commit()
    await db_session.refresh(foreign_asset)

    r = await auth_client.post(
        "/api/image-posts",
        json={
            "account_id": str(account.id),
            "template": "single_panel_caption",
            "topic": "t",
            "panel_asset_ids": [str(foreign_asset.id)],
        },
    )
    assert r.status_code == 400
    assert "asset_id" in r.json()["detail"]


async def test_regenerate_captions_route(auth_client, db_session, tmp_path, monkeypatch):
    import json as _json
    from app.ai_providers.base import ChatResult, TokenUsage

    async def fake_chat(messages, *, model, temperature, json_mode=False, **k):
        return ChatResult(
            content=_json.dumps({
                "captions": ["新上", "新下"],
                "scene_prompts": ["s1", "s2"],
            }),
            model=model,
            usage=TokenUsage(prompt_tokens=10, completion_tokens=10),
        )

    from app.image_posts import routes as image_posts_routes
    class FakeProvider:
        name = "fake"
        async def chat(self, *a, **k): return await fake_chat(*a, **k)
    fake_registry = type("R", (), {
        "role": lambda self, r: (FakeProvider(), "m"),
    })()
    monkeypatch.setattr(image_posts_routes, "get_registry", lambda: fake_registry, raising=False)
    async def _noop(s): return None
    monkeypatch.setattr(image_posts_routes, "_ensure_registry", _noop, raising=False)

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
    r = await auth_client.post(f"/api/image-posts/{post_id}/regenerate-captions")
    assert r.status_code == 200
    body = r.json()
    assert body["captions"] == ["新上", "新下"]


async def test_regenerate_route_resets_status(auth_client, db_session, tmp_path):
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
    # Force into failed
    from app.image_posts.models import ImagePost, ImagePostStatus
    from sqlalchemy import select
    obj = (await db_session.execute(
        select(ImagePost).where(ImagePost.id == uuid.UUID(post_id))
    )).scalar_one()
    obj.status = ImagePostStatus.failed
    await db_session.commit()

    r = await auth_client.post(f"/api/image-posts/{post_id}/regenerate")
    assert r.status_code == 202
    await db_session.refresh(obj)
    assert obj.status == ImagePostStatus.pending


async def test_push_route_dispatches_task(auth_client, db_session, tmp_path):
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
    # Force status=generated
    from app.image_posts.models import ImagePost, ImagePostStatus
    from sqlalchemy import select
    obj = (await db_session.execute(
        select(ImagePost).where(ImagePost.id == uuid.UUID(post_id))
    )).scalar_one()
    obj.status = ImagePostStatus.generated
    obj.captions = ["上", "下"]
    obj.asset_ids = []
    await db_session.commit()

    r = await auth_client.post(f"/api/image-posts/{post_id}/push-to-wechat")
    assert r.status_code == 202


async def test_push_rejects_non_generated_status(auth_client, db_session, tmp_path):
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
    # status is "pending" by default
    r = await auth_client.post(f"/api/image-posts/{post_id}/push-to-wechat")
    assert r.status_code == 409
