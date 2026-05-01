import fakeredis.aioredis
import httpx
import pytest
import respx

from app.wechat.token import WeChatTokenError, _redis_key, get_access_token


@pytest.mark.asyncio
async def test_token_fetched_when_cache_missing(monkeypatch):
    fake = fakeredis.aioredis.FakeRedis(decode_responses=True)
    monkeypatch.setattr("app.wechat.token._get_redis", lambda: fake)
    async with respx.mock(base_url="https://api.weixin.qq.com") as mock:
        mock.get("/cgi-bin/token").mock(
            return_value=httpx.Response(
                200, json={"access_token": "TOK1", "expires_in": 7200}
            )
        )
        token = await get_access_token(account_id="abc", appid="x", secret="y")
    assert token == "TOK1"
    assert await fake.get(_redis_key("abc")) == "TOK1"


@pytest.mark.asyncio
async def test_token_cache_hit_skips_api(monkeypatch):
    fake = fakeredis.aioredis.FakeRedis(decode_responses=True)
    await fake.set(_redis_key("abc"), "CACHED", ex=600)
    monkeypatch.setattr("app.wechat.token._get_redis", lambda: fake)
    token = await get_access_token(account_id="abc", appid="x", secret="y")
    assert token == "CACHED"


@pytest.mark.asyncio
async def test_token_error_response_raises(monkeypatch):
    fake = fakeredis.aioredis.FakeRedis(decode_responses=True)
    monkeypatch.setattr("app.wechat.token._get_redis", lambda: fake)
    async with respx.mock(base_url="https://api.weixin.qq.com") as mock:
        mock.get("/cgi-bin/token").mock(
            return_value=httpx.Response(
                200, json={"errcode": 40013, "errmsg": "invalid appid"}
            )
        )
        with pytest.raises(WeChatTokenError):
            await get_access_token(account_id="abc", appid="x", secret="y")
