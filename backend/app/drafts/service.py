import logging
import uuid
from pathlib import Path

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.drafts.models import Draft, DraftStatus, ReviewReport
from app.images.models import Image

logger = logging.getLogger(__name__)


GROUP_STATUSES: dict[str, list[DraftStatus]] = {
    "active": [DraftStatus.draft, DraftStatus.reviewing],
    "done": [DraftStatus.reviewed],
    "published": [DraftStatus.published_to_wechat],
    "failed": [DraftStatus.failed],
}


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


async def list_drafts_paginated(
    db: AsyncSession,
    *,
    group: str | None = None,
    account_id: uuid.UUID | None = None,
    page: int = 1,
    page_size: int = 10,
) -> tuple[list[Draft], int]:
    """List drafts in a single status group, paginated. Returns (items, total)."""
    base = select(Draft).order_by(Draft.created_at.desc())
    count_base = select(func.count()).select_from(Draft)

    if group is not None and group in GROUP_STATUSES:
        statuses = GROUP_STATUSES[group]
        base = base.where(Draft.status.in_(statuses))
        count_base = count_base.where(Draft.status.in_(statuses))

    if account_id is not None:
        base = base.where(Draft.account_id == account_id)
        count_base = count_base.where(Draft.account_id == account_id)

    paginated = base.limit(page_size).offset(max(0, (page - 1) * page_size))
    items = list((await db.execute(paginated)).scalars().all())
    total = int((await db.execute(count_base)).scalar_one())
    return items, total


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


async def delete_draft_with_cleanup(db: AsyncSession, draft: Draft) -> None:
    """Delete a draft and all dependent rows + image files on disk.

    Order matters because of foreign keys: drafts.review_report_id <->
    review_reports.draft_id is a circular FK (drafts uses use_alter=True).
    Image rows reference drafts via images.draft_id.

    Caller is responsible for ensuring the draft is in a deletable state.
    """
    images = list(
        (
            await db.execute(
                select(Image).where(Image.draft_id == draft.id)
            )
        )
        .scalars()
        .all()
    )

    review_report_id = draft.review_report_id
    if review_report_id is not None:
        draft.review_report_id = None
        await db.flush()

    reports = list(
        (
            await db.execute(
                select(ReviewReport).where(ReviewReport.draft_id == draft.id)
            )
        )
        .scalars()
        .all()
    )
    for r in reports:
        await db.delete(r)

    for img in images:
        if img.local_path:
            try:
                Path(img.local_path).unlink(missing_ok=True)
            except OSError as exc:
                logger.warning(
                    "failed to unlink image file %s: %s", img.local_path, exc
                )
        await db.delete(img)

    await db.delete(draft)
    await db.commit()
