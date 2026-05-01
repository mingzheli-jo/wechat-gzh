"""Periodic maintenance tasks (run via celery beat)."""
import asyncio
import logging
import shutil
from datetime import UTC, datetime, timedelta
from pathlib import Path

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import async_sessionmaker

from app.ai_providers.models import AIUsage
from app.config import get_settings
from app.db.session import make_engine
from app.drafts.models import Draft, DraftStatus
from app.images.models import Image
from app.library.models import LibraryItem, LibraryStatus
from app.tasks.celery_app import celery_app

logger = logging.getLogger(__name__)


async def _do_cleanup(
    *, image_age_days: int, ai_usage_age_days: int
) -> dict[str, int]:
    settings = get_settings()
    cutoff_image = datetime.now(UTC) - timedelta(days=image_age_days)
    cutoff_usage = datetime.now(UTC) - timedelta(days=ai_usage_age_days)

    counts = {
        "files_removed": 0,
        "images_db_removed": 0,
        "ai_usage_removed": 0,
        "draft_dirs_removed": 0,
    }

    engine = make_engine()
    sm = async_sessionmaker(engine, expire_on_commit=False)
    async with sm() as session:
        # 1. Find published or failed drafts whose images can be safely removed
        old_drafts = (
            await session.execute(
                select(Draft.id).where(
                    Draft.created_at < cutoff_image,
                    Draft.status.in_(
                        [DraftStatus.published_to_wechat, DraftStatus.failed]
                    ),
                )
            )
        ).scalars().all()

        for draft_id in old_drafts:
            draft_dir = Path(settings.image_storage_dir) / str(draft_id)
            if draft_dir.exists():
                shutil.rmtree(draft_dir, ignore_errors=True)
                counts["draft_dirs_removed"] += 1

            img_ids = (
                await session.execute(
                    select(Image.id).where(Image.draft_id == draft_id)
                )
            ).scalars().all()
            await session.execute(
                delete(Image).where(Image.draft_id == draft_id)
            )
            counts["images_db_removed"] += len(img_ids)

        # 2. Trim ai_usage to retention window
        usage_ids = (
            await session.execute(
                select(AIUsage.id).where(AIUsage.created_at < cutoff_usage)
            )
        ).scalars().all()
        await session.execute(
            delete(AIUsage).where(AIUsage.created_at < cutoff_usage)
        )
        counts["ai_usage_removed"] = len(usage_ids)

        await session.commit()
    await engine.dispose()
    return counts


async def _do_reset_stuck() -> dict[str, int]:
    """Reset library_items stuck in 'processing' for >1 hour back to 'pending'."""
    cutoff = datetime.now(UTC) - timedelta(hours=1)
    counts = {"library_items_reset": 0}
    engine = make_engine()
    sm = async_sessionmaker(engine, expire_on_commit=False)
    async with sm() as session:
        stuck = (
            await session.execute(
                select(LibraryItem).where(
                    LibraryItem.status == LibraryStatus.processing,
                    LibraryItem.updated_at < cutoff,
                )
            )
        ).scalars().all()
        for item in stuck:
            item.status = LibraryStatus.pending
            item.error_msg = "auto-reset: stuck in processing > 1h"
            counts["library_items_reset"] += 1
        await session.commit()
    await engine.dispose()
    return counts


@celery_app.task(name="app.tasks.maintenance.cleanup")
def cleanup(
    image_age_days: int = 30, ai_usage_age_days: int = 90
) -> dict[str, int]:
    counts = asyncio.run(
        _do_cleanup(
            image_age_days=image_age_days, ai_usage_age_days=ai_usage_age_days
        )
    )
    logger.info("cleanup result: %s", counts)
    return counts


@celery_app.task(name="app.tasks.maintenance.reset_stuck")
def reset_stuck() -> dict[str, int]:
    counts = asyncio.run(_do_reset_stuck())
    logger.info("reset_stuck result: %s", counts)
    return counts


# Beat schedule registered on celery_app
celery_app.conf.beat_schedule = {
    "cleanup-daily": {
        "task": "app.tasks.maintenance.cleanup",
        "schedule": 60 * 60 * 24,
    },
    "reset-stuck-hourly": {
        "task": "app.tasks.maintenance.reset_stuck",
        "schedule": 60 * 60,
    },
}
