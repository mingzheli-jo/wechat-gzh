import uuid

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.drafts.models import Draft, DraftStatus
from app.library.models import LibraryItem, LibraryStatus


async def create_pending(
    db: AsyncSession, url: str, tags: list[str]
) -> tuple[LibraryItem, bool]:
    """按 URL 幂等入库，返回 (条目, 调用方是否应派发抓取)。

    source_url 有唯一约束，重复提交同一链接原本会直接 IntegrityError 500。
    自动出稿每天按热榜话题搜素材，撞到已入库的链接是常态，所以这里复用既有
    条目。failed / pending 的条目要求重新派发抓取：failed 是抓砸了，pending
    则可能是上次派发本身就没成功（比如 broker 抖动），不重派就永远卡住。
    """
    existing = await _find_by_url(db, url)
    if existing is not None:
        return existing, await _revive(db, existing, tags)

    obj = LibraryItem(source_url=url, tags=tags, status=LibraryStatus.pending)
    db.add(obj)
    try:
        await db.commit()
    except IntegrityError:
        # 并发提交同一新链接：两边都查不到、都插入，后提交的撞唯一约束。
        await db.rollback()
        existing = await _find_by_url(db, url)
        if existing is None:  # 约束冲突却查不到，只能把原始错误抛出去
            raise
        return existing, await _revive(db, existing, tags)
    await db.refresh(obj)
    return obj, True


async def _find_by_url(db: AsyncSession, url: str) -> LibraryItem | None:
    return (
        await db.execute(
            select(LibraryItem).where(LibraryItem.source_url == url)
        )
    ).scalar_one_or_none()


async def _revive(
    db: AsyncSession, item: LibraryItem, tags: list[str]
) -> bool:
    """合并新 tags，必要时把条目重置为待抓。返回是否应派发抓取。"""
    merged = list(dict.fromkeys([*(item.tags or []), *tags]))
    changed = merged != (item.tags or [])
    if changed:
        item.tags = merged
    should_crawl = item.status in (LibraryStatus.failed, LibraryStatus.pending)
    if should_crawl:
        item.status = LibraryStatus.pending
        item.error_msg = None
        changed = True
    if changed:
        await db.commit()
        await db.refresh(item)
    return should_crawl


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
