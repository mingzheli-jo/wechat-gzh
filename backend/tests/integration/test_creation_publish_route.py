import uuid

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker

from app.accounts.models import Account
from app.api.deps import get_db
from app.creator.models import CreationInputMode, CreationStatus, ThemeCreation
from app.drafts.models import Draft, DraftStatus
from app.main import create_app


@pytest.fixture
def dispatched():
    return []


@pytest.fixture
def app(db_session, monkeypatch, dispatched):
    from app.tasks import images as images_module
    from app.tasks import publish as publish_module

    # Capture the dispatched chain instead of hitting the broker.
    monkeypatch.setattr(
        images_module.process_draft_images,
        "apply_async",
        lambda *a, **k: dispatched.append((a, k)),
        raising=False,
    )
    monkeypatch.setattr(
        publish_module.publish_draft,
        "si",
        lambda *a, **k: ("si", a),
        raising=False,
    )

    app = create_app()

    async def _override():
        yield db_session

    app.dependency_overrides[get_db] = _override
    return app


@pytest.fixture
async def auth_client(app):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        login = await client.post(
            "/api/auth/login",
            data={"username": "admin", "password": "hunter2"},
        )
        client.headers["Authorization"] = f"Bearer {login.json()['access_token']}"
        yield client


async def _seed_account(db_session) -> Account:
    account = Account(
        name="A",
        wechat_appid="wx",
        wechat_secret="s",
        category="职场",
    )
    db_session.add(account)
    await db_session.commit()
    await db_session.refresh(account)
    return account


async def _seed_creation(
    db_session,
    *,
    status: CreationStatus = CreationStatus.done,
    account_id: uuid.UUID | None = None,
    generated_title: str | None = "生成标题",
    generated_content_html: str | None = "<p>生成正文</p>",
) -> ThemeCreation:
    obj = ThemeCreation(
        input_mode=CreationInputMode.manual,
        extracted_theme="主题",
        generated_title=generated_title,
        generated_content_html=generated_content_html,
        fact_check={"score": 90},
        account_id=account_id,
        status=status,
    )
    db_session.add(obj)
    await db_session.commit()
    await db_session.refresh(obj)
    return obj


async def test_publish_happy_path_builds_draft_and_dispatches(
    auth_client, db_session, db_engine, dispatched
):
    account = await _seed_account(db_session)
    creation = await _seed_creation(db_session, account_id=account.id)

    r = await auth_client.post(
        f"/api/creations/{creation.id}/publish-to-wechat", json={}
    )
    assert r.status_code == 202
    body = r.json()
    assert body["library_item_id"] is None
    assert body["status"] == DraftStatus.reviewed.value
    assert body["title"] == "生成标题"

    # The image→publish chain was dispatched exactly once.
    assert len(dispatched) == 1

    fresh_sm = async_sessionmaker(db_engine, expire_on_commit=False)
    async with fresh_sm() as fresh:
        draft = (
            await fresh.execute(
                select(Draft).where(Draft.source_creation_id == creation.id)
            )
        ).scalar_one()
        assert draft.library_item_id is None
        assert draft.source_creation_id == creation.id
        assert draft.status == DraftStatus.reviewed
        assert draft.account_id == account.id
        assert draft.content_html == "<p>生成正文</p>"

    # The dispatch must target the real created draft, not some other id.
    _args, kwargs = dispatched[0]
    assert kwargs["args"] == [str(draft.id)]


async def test_publish_twice_is_idempotent(
    auth_client, db_session, db_engine, dispatched
):
    account = await _seed_account(db_session)
    creation = await _seed_creation(db_session, account_id=account.id)

    first = await auth_client.post(
        f"/api/creations/{creation.id}/publish-to-wechat", json={}
    )
    assert first.status_code == 202

    # A retry / double-click must not create a second draft or re-dispatch.
    second = await auth_client.post(
        f"/api/creations/{creation.id}/publish-to-wechat", json={}
    )
    assert second.status_code == 409

    assert len(dispatched) == 1

    fresh_sm = async_sessionmaker(db_engine, expire_on_commit=False)
    async with fresh_sm() as fresh:
        drafts = (
            await fresh.execute(
                select(Draft).where(Draft.source_creation_id == creation.id)
            )
        ).scalars().all()
        assert len(drafts) == 1


async def test_publish_uses_payload_account_override(
    auth_client, db_session, db_engine
):
    account = await _seed_account(db_session)
    # Creation has no account of its own; payload supplies it.
    creation = await _seed_creation(db_session, account_id=None)

    r = await auth_client.post(
        f"/api/creations/{creation.id}/publish-to-wechat",
        json={"account_id": str(account.id)},
    )
    assert r.status_code == 202
    assert r.json()["account_id"] == str(account.id)


async def test_delete_creation_with_linked_draft_nulls_source(
    auth_client, db_session, db_engine
):
    account = await _seed_account(db_session)
    creation = await _seed_creation(db_session, account_id=account.id)

    r = await auth_client.post(
        f"/api/creations/{creation.id}/publish-to-wechat", json={}
    )
    assert r.status_code == 202
    draft_id = uuid.UUID(r.json()["id"])

    # Deleting the creation must not raise an FK violation; ondelete=SET NULL
    # nulls the linked draft's source_creation_id instead.
    d = await auth_client.delete(f"/api/creations/{creation.id}")
    assert d.status_code == 204

    fresh_sm = async_sessionmaker(db_engine, expire_on_commit=False)
    async with fresh_sm() as fresh:
        draft = (
            await fresh.execute(select(Draft).where(Draft.id == draft_id))
        ).scalar_one()
        assert draft.source_creation_id is None


async def test_publish_404_when_missing(auth_client):
    r = await auth_client.post(
        f"/api/creations/{uuid.uuid4()}/publish-to-wechat", json={}
    )
    assert r.status_code == 404


async def test_publish_409_when_not_done(auth_client, db_session):
    account = await _seed_account(db_session)
    creation = await _seed_creation(
        db_session, status=CreationStatus.generating, account_id=account.id
    )
    r = await auth_client.post(
        f"/api/creations/{creation.id}/publish-to-wechat", json={}
    )
    assert r.status_code == 409


async def test_publish_400_when_no_account(auth_client, db_session):
    creation = await _seed_creation(db_session, account_id=None)
    r = await auth_client.post(
        f"/api/creations/{creation.id}/publish-to-wechat", json={}
    )
    assert r.status_code == 400
