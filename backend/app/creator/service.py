import uuid

from sqlalchemy import delete as sa_delete
from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.creator.models import CreationInputMode, CreationStatus, ThemeCreation


# TODO(auto-publish): wired by the future unattended-publish client; staged now.
def check_auto_publish_gate(
    creation: ThemeCreation, *, min_score: int
) -> tuple[bool, str | None]:
    """Pure gate deciding whether a creation may be auto-published unattended.

    Returns (ok, reason_if_not). No DB/IO — callers pass a loaded row. This is
    for the future unattended pipeline; the manual publish endpoint enforces
    only the hard preconditions (mirroring manual draft-publish, which has no
    score threshold).
    """
    if creation.status != CreationStatus.done:
        return False, "创作尚未完成"
    if creation.account_id is None:
        return False, "未绑定公众号账号"
    if not (creation.generated_title and creation.generated_title.strip()):
        return False, "缺少标题"
    if not (
        creation.generated_content_html
        and creation.generated_content_html.strip()
    ):
        return False, "缺少正文"
    fact_check = creation.fact_check
    if not fact_check:
        return False, "缺少事实核查结果"
    if fact_check.get("mode") == "no_sources":
        return False, "无检索素材，未做事实核查"
    score = fact_check.get("score")
    if score is None:
        return False, "事实核查未给出分数"
    if score < min_score:
        return False, f"事实核查分数 {score} 低于阈值 {min_score}"
    return True, None


async def create_creation(
    db: AsyncSession,
    *,
    input_mode: CreationInputMode,
    source_url: str | None,
    theme: str | None,
    account_id: uuid.UUID | None,
) -> ThemeCreation:
    obj = ThemeCreation(
        input_mode=input_mode,
        source_url=source_url,
        # In manual mode the supplied theme is the extracted theme directly.
        extracted_theme=theme if input_mode == CreationInputMode.manual else None,
        account_id=account_id,
        status=CreationStatus.pending,
    )
    db.add(obj)
    await db.commit()
    await db.refresh(obj)
    return obj


async def get_creation(
    db: AsyncSession, creation_id: uuid.UUID
) -> ThemeCreation | None:
    return await db.get(ThemeCreation, creation_id)


async def list_creations_paginated(
    db: AsyncSession,
    *,
    status: CreationStatus | None = None,
    account_id: uuid.UUID | None = None,
    page: int = 1,
    page_size: int = 10,
) -> tuple[list[ThemeCreation], int]:
    base = select(ThemeCreation).order_by(ThemeCreation.created_at.desc())
    count_base = select(func.count()).select_from(ThemeCreation)

    if status is not None:
        base = base.where(ThemeCreation.status == status)
        count_base = count_base.where(ThemeCreation.status == status)
    if account_id is not None:
        base = base.where(ThemeCreation.account_id == account_id)
        count_base = count_base.where(ThemeCreation.account_id == account_id)

    paginated = base.limit(page_size).offset(max(0, (page - 1) * page_size))
    items = list((await db.execute(paginated)).scalars().all())
    total = int((await db.execute(count_base)).scalar_one())
    return items, total


async def update_creation(
    db: AsyncSession,
    obj: ThemeCreation,
    *,
    generated_title: str | None,
    generated_content_html: str | None,
) -> ThemeCreation:
    if generated_title is None and generated_content_html is None:
        return obj
    if generated_title is not None:
        obj.generated_title = generated_title
    if generated_content_html is not None:
        obj.generated_content_html = generated_content_html
    await db.commit()
    await db.refresh(obj)
    return obj


async def reset_for_regenerate(
    db: AsyncSession, obj: ThemeCreation
) -> ThemeCreation:
    """Clear generated output so the pipeline can re-run on the same row.

    The original input (source_url / manual theme) is preserved; manual-mode
    rows keep their extracted_theme, link-mode rows re-extract from scratch.
    Status returns to pending. Caller must ensure the row isn't mid-run.
    """
    keep_theme = (
        obj.extracted_theme
        if obj.input_mode == CreationInputMode.manual
        else None
    )
    await db.execute(
        update(ThemeCreation)
        .where(ThemeCreation.id == obj.id)
        .values(
            extracted_theme=keep_theme,
            keywords=None,
            retrieved_sources=None,
            generated_title=None,
            generated_content_md=None,
            generated_content_html=None,
            fact_check=None,
            error_msg=None,
            # Bulk UPDATE bypasses the ORM, so onupdate doesn't fire — set
            # updated_at explicitly to keep it fresh.
            updated_at=func.now(),
            status=CreationStatus.pending,
        )
    )
    await db.commit()
    await db.refresh(obj)
    return obj


async def delete_creation(db: AsyncSession, obj: ThemeCreation) -> None:
    await db.execute(
        sa_delete(ThemeCreation).where(ThemeCreation.id == obj.id)
    )
    await db.commit()
