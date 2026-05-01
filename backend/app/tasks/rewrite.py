"""Rewrite pipeline: title -> content -> review (4-dim group) -> aggregate."""
import asyncio
import logging
import uuid
from pathlib import Path
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.accounts.models import Account
from app.ai_providers.registry import RegistryError, get_registry, load_from_db
from app.ai_providers.usage import record_usage
from app.db.session import make_engine
from app.drafts.models import Draft, DraftStatus, ReviewReport
from app.images import service as image_service
from app.library.models import LibraryItem
from app.reviewer.aggregator import aggregate
from app.reviewer.clickbait import review_clickbait
from app.reviewer.compliance import review_compliance
from app.reviewer.originality import review_originality
from app.reviewer.quality import review_quality
from app.reviewer.sensitive_words import SensitiveWordChecker
from app.rewriter.prompt_builder import (
    build_content_messages,
    build_title_messages,
)
from app.tasks.celery_app import celery_app

logger = logging.getLogger(__name__)


SENSITIVE_WORDS_PATH = (
    Path(__file__).parent.parent.parent / "data" / "sensitive_words.txt"
)


async def _ensure_registry(session: AsyncSession) -> None:
    """Reload registry from DB on every call.

    This is intentional: the API container's registry hot-reloads on PUT
    /role-bindings, but the worker process's registry is a separate in-memory
    instance and would otherwise hold stale provider/key data after binding
    edits. The cost is cheap (a couple of SELECTs per task).
    """
    await load_from_db(session)


async def _rewrite_with_session(
    session: AsyncSession,
    draft_id: uuid.UUID,
    override_title: str | None,
    override_content: str | None,
) -> None:
    """Core rewrite + review pipeline. Tests pass their own session."""
    draft = (
        await session.execute(select(Draft).where(Draft.id == draft_id))
    ).scalar_one_or_none()
    if draft is None:
        return
    item = (
        await session.execute(
            select(LibraryItem).where(LibraryItem.id == draft.library_item_id)
        )
    ).scalar_one()
    account = (
        await session.execute(
            select(Account).where(Account.id == draft.account_id)
        )
    ).scalar_one()

    await _ensure_registry(session)
    registry = get_registry()
    try:
        writer, writer_model = registry.role("writer")
        reviewer, reviewer_model = registry.role("reviewer")
    except RegistryError as exc:
        draft.status = DraftStatus.failed
        draft.error_msg = f"AI role binding error: {exc}"
        await session.commit()
        return

    try:
        title_msgs = build_title_messages(
            account_title_prompt=account.title_prompt,
            category=account.category,
            style_desc=account.style_desc,
            original_title=item.original_title or "",
            override=override_title,
        )
        title_result = await writer.chat(
            title_msgs, model=writer_model, temperature=0.7
        )
        draft.title = title_result.content.strip()
        await record_usage(
            session,
            provider_name=writer.name,
            role="writer",
            model=writer_model,
            usage=title_result.usage,
            purpose="rewrite_title",
            ref_id=draft.id,
        )

        content_msgs = build_content_messages(
            account_content_prompt=account.content_prompt,
            category=account.category,
            style_desc=account.style_desc,
            original_content=item.original_content_text or "",
            override=override_content,
        )
        content_result = await writer.chat(
            content_msgs,
            model=writer_model,
            temperature=0.7,
            max_tokens=4000,
        )
        draft.content_html = content_result.content
        draft.status = DraftStatus.reviewing
        await session.commit()
        await record_usage(
            session,
            provider_name=writer.name,
            role="writer",
            model=writer_model,
            usage=content_result.usage,
            purpose="rewrite_content",
            ref_id=draft.id,
        )

        checker = SensitiveWordChecker.from_file(SENSITIVE_WORDS_PATH)
        review_tasks = [
            review_compliance(
                provider=reviewer,
                model=reviewer_model,
                title=draft.title,
                content=item.original_content_text or "",
                sensitive_checker=checker,
            ),
            review_originality(
                provider=reviewer,
                model=reviewer_model,
                original_text=item.original_content_text or "",
                rewritten_text=content_result.content,
            ),
            review_quality(
                provider=reviewer,
                model=reviewer_model,
                title=draft.title,
                content=content_result.content,
            ),
            review_clickbait(
                provider=reviewer,
                model=reviewer_model,
                title=draft.title,
                content_excerpt=(content_result.content or "")[:1500],
            ),
        ]
        comp, orig, qual, cb = await asyncio.gather(
            *review_tasks, return_exceptions=False
        )
        reports: dict[str, Any] = {
            "compliance": comp,
            "originality": orig,
            "quality": qual,
            "clickbait": cb,
        }
        overall = aggregate(reports)

        report = ReviewReport(
            draft_id=draft.id,
            compliance=comp,
            originality=orig,
            quality=qual,
            clickbait=cb,
            overall_score=overall,
        )
        session.add(report)
        await session.flush()
        draft.review_report_id = report.id
        draft.status = DraftStatus.reviewed
        await session.commit()

        if item.images:
            await image_service.create_pending_for_draft(
                session,
                draft_id=draft.id,
                original_urls=[img["url"] for img in item.images],
            )
    except Exception as exc:
        logger.exception("rewrite pipeline failed for draft %s", draft.id)
        draft.status = DraftStatus.failed
        draft.error_msg = f"{type(exc).__name__}: {exc}"
        await session.commit()


async def _do_rewrite(
    draft_id: uuid.UUID,
    override_title: str | None,
    override_content: str | None,
) -> None:
    engine = make_engine()
    sm = async_sessionmaker(engine, expire_on_commit=False)
    async with sm() as session:
        await _rewrite_with_session(
            session, draft_id, override_title, override_content
        )
    await engine.dispose()


@celery_app.task(
    name="app.tasks.rewrite.run_pipeline",
    bind=True,
    max_retries=2,
    default_retry_delay=30,
)
def run_pipeline(
    self: Any,
    draft_id: str,
    override_title: str | None = None,
    override_content: str | None = None,
) -> None:
    asyncio.run(
        _do_rewrite(uuid.UUID(draft_id), override_title, override_content)
    )
