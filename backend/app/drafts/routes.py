import uuid
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db
from app.auth.dependencies import get_current_username
from app.config import get_settings
from app.drafts import service
from app.drafts.models import DraftStatus
from app.drafts.schemas import (
    DraftDetail,
    DraftEdit,
    DraftListPage,
    DraftOut,
    ReviewReportOut,
    RewriteTriggerRequest,
)

router = APIRouter(prefix="/drafts", tags=["drafts"])

DraftGroup = Literal["active", "done", "published", "failed"]


@router.post("/rewrite", response_model=list[DraftOut], status_code=202)
async def trigger_rewrite(
    payload: RewriteTriggerRequest,
    db: AsyncSession = Depends(get_db),
    _: str = Depends(get_current_username),
) -> list[DraftOut]:
    settings = get_settings()
    if len(payload.library_item_ids) > settings.rewrite_batch_max:
        raise HTTPException(400, f"Batch exceeds {settings.rewrite_batch_max}")
    from app.tasks.rewrite import run_pipeline

    drafts: list[DraftOut] = []
    for item_id in payload.library_item_ids:
        d = await service.create_draft(
            db, library_item_id=item_id, account_id=payload.account_id
        )
        run_pipeline.delay(
            str(d.id),
            payload.override_title_prompt,
            payload.override_content_prompt,
        )
        drafts.append(DraftOut.model_validate(d))
    return drafts


@router.get("", response_model=DraftListPage)
async def list_all(
    group: DraftGroup | None = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(10, ge=1, le=100),
    account_id: uuid.UUID | None = None,
    db: AsyncSession = Depends(get_db),
    _: str = Depends(get_current_username),
) -> DraftListPage:
    items, total = await service.list_drafts_paginated(
        db,
        group=group,
        account_id=account_id,
        page=page,
        page_size=page_size,
    )
    return DraftListPage(
        items=[DraftOut.model_validate(r) for r in items],
        total=total,
    )


@router.get("/{draft_id}", response_model=DraftDetail)
async def get_one(
    draft_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    _: str = Depends(get_current_username),
) -> DraftDetail:
    obj = await service.get_draft(db, draft_id)
    if obj is None:
        raise HTTPException(404, "Draft not found")
    return DraftDetail.model_validate(obj)


@router.patch("/{draft_id}", response_model=DraftDetail)
async def update(
    draft_id: uuid.UUID,
    payload: DraftEdit,
    db: AsyncSession = Depends(get_db),
    _: str = Depends(get_current_username),
) -> DraftDetail:
    obj = await service.get_draft(db, draft_id)
    if obj is None:
        raise HTTPException(404, "Draft not found")
    obj = await service.update_draft(
        db, obj, title=payload.title, content_html=payload.content_html
    )
    return DraftDetail.model_validate(obj)


@router.delete("/{draft_id}", status_code=204)
async def delete(
    draft_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    _: str = Depends(get_current_username),
) -> None:
    obj = await service.get_draft(db, draft_id)
    if obj is None:
        raise HTTPException(404, "Draft not found")
    if obj.status in (DraftStatus.draft, DraftStatus.reviewing):
        raise HTTPException(409, "进行中的草稿不能删除")
    await service.delete_draft_with_cleanup(db, obj)


@router.post("/{draft_id}/rewrite", response_model=DraftOut, status_code=202)
async def rewrite_again(
    draft_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    _: str = Depends(get_current_username),
) -> DraftOut:
    obj = await service.get_draft(db, draft_id)
    if obj is None:
        raise HTTPException(404, "Draft not found")
    if obj.status in (DraftStatus.draft, DraftStatus.reviewing):
        raise HTTPException(409, "进行中的草稿不能重写")
    if obj.status == DraftStatus.published_to_wechat:
        raise HTTPException(409, "已推送至微信的草稿不能重写")
    settings = get_settings()
    if obj.regenerate_count >= settings.draft_max_regenerations:
        raise HTTPException(
            409,
            f"已达 {settings.draft_max_regenerations} 次改写上限",
        )
    obj = await service.reset_for_rewrite(db, obj)
    from app.tasks.rewrite import run_pipeline

    run_pipeline.delay(str(obj.id), None, None)
    return DraftOut.model_validate(obj)


@router.get("/{draft_id}/report", response_model=ReviewReportOut)
async def get_report(
    draft_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    _: str = Depends(get_current_username),
) -> ReviewReportOut:
    draft = await service.get_draft(db, draft_id)
    if draft is None or draft.review_report_id is None:
        raise HTTPException(404, "Report not found")
    report = await service.get_review_report(db, draft.review_report_id)
    if report is None:
        raise HTTPException(404, "Report not found")
    return ReviewReportOut.model_validate(report)


@router.post("/{draft_id}/publish-to-wechat", response_model=DraftOut, status_code=202)
async def publish(
    draft_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    _: str = Depends(get_current_username),
) -> DraftOut:
    obj = await service.get_draft(db, draft_id)
    if obj is None:
        raise HTTPException(404, "Draft not found")
    from app.tasks.images import process_draft_images
    from app.tasks.publish import publish_draft

    process_draft_images.apply_async(
        args=[str(obj.id)], link=publish_draft.si(str(obj.id))
    )
    return DraftOut.model_validate(obj)
