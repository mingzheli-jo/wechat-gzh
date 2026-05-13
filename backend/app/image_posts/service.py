"""Image post DB helpers."""
import uuid

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.image_posts.models import ImageAsset, ImagePost, ImagePostStatus


async def get_image_post(
    db: AsyncSession, post_id: uuid.UUID
) -> ImagePost | None:
    return (
        await db.execute(select(ImagePost).where(ImagePost.id == post_id))
    ).scalar_one_or_none()


async def list_image_posts(
    db: AsyncSession,
    *,
    account_id: uuid.UUID | None = None,
    status: ImagePostStatus | None = None,
    page: int = 1,
    page_size: int = 20,
) -> tuple[list[ImagePost], int]:
    stmt = select(ImagePost)
    count_stmt = select(func.count()).select_from(ImagePost)
    if account_id is not None:
        stmt = stmt.where(ImagePost.account_id == account_id)
        count_stmt = count_stmt.where(ImagePost.account_id == account_id)
    if status is not None:
        stmt = stmt.where(ImagePost.status == status)
        count_stmt = count_stmt.where(ImagePost.status == status)
    stmt = (
        stmt.order_by(ImagePost.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    items = (await db.execute(stmt)).scalars().all()
    total = (await db.execute(count_stmt)).scalar_one()
    return list(items), total


async def get_image_asset(
    db: AsyncSession, asset_id: uuid.UUID
) -> ImageAsset | None:
    return (
        await db.execute(select(ImageAsset).where(ImageAsset.id == asset_id))
    ).scalar_one_or_none()


async def list_image_assets(
    db: AsyncSession,
    *,
    account_id: uuid.UUID | None = None,
    page: int = 1,
    page_size: int = 24,
) -> tuple[list[ImageAsset], int]:
    stmt = select(ImageAsset)
    count_stmt = select(func.count()).select_from(ImageAsset)
    if account_id is not None:
        stmt = stmt.where(ImageAsset.account_id == account_id)
        count_stmt = count_stmt.where(ImageAsset.account_id == account_id)
    stmt = (
        stmt.order_by(ImageAsset.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    items = (await db.execute(stmt)).scalars().all()
    total = (await db.execute(count_stmt)).scalar_one()
    return list(items), total
