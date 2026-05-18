from datetime import date

import httpx
import pytest
import respx

from app.wechat import stats as stats_client


@pytest.mark.asyncio
@respx.mock
async def test_fetch_user_summary_parses_list() -> None:
    respx.get("https://api.weixin.qq.com/datacube/getusersummary").mock(
        return_value=httpx.Response(
            200,
            json={
                "list": [
                    {
                        "ref_date": "2026-05-17",
                        "user_source": 0,
                        "new_user": 12,
                        "cancel_user": 3,
                    }
                ]
            },
        )
    )
    rows = await stats_client.fetch_user_summary(
        access_token="tok",
        begin_date=date(2026, 5, 17),
        end_date=date(2026, 5, 17),
    )
    assert rows == [
        {
            "ref_date": "2026-05-17",
            "user_source": 0,
            "new_user": 12,
            "cancel_user": 3,
        }
    ]


@pytest.mark.asyncio
@respx.mock
async def test_fetch_user_cumulate_parses_list() -> None:
    respx.get("https://api.weixin.qq.com/datacube/getusercumulate").mock(
        return_value=httpx.Response(
            200,
            json={
                "list": [
                    {"ref_date": "2026-05-17", "cumulate_user": 1234}
                ]
            },
        )
    )
    rows = await stats_client.fetch_user_cumulate(
        access_token="tok",
        begin_date=date(2026, 5, 17),
        end_date=date(2026, 5, 17),
    )
    assert rows == [{"ref_date": "2026-05-17", "cumulate_user": 1234}]


@pytest.mark.asyncio
@respx.mock
async def test_fetch_article_total_returns_raw_rows() -> None:
    payload = {
        "list": [
            {
                "ref_date": "2026-05-17",
                "msgid": "100000001_1",
                "title": "标题",
                "details": [
                    {
                        "stat_date": "2026-05-17",
                        "int_page_read_user": 100,
                        "int_page_read_count": 200,
                        "share_user": 5,
                        "share_count": 10,
                        "like_user": 8,
                        "like_count": 12,
                    }
                ],
            }
        ]
    }
    respx.get("https://api.weixin.qq.com/datacube/getarticletotal").mock(
        return_value=httpx.Response(200, json=payload)
    )
    rows = await stats_client.fetch_article_total(
        access_token="tok",
        begin_date=date(2026, 5, 10),
        end_date=date(2026, 5, 17),
    )
    assert rows == payload["list"]


@pytest.mark.asyncio
@respx.mock
async def test_fetch_comment_count_returns_total() -> None:
    respx.post(
        "https://api.weixin.qq.com/cgi-bin/comment/list"
    ).mock(
        return_value=httpx.Response(
            200,
            json={"total": 23, "comment": []},
        )
    )
    total = await stats_client.fetch_comment_count(
        access_token="tok",
        msg_data_id=100000001,
        index=1,
    )
    assert total == 23


@pytest.mark.asyncio
@respx.mock
async def test_fetch_user_summary_raises_on_errcode() -> None:
    respx.get("https://api.weixin.qq.com/datacube/getusersummary").mock(
        return_value=httpx.Response(
            200,
            json={"errcode": 40013, "errmsg": "invalid appid"},
        )
    )
    with pytest.raises(stats_client.WechatStatsError) as exc:
        await stats_client.fetch_user_summary(
            access_token="tok",
            begin_date=date(2026, 5, 17),
            end_date=date(2026, 5, 17),
        )
    assert "40013" in str(exc.value)
