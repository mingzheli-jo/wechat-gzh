import httpx
import pytest
import respx

from app.wechat.material import WeChatMaterialError, upload_image


@pytest.mark.asyncio
async def test_upload_image_returns_media_id_and_url():
    async with respx.mock(base_url="https://api.weixin.qq.com") as mock:
        mock.post("/cgi-bin/material/add_material").mock(
            return_value=httpx.Response(
                200,
                json={
                    "media_id": "MID-1",
                    "url": "https://mmbiz.qpic.cn/mmbiz_jpg/abc/0",
                },
            )
        )
        result = await upload_image(access_token="TOK", file_path=__file__)
    assert result["media_id"] == "MID-1"
    assert "mmbiz" in result["url"]


@pytest.mark.asyncio
async def test_upload_image_error_raises():
    async with respx.mock(base_url="https://api.weixin.qq.com") as mock:
        mock.post("/cgi-bin/material/add_material").mock(
            return_value=httpx.Response(
                200, json={"errcode": 40001, "errmsg": "invalid token"}
            )
        )
        with pytest.raises(WeChatMaterialError):
            await upload_image(access_token="TOK", file_path=__file__)
