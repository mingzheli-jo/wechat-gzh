import asyncio
import random

import httpx

from app.config import get_settings


class FetchError(Exception):
    pass


_USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0 Safari/537.36",  # noqa: E501
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_0) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Safari/605.1.15",  # noqa: E501
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0 Safari/537.36",  # noqa: E501
]


async def fetch_html(
    url: str, *, timeout: int | None = None, max_retries: int | None = None
) -> str:
    settings = get_settings()
    timeout = timeout or settings.crawler_timeout
    max_retries = max_retries or settings.crawler_max_retry
    last_exc: Exception | None = None
    for attempt in range(1, max_retries + 1):
        headers = {"User-Agent": random.choice(_USER_AGENTS)}  # noqa: S311
        try:
            async with httpx.AsyncClient(
                timeout=timeout, follow_redirects=True
            ) as client:
                response = await client.get(url, headers=headers)
            if response.status_code >= 500:
                last_exc = FetchError(f"5xx: {response.status_code}")
                await asyncio.sleep(2**attempt)
                continue
            if response.status_code == 200:
                if "wappoc_appmsgcaptcha" in str(response.url):
                    raise FetchError(
                        "WeChat anti-bot captcha triggered "
                        "(redirected to wappoc_appmsgcaptcha)"
                    )
                return response.text
            raise FetchError(f"HTTP {response.status_code}")
        except httpx.TimeoutException as exc:
            last_exc = exc
            await asyncio.sleep(2**attempt)
        except httpx.HTTPError as exc:
            raise FetchError(str(exc)) from exc
    raise FetchError(f"failed after {max_retries} retries: {last_exc}")
