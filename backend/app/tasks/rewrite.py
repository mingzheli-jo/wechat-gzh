"""Rewrite pipeline: title -> content -> review (4-dim group) -> aggregate."""
import asyncio
import json
import logging
import uuid
from pathlib import Path
from typing import Any, cast

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.accounts.models import Account
from app.ai_providers.registry import RegistryError, get_registry, load_from_db
from app.ai_providers.usage import record_usage
from app.config import get_settings
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
from app.rewriter.renderer import render_markdown
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
    # 幂等守卫：仅对处于 `draft` 状态的草稿执行改写。任务因 acks_late 重投时，
    # 已进入 reviewing/reviewed/published/failed 的草稿不再重复改写（避免重复调用
    # LLM 烧钱、重复产出）。需要重跑请走 reset_for_rewrite（会把状态重置为 draft）。
    if draft.status != DraftStatus.draft:
        logger.info(
            "skip rewrite for draft %s: status=%s (idempotency guard)",
            draft.id,
            draft.status,
        )
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
        original_text = item.original_content_text or ""
        logger.info(
            "rewrite start: draft_id=%s library_item_id=%s source_url=%s "
            "title=%r content_len=%d content_head=%r",
            draft.id,
            item.id,
            (item.source_url or "")[:80],
            (item.original_title or "")[:50],
            len(original_text),
            original_text[:80],
        )

        def _coerce(result: Any, dim: str) -> dict[str, Any]:
            if isinstance(result, BaseException):
                logger.warning(
                    "reviewer dim %s failed for draft %s: %r",
                    dim,
                    draft.id,
                    result,
                )
                return {
                    "score": 0,
                    "issues": [f"{dim} 审核失败：{result}"],
                    "error": True,
                }
            return cast(dict[str, Any], result)

        def _issues_text(block: dict[str, Any]) -> str:
            lines: list[str] = []
            for issue in block.get("issues") or []:
                lines.append(
                    f"- {issue if isinstance(issue, str) else json.dumps(issue, ensure_ascii=False)}"
                )
            return "\n".join(lines)

        checker = SensitiveWordChecker.from_file(SENSITIVE_WORDS_PATH)
        settings = get_settings()
        max_fix_passes = (
            settings.review_auto_fix_max_passes
            if settings.review_auto_fix_enabled
            else 0
        )
        corrections = ""
        comp = orig = qual = cb = {}
        content_result = None

        # 合规不达标时自动重写一轮：把上一稿的违规条目回灌给写手模型。
        # 只针对 compliance——原创度和 AI 味不达标属于风格问题，交由人工判断，
        # 自动重跑既费 token 又未必收敛。
        for attempt in range(max_fix_passes + 1):
            content_msgs = build_content_messages(
                account_content_prompt=account.content_prompt,
                category=account.category,
                style_desc=account.style_desc,
                original_content=item.original_content_text or "",
                override=override_content,
                corrections=corrections,
            )
            content_result = await writer.chat(
                content_msgs,
                model=writer_model,
                temperature=0.7,
                max_tokens=4000,
            )
            if not (content_result.content or "").strip():
                raise ValueError("改写返回空正文，已中止")
            draft.content_html = render_markdown(content_result.content)
            draft.status = DraftStatus.reviewing
            await session.commit()
            await record_usage(
                session,
                provider_name=writer.name,
                role="writer",
                model=writer_model,
                usage=content_result.usage,
                purpose="rewrite_content" if attempt == 0 else "rewrite_content_autofix",
                ref_id=draft.id,
            )

            # 标题基于本轮成稿生成，而非原标题。放在正文之后，确保标题概括的是
            # 真正要发的内容；自动重试改了正文时，标题也随之重写，避免标文错位。
            title_msgs = build_title_messages(
                account_title_prompt=account.title_prompt,
                category=account.category,
                style_desc=account.style_desc,
                original_title=item.original_title or "",
                rewritten_content=content_result.content or "",
                override=override_title,
            )
            title_result = await writer.chat(
                title_msgs, model=writer_model, temperature=0.7
            )
            new_title = title_result.content.strip()
            if not new_title:
                raise ValueError("改写返回空标题，已中止")
            draft.title = new_title
            await session.commit()
            await record_usage(
                session,
                provider_name=writer.name,
                role="writer",
                model=writer_model,
                usage=title_result.usage,
                purpose="rewrite_title" if attempt == 0 else "rewrite_title_autofix",
                ref_id=draft.id,
            )

            review_tasks = [
                review_compliance(
                    provider=reviewer,
                    model=reviewer_model,
                    title=draft.title,
                    # 必须审改写后的正文——那才是要推送到公众号的内容。
                    # 早期版本误传了 item.original_content_text（原文），导致合规维度
                    # 一直在审素材而非成稿，改写引入的违规表述全部漏检。
                    content=content_result.content or "",
                    sensitive_checker=checker,
                    # 账号自己的红线（禁用词、禁止的表述方式）写在 content_prompt 里，
                    # 通用合规规则覆盖不到，需一并送审。
                    account_rules=account.content_prompt or "",
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
            # 容错：单个审核维度失败不应让整篇改写报废（否则草稿卡在 failed 且无报告，
            # 用户无法推送）。失败维度用占位结果补齐，保证 ReviewReport 一定生成。
            results = await asyncio.gather(*review_tasks, return_exceptions=True)

            comp = _coerce(results[0], "compliance")
            orig = _coerce(results[1], "originality")
            qual = _coerce(results[2], "quality")
            cb = _coerce(results[3], "clickbait")

            if comp.get("error"):
                # 合规维度本身挂了，拿不到可回灌的问题清单，重试没有意义。
                break
            if comp["score"] >= settings.review_auto_fix_compliance_min:
                break
            if attempt >= max_fix_passes:
                logger.warning(
                    "draft %s compliance=%d still below %d after %d auto-fix pass(es)",
                    draft.id,
                    comp["score"],
                    settings.review_auto_fix_compliance_min,
                    max_fix_passes,
                )
                break
            corrections = _issues_text(comp)
            logger.info(
                "draft %s compliance=%d < %d, triggering auto-fix pass %d",
                draft.id,
                comp["score"],
                settings.review_auto_fix_compliance_min,
                attempt + 1,
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
