import httpx
import pytest
import respx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker

from app.accounts.models import Account
from app.drafts.models import Draft, DraftStatus
from app.images.models import Image, ImageStatus
from app.library.models import LibraryItem, LibraryStatus
from app.tasks.images import _do_process


@pytest.mark.asyncio
async def test_process_uploads_each_image(
    db_engine, db_session, monkeypatch, tmp_path
):
    monkeypatch.setenv("IMAGE_STORAGE_DIR", str(tmp_path))
    from app.config import get_settings

    get_settings.cache_clear()

    async def fake_token(**kwargs):
        return "TOK"

    monkeypatch.setattr("app.tasks.images.get_access_token", fake_token)

    item = LibraryItem(source_url="https://x/article", status=LibraryStatus.done)
    account = Account(
        name="A",
        wechat_appid="x",
        wechat_secret="y",
        category="职场",
    )
    db_session.add_all([item, account])
    await db_session.commit()
    draft = Draft(
        library_item_id=item.id,
        account_id=account.id,
        status=DraftStatus.reviewed,
        content_html='<p><img src="https://x/a.jpg"/></p>',
    )
    db_session.add(draft)
    await db_session.commit()
    img = Image(
        draft_id=draft.id, original_url="https://x/a.jpg", position=0
    )
    db_session.add(img)
    await db_session.commit()

    async with respx.mock() as mock:
        mock.get("https://x/a.jpg").mock(
            return_value=httpx.Response(200, content=b"\xff\xd8\xff" * 10)
        )
        mock.post(
            "https://api.weixin.qq.com/cgi-bin/material/add_material"
        ).mock(
            return_value=httpx.Response(
                200,
                json={
                    "media_id": "MID",
                    "url": "https://mmbiz.qpic.cn/wx_a.jpg",
                },
            )
        )
        await _do_process(draft.id)

    fresh_sm = async_sessionmaker(db_engine, expire_on_commit=False)
    async with fresh_sm() as fresh:
        refreshed_img = (
            await fresh.execute(select(Image).where(Image.id == img.id))
        ).scalar_one()
        assert refreshed_img.status == ImageStatus.uploaded
        assert refreshed_img.wechat_media_id == "MID"
        refreshed_draft = (
            await fresh.execute(select(Draft).where(Draft.id == draft.id))
        ).scalar_one()
        assert "wx_a.jpg" in refreshed_draft.content_html
        assert "x/a.jpg" not in refreshed_draft.content_html
