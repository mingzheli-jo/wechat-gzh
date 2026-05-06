import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db
from app.auth.dependencies import get_current_username
from app.library import service
from app.library.models import LibraryStatus
from app.library.schemas import (
    IngestRequest,
    LibraryItemDetail,
    LibraryItemOut,
    TagsUpdate,
)

router = APIRouter(prefix="/library", tags=["library"])


@router.post("", response_model=list[LibraryItemOut], status_code=201)
async def ingest(
    payload: IngestRequest,
    db: AsyncSession = Depends(get_db),
    _: str = Depends(get_current_username),
) -> list[LibraryItemOut]:
    from app.tasks.crawl import crawl_library_item

    items: list[LibraryItemOut] = []
    for url in payload.urls:
        obj = await service.create_pending(db, url, payload.tags)
        crawl_library_item.delay(str(obj.id))
        items.append(LibraryItemOut.model_validate(obj))
    return items


@router.get("", response_model=list[LibraryItemOut])
async def list_all(
    status_filter: LibraryStatus | None = None,
    tag: str | None = None,
    limit: int = 50,
    offset: int = 0,
    db: AsyncSession = Depends(get_db),
    _: str = Depends(get_current_username),
) -> list[LibraryItemOut]:
    rows = await service.list_items_with_counts(
        db, status=status_filter, tag=tag, limit=limit, offset=offset
    )
    return [
        LibraryItemOut.model_validate(item).model_copy(
            update={"rewrite_count": count}
        )
        for item, count in rows
    ]


@router.get("/{item_id}", response_model=LibraryItemDetail)
async def get_one(
    item_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    _: str = Depends(get_current_username),
) -> LibraryItemDetail:
    obj = await service.get(db, item_id)
    if obj is None:
        raise HTTPException(404, "Item not found")
    return LibraryItemDetail.model_validate(obj)


@router.patch("/{item_id}/tags", response_model=LibraryItemOut)
async def update_tags(
    item_id: uuid.UUID,
    payload: TagsUpdate,
    db: AsyncSession = Depends(get_db),
    _: str = Depends(get_current_username),
) -> LibraryItemOut:
    obj = await service.get(db, item_id)
    if obj is None:
        raise HTTPException(404, "Item not found")
    return LibraryItemOut.model_validate(
        await service.set_tags(db, obj, payload.tags)
    )


@router.delete("/{item_id}", status_code=204)
async def delete(
    item_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    _: str = Depends(get_current_username),
) -> None:
    obj = await service.get(db, item_id)
    if obj is None:
        raise HTTPException(404, "Item not found")
    await service.delete(db, obj)


@router.post("/{item_id}/retry", response_model=LibraryItemOut)
async def retry(
    item_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    _: str = Depends(get_current_username),
) -> LibraryItemOut:
    from app.tasks.crawl import crawl_library_item

    obj = await service.get(db, item_id)
    if obj is None:
        raise HTTPException(404, "Item not found")
    obj.status = LibraryStatus.pending
    obj.error_msg = None
    await db.commit()
    await db.refresh(obj)
    crawl_library_item.delay(str(obj.id))
    return LibraryItemOut.model_validate(obj)
