import uuid

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.drafts.models import Draft, DraftStatus
from app.library.models import LibraryItem, LibraryStatus


async def create_pending(
    db: AsyncSession, url: str, tags: list[str]
) -> tuple[LibraryItem, bool]:
    """按 URL 幂等入库，返回 (条目, 是否新建)。

    source_url 有唯一约束，重复提交同一链接原本会直接 IntegrityError 500。
    自动出稿每天按热榜话题搜素材，撞到已入库的链接是常态，所以这里返回既有
    条目；抓取失败过的条目重置为 pending，让调用方重新派发抓取。
    """
    existing = (
        await db.execute(
            select(LibraryItem).where(LibraryItem.source_url == url)
        )
    ).scalar_one_or_none()
    if existing is not None:
        if existing.status == LibraryStatus.failed:
            existing.status = LibraryStatus.pending
            existing.error_msg = None
            await db.commit()
            await db.refresh(existing)
            return existing, True
        return existing, False

    obj = LibraryItem(source_url=url, tags=tags, status=LibraryStatus.pending)
    db.add(obj)
    await db.commit()
    await db.refresh(obj)
    return obj, True


async def get(db: AsyncSession, item_id: uuid.UUID) -> LibraryItem | None:
    return await db.get(LibraryItem, item_id)


async def list_items_with_counts(
    db: AsyncSession,
    *,
    status: LibraryStatus | None = None,
    tag: str | None = None,
    limit: int = 50,
    offset: int = 0,
) -> list[tuple[LibraryItem, int]]:
    """List library items with non-failed draft counts per item.

    Returns tuples of (item, rewrite_count) where rewrite_count counts drafts
    in any non-failed state (draft/reviewing/reviewed/published_to_wechat).
    """
    count_subq = (
        select(
            Draft.library_item_id.label("library_item_id"),
            func.count(Draft.id).label("rewrite_count"),
        )
        .where(Draft.status != DraftStatus.failed)
        .group_by(Draft.library_item_id)
        .subquery()
    )

    stmt = (
        select(
            LibraryItem,
            func.coalesce(count_subq.c.rewrite_count, 0).label("rewrite_count"),
        )
        .outerjoin(count_subq, count_subq.c.library_item_id == LibraryItem.id)
        .order_by(LibraryItem.created_at.desc())
        .limit(limit)
        .offset(offset)
    )
    if status is not None:
        stmt = stmt.where(LibraryItem.status == status)
    if tag is not None:
        stmt = stmt.where(LibraryItem.tags.contains([tag]))
    result = await db.execute(stmt)
    return [(row[0], int(row[1])) for row in result.all()]


async def list_items(
    db: AsyncSession,
    *,
    status: LibraryStatus | None = None,
    tag: str | None = None,
    limit: int = 50,
    offset: int = 0,
) -> list[LibraryItem]:
    stmt = (
        select(LibraryItem)
        .order_by(LibraryItem.created_at.desc())
        .limit(limit)
        .offset(offset)
    )
    if status is not None:
        stmt = stmt.where(LibraryItem.status == status)
    if tag is not None:
        stmt = stmt.where(LibraryItem.tags.contains([tag]))
    result = await db.execute(stmt)
    return list(result.scalars().all())


async def set_tags(
    db: AsyncSession, item: LibraryItem, tags: list[str]
) -> LibraryItem:
    item.tags = tags
    await db.commit()
    await db.refresh(item)
    return item


async def delete(db: AsyncSession, item: LibraryItem) -> None:
    await db.delete(item)
    await db.commit()
