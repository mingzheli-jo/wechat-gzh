import uuid

from fastapi import APIRouter, Depends, HTTPException, Query
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
)

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
