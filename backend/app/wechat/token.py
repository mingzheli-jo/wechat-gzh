import asyncio
from typing import cast

import httpx
import redis.asyncio as redis

from app.config import get_settings


class WeChatTokenError(Exception):
    pass


_REFRESH_BUFFER_SECONDS = 600
# 刷新锁的最长持有时间（秒）；网络调用 15s 超时，留足余量后自动过期防死锁
_REFRESH_LOCK_TTL = 20
# 等待他人刷新完成时的轮询参数
_LOCK_WAIT_TRIES = 20
_LOCK_WAIT_INTERVAL = 0.5


def _redis_key(account_id: str) -> str:
    return f"wechat:token:{account_id}"


def _lock_key(account_id: str) -> str:
    return f"wechat:token:{account_id}:lock"


async def _refresh_token(
    rds: redis.Redis, *, account_id: str, appid: str, secret: str
) -> str:
    """实际向微信请求新 token 并写入缓存。调用方需已持有刷新锁。"""
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
    try:
        if not force_refresh:
            cached = await rds.get(_redis_key(account_id))
            if cached:
                return str(cached)

        # 分布式锁：避免多 worker 同时刷新导致互相把对方 token 顶掉、或并发打爆
        # 微信 token 接口。第一个拿到锁的负责刷新，其余等待并复用其结果。
        lock_key = _lock_key(account_id)
        got_lock = await rds.set(lock_key, "1", nx=True, ex=_REFRESH_LOCK_TTL)
        if not got_lock and not force_refresh:
            for _ in range(_LOCK_WAIT_TRIES):
                await asyncio.sleep(_LOCK_WAIT_INTERVAL)
                cached = await rds.get(_redis_key(account_id))
                if cached:
                    return str(cached)
            # 等待超时仍无结果：强行抢锁刷新，避免永久阻塞
            got_lock = await rds.set(lock_key, "1", ex=_REFRESH_LOCK_TTL)

        try:
            # 二次确认：可能在抢锁期间别的 worker 已经刷好
            if not force_refresh:
                cached = await rds.get(_redis_key(account_id))
                if cached:
                    return str(cached)
            return await _refresh_token(
                rds, account_id=account_id, appid=appid, secret=secret
            )
        finally:
            await rds.delete(lock_key)
    finally:
        await rds.aclose()


async def invalidate(account_id: str) -> None:
    rds = _get_redis()
    try:
        await rds.delete(_redis_key(account_id))
    finally:
        await rds.aclose()
