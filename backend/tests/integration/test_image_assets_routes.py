import uuid

import pytest
from httpx import ASGITransport, AsyncClient

from app.accounts.models import Account
from app.api.deps import get_db
from app.image_posts.models import ImageAsset, ImageAssetSource
from app.main import create_app


@pytest.fixture
def app(db_session, monkeypatch, tmp_path):
    # The /file endpoint enforces a containment check against
    # settings.image_storage_dir, so point it at the per-test tmp_path
    # where _seed_assets writes its fake PNGs.
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


async def _seed_assets(db_session, tmp_path, n=3) -> tuple[Account, list[ImageAsset]]:
    account = Account(name="A", wechat_appid="wx", wechat_secret="s", category="x")
    db_session.add(account)
    await db_session.commit()
    await db_session.refresh(account)

    assets = []
    for i in range(n):
        p = tmp_path / f"a{i}.png"
        p.write_bytes(b"\x89PNG\r\n\x1a\nfake" + bytes([i]))
        a = ImageAsset(
            account_id=account.id,
            image_path=str(p),
            scene_prompt=f"scene {i}",
            tags=["test", f"tag{i}"],
            source=ImageAssetSource.ai_generated,
        )
        db_session.add(a)
        await db_session.commit()
        await db_session.refresh(a)
        assets.append(a)
    return account, assets


async def test_list_image_assets(auth_client, db_session, tmp_path):
    account, _ = await _seed_assets(db_session, tmp_path, n=3)
    r = await auth_client.get(f"/api/image-assets?account_id={account.id}")
    assert r.status_code == 200
    body = r.json()
    assert body["total"] == 3
    assert len(body["items"]) == 3


async def test_get_image_asset_detail(auth_client, db_session, tmp_path):
    _, assets = await _seed_assets(db_session, tmp_path, n=1)
    r = await auth_client.get(f"/api/image-assets/{assets[0].id}")
    assert r.status_code == 200
    body = r.json()
    assert body["scene_prompt"] == "scene 0"


async def test_get_image_asset_file(auth_client, db_session, tmp_path):
    _, assets = await _seed_assets(db_session, tmp_path, n=1)
    r = await auth_client.get(f"/api/image-assets/{assets[0].id}/file")
    assert r.status_code == 200
    assert r.headers["content-type"].startswith("image/")
    assert len(r.content) > 0


async def test_get_image_asset_detail_404(auth_client):
    bogus = uuid.uuid4()
    r = await auth_client.get(f"/api/image-assets/{bogus}")
    assert r.status_code == 404


async def test_get_image_asset_file_missing(auth_client, db_session, tmp_path):
    """Row exists but the file on disk does not."""
    _, assets = await _seed_assets(db_session, tmp_path, n=1)
    assets[0].image_path = str(tmp_path / "ghost.png")  # never written
    await db_session.commit()
    r = await auth_client.get(f"/api/image-assets/{assets[0].id}/file")
    assert r.status_code == 404


async def test_get_image_asset_file_rejects_traversal(
    auth_client, db_session, tmp_path
):
    """A tampered DB row pointing outside storage_root must 403."""
    _, assets = await _seed_assets(db_session, tmp_path, n=1)
    # Point at a real file outside storage_root so we don't accidentally
    # 404 on file-missing before the containment check fires.
    outside = tmp_path.parent / "escape.png"
    outside.write_bytes(b"\x89PNG\r\n\x1a\nfake")
    assets[0].image_path = str(outside)
    await db_session.commit()
    r = await auth_client.get(f"/api/image-assets/{assets[0].id}/file")
    assert r.status_code == 403
