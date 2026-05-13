import httpx
import pytest
import respx

from app.image_generator.base import ImageGenRequest
from app.image_generator.doubao import DoubaoImageProvider


@pytest.mark.asyncio
async def test_doubao_generate_text_only():
    provider = DoubaoImageProvider(
        api_key="test_key",
        base_url="https://ark.cn-beijing.volces.com/api/v3",
        model="doubao-seedream-3-0-t2i-250415",
    )
    async with respx.mock() as mock:
        mock.post(
            "https://ark.cn-beijing.volces.com/api/v3/images/generations"
        ).mock(
            return_value=httpx.Response(
                200,
                json={
                    "data": [{"url": "https://cdn.ark/img1.png"}],
                    "usage": {"generated_images": 1},
                },
            )
        )
        result = await provider.generate(
            ImageGenRequest(
                prompt="a cute capybara at desk",
                negative_prompt="text, captions",
            )
        )
    assert result.url == "https://cdn.ark/img1.png"
    assert "data" in result.raw


@pytest.mark.asyncio
async def test_doubao_generate_with_reference_image():
    provider = DoubaoImageProvider(
        api_key="k", base_url="https://x", model="m",
    )
    captured: dict = {}
    async with respx.mock() as mock:
        def _capture(req):
            import json as _json
            captured.update(_json.loads(req.content))
            return httpx.Response(200, json={"data": [{"url": "https://x/y.png"}]})
        mock.post("https://x/images/generations").mock(side_effect=_capture)
        await provider.generate(
            ImageGenRequest(prompt="p", reference_image_b64="BASE64DATA"),
        )
    assert "image" in captured
    assert captured["image"].startswith("data:image/png;base64,")


@pytest.mark.asyncio
async def test_doubao_generate_raises_on_error():
    from app.image_generator.doubao import DoubaoImageError

    provider = DoubaoImageProvider(api_key="k", base_url="https://x", model="m")
    async with respx.mock() as mock:
        mock.post("https://x/images/generations").mock(
            return_value=httpx.Response(
                400, json={"error": {"message": "invalid prompt"}}
            )
        )
        with pytest.raises(DoubaoImageError):
            await provider.generate(ImageGenRequest(prompt="bad"))
