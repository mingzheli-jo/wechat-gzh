import json

import httpx
import pytest
import respx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker

from app.accounts.models import Account
from app.drafts.models import Draft, DraftStatus
from app.images.models import Image, ImageStatus
from app.library.models import LibraryItem, LibraryStatus
from app.tasks.publish import _do_publish


async def _seed(db_session, *, default_thumb_media_id=None):
    item = LibraryItem(source_url="https://x/article", status=LibraryStatus.done)
    account = Account(
        name="A",
        wechat_appid="wx",
        wechat_secret="s",
        category="职场",
        default_thumb_media_id=default_thumb_media_id,
    )
    db_session.add_all([item, account])
    await db_session.commit()
    draft = Draft(
        library_item_id=item.id,
        account_id=account.id,
        status=DraftStatus.reviewed,
        title="标题",
        content_html="<p>正文</p>",
    )
    db_session.add(draft)
    await db_session.commit()
    return draft, account


async def _fake_token(**_kwargs):
    return "TOK"


def _capture_thumb(captured: dict[str, str]):
    def _fn(req: httpx.Request) -> httpx.Response:
        captured["thumb_media_id"] = json.loads(req.content)["articles"][0][
            "thumb_media_id"
        ]
        return httpx.Response(200, json={"media_id": "PUSHED"})

    return _fn


@pytest.mark.asyncio
async def test_publish_uses_draft_cover_when_available(
    db_engine, db_session, monkeypatch
):
    monkeypatch.setattr("app.tasks.publish.get_access_token", _fake_token)
    draft, _ = await _seed(db_session, default_thumb_media_id="ACC_DEFAULT")
    cover = Image(
        draft_id=draft.id,
        original_url="https://x/c.jpg",
        position=0,
        is_cover=True,
        status=ImageStatus.uploaded,
        wechat_media_id="DRAFT_COVER",
    )
    db_session.add(cover)
    await db_session.commit()

    captured: dict[str, str] = {}
    async with respx.mock(assert_all_called=False) as mock:
        mock.post("https://api.weixin.qq.com/cgi-bin/draft/add").mock(
            side_effect=_capture_thumb(captured)
        )
        await _do_publish(draft.id)

    assert captured["thumb_media_id"] == "DRAFT_COVER"

    fresh_sm = async_sessionmaker(db_engine, expire_on_commit=False)
    async with fresh_sm() as fresh:
        refreshed = (
            await fresh.execute(select(Draft).where(Draft.id == draft.id))
        ).scalar_one()
        assert refreshed.status == DraftStatus.published_to_wechat


@pytest.mark.asyncio
async def test_publish_falls_back_to_account_default_when_no_cover(
    db_engine, db_session, monkeypatch
):
    monkeypatch.setattr("app.tasks.publish.get_access_token", _fake_token)
    draft, _ = await _seed(db_session, default_thumb_media_id="ACC_DEFAULT")

    captured: dict[str, str] = {}
    async with respx.mock(assert_all_called=False) as mock:
        mock.post("https://api.weixin.qq.com/cgi-bin/draft/add").mock(
            side_effect=_capture_thumb(captured)
        )
        await _do_publish(draft.id)

    assert captured["thumb_media_id"] == "ACC_DEFAULT"

    fresh_sm = async_sessionmaker(db_engine, expire_on_commit=False)
    async with fresh_sm() as fresh:
        refreshed = (
            await fresh.execute(select(Draft).where(Draft.id == draft.id))
        ).scalar_one()
        assert refreshed.status == DraftStatus.published_to_wechat


@pytest.mark.asyncio
async def test_publish_fails_when_no_cover_and_no_default(
    db_engine, db_session, monkeypatch
):
    monkeypatch.setattr("app.tasks.publish.get_access_token", _fake_token)
    draft, _ = await _seed(db_session, default_thumb_media_id=None)

    await _do_publish(draft.id)

    fresh_sm = async_sessionmaker(db_engine, expire_on_commit=False)
    async with fresh_sm() as fresh:
        refreshed = (
            await fresh.execute(select(Draft).where(Draft.id == draft.id))
        ).scalar_one()
        assert refreshed.status == DraftStatus.failed
        assert refreshed.error_msg is not None
        assert "封面" in refreshed.error_msg
