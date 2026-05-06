import logging
import uuid
from pathlib import Path

from sqlalchemy import delete as sa_delete, func, select, update
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


async def list_drafts_for_library_item(
    db: AsyncSession, library_item_id: uuid.UUID
) -> list[Draft]:
    """All drafts that reference a given library item, regardless of status."""
    return list(
        (
            await db.execute(
                select(Draft).where(Draft.library_item_id == library_item_id)
            )
        )
        .scalars()
        .all()
    )


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

    Uses core-level DELETE statements rather than ORM `session.delete()`
    to bypass dependency-sort ambiguity caused by the circular FK
    between drafts and review_reports (drafts.review_report_id is
    use_alter=True, which made the ORM sometimes attempt to DELETE
    drafts before review_reports during commit).

    Order:
      1. UPDATE drafts SET review_report_id = NULL  (breaks the cycle)
      2. DELETE images WHERE draft_id = X
      3. DELETE review_reports WHERE draft_id = X
      4. DELETE drafts WHERE id = X
      5. commit, then unlink image files (best-effort, post-commit)

    Caller is responsible for ensuring the draft is in a deletable state.
    """
    draft_id = draft.id

    # Capture image local_paths before deletion (need them for disk cleanup)
    image_paths = list(
        (
            await db.execute(
                select(Image.local_path).where(Image.draft_id == draft_id)
            )
        )
        .scalars()
        .all()
    )

    # Break circular FK so the draft can be deleted last
    if draft.review_report_id is not None:
        await db.execute(
            update(Draft)
            .where(Draft.id == draft_id)
            .values(review_report_id=None)
        )

    # Explicit DELETEs in reverse-dependency order
    await db.execute(sa_delete(Image).where(Image.draft_id == draft_id))
    await db.execute(
        sa_delete(ReviewReport).where(ReviewReport.draft_id == draft_id)
    )
    await db.execute(sa_delete(Draft).where(Draft.id == draft_id))
    await db.commit()

    # Best-effort disk cleanup post-commit
    for path in image_paths:
        if not path:
            continue
        try:
            Path(path).unlink(missing_ok=True)
        except OSError as exc:
            logger.warning(
                "failed to unlink image file %s: %s", path, exc
            )
