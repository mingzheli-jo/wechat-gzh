import asyncio
import logging
import uuid
from datetime import UTC, datetime
from typing import Any
from urllib.parse import urlparse

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.crawler.fetcher import FetchError, fetch_html
from app.crawler.parser import (
    ParsedArticle,
    ParseError,
    parse_generic_article,
    parse_wechat_article,
)
from app.db.session import make_engine
from app.library.models import LibraryItem, LibraryStatus
from app.tasks.celery_app import celery_app

logger = logging.getLogger(__name__)


_WECHAT_HOSTS = ("mp.weixin.qq.com", "weixin.qq.com")


def _parse(source_url: str, html: str) -> ParsedArticle:
    """按来源域名选解析器：微信走专用 xpath，其余新闻站走通用抽取。"""
    host = (urlparse(source_url).hostname or "").lower()
    is_wechat = any(
        host == d or host.endswith("." + d) for d in _WECHAT_HOSTS
    )
    if not is_wechat:
        return parse_generic_article(html)
    parsed = parse_wechat_article(html)
    # 微信解析器抓不到 #js_content 时返回空正文。以前这种情况会被标成
    # done，素材库里留下一条空壳——检索时命中它比命中不到更糟。
    if not parsed.content_text.strip():
        raise ParseError("微信正文为空（页面结构不符或已被拦截）")
    return parsed


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
        parsed = _parse(item.source_url, html)
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
    except ParseError as exc:
        # 页面结构问题，重试也是一样的结果，不进 autoretry。
        item.status = LibraryStatus.failed
        item.error_msg = f"parse error: {exc}"
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
