from typing import cast

import httpx
import redis.asyncio as redis

from app.config import get_settings


class WeChatTokenError(Exception):
    pass


_REFRESH_BUFFER_SECONDS = 600


def _redis_key(account_id: str) -> str:
    return f"wechat:token:{account_id}"


def _get_redis() -> redis.Redis:
    return cast(
        redis.Redis,
        redis.from_url(  # type: ignore[no-untyped-call]
            get_settings().redis_url, decode_responses=True
        ),
    )


async def get_access_token(
    *,
    account_id: str,
    appid: str,
    secret: str,
    force_refresh: bool = False,
) -> str:
    rds = _get_redis()
    if not force_refresh:
        cached = await rds.get(_redis_key(account_id))
        if cached:
            return str(cached)
    async with httpx.AsyncClient(timeout=15) as client:
        resp = await client.get(
            "https://api.weixin.qq.com/cgi-bin/token",
            params={
                "grant_type": "client_credential",
                "appid": appid,
                "secret": secret,
            },
        )
    data = resp.json()
    token = data.get("access_token")
    if not token:
        raise WeChatTokenError(
            f"errcode={data.get('errcode')}, errmsg={data.get('errmsg')}"
        )
    expires_in = int(data.get("expires_in", 7200))
    ttl = max(60, expires_in - _REFRESH_BUFFER_SECONDS)
    await rds.set(_redis_key(account_id), token, ex=ttl)
    return str(token)


async def invalidate(account_id: str) -> None:
    await _get_redis().delete(_redis_key(account_id))
