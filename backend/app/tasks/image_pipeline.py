"""AI image post Celery pipeline."""
import asyncio
import base64
import json
import logging
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import httpx
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.accounts.models import Account
from app.ai_providers.base import Message
from app.ai_providers.registry import RegistryError, get_registry, load_from_db
from app.config import get_settings
from app.db.session import make_engine
from app.image_composer.compose import compose
from app.image_generator.base import ImageGenRequest
from app.image_generator.factory import get_image_provider
from app.image_posts.models import (
    ImageAsset,
    ImageAssetSource,
    ImagePost,
    ImagePostStatus,
    ImagePostTemplate,
)
from app.image_posts.templates import TEMPLATES
from app.tasks.celery_app import celery_app
from app.wechat.draft import WeChatDraftError, push_draft
from app.wechat.material import upload_image
from app.wechat.token import get_access_token

logger = logging.getLogger(__name__)


async def _ensure_registry(session: AsyncSession) -> None:
    await load_from_db(session)


def _parse_json_safe(content: str) -> dict[str, Any]:
    """Best-effort JSON parse: try direct, then fall back to the first {...} span.

    Aligns with ``app.reviewer.compliance._parse_json_safe`` — strip-by-char on
    backticks is brittle when the model returns ``````` fences
    or other framing chars.
    """
    try:
        parsed = json.loads(content)
    except json.JSONDecodeError:
        start = content.find("{")
        end = content.rfind("}")
        if start >= 0 and end > start:
            parsed = json.loads(content[start : end + 1])
        else:
            raise
    if not isinstance(parsed, dict):
        raise ValueError(f"expected JSON object, got {type(parsed).__name__}")
    return parsed


async def _download_to_local(url: str, target_dir: Path) -> Path:
    target_dir.mkdir(parents=True, exist_ok=True)
    async with httpx.AsyncClient(timeout=60) as client:
        resp = await client.get(url)
        resp.raise_for_status()
    asset_id = uuid.uuid4()
    target = target_dir / f"{asset_id}.png"
    target.write_bytes(resp.content)
    return target


async def _generate_with_session(
    session: AsyncSession, post_id: uuid.UUID
) -> None:
    post = (
        await session.execute(select(ImagePost).where(ImagePost.id == post_id))
    ).scalar_one_or_none()
    if post is None:
        logger.warning("image_post %s not found", post_id)
        return
    account = (
        await session.execute(
            select(Account).where(Account.id == post.account_id)
        )
    ).scalar_one()

    if not account.character_reference_path:
        post.status = ImagePostStatus.failed
        post.error_msg = "该公众号未上传角色参考图"
        await session.commit()
        return

    post.status = ImagePostStatus.generating
    await session.commit()

    try:
        template = TEMPLATES[ImagePostTemplate(post.template)]

        # ── Caption stage ────────────────────────
        await _ensure_registry(session)
        try:
            writer, writer_model = get_registry().role("writer")
        except RegistryError as exc:
            post.status = ImagePostStatus.failed
            post.error_msg = f"AI role binding error: {exc}"
            await session.commit()
            return

        prompt = template.caption_prompt_template.format(
            topic=post.topic, tone=post.tone or "通用",
        )
        chat_result = await writer.chat(
            [Message(role="user", content=prompt)],
            model=writer_model,
            temperature=0.8,
            json_mode=True,
        )
        parsed = _parse_json_safe(chat_result.content)
        post.captions = parsed["captions"]
        post.panel_prompts = parsed["scene_prompts"]
        await session.commit()

        # ── Image stage ──────────────────────────
        if post.panel_asset_ids:
            # 复用路径（阶段 2 启用，阶段 1 不会触发）
            post.asset_ids = post.panel_asset_ids
            for aid in post.panel_asset_ids:
                await session.execute(
                    update(ImageAsset)
                    .where(ImageAsset.id == uuid.UUID(str(aid)))
                    .values(used_count=ImageAsset.used_count + 1)
                )
        else:
            provider = get_image_provider()
            ref_bytes = Path(account.character_reference_path).read_bytes()
            ref_b64 = base64.b64encode(ref_bytes).decode()
            settings = get_settings()
            storage_root = Path(settings.image_storage_dir) / "image_assets"

            asset_ids: list[str] = []
            for scene in post.panel_prompts or []:
                result = await provider.generate(
                    ImageGenRequest(
                        prompt=scene + " (style: flat cartoon, no text, no captions)",
                        reference_image_b64=ref_b64,
                        size="1024x1024",
                        negative_prompt="text, chinese characters, captions, letters",
                    )
                )
                local_path = await _download_to_local(result.url, storage_root)
                asset = ImageAsset(
                    account_id=account.id,
                    image_path=str(local_path),
                    scene_prompt=scene,
                    tags=[],
                    source=ImageAssetSource.ai_generated,
                )
                session.add(asset)
                await session.flush()
                asset_ids.append(str(asset.id))
            post.asset_ids = asset_ids

        post.status = ImagePostStatus.generated
        post.error_msg = None
        await session.commit()
    except Exception as exc:
        logger.exception("image post generation failed: %s", post.id)
        post.status = ImagePostStatus.failed
        post.error_msg = f"{type(exc).__name__}: {exc}"
        await session.commit()


async def _do_generate(post_id: uuid.UUID) -> None:
    engine = make_engine()
    sm = async_sessionmaker(engine, expire_on_commit=False)
    async with sm() as session:
        await _generate_with_session(session, post_id)
    await engine.dispose()


@celery_app.task(
    name="app.tasks.image_pipeline.generate_image_post",
    bind=True,
    max_retries=2,
    default_retry_delay=30,
)
def generate_image_post(self: Any, post_id: str) -> None:
    asyncio.run(_do_generate(uuid.UUID(post_id)))


async def _compose_and_push_with_session(
    session: AsyncSession, post_id: uuid.UUID
) -> None:
    post = (
        await session.execute(select(ImagePost).where(ImagePost.id == post_id))
    ).scalar_one_or_none()
    if post is None:
        return
    account = (
        await session.execute(
            select(Account).where(Account.id == post.account_id)
        )
    ).scalar_one()
    if post.status not in (
        ImagePostStatus.generated, ImagePostStatus.failed
    ):
        logger.warning(
            "cannot push image_post %s from status %s", post.id, post.status
        )
        return

    asset_ids = post.asset_ids or []
    asset_uuid_list = [uuid.UUID(a) for a in asset_ids]
    assets = (await session.execute(
        select(ImageAsset).where(ImageAsset.id.in_(asset_uuid_list))
    )).scalars().all()
    # Preserve order from asset_ids
    by_id = {str(a.id): a for a in assets}
    ordered_paths = [Path(by_id[str(aid)].image_path) for aid in asset_ids]

    template = TEMPLATES[ImagePostTemplate(post.template)]
    post.status = ImagePostStatus.composing
    await session.commit()

    try:
        settings = get_settings()
        output_dir = Path(settings.image_storage_dir) / "image_posts"
        output_dir.mkdir(parents=True, exist_ok=True)
        output_path = output_dir / f"{post.id}.png"
        # Pillow compose is sync + CPU-bound; offload so we don't block the
        # event loop (cheap insurance even though Celery's asyncio.run loop
        # has nothing else to do).
        await asyncio.to_thread(
            compose,
            template=template,
            panel_paths=ordered_paths,
            captions=post.captions or [],
            watermark=f"公众号·{account.name}",
            font_path=Path(settings.image_posts_font_path),
            output_path=output_path,
        )
        # Persist composed_image_path BEFORE upload so a retry from `failed`
        # can skip recompose and reuse the rendered file on disk.
        post.composed_image_path = str(output_path)
        post.status = ImagePostStatus.pushing
        await session.commit()

        token = await get_access_token(
            account_id=str(account.id),
            appid=account.wechat_appid,
            secret=account.wechat_secret,
        )
        upload_result = await upload_image(
            access_token=token, file_path=str(output_path),
        )
        post.wechat_thumb_media_id = upload_result["media_id"]

        title = (post.captions or ["未命名"])[0][:30]
        wechat_img_url = upload_result.get("url", "")
        content_html = (
            f'<p style="text-align:center;">'
            f'<img src="{wechat_img_url}" style="max-width:100%;"/>'
            f'</p>'
        )
        try:
            draft_media_id = await push_draft(
                access_token=token,
                title=title,
                content_html=content_html,
                thumb_media_id=post.wechat_thumb_media_id,
                author=account.name,
            )
        except WeChatDraftError as exc:
            if exc.errcode == 40001:
                token = await get_access_token(
                    account_id=str(account.id),
                    appid=account.wechat_appid,
                    secret=account.wechat_secret,
                    force_refresh=True,
                )
                draft_media_id = await push_draft(
                    access_token=token,
                    title=title,
                    content_html=content_html,
                    thumb_media_id=post.wechat_thumb_media_id,
                    author=account.name,
                )
            else:
                raise

        post.wechat_draft_media_id = draft_media_id
        post.wechat_pushed_at = datetime.now(UTC)
        post.status = ImagePostStatus.pushed
        post.error_msg = None
        await session.commit()
    except Exception as exc:
        logger.exception("compose_and_push failed for image_post %s", post.id)
        post.status = ImagePostStatus.failed
        post.error_msg = f"{type(exc).__name__}: {exc}"
        await session.commit()


async def _do_compose_and_push(post_id: uuid.UUID) -> None:
    engine = make_engine()
    sm = async_sessionmaker(engine, expire_on_commit=False)
    async with sm() as session:
        await _compose_and_push_with_session(session, post_id)
    await engine.dispose()


@celery_app.task(
    name="app.tasks.image_pipeline.compose_and_push_image_post",
    bind=True,
    max_retries=2,
    default_retry_delay=15,
)
def compose_and_push_image_post(self: Any, post_id: str) -> None:
    asyncio.run(_do_compose_and_push(uuid.UUID(post_id)))
