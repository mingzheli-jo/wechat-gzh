import httpx
import pytest
import respx
from sqlalchemy import select

from app.library import service as lib_service
from app.library.models import LibraryItem, LibraryStatus
from app.tasks.crawl import _crawl_with_session


@pytest.mark.asyncio
async def test_crawl_marks_item_done(db_session):
    item, _ = await lib_service.create_pending(
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
    item, _ = await lib_service.create_pending(
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


@pytest.mark.asyncio
async def test_crawl_news_site_uses_generic_parser(db_session):
    """非微信域名走通用抽取——微信 xpath 在新闻站上什么都抽不到。"""
    body = "养老金上调的通知已经下发，各地正在按新的计发办法执行。" * 8
    sample = f"""
    <html><head><title>养老金上调通知下发</title></head><body>
      <div class='nav'>首页 财经</div>
      <div class='article'><h1>养老金上调通知下发</h1>
        <p>{body}</p><p>{body}</p></div>
    </body></html>"""
    item, _ = await lib_service.create_pending(
        db_session, "https://news.qq.com/rain/a/20260724A03", []
    )
    async with respx.mock(base_url="https://news.qq.com") as mock:
        mock.get("/rain/a/20260724A03").mock(
            return_value=httpx.Response(200, text=sample)
        )
        await _crawl_with_session(db_session, item.id)
    refreshed = (
        await db_session.execute(
            select(LibraryItem).where(LibraryItem.id == item.id)
        )
    ).scalar_one()
    assert refreshed.status == LibraryStatus.done
    assert "计发办法" in (refreshed.original_content_text or "")


@pytest.mark.asyncio
async def test_crawl_marks_failed_when_no_real_content(db_session):
    """抓到的是导航样板页时必须判失败——空壳素材被检索到比检索不到更糟。"""
    item, _ = await lib_service.create_pending(
        db_session, "https://news.qq.com/rain/a/20260724A04", []
    )
    async with respx.mock(base_url="https://news.qq.com") as mock:
        mock.get("/rain/a/20260724A04").mock(
            return_value=httpx.Response(
                200, text="<html><body><div>首页 财经 体育</div></body></html>"
            )
        )
        await _crawl_with_session(db_session, item.id)
    refreshed = (
        await db_session.execute(
            select(LibraryItem).where(LibraryItem.id == item.id)
        )
    ).scalar_one()
    assert refreshed.status == LibraryStatus.failed
    assert "parse error" in (refreshed.error_msg or "")
