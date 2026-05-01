import httpx
import pytest
import respx

from app.wechat.draft import WeChatDraftError, push_draft


@pytest.mark.asyncio
async def test_push_draft_returns_media_id():
    async with respx.mock(base_url="https://api.weixin.qq.com") as mock:
        mock.post("/cgi-bin/draft/add").mock(
            return_value=httpx.Response(200, json={"media_id": "DRAFT-1"})
        )
        result = await push_draft(
            access_token="TOK",
            title="t",
            content_html="<p>x</p>",
            thumb_media_id="COVER",
            author="a",
            digest="d",
        )
    assert result == "DRAFT-1"


@pytest.mark.asyncio
async def test_push_draft_token_invalid_raises():
    async with respx.mock(base_url="https://api.weixin.qq.com") as mock:
        mock.post("/cgi-bin/draft/add").mock(
            return_value=httpx.Response(
                200, json={"errcode": 40001, "errmsg": "invalid token"}
            )
        )
        with pytest.raises(WeChatDraftError):
            await push_draft(
                access_token="TOK",
                title="t",
                content_html="<p/>",
                thumb_media_id="C",
                author="a",
                digest="d",
            )
