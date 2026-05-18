from datetime import date
from typing import Any

import httpx


class WechatStatsError(Exception):
    pass


_DATACUBE_BASE = "https://api.weixin.qq.com/datacube"
_COMMENT_LIST_URL = "https://api.weixin.qq.com/cgi-bin/comment/list"
_TIMEOUT_SECONDS = 10.0


def _check_errcode(data: dict[str, Any]) -> None:
    errcode = data.get("errcode")
    if errcode is not None and errcode != 0:
        raise WechatStatsError(
            f"errcode={errcode}, errmsg={data.get('errmsg')}"
        )


async def _get_datacube(
    path: str, *, access_token: str, begin_date: date, end_date: date
) -> list[dict[str, Any]]:
    async with httpx.AsyncClient(timeout=_TIMEOUT_SECONDS) as client:
        resp = await client.get(
            f"{_DATACUBE_BASE}/{path}",
            params={
                "access_token": access_token,
                "begin_date": begin_date.isoformat(),
                "end_date": end_date.isoformat(),
            },
        )
    data = resp.json()
    _check_errcode(data)
    return list(data.get("list", []))


async def fetch_user_summary(
    *, access_token: str, begin_date: date, end_date: date
) -> list[dict[str, Any]]:
    return await _get_datacube(
        "getusersummary",
        access_token=access_token,
        begin_date=begin_date,
        end_date=end_date,
    )


async def fetch_user_cumulate(
    *, access_token: str, begin_date: date, end_date: date
) -> list[dict[str, Any]]:
    return await _get_datacube(
        "getusercumulate",
        access_token=access_token,
        begin_date=begin_date,
        end_date=end_date,
    )


async def fetch_article_total(
    *, access_token: str, begin_date: date, end_date: date
) -> list[dict[str, Any]]:
    return await _get_datacube(
        "getarticletotal",
        access_token=access_token,
        begin_date=begin_date,
        end_date=end_date,
    )


async def fetch_comment_count(
    *, access_token: str, msg_data_id: int, index: int
) -> int:
    async with httpx.AsyncClient(timeout=_TIMEOUT_SECONDS) as client:
        resp = await client.post(
            _COMMENT_LIST_URL,
            params={"access_token": access_token},
            json={
                "msg_data_id": msg_data_id,
                "index": index,
                "begin": 0,
                "count": 0,
                "type": 0,
            },
        )
    data = resp.json()
    _check_errcode(data)
    return int(data.get("total", 0))
