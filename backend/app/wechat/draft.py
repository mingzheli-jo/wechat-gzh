from typing import Any

import httpx


class WeChatDraftError(Exception):
    def __init__(self, message: str, *, errcode: int | None = None) -> None:
        super().__init__(message)
        self.errcode = errcode


async def push_draft(
    *,
    access_token: str,
    title: str,
    content_html: str,
    thumb_media_id: str,
    author: str = "",
    digest: str = "",
) -> str:
    """Push article to WeChat draft box; returns the draft media_id."""
    payload: dict[str, Any] = {
        "articles": [
            {
                "title": title,
                "author": author,
                "digest": digest[:120],
                "content": content_html,
                "thumb_media_id": thumb_media_id,
                "need_open_comment": 0,
                "only_fans_can_comment": 0,
            }
        ]
    }
    async with httpx.AsyncClient(timeout=60) as client:
        resp = await client.post(
            "https://api.weixin.qq.com/cgi-bin/draft/add",
            params={"access_token": access_token},
            json=payload,
        )
    data = resp.json()
    if "errcode" in data and data["errcode"] != 0:
        raise WeChatDraftError(
            f"errcode={data['errcode']}, errmsg={data.get('errmsg')}",
            errcode=data["errcode"],
        )
    if "media_id" not in data:
        raise WeChatDraftError(f"unexpected response: {data}")
    return str(data["media_id"])
