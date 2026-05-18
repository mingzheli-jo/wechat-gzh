import uuid
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.accounts.models import Account
from app.api.deps import get_db
from app.auth.dependencies import get_current_username
from app.stats import service
from app.stats.schemas import (
    AccountStatsRow,
    ArticleStatsRow,
    RefreshTriggerResponse,
)
from app.tasks.stats import sync_all_accounts_stats, sync_one_account_stats

router = APIRouter(prefix="/stats", tags=["stats"])


@router.get("/accounts", response_model=list[AccountStatsRow])
async def list_accounts(
    db: AsyncSession = Depends(get_db),
    _: str = Depends(get_current_username),
) -> list[AccountStatsRow]:
    return await service.list_account_stats(db)


@router.get(
    "/accounts/{account_id}/articles", response_model=list[ArticleStatsRow]
)
async def list_articles(
    account_id: uuid.UUID,
    days: int = Query(default=30, ge=1, le=365),
    sort: str = Query(default="publish_time"),
    order: Literal["asc", "desc"] = Query(default="desc"),
    db: AsyncSession = Depends(get_db),
    _: str = Depends(get_current_username),
) -> list[ArticleStatsRow]:
    account = await db.get(Account, account_id)
    if account is None:
        raise HTTPException(404, "Account not found")
    return await service.list_articles(
        db, account_id, days=days, sort=sort, order=order
    )


@router.post(
    "/refresh", response_model=RefreshTriggerResponse, status_code=202
)
async def refresh(
    account_id: uuid.UUID | None = None,
    db: AsyncSession = Depends(get_db),
    _: str = Depends(get_current_username),
) -> RefreshTriggerResponse:
    if account_id is not None:
        account = await db.get(Account, account_id)
        if account is None:
            raise HTTPException(404, "Account not found")
        job = sync_one_account_stats.delay(str(account_id))
    else:
        job = sync_all_accounts_stats.delay()
    return RefreshTriggerResponse(job_id=str(job.id), status="queued")
