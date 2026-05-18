"""Image post API routes."""
import uuid
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.accounts import service as account_service
from app.api.deps import get_db
from app.auth.dependencies import get_current_username
from app.image_posts import service
from app.image_posts.models import (
    ImageAsset,
    ImagePost,
    ImagePostStatus,
)
from app.image_posts.schemas import (
    ImagePostCreate,
    ImagePostDetail,
    ImagePostListPage,
    ImagePostOut,
    ImagePostUpdate,
)
from app.image_posts.templates import TEMPLATES

router = APIRouter(prefix="/image-posts", tags=["image-posts"])


def _post_to_out(post: ImagePost) -> ImagePostOut:
    return ImagePostOut.model_validate(post)


def _post_to_detail(post: ImagePost) -> ImagePostDetail:
    return ImagePostDetail.model_validate(post)


@router.post("", response_model=ImagePostOut, status_code=202)
async def create(
    payload: ImagePostCreate,
    db: AsyncSession = Depends(get_db),
    _: str = Depends(get_current_username),
) -> ImagePostOut:
    account = await account_service.get_account(db, payload.account_id)
    if account is None:
        raise HTTPException(404, "Account not found")
    if not account.character_reference_path:
        raise HTTPException(400, "该公众号未上传角色参考图")

    if payload.panel_asset_ids is not None:
        expected = TEMPLATES[payload.template].panel_count
        if len(payload.panel_asset_ids) != expected:
            raise HTTPException(
                400,
                f"panel_asset_ids 长度需等于模板 panel_count ({expected})",
            )
        rows = (
            await db.execute(
                select(ImageAsset.id).where(
                    ImageAsset.id.in_(payload.panel_asset_ids),
                    ImageAsset.account_id == payload.account_id,
                )
            )
        ).all()
        if len(rows) != len(payload.panel_asset_ids):
            raise HTTPException(400, "存在非法或非本账号的 asset_id")

    post = ImagePost(
        account_id=payload.account_id,
        template=payload.template,
        topic=payload.topic,
        tone=payload.tone,
        status=ImagePostStatus.pending,
        panel_asset_ids=(
            [str(a) for a in payload.panel_asset_ids]
            if payload.panel_asset_ids
            else None
        ),
    )
    db.add(post)
    await db.commit()
    await db.refresh(post)

    from app.tasks.image_pipeline import generate_image_post
    generate_image_post.delay(str(post.id))

    return _post_to_out(post)


@router.get("", response_model=ImagePostListPage)
async def list_all(
    account_id: uuid.UUID | None = None,
    status: ImagePostStatus | None = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    _: str = Depends(get_current_username),
) -> ImagePostListPage:
    items, total = await service.list_image_posts(
        db,
        account_id=account_id,
        status=status,
        page=page,
        page_size=page_size,
    )
    return ImagePostListPage(
        items=[_post_to_out(p) for p in items],
        total=total,
    )


@router.get("/{post_id}", response_model=ImagePostDetail)
async def get_one(
    post_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    _: str = Depends(get_current_username),
) -> ImagePostDetail:
    obj = await service.get_image_post(db, post_id)
    if obj is None:
        raise HTTPException(404, "ImagePost not found")
    return _post_to_detail(obj)


@router.patch("/{post_id}", response_model=ImagePostDetail)
async def update(
    post_id: uuid.UUID,
    payload: ImagePostUpdate,
    db: AsyncSession = Depends(get_db),
    _: str = Depends(get_current_username),
) -> ImagePostDetail:
    obj = await service.get_image_post(db, post_id)
    if obj is None:
        raise HTTPException(404, "ImagePost not found")
    if payload.captions is not None:
        obj.captions = payload.captions
    await db.commit()
    await db.refresh(obj)
    return _post_to_detail(obj)


@router.delete("/{post_id}", status_code=204)
async def delete(
    post_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    _: str = Depends(get_current_username),
) -> None:
    obj = await service.get_image_post(db, post_id)
    if obj is None:
        raise HTTPException(404, "ImagePost not found")
    if obj.status in (
        ImagePostStatus.generating,
        ImagePostStatus.composing,
        ImagePostStatus.pushing,
    ):
        raise HTTPException(409, "进行中的图片草稿不能删除")
    if obj.composed_image_path:
        Path(obj.composed_image_path).unlink(missing_ok=True)
    await db.delete(obj)
    await db.commit()
