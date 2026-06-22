# ruff: noqa: E501
"""Retrieve real, related articles from the crawled library to ground writing.

Strategy (v1, no extra infra): the lite model extracts a few keywords from the
theme; Postgres ILIKE fetches keyword-matching + most-recent done items as a
candidate pool; the lite model reranks the pool against the theme and picks the
top-K. Excerpts handed downstream are sliced from the *real* article text, never
model-generated, so the generation stage stays grounded.
"""
import json
import uuid
from typing import Any

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai_providers.base import BaseProvider, Message, TokenUsage
from app.library.models import LibraryItem, LibraryStatus

# Reused so LLM output is sanitized before landing in the JSONB `keywords`
# column (lone surrogates break the Postgres JSONB write).
from app.reviewer.compliance import _strip_surrogates

# Chars of real article text stored per source (display + grounding material).
EXCERPT_CHARS = 800
# Shorter slice shown to the reranker so the candidate list stays compact.
RERANK_PREVIEW_CHARS = 300

KEYWORD_PROMPT = """你是一名检索助手。根据给定的文章主题，提炼 3-6 个最适合用于全文检索的中文关键词或短词。
要求：关键词应是主题中的核心实体、概念或事件，避免虚词和过于宽泛的词。
输出严格 JSON：{"keywords": ["词1", "词2", ...]}。"""

RERANK_PROMPT = """你是一名资料筛选员。下面给出一个【主题】和一批【候选文章】（含编号、标题、摘录）。
请从候选中挑出与主题最相关、最能作为写作素材的文章，最多 {top_k} 篇。
只选真正相关的；若某篇明显无关则不要选。
输出严格 JSON：{{"selected": [{{"index": 候选编号, "relevance": 0-100 相关度整数}}, ...]}}，按相关度从高到低排列。"""


def _parse_keywords(text: str) -> list[str]:
    try:
        parsed = json.loads(text)
    except json.JSONDecodeError:
        start, end = text.find("{"), text.rfind("}")
        if start >= 0 and end > start:
            try:
                parsed = json.loads(text[start : end + 1])
            except json.JSONDecodeError:
                return []
        else:
            return []
    if not isinstance(parsed, dict):
        return []
    raw = parsed.get("keywords") or []
    out: list[str] = []
    for kw in raw:
        s = _strip_surrogates(str(kw).strip())
        if s and s not in out:
            out.append(s)
    return out


def _parse_selected(text: str) -> list[dict[str, Any]]:
    try:
        parsed = json.loads(text)
    except json.JSONDecodeError:
        start, end = text.find("{"), text.rfind("}")
        if start >= 0 and end > start:
            try:
                parsed = json.loads(text[start : end + 1])
            except json.JSONDecodeError:
                return []
        else:
            return []
    if not isinstance(parsed, dict):
        return []
    return [s for s in (parsed.get("selected") or []) if isinstance(s, dict)]


async def extract_keywords(
    *, provider: BaseProvider, model: str, theme: str
) -> tuple[list[str], TokenUsage]:
    result = await provider.chat(
        [
            Message(role="system", content=KEYWORD_PROMPT),
            Message(role="user", content=f"【主题】{theme}"),
        ],
        model=model,
        json_mode=True,
        temperature=0.2,
    )
    return _parse_keywords(result.content), result.usage


async def fetch_candidates(
    session: AsyncSession,
    keywords: list[str],
    *,
    recent_count: int,
    candidate_limit: int,
) -> list[LibraryItem]:
    """Keyword-matching + most-recent done items, deduped, capped.

    Recent items are mixed in so the writing can reflect "current" library
    content even when keyword overlap is thin.
    """
    candidates: dict[uuid.UUID, LibraryItem] = {}

    if keywords:
        conditions = []
        for kw in keywords:
            like = f"%{kw}%"
            conditions.append(LibraryItem.original_title.ilike(like))
            conditions.append(LibraryItem.original_content_text.ilike(like))
        matched = (
            await session.execute(
                select(LibraryItem)
                .where(
                    LibraryItem.status == LibraryStatus.done,
                    or_(*conditions),
                )
                .order_by(LibraryItem.crawled_at.desc().nullslast())
                .limit(candidate_limit)
            )
        ).scalars().all()
        for item in matched:
            candidates[item.id] = item

    if recent_count > 0:
        recent = (
            await session.execute(
                select(LibraryItem)
                .where(LibraryItem.status == LibraryStatus.done)
                .order_by(LibraryItem.crawled_at.desc().nullslast())
                .limit(recent_count)
            )
        ).scalars().all()
        for item in recent:
            candidates.setdefault(item.id, item)

    return list(candidates.values())[:candidate_limit]


async def rerank(
    *,
    provider: BaseProvider,
    model: str,
    theme: str,
    candidates: list[LibraryItem],
    top_k: int,
) -> tuple[list[dict[str, Any]], TokenUsage]:
    """Rerank candidates; return grounding-source dicts for the top picks.

    Excerpts are sliced from the real article text — never the model's words.
    """
    lines: list[str] = []
    for idx, item in enumerate(candidates):
        preview = (item.original_content_text or "")[:RERANK_PREVIEW_CHARS]
        lines.append(
            f"[{idx}] 标题：{item.original_title or '（无标题）'}\n摘录：{preview}"
        )
    user = f"【主题】{theme}\n\n【候选文章】\n" + "\n\n".join(lines)
    result = await provider.chat(
        [
            Message(role="system", content=RERANK_PROMPT.format(top_k=top_k)),
            Message(role="user", content=user),
        ],
        model=model,
        json_mode=True,
        temperature=0.1,
    )
    selected = _parse_selected(result.content)

    sources: list[dict[str, Any]] = []
    seen: set[int] = set()
    for sel in selected:
        raw_idx = sel.get("index")
        if not isinstance(raw_idx, (int, str)):
            continue
        try:
            idx = int(raw_idx)
        except ValueError:
            continue
        if idx < 0 or idx >= len(candidates) or idx in seen:
            continue
        seen.add(idx)
        item = candidates[idx]
        try:
            relevance = int(sel.get("relevance", 0))
        except (TypeError, ValueError):
            relevance = 0
        sources.append(
            {
                "library_item_id": str(item.id),
                "title": item.original_title,
                "source_url": item.source_url,
                "relevance": relevance,
                "excerpt": (item.original_content_text or "")[:EXCERPT_CHARS],
            }
        )
        if len(sources) >= top_k:
            break
    return sources, result.usage
