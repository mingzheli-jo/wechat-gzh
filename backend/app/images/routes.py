import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db
from app.auth.dependencies import get_current_username
from app.images import service
from app.images.schemas import ImageOut

router = APIRouter(prefix="/images", tags=["images"])


@router.get("/by-draft/{draft_id}", response_model=list[ImageOut])
async def list_for_draft(
    draft_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    _: str = Depends(get_current_username),
) -> list[ImageOut]:
    return [
        ImageOut.model_validate(r)
        for r in await service.list_for_draft(db, draft_id)
    ]


@router.post("/{image_id}/cover", response_model=list[ImageOut])
async def set_cover(
    image_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    _: str = Depends(get_current_username),
) -> list[ImageOut]:
    img = await service.get(db, image_id)
    if img is None:
        raise HTTPException(404, "Image not found")
    await service.set_cover(db, img.draft_id, img.id)
    return [
        ImageOut.model_validate(r)
        for r in await service.list_for_draft(db, img.draft_id)
    ]


@router.delete("/{image_id}", response_model=ImageOut)
async def remove(
    image_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    _: str = Depends(get_current_username),
) -> ImageOut:
    img = await service.get(db, image_id)
    if img is None:
        raise HTTPException(404, "Image not found")
    return ImageOut.model_validate(await service.mark_removed(db, img))
