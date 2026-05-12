import asyncio
import logging
import uuid
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker

from app.accounts.models import Account
from app.db.session import make_engine
from app.drafts.models import Draft, DraftStatus
from app.images.models import Image, ImageStatus
from app.tasks.celery_app import celery_app
from app.wechat.draft import WeChatDraftError, push_draft
from app.wechat.token import get_access_token

logger = logging.getLogger(__name__)


async def _do_publish(draft_id: uuid.UUID) -> None:
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
                select(Image).where(Image.draft_id == draft_id)
            )
        ).scalars().all()

        cover = next((i for i in images if i.is_cover), None)
        draft_cover_ready = (
            cover is not None
            and cover.status == ImageStatus.uploaded
            and bool(cover.wechat_media_id)
        )
        if draft_cover_ready:
            assert cover is not None and cover.wechat_media_id is not None
            thumb_media_id: str = cover.wechat_media_id
        elif account.default_thumb_media_id:
            thumb_media_id = account.default_thumb_media_id
        else:
            draft.status = DraftStatus.failed
            draft.error_msg = "本草稿无封面图片，且账号未配置默认封面"
            await session.commit()
            return
        non_cover_pending = [
            i
            for i in images
            if not i.is_cover
            and i.status not in (ImageStatus.uploaded, ImageStatus.removed)
        ]
        if non_cover_pending:
            draft.status = DraftStatus.failed
            draft.error_msg = f"{len(non_cover_pending)} 张图片未完成上传"
            await session.commit()
            return

        try:
            token = await get_access_token(
                account_id=str(account.id),
                appid=account.wechat_appid,
                secret=account.wechat_secret,
            )
            try:
                media_id = await push_draft(
                    access_token=token,
                    title=draft.title or "",
                    content_html=draft.content_html or "",
                    thumb_media_id=thumb_media_id,
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
                    media_id = await push_draft(
                        access_token=token,
                        title=draft.title or "",
                        content_html=draft.content_html or "",
                        thumb_media_id=thumb_media_id,
                        author=account.name,
                    )
                else:
                    raise
            draft.wechat_media_id = media_id
            draft.wechat_pushed_at = datetime.now(UTC)
            draft.status = DraftStatus.published_to_wechat
            draft.error_msg = None
            await session.commit()
        except Exception as exc:
            logger.exception("publish failed for draft %s", draft.id)
            draft.status = DraftStatus.failed
            draft.error_msg = f"{type(exc).__name__}: {exc}"
            await session.commit()
    await engine.dispose()


@celery_app.task(
    name="app.tasks.publish.publish_draft",
    bind=True,
    max_retries=2,
    default_retry_delay=15,
)
def publish_draft(self: Any, draft_id: str) -> None:
    asyncio.run(_do_publish(uuid.UUID(draft_id)))
