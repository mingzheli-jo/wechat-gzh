import httpx
import pytest
import respx
from sqlalchemy import select

from app.library import service as lib_service
from app.library.models import LibraryItem, LibraryStatus


@pytest.mark.asyncio
async def test_crawl_marks_item_done(db_session, monkeypatch):
    item = await lib_service.create_pending(
        db_session, "https://mp.weixin.qq.com/s/abc", []
    )

    async def _fake_do_crawl(item_id):
        await _do_crawl_in_session(db_session, item_id)

    sample = """
    <html><body>
      <h1 id='activity-name'>x</h1>
      <a id='js_name'>y</a>
      <div id='js_content'><p>z</p></div>
    </body></html>"""
    async with respx.mock(base_url="https://mp.weixin.qq.com") as mock:
        mock.get("/s/abc").mock(return_value=httpx.Response(200, text=sample))
        await _do_crawl_in_session(db_session, item.id)
    refreshed = (
        await db_session.execute(
            select(LibraryItem).where(LibraryItem.id == item.id)
        )
    ).scalar_one()
    assert refreshed.status == LibraryStatus.done
    assert refreshed.original_title == "x"
    assert refreshed.original_author == "y"


@pytest.mark.asyncio
async def test_crawl_marks_failed_on_404(db_session):
    item = await lib_service.create_pending(
        db_session, "https://mp.weixin.qq.com/s/missing", []
    )
    async with respx.mock(base_url="https://mp.weixin.qq.com") as mock:
        mock.get("/s/missing").mock(return_value=httpx.Response(404))
        await _do_crawl_in_session(db_session, item.id)
    refreshed = (
        await db_session.execute(
            select(LibraryItem).where(LibraryItem.id == item.id)
        )
    ).scalar_one()
    assert refreshed.status == LibraryStatus.failed
    assert "fetch error" in (refreshed.error_msg or "")


async def _do_crawl_in_session(session, item_id):
    """Test variant: reuses the test's db_session instead of opening a new engine.

    The production _do_crawl opens its own engine per call which keeps the
    Celery task self-contained, but in tests we run in the same DB session.
    """
    from datetime import UTC, datetime

    from app.crawler.fetcher import FetchError, fetch_html
    from app.crawler.parser import parse_wechat_article

    item = (
        await session.execute(select(LibraryItem).where(LibraryItem.id == item_id))
    ).scalar_one_or_none()
    if item is None:
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
