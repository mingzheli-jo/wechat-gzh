import json
from pathlib import Path

import httpx
import pytest
import respx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker

from app.accounts.models import Account
from app.image_posts.models import (
    ImageAsset,
    ImagePost,
    ImagePostStatus,
    ImagePostTemplate,
)


@pytest.fixture(autouse=True)
def stub_providers(monkeypatch, tmp_path):
    """Provide a fake reference image + ensure storage dir."""
    monkeypatch.setenv("IMAGE_STORAGE_DIR", str(tmp_path))
    monkeypatch.setenv("DOUBAO_API_KEY", "test_key")
    monkeypatch.setenv("DOUBAO_BASE_URL", "https://ark.test/api/v3")
    monkeypatch.setenv("DOUBAO_IMAGE_MODEL", "test-model")
    from app.config import get_settings
    get_settings.cache_clear()

    # Fake reference image
    ref_dir = tmp_path / "accounts"
    ref_dir.mkdir(parents=True, exist_ok=True)


async def _seed_account_with_ref(db_session, ref_path: Path) -> Account:
    ref_path.write_bytes(b"\x89PNG\r\n\x1a\nfake_png_data")
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


@pytest.mark.asyncio
async def test_generate_image_post_two_panel(
    db_engine, db_session, monkeypatch, tmp_path
):
    # Patch LLM registry
    from app.tasks import image_pipeline

    async def fake_chat(messages, *, model, temperature, json_mode=False, **k):
        from app.ai_providers.base import ChatResult, TokenUsage
        return ChatResult(
            content=json.dumps({
                "captions": ["上文案", "下文案"],
                "scene_prompts": ["panel 1 scene", "panel 2 scene"],
            }),
            model=model,
            usage=TokenUsage(prompt_tokens=10, completion_tokens=20),
        )

    class FakeProvider:
        name = "fake"
        async def chat(self, *a, **k):
            return await fake_chat(*a, **k)

    fake_registry = type("R", (), {
        "role": lambda self, r: (FakeProvider(), "fake-model"),
    })()
    monkeypatch.setattr(
        image_pipeline, "get_registry", lambda: fake_registry, raising=False,
    )
    monkeypatch.setattr(
        image_pipeline, "_ensure_registry",
        lambda session: _noop_async(), raising=False,
    )

    account = await _seed_account_with_ref(
        db_session, tmp_path / "accounts" / "char.png"
    )
    post = ImagePost(
        account_id=account.id,
        template=ImagePostTemplate.two_panel_contrast,
        topic="测试主题",
        tone="self_mockery",
        status=ImagePostStatus.pending,
    )
    db_session.add(post)
    await db_session.commit()

    async with respx.mock(assert_all_called=True) as mock:
        # mock doubao - returns 2 image URLs
        mock.post("https://ark.test/api/v3/images/generations").mock(
            return_value=httpx.Response(
                200,
                json={"data": [{"url": "https://cdn/img.png"}]},
            )
        )
        # mock the download
        mock.get("https://cdn/img.png").mock(
            return_value=httpx.Response(
                200, content=b"\x89PNG\r\n\x1a\nimg_bytes" * 100,
            )
        )
        await image_pipeline._generate_with_session(db_session, post.id)

    # Reload via fresh session
    fresh_sm = async_sessionmaker(db_engine, expire_on_commit=False)
    async with fresh_sm() as fresh:
        refreshed = (
            await fresh.execute(select(ImagePost).where(ImagePost.id == post.id))
        ).scalar_one()
        assert refreshed.status == ImagePostStatus.generated
        assert refreshed.captions == ["上文案", "下文案"]
        assert refreshed.panel_prompts == ["panel 1 scene", "panel 2 scene"]
        assert refreshed.asset_ids
        assert len(refreshed.asset_ids) == 2

        assets = (await fresh.execute(
            select(ImageAsset).where(ImageAsset.account_id == account.id)
        )).scalars().all()
        assert len(assets) == 2


async def _noop_async():
    return None


async def _async_value(v):
    return v


@pytest.mark.asyncio
async def test_compose_and_push_two_panel_success(
    db_engine, db_session, monkeypatch, tmp_path
):
    from app.image_posts.models import ImageAsset, ImageAssetSource
    from app.tasks import image_pipeline

    monkeypatch.setattr(
        "app.tasks.image_pipeline.get_access_token",
        lambda **k: _async_value("TOK"),
        raising=False,
    )

    account = await _seed_account_with_ref(
        db_session, tmp_path / "accounts" / "char.png"
    )
    # Pre-seed assets (simulating prior generation)
    from PIL import Image as _Img
    asset_paths = []
    for i in range(2):
        p = tmp_path / "image_assets" / f"a{i}.png"
        p.parent.mkdir(parents=True, exist_ok=True)
        _Img.new("RGB", (1024, 1024), (200, 150, 100)).save(p)
        asset = ImageAsset(
            account_id=account.id,
            image_path=str(p),
            scene_prompt=f"scene {i}",
            tags=[],
            source=ImageAssetSource.ai_generated,
        )
        db_session.add(asset)
        await db_session.commit()
        await db_session.refresh(asset)
        asset_paths.append(asset.id)

    post = ImagePost(
        account_id=account.id,
        template=ImagePostTemplate.two_panel_contrast,
        topic="t",
        status=ImagePostStatus.generated,
        captions=["上文案", "下文案"],
        panel_prompts=["s1", "s2"],
        asset_ids=[str(a) for a in asset_paths],
    )
    db_session.add(post)
    await db_session.commit()

    async with respx.mock(assert_all_called=False) as mock:
        mock.post(
            "https://api.weixin.qq.com/cgi-bin/material/add_material"
        ).mock(
            return_value=httpx.Response(
                200,
                json={"media_id": "MID", "url": "https://mmbiz/img.png"},
            )
        )
        mock.post("https://api.weixin.qq.com/cgi-bin/draft/add").mock(
            return_value=httpx.Response(
                200, json={"media_id": "DRAFT_MID"}
            )
        )
        await image_pipeline._compose_and_push_with_session(db_session, post.id)

    fresh_sm = async_sessionmaker(db_engine, expire_on_commit=False)
    async with fresh_sm() as fresh:
        refreshed = (
            await fresh.execute(select(ImagePost).where(ImagePost.id == post.id))
        ).scalar_one()
        assert refreshed.status == ImagePostStatus.pushed
        assert refreshed.wechat_thumb_media_id == "MID"
        assert refreshed.wechat_draft_media_id == "DRAFT_MID"
        assert refreshed.composed_image_path
        assert Path(refreshed.composed_image_path).exists()
