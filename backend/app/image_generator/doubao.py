"""Doubao Seedream image provider."""
from typing import Any

import httpx

from app.image_generator.base import (
    BaseImageProvider,
    ImageGenRequest,
    ImageGenResult,
)


class DoubaoImageError(Exception):
    pass


class DoubaoImageProvider(BaseImageProvider):
    name = "doubao"

    def __init__(self, *, api_key: str, base_url: str, model: str) -> None:
        self._api_key = api_key
        self._base_url = base_url.rstrip("/")
        self._model = model

    async def generate(self, req: ImageGenRequest) -> ImageGenResult:
        payload: dict[str, Any] = {
            "model": self._model,
            "prompt": req.prompt,
            "size": req.size,
            "response_format": "url",
        }
        if req.reference_image_b64:
            payload["image"] = f"data:image/png;base64,{req.reference_image_b64}"
        if req.negative_prompt:
            payload["negative_prompt"] = req.negative_prompt

        url = f"{self._base_url}/images/generations"
        headers = {
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type": "application/json",
        }
        async with httpx.AsyncClient(timeout=120) as client:
            resp = await client.post(url, json=payload, headers=headers)
        data = resp.json()
        if resp.status_code >= 400 or "error" in data:
            msg = data.get("error", {}).get("message") if isinstance(data, dict) else str(data)
            raise DoubaoImageError(f"doubao API failed: {msg} (status={resp.status_code})")
        if "data" not in data or not data["data"]:
            raise DoubaoImageError(f"unexpected response: {data}")
        image_url = data["data"][0].get("url")
        if not image_url:
            raise DoubaoImageError(f"no url in response: {data}")
        return ImageGenResult(url=image_url, raw=data)
