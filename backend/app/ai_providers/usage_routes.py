from datetime import UTC, datetime, timedelta
from decimal import Decimal

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai_providers.models import AIProvider, AIUsage
from app.api.deps import get_db
from app.auth.dependencies import get_current_username

router = APIRouter(prefix="/usage", tags=["usage"])


class DailyUsage(BaseModel):
    day: str
    prompt_tokens: int
    completion_tokens: int
    cost_estimate: float


class RoleUsage(BaseModel):
    role: str | None
    provider: str | None
    model: str
    calls: int
    prompt_tokens: int
    completion_tokens: int
    cost_estimate: float


class UsageSummary(BaseModel):
    days: int
    daily: list[DailyUsage]
    by_role: list[RoleUsage]
    total_prompt_tokens: int
    total_completion_tokens: int
    total_cost: float


@router.get("/summary", response_model=UsageSummary)
async def summary(
    days: int = 30,
    db: AsyncSession = Depends(get_db),
    _: str = Depends(get_current_username),
) -> UsageSummary:
    cutoff = datetime.now(UTC) - timedelta(days=days)

    daily_stmt = (
        select(
            func.date_trunc("day", AIUsage.created_at).label("day"),
            func.sum(AIUsage.prompt_tokens).label("prompt"),
            func.sum(AIUsage.completion_tokens).label("completion"),
            func.sum(AIUsage.cost_estimate).label("cost"),
        )
        .where(AIUsage.created_at >= cutoff)
        .group_by("day")
        .order_by("day")
    )
    daily_rows = (await db.execute(daily_stmt)).all()
    daily = [
        DailyUsage(
            day=row.day.date().isoformat(),
            prompt_tokens=int(row.prompt or 0),
            completion_tokens=int(row.completion or 0),
            cost_estimate=float(row.cost or Decimal(0)),
        )
        for row in daily_rows
    ]

    role_stmt = (
        select(
            AIUsage.role,
            AIProvider.name.label("provider"),
            AIUsage.model,
            func.count().label("calls"),
            func.sum(AIUsage.prompt_tokens).label("prompt"),
            func.sum(AIUsage.completion_tokens).label("completion"),
            func.sum(AIUsage.cost_estimate).label("cost"),
        )
        .join(AIProvider, AIUsage.provider_id == AIProvider.id, isouter=True)
        .where(AIUsage.created_at >= cutoff)
        .group_by(AIUsage.role, AIProvider.name, AIUsage.model)
        .order_by(func.sum(AIUsage.cost_estimate).desc())
    )
    role_rows = (await db.execute(role_stmt)).all()
    by_role = [
        RoleUsage(
            role=row.role,
            provider=row.provider,
            model=row.model,
            calls=int(row.calls),
            prompt_tokens=int(row.prompt or 0),
            completion_tokens=int(row.completion or 0),
            cost_estimate=float(row.cost or Decimal(0)),
        )
        for row in role_rows
    ]

    total_p = sum(d.prompt_tokens for d in daily)
    total_c = sum(d.completion_tokens for d in daily)
    total_cost = sum(d.cost_estimate for d in daily)

    return UsageSummary(
        days=days,
        daily=daily,
        by_role=by_role,
        total_prompt_tokens=total_p,
        total_completion_tokens=total_c,
        total_cost=total_cost,
    )
