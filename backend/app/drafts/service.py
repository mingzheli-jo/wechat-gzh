import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.drafts.models import Draft, DraftStatus, ReviewReport


async def create_draft(
    db: AsyncSession, *, library_item_id: uuid.UUID, account_id: uuid.UUID
) -> Draft:
    obj = Draft(
        library_item_id=library_item_id,
        account_id=account_id,
        status=DraftStatus.draft,
    )
    db.add(obj)
    await db.commit()
    await db.refresh(obj)
    return obj


async def list_drafts(
    db: AsyncSession,
    *,
    account_id: uuid.UUID | None = None,
    status: DraftStatus | None = None,
    limit: int = 50,
    offset: int = 0,
) -> list[Draft]:
    stmt = (
        select(Draft)
        .order_by(Draft.created_at.desc())
        .limit(limit)
        .offset(offset)
    )
    if account_id is not None:
        stmt = stmt.where(Draft.account_id == account_id)
    if status is not None:
        stmt = stmt.where(Draft.status == status)
    return list((await db.execute(stmt)).scalars().all())


async def get_draft(db: AsyncSession, draft_id: uuid.UUID) -> Draft | None:
    return await db.get(Draft, draft_id)


async def get_review_report(
    db: AsyncSession, report_id: uuid.UUID
) -> ReviewReport | None:
    return await db.get(ReviewReport, report_id)


async def update_draft(
    db: AsyncSession,
    draft: Draft,
    *,
    title: str | None,
    content_html: str | None,
) -> Draft:
    if title is not None:
        draft.title = title
    if content_html is not None:
        draft.content_html = content_html
    await db.commit()
    await db.refresh(draft)
    return draft
