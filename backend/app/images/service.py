import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.images.models import Image, ImageStatus


async def create_pending_for_draft(
    db: AsyncSession, draft_id: uuid.UUID, original_urls: list[str]
) -> list[Image]:
    images: list[Image] = []
    for idx, url in enumerate(original_urls):
        img = Image(
            draft_id=draft_id,
            original_url=url,
            position=idx,
            is_cover=(idx == 0),
            status=ImageStatus.pending,
        )
        db.add(img)
        images.append(img)
    await db.commit()
    for img in images:
        await db.refresh(img)
    return images


async def list_for_draft(
    db: AsyncSession, draft_id: uuid.UUID
) -> list[Image]:
    rows = (
        await db.execute(
            select(Image)
            .where(Image.draft_id == draft_id)
            .order_by(Image.position)
        )
    ).scalars().all()
    return list(rows)


async def get(db: AsyncSession, image_id: uuid.UUID) -> Image | None:
    return await db.get(Image, image_id)


async def set_cover(
    db: AsyncSession, draft_id: uuid.UUID, image_id: uuid.UUID
) -> None:
    rows = await list_for_draft(db, draft_id)
    for img in rows:
        img.is_cover = img.id == image_id
    await db.commit()


async def mark_removed(db: AsyncSession, image: Image) -> Image:
    image.status = ImageStatus.removed
    image.is_cover = False
    await db.commit()
    await db.refresh(image)
    return image
