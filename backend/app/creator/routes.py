import uuid

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db
from app.auth.dependencies import get_current_username
from app.creator import service
from app.creator.models import CreationInputMode, CreationStatus
from app.creator.schemas import (
    CreationCreateRequest,
    CreationDetail,
    CreationEdit,
    CreationListPage,
    CreationOut,
    CreationPublishRequest,
)
from app.drafts import service as drafts_service
from app.drafts.models import Draft, DraftStatus
from app.drafts.schemas import DraftOut

# NOTE: prefix is "/creations" (not "/api/creations"); api_router already
# mounts everything under /api in main.py.
router = APIRouter(prefix="/creations", tags=["creations"])

# Statuses that mean the pipeline is actively running — block mutation/delete.
RUNNING_STATUSES = (
    CreationStatus.pending,
    CreationStatus.extracting,
    CreationStatus.retrieving,
    CreationStatus.generating,
    CreationStatus.reviewing,
)


@router.post("", response_model=CreationOut, status_code=202)
async def create(
    payload: CreationCreateRequest,
    db: AsyncSession = Depends(get_db),
    _: str = Depends(get_current_username),
) -> CreationOut:
    # A source_url takes precedence (link mode); otherwise manual theme mode.
    if payload.source_url and payload.source_url.strip():
        input_mode = CreationInputMode.link
        source_url = payload.source_url.strip()
        theme = None
    else:
        input_mode = CreationInputMode.manual
        source_url = None
        theme = (payload.theme or "").strip()

    obj = await service.create_creation(
        db,
        input_mode=input_mode,
        source_url=source_url,
        theme=theme,
        account_id=payload.account_id,
    )
    from app.tasks.create import run_creation_pipeline

    run_creation_pipeline.delay(str(obj.id))
    return CreationOut.model_validate(obj)


@router.get("", response_model=CreationListPage)
async def list_all(
    status: CreationStatus | None = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(10, ge=1, le=100),
    account_id: uuid.UUID | None = None,
    db: AsyncSession = Depends(get_db),
    _: str = Depends(get_current_username),
) -> CreationListPage:
    items, total = await service.list_creations_paginated(
        db,
        status=status,
        account_id=account_id,
        page=page,
        page_size=page_size,
    )
    return CreationListPage(
        items=[CreationOut.model_validate(c) for c in items],
        total=total,
    )


@router.get("/{creation_id}", response_model=CreationDetail)
async def get_one(
    creation_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    _: str = Depends(get_current_username),
) -> CreationDetail:
    obj = await service.get_creation(db, creation_id)
    if obj is None:
        raise HTTPException(404, "Creation not found")
    return CreationDetail.model_validate(obj)


@router.patch("/{creation_id}", response_model=CreationDetail)
async def update(
    creation_id: uuid.UUID,
    payload: CreationEdit,
    db: AsyncSession = Depends(get_db),
    _: str = Depends(get_current_username),
) -> CreationDetail:
    obj = await service.get_creation(db, creation_id)
    if obj is None:
        raise HTTPException(404, "Creation not found")
    if obj.status in RUNNING_STATUSES:
        raise HTTPException(409, "生成中的创作不能编辑")
    obj = await service.update_creation(
        db,
        obj,
        generated_title=payload.generated_title,
        generated_content_html=payload.generated_content_html,
    )
    return CreationDetail.model_validate(obj)


@router.post("/{creation_id}/regenerate", response_model=CreationOut, status_code=202)
async def regenerate(
    creation_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    _: str = Depends(get_current_username),
) -> CreationOut:
    obj = await service.get_creation(db, creation_id)
    if obj is None:
        raise HTTPException(404, "Creation not found")
    if obj.status in RUNNING_STATUSES:
        raise HTTPException(409, "生成中的创作不能重新生成")
    obj = await service.reset_for_regenerate(db, obj)
    from app.tasks.create import run_creation_pipeline

    run_creation_pipeline.delay(str(obj.id))
    return CreationOut.model_validate(obj)


@router.post(
    "/{creation_id}/publish-to-wechat", response_model=DraftOut, status_code=202
)
async def publish_to_wechat(
    creation_id: uuid.UUID,
    payload: CreationPublishRequest,
    db: AsyncSession = Depends(get_db),
    _: str = Depends(get_current_username),
) -> DraftOut:
    obj = await service.get_creation(db, creation_id)
    if obj is None:
        raise HTTPException(404, "Creation not found")
    # Manual publish enforces only hard preconditions (no score gate); the
    # score gate is reserved for the future unattended pipeline.
    account_id = payload.account_id or obj.account_id
    if account_id is None:
        raise HTTPException(400, "未指定公众号账号")
    if obj.status != CreationStatus.done:
        raise HTTPException(409, "创作尚未完成，无法推送")
    if not (obj.generated_title and obj.generated_title.strip()):
        raise HTTPException(409, "创作缺少标题，无法推送")
    if not (
        obj.generated_content_html and obj.generated_content_html.strip()
    ):
        raise HTTPException(409, "创作缺少正文，无法推送")

    # Idempotency guard: a retry/double-click must not create a second draft or
    # re-dispatch the publish chain. Any existing non-failed draft for this
    # creation means it was already pushed (or is mid-push).
    existing = (
        await db.execute(
            select(Draft.id).where(
                Draft.source_creation_id == obj.id,
                Draft.status != DraftStatus.failed,
            )
        )
    ).first()
    if existing is not None:
        raise HTTPException(409, "该创作已生成草稿/已推送，勿重复推送")

    draft = await drafts_service.create_draft_from_creation(
        db,
        creation_id=obj.id,
        account_id=account_id,
        title=obj.generated_title,
        content_html=obj.generated_content_html,
    )

    from app.tasks.images import process_draft_images
    from app.tasks.publish import publish_draft

    process_draft_images.apply_async(
        args=[str(draft.id)], link=publish_draft.si(str(draft.id))
    )
    return DraftOut.model_validate(draft)


@router.delete("/{creation_id}", status_code=204)
async def delete(
    creation_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    _: str = Depends(get_current_username),
) -> None:
    obj = await service.get_creation(db, creation_id)
    if obj is None:
        raise HTTPException(404, "Creation not found")
    if obj.status in RUNNING_STATUSES:
        raise HTTPException(409, "生成中的创作不能删除")
    await service.delete_creation(db, obj)
