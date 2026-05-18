"""AI image post Celery pipeline."""
import asyncio
import base64
import json
import logging
import uuid
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
