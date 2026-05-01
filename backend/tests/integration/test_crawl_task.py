import httpx
import pytest
import respx
from sqlalchemy import select

from app.library import service as lib_service
from app.library.models import LibraryItem, LibraryStatus
from app.tasks.crawl import _crawl_with_session


@pytest.mark.asyncio
async def test_crawl_marks_item_done(db_session):
    item = await lib_service.create_pending(
        db_session, "https://mp.weixin.qq.com/s/abc", []
    )
    sample = """
    <html><body>
      <h1 id='activity-name'>x</h1>
      <a id='js_name'>y</a>
      <div id='js_content'><p>z</p></div>
    </body></html>"""
    async with respx.mock(base_url="https://mp.weixin.qq.com") as mock:
        mock.get("/s/abc").mock(return_value=httpx.Response(200, text=sample))
        await _crawl_with_session(db_session, item.id)
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
        await _crawl_with_session(db_session, item.id)
    refreshed = (
        await db_session.execute(
            select(LibraryItem).where(LibraryItem.id == item.id)
        )
    ).scalar_one()
    assert refreshed.status == LibraryStatus.failed
    assert "fetch error" in (refreshed.error_msg or "")
