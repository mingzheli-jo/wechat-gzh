import asyncio
import logging
import uuid
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.crawler.fetcher import FetchError, fetch_html
from app.crawler.parser import parse_wechat_article
from app.db.session import make_engine
from app.library.models import LibraryItem, LibraryStatus
from app.tasks.celery_app import celery_app

logger = logging.getLogger(__name__)


async def _crawl_with_session(session: AsyncSession, item_id: uuid.UUID) -> None:
    """Core crawl logic. Tests pass their own session; production wraps via _do_crawl."""
    item = (
        await session.execute(
            select(LibraryItem).where(LibraryItem.id == item_id)
        )
    ).scalar_one_or_none()
    if item is None:
        logger.warning("library_item %s not found", item_id)
        return
    item.status = LibraryStatus.processing
    await session.commit()
    try:
        html = await fetch_html(item.source_url)
        parsed = parse_wechat_article(html)
        item.original_title = parsed.title
        item.original_author = parsed.author
        item.original_content_html = parsed.content_html
        item.original_content_text = parsed.content_text
        item.images = parsed.images
        item.status = LibraryStatus.done
        item.crawled_at = datetime.now(UTC)
        item.error_msg = None
    except FetchError as exc:
        item.status = LibraryStatus.failed
        item.error_msg = f"fetch error: {exc}"
    except Exception as exc:
        item.status = LibraryStatus.failed
        item.error_msg = f"unexpected: {exc!r}"
    await session.commit()


async def _do_crawl(item_id: uuid.UUID) -> None:
    engine = make_engine()
    sm = async_sessionmaker(engine, expire_on_commit=False)
    async with sm() as session:
        await _crawl_with_session(session, item_id)
    await engine.dispose()


@celery_app.task(
    name="app.tasks.crawl.crawl_library_item",
    bind=True,
    autoretry_for=(FetchError,),
    max_retries=2,
    default_retry_delay=10,
)
def crawl_library_item(self: Any, item_id: str) -> None:
    asyncio.run(_do_crawl(uuid.UUID(item_id)))
