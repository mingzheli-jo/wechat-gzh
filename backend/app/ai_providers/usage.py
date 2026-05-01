"""Helper to record AIUsage rows. Failures are swallowed and logged."""
import logging
import uuid
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai_providers.base import TokenUsage
from app.ai_providers.models import AIProvider, AIUsage

logger = logging.getLogger(__name__)


# Rough USD/¥-equivalent prices per 1M tokens. Approximate; update as needed.
_PRICE_PER_M_TOKENS: dict[str, dict[str, tuple[float, float]]] = {
    # provider_name -> { model_id: (prompt_per_m, completion_per_m) }
    "deepseek": {"deepseek-chat": (0.14, 0.28)},
    "kimi": {
        "moonshot-v1-8k": (1.0, 1.0),
        "moonshot-v1-32k": (3.0, 3.0),
        "moonshot-v1-128k": (10.0, 10.0),
    },
}


def estimate_cost(provider_name: str, model: str, usage: TokenUsage) -> Decimal:
    table = _PRICE_PER_M_TOKENS.get(provider_name, {})
    prompt_price, completion_price = table.get(model, (0.0, 0.0))
    cost = (
        usage.prompt_tokens * prompt_price
        + usage.completion_tokens * completion_price
    ) / 1_000_000
    return Decimal(f"{cost:.6f}")


async def record_usage(
    session: AsyncSession,
    *,
    provider_name: str,
    role: str | None,
    model: str,
    usage: TokenUsage,
    purpose: str,
    ref_id: uuid.UUID | None = None,
    error: str | None = None,
) -> None:
    try:
        provider = (
            await session.execute(
                select(AIProvider).where(AIProvider.name == provider_name)
            )
        ).scalar_one_or_none()
        row = AIUsage(
            provider_id=provider.id if provider else None,
            role=role,
            model=model,
            prompt_tokens=usage.prompt_tokens,
            completion_tokens=usage.completion_tokens,
            cost_estimate=estimate_cost(provider_name, model, usage),
            purpose=purpose,
            ref_id=ref_id,
            error=error,
        )
        session.add(row)
        await session.commit()
    except Exception:
        logger.exception("record_usage failed for purpose=%s", purpose)
