from pathlib import Path

import httpx


class WeChatMaterialError(Exception):
    pass


async def upload_image(
    *, access_token: str, file_path: str
) -> dict[str, str]:
    path = Path(file_path)
    async with httpx.AsyncClient(timeout=60) as client:
        with path.open("rb") as fh:
            files = {"media": (path.name, fh, "image/jpeg")}
            resp = await client.post(
                "https://api.weixin.qq.com/cgi-bin/material/add_material",
                params={"access_token": access_token, "type": "image"},
                files=files,
            )
    data = resp.json()
    if "errcode" in data and data["errcode"] != 0:
        raise WeChatMaterialError(
            f"errcode={data['errcode']}, errmsg={data.get('errmsg')}"
        )
    if "media_id" not in data:
        raise WeChatMaterialError(f"unexpected response: {data}")
    return {"media_id": data["media_id"], "url": data.get("url", "")}
