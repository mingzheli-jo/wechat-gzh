import httpx
import pytest
import respx

from app.crawler.fetcher import FetchError, fetch_html


@pytest.mark.asyncio
async def test_fetch_html_success():
    async with respx.mock(base_url="https://mp.weixin.qq.com") as mock:
        mock.get("/s/abc").mock(
            return_value=httpx.Response(200, text="<html>hello</html>")
        )
        result = await fetch_html("https://mp.weixin.qq.com/s/abc")
        assert "hello" in result


@pytest.mark.asyncio
async def test_fetch_html_404_raises():
    async with respx.mock(base_url="https://mp.weixin.qq.com") as mock:
        mock.get("/s/x").mock(return_value=httpx.Response(404))
        with pytest.raises(FetchError):
            await fetch_html("https://mp.weixin.qq.com/s/x")


@pytest.mark.asyncio
async def test_fetch_html_retries_on_5xx():
    async with respx.mock(base_url="https://mp.weixin.qq.com") as mock:
        route = mock.get("/s/y")
        route.side_effect = [
            httpx.Response(503),
            httpx.Response(503),
            httpx.Response(200, text="<html>ok</html>"),
        ]
        result = await fetch_html("https://mp.weixin.qq.com/s/y", max_retries=3)
        assert "ok" in result
        assert route.call_count == 3
