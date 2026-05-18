"""Image asset library routes."""
import mimetypes
import uuid
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import FileResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db
from app.auth.dependencies import get_current_username
from app.config import get_settings
from app.image_posts import service
from app.image_posts.schemas import ImageAssetListPage, ImageAssetOut

router = APIRouter(prefix="/image-assets", tags=["image-assets"])


@router.get("", response_model=ImageAssetListPage)
async def list_all(
    account_id: uuid.UUID | None = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(24, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    _: str = Depends(get_current_username),
) -> ImageAssetListPage:
    items, total = await service.list_image_assets(
        db, account_id=account_id, page=page, page_size=page_size,
    )
    return ImageAssetListPage(
        items=[ImageAssetOut.model_validate(a) for a in items], total=total,
    )


@router.get("/{asset_id}", response_model=ImageAssetOut)
async def get_one(
    asset_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    _: str = Depends(get_current_username),
) -> ImageAssetOut:
    obj = await service.get_image_asset(db, asset_id)
    if obj is None:
        raise HTTPException(404, "ImageAsset not found")
    return ImageAssetOut.model_validate(obj)


@router.get("/{asset_id}/file")
async def get_file(
    asset_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    _: str = Depends(get_current_username),
) -> FileResponse:
    obj = await service.get_image_asset(db, asset_id)
    if obj is None:
        raise HTTPException(404, "ImageAsset not found")
    p = Path(obj.image_path).resolve()
    # Defense in depth: image_path is set by our own Celery code under
    # settings.image_storage_dir, but a tampered DB row could escape the
    # storage root. Refuse anything outside it.
    storage_root = Path(get_settings().image_storage_dir).resolve()
    try:
        p.relative_to(storage_root)
    except ValueError as exc:
        raise HTTPException(403, "Forbidden") from exc
    if not p.exists():
        raise HTTPException(404, "Image file missing")
    guessed, _enc = mimetypes.guess_type(str(p))
    return FileResponse(p, media_type=guessed or "application/octet-stream")
