"""Theme-creation pipeline.

(optional crawl) -> extract ~100 char theme -> retrieve real related articles
from the library -> grounded divergent generation -> fact-consistency review.

Mirrors the rewrite pipeline's conventions: a `_create_with_session` core that
tests drive with their own session, an idempotency guard on the `pending`
status, registry hot-reload per task, and per-call usage recording.
"""
import asyncio
import logging
import uuid
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.accounts.models import Account
from app.ai_providers.registry import RegistryError, get_registry, load_from_db
from app.ai_providers.usage import record_usage
from app.config import get_settings
from app.crawler.fetcher import FetchError, fetch_html
from app.crawler.parser import parse_wechat_article
from app.creator import generator, retriever, theme_extractor
from app.creator.models import CreationInputMode, CreationStatus, ThemeCreation
from app.db.session import make_engine
from app.reviewer.grounding import review_grounding
from app.rewriter.renderer import render_markdown
from app.tasks.celery_app import celery_app

logger = logging.getLogger(__name__)


def _sources_text(sources: list[dict[str, Any]]) -> str:
    blocks: list[str] = []
    for idx, src in enumerate(sources, start=1):
        title = src.get("title") or "（无标题）"
        excerpt = src.get("excerpt") or ""
        blocks.append(f"[{idx}] {title}\n{excerpt}")
    return "\n\n".join(blocks)


async def _create_with_session(
    session: AsyncSession, creation_id: uuid.UUID
) -> None:
    creation = (
        await session.execute(
            select(ThemeCreation).where(ThemeCreation.id == creation_id)
        )
    ).scalar_one_or_none()
    if creation is None:
        logger.warning("theme_creation %s not found", creation_id)
        return
    # Idempotency guard: only run for pending rows. Re-runs go through
    # reset_for_regenerate (which moves status back to pending).
    if creation.status != CreationStatus.pending:
        logger.info(
            "skip creation %s: status=%s (idempotency guard)",
            creation.id,
            creation.status,
        )
        return

    await load_from_db(session)
    registry = get_registry()
    try:
        lite, lite_model = registry.role("lite")
        writer, writer_model = registry.role("writer")
        reviewer, reviewer_model = registry.role("reviewer")
    except RegistryError as exc:
        creation.status = CreationStatus.failed
        creation.error_msg = f"AI role binding error: {exc}"
        await session.commit()
        return

    settings = get_settings()

    try:
        # --- 1. Resolve theme (crawl + extract, or use manual theme) ---
        if creation.input_mode == CreationInputMode.link:
            if not creation.source_url:
                raise ValueError("链接模式缺少 source_url")
            creation.status = CreationStatus.extracting
            await session.commit()
            html = await fetch_html(creation.source_url)
            parsed = parse_wechat_article(html)
            creation.source_title = parsed.title
            creation.source_text_snapshot = parsed.content_text
            if not (parsed.content_text or "").strip():
                raise ValueError("原文抓取为空，无法提炼主题")
            theme, theme_usage = await theme_extractor.extract_theme(
                provider=lite,
                model=lite_model,
                content=parsed.content_text,
            )
            creation.extracted_theme = theme
            await session.commit()
            await record_usage(
                session,
                provider_name=lite.name,
                role="lite",
                model=lite_model,
                usage=theme_usage,
                purpose="creation_extract_theme",
                ref_id=creation.id,
            )
        else:
            theme = (creation.extracted_theme or "").strip()
            if not theme:
                raise ValueError("手动模式缺少主题文本")

        # --- 2. Retrieve grounding sources from the library ---
        creation.status = CreationStatus.retrieving
        await session.commit()
        keywords, kw_usage = await retriever.extract_keywords(
            provider=lite, model=lite_model, theme=theme
        )
        creation.keywords = keywords
        await record_usage(
            session,
            provider_name=lite.name,
            role="lite",
            model=lite_model,
            usage=kw_usage,
            purpose="creation_keywords",
            ref_id=creation.id,
        )
        candidates = await retriever.fetch_candidates(
            session,
            keywords,
            recent_count=settings.creation_recent_count,
            candidate_limit=settings.creation_candidate_limit,
        )
        sources: list[dict[str, Any]] = []
        if candidates:
            sources, rr_usage = await retriever.rerank(
                provider=lite,
                model=lite_model,
                theme=theme,
                candidates=candidates,
                top_k=settings.creation_retrieval_top_k,
            )
            await record_usage(
                session,
                provider_name=lite.name,
                role="lite",
                model=lite_model,
                usage=rr_usage,
                purpose="creation_rerank",
                ref_id=creation.id,
            )
        creation.retrieved_sources = sources
        await session.commit()

        # --- 3. Optional account context for style ---
        category = ""
        style_desc = ""
        content_prompt = ""
        if creation.account_id is not None:
            account = (
                await session.execute(
                    select(Account).where(Account.id == creation.account_id)
                )
            ).scalar_one_or_none()
            if account is not None:
                category = account.category or ""
                style_desc = account.style_desc or ""
                content_prompt = account.content_prompt or ""

        # --- 4. Grounded generation (title + content) ---
        creation.status = CreationStatus.generating
        await session.commit()

        title_result = await writer.chat(
            generator.build_title_messages(theme=theme, style_desc=style_desc),
            model=writer_model,
            temperature=0.7,
        )
        new_title = (title_result.content or "").strip()
        if new_title:
            creation.generated_title = new_title
        await record_usage(
            session,
            provider_name=writer.name,
            role="writer",
            model=writer_model,
            usage=title_result.usage,
            purpose="creation_title",
            ref_id=creation.id,
        )

        content_result = await writer.chat(
            generator.build_content_messages(
                theme=theme,
                sources=sources,
                category=category,
                style_desc=style_desc,
                content_prompt=content_prompt,
            ),
            model=writer_model,
            temperature=0.7,
            max_tokens=4000,
        )
        content_md = (content_result.content or "").strip()
        if not content_md:
            raise ValueError("文章生成返回空正文，已中止")
        creation.generated_content_md = content_md
        creation.generated_content_html = render_markdown(content_md)
        await session.commit()
        await record_usage(
            session,
            provider_name=writer.name,
            role="writer",
            model=writer_model,
            usage=content_result.usage,
            purpose="creation_content",
            ref_id=creation.id,
        )

        # --- 5. Fact-consistency review ---
        creation.status = CreationStatus.reviewing
        await session.commit()
        if sources:
            try:
                fact_check = await review_grounding(
                    provider=reviewer,
                    model=reviewer_model,
                    article=content_md,
                    sources_text=_sources_text(sources),
                )
            except Exception as exc:
                logger.warning(
                    "grounding review failed for creation %s: %r",
                    creation.id,
                    exc,
                )
                fact_check = {
                    "score": 0,
                    "unsupported_claims": [],
                    "issues": [f"事实核查失败：{exc}"],
                    "error": True,
                }
        else:
            # No grounding material: distinct from a real 0 fact-check score.
            # `mode` lets callers/UI tell the two apart.
            fact_check = {
                "score": None,
                "mode": "no_sources",
                "unsupported_claims": [],
                "issues": [],
                "note": "未检索到库内相关素材，本文未基于真实资料，请谨慎使用。",
            }
        creation.fact_check = fact_check
        creation.status = CreationStatus.done
        await session.commit()
    except FetchError as exc:
        logger.warning("creation crawl failed for %s: %s", creation.id, exc)
        creation.status = CreationStatus.failed
        creation.error_msg = f"fetch error: {exc}"
        await session.commit()
    except Exception as exc:
        logger.exception("creation pipeline failed for %s", creation.id)
        creation.status = CreationStatus.failed
        creation.error_msg = f"{type(exc).__name__}: {exc}"
        await session.commit()


async def _do_create(creation_id: uuid.UUID) -> None:
    engine = make_engine()
    sm = async_sessionmaker(engine, expire_on_commit=False)
    async with sm() as session:
        await _create_with_session(session, creation_id)
    await engine.dispose()


@celery_app.task(
    name="app.tasks.create.run_creation_pipeline",
    bind=True,
    max_retries=2,
    default_retry_delay=30,
)
def run_creation_pipeline(self: Any, creation_id: str) -> None:
    asyncio.run(_do_create(uuid.UUID(creation_id)))
