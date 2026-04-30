import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.library.models import LibraryItem, LibraryStatus


async def create_pending(
    db: AsyncSession, url: str, tags: list[str]
) -> LibraryItem:
    obj = LibraryItem(source_url=url, tags=tags, status=LibraryStatus.pending)
    db.add(obj)
    await db.commit()
    await db.refresh(obj)
    return obj


async def get(db: AsyncSession, item_id: uuid.UUID) -> LibraryItem | None:
    return await db.get(LibraryItem, item_id)


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
