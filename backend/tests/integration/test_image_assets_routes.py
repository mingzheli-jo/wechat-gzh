import pytest
from httpx import ASGITransport, AsyncClient

from app.accounts.models import Account
from app.api.deps import get_db
from app.image_posts.models import ImageAsset, ImageAssetSource
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
