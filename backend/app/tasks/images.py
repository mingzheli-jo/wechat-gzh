"""Process images for a draft: download original, upload to WeChat, rewrite content_html."""
import asyncio
import logging
import uuid
from pathlib import Path
from typing import Any

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker

from app.accounts.models import Account
from app.config import get_settings
from app.db.session import make_engine
from app.drafts.models import Draft
from app.images.models import Image, ImageStatus
from app.tasks.celery_app import celery_app
from app.wechat.material import WeChatMaterialError, upload_image
from app.wechat.token import get_access_token

logger = logging.getLogger(__name__)


async def _download(url: str, dest: Path) -> None:
    async with httpx.AsyncClient(timeout=30, follow_redirects=True) as client:
        async with client.stream("GET", url) as resp:
            resp.raise_for_status()
            dest.parent.mkdir(parents=True, exist_ok=True)
            with dest.open("wb") as fh:
                async for chunk in resp.aiter_bytes():
                    fh.write(chunk)


async def _do_process(draft_id: uuid.UUID) -> None:
    settings = get_settings()
    engine = make_engine()
    sm = async_sessionmaker(engine, expire_on_commit=False)
    async with sm() as session:
        draft = (
            await session.execute(select(Draft).where(Draft.id == draft_id))
        ).scalar_one()
        account = (
            await session.execute(
                select(Account).where(Account.id == draft.account_id)
            )
        ).scalar_one()
        images = (
            await session.execute(
                select(Image)
                .where(Image.draft_id == draft_id)
                .order_by(Image.position)
            )
        ).scalars().all()

        token = await get_access_token(
            account_id=str(account.id),
            appid=account.wechat_appid,
            secret=account.wechat_secret,
        )
        for img in images:
            if img.status in (
                ImageStatus.uploaded,
                ImageStatus.removed,
                ImageStatus.replaced,
            ):
                continue
            local: Path | None = None
            try:
                ext = Path(img.original_url).suffix or ".jpg"
                local = (
                    Path(settings.image_storage_dir)
                    / str(draft.id)
                    / f"{img.position}{ext}"
                )
                await _download(img.original_url, local)
                img.local_path = str(local)
                img.status = ImageStatus.downloaded
                await session.commit()

                result = await upload_image(
                    access_token=token, file_path=str(local)
                )
                img.wechat_media_id = result["media_id"]
                img.wechat_url = result["url"]
                img.status = ImageStatus.uploaded
                await session.commit()

                if draft.content_html and result["url"]:
                    draft.content_html = draft.content_html.replace(
                        img.original_url, result["url"]
                    )
                    await session.commit()
            except WeChatMaterialError as exc:
                if "40001" in str(exc) and local is not None:
                    token = await get_access_token(
                        account_id=str(account.id),
                        appid=account.wechat_appid,
                        secret=account.wechat_secret,
                        force_refresh=True,
                    )
                    try:
                        result = await upload_image(
                            access_token=token, file_path=str(local)
                        )
                        img.wechat_media_id = result["media_id"]
                        img.wechat_url = result["url"]
                        img.status = ImageStatus.uploaded
                    except Exception as inner:
                        img.status = ImageStatus.failed
                        img.error_msg = str(inner)[:500]
                else:
                    img.status = ImageStatus.failed
                    img.error_msg = str(exc)[:500]
                await session.commit()
            except Exception as exc:
                logger.exception("image processing failed")
                img.status = ImageStatus.failed
                img.error_msg = f"{type(exc).__name__}: {exc}"[:500]
                await session.commit()
    await engine.dispose()


@celery_app.task(
    name="app.tasks.images.process_draft_images",
    bind=True,
    max_retries=1,
    default_retry_delay=15,
)
def process_draft_images(self: Any, draft_id: str) -> None:
    asyncio.run(_do_process(uuid.UUID(draft_id)))
