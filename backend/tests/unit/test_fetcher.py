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
async def test_fetch_html_detects_wechat_captcha_redirect():
    async with respx.mock() as mock:
        mock.get("https://mp.weixin.qq.com/s/captcha-test").mock(
            return_value=httpx.Response(
                302,
                headers={
                    "Location": "https://mp.weixin.qq.com/mp/wappoc_appmsgcaptcha?poc_token=x"
                },
            )
        )
        mock.get(
            "https://mp.weixin.qq.com/mp/wappoc_appmsgcaptcha",
            params={"poc_token": "x"},
        ).mock(return_value=httpx.Response(200, text="<html>captcha page</html>"))
        with pytest.raises(FetchError, match="captcha"):
            await fetch_html("https://mp.weixin.qq.com/s/captcha-test")


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


@pytest.mark.asyncio
async def test_fetch_html_rejects_redirect_off_allowlist():
    """白名单里的门户站带外跳端点，跳转目标必须重新校验，否则等于开放重定向。"""
    async with respx.mock() as mock:
        mock.get("https://news.qq.com/link").mock(
            return_value=httpx.Response(
                302, headers={"Location": "http://169.254.169.254/latest/meta-data/"}
            )
        )
        mock.get("http://169.254.169.254/latest/meta-data/").mock(
            return_value=httpx.Response(200, text="ami-id\ninstance-id")
        )
        with pytest.raises(FetchError, match="non-allowlisted"):
            await fetch_html("https://news.qq.com/link")


@pytest.mark.asyncio
async def test_fetch_html_allows_redirect_within_allowlist():
    async with respx.mock() as mock:
        mock.get("https://news.qq.com/a/short").mock(
            return_value=httpx.Response(
                302, headers={"Location": "https://new.qq.com/rain/a/full"}
            )
        )
        mock.get("https://new.qq.com/rain/a/full").mock(
            return_value=httpx.Response(200, text="<html>正文</html>")
        )
        assert "正文" in await fetch_html("https://news.qq.com/a/short")
