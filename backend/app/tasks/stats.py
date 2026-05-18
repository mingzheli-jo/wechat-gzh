"""Sync wechat account & article stats (daily via beat)."""
import asyncio
import logging
import uuid
from datetime import UTC, date, datetime, timedelta, timezone
from typing import Any

from celery import shared_task  # type: ignore[import-untyped]
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.accounts.models import Account
from app.config import get_settings
from app.db.session import make_engine
from app.stats import service
from app.wechat import stats as wechat_stats
from app.wechat import token as wechat_token

logger = logging.getLogger(__name__)


def _yesterday_in_beijing() -> date:
    tz_beijing = timezone(timedelta(hours=8))
    return (datetime.now(tz_beijing) - timedelta(days=1)).date()


def _parse_msgid(raw: str) -> tuple[int, int]:
    if "_" in raw:
        head, _, tail = raw.partition("_")
        return int(head), int(tail)
    return int(raw), 0


async def _sync_followers(
    db: AsyncSession, account: Account, access_token: str, yesterday: date
) -> None:
    follower_count = 0
    new_follow = 0
    cancel_follow = 0

    cum_rows = await wechat_stats.fetch_user_cumulate(
        access_token=access_token, begin_date=yesterday, end_date=yesterday
    )
    if cum_rows:
        follower_count = int(cum_rows[-1].get("cumulate_user", 0))

    sum_rows = await wechat_stats.fetch_user_summary(
        access_token=access_token, begin_date=yesterday, end_date=yesterday
    )
    if sum_rows:
        new_follow = sum(int(r.get("new_user", 0)) for r in sum_rows)
        cancel_follow = sum(int(r.get("cancel_user", 0)) for r in sum_rows)

    await service.upsert_account_stats(
        db,
        account.id,
        follower_count=follower_count,
        new_follow=new_follow,
        cancel_follow=cancel_follow,
        synced_at=datetime.now(UTC),
    )


async def _sync_articles(
    db: AsyncSession,
    account: Account,
    access_token: str,
    yesterday: date,
    backfill_days: int,
) -> None:
    end = yesterday
    start = end - timedelta(days=backfill_days)

    rows: list[dict[str, Any]] = []
    cursor = start
    while cursor <= end:
        chunk_end = min(cursor + timedelta(days=6), end)
        try:
            chunk = await wechat_stats.fetch_article_total(
                access_token=access_token,
                begin_date=cursor,
                end_date=chunk_end,
            )
            rows.extend(chunk)
        except Exception:
            logger.exception(
                "fetch_article_total failed: account=%s window=%s..%s",
                account.id,
                cursor,
                chunk_end,
            )
        cursor = chunk_end + timedelta(days=1)

    synced = datetime.now(UTC)
    for row in rows:
        try:
            msgid_str = row.get("msgid", "")
            msgid_int, idx = _parse_msgid(str(msgid_str))
            title = str(row.get("title", ""))[:200]
            details_raw = row.get("details") or []
            details: list[dict[str, Any]] = (
                details_raw if isinstance(details_raw, list) else []
            )
            detail: dict[str, Any] = details[0] if details else {}
            read_count = int(detail.get("int_page_read_count", 0))
            like_count = int(detail.get("like_count", 0))
            share_count = int(detail.get("share_count", 0))
            ref_date = row.get("ref_date") or yesterday.isoformat()
            publish_time = datetime.fromisoformat(str(ref_date)).replace(
                tzinfo=UTC
            )
            await service.upsert_article(
                db,
                account.id,
                msgid=msgid_int,
                article_idx=idx,
                title=title,
                publish_time=publish_time,
                read_count=read_count,
                like_count=like_count,
                share_count=share_count,
                last_synced_at=synced,
            )
            try:
                count = await wechat_stats.fetch_comment_count(
                    access_token=access_token,
                    msg_data_id=msgid_int,
                    index=idx,
                )
                await service.update_comment_count(
                    db, account.id, msgid_int, idx, count
                )
            except Exception:
                logger.exception(
                    "fetch_comment_count failed: account=%s msgid=%s idx=%s",
                    account.id,
                    msgid_int,
                    idx,
                )
        except Exception:
            logger.exception(
                "upsert article failed: account=%s row=%s", account.id, row
            )


async def _sync_one_account(db: AsyncSession, account: Account) -> None:
    settings = get_settings()
    yesterday = _yesterday_in_beijing()

    access_token = await wechat_token.get_access_token(
        account_id=str(account.id),
        appid=account.wechat_appid,
        secret=account.wechat_secret,
    )

    await _sync_followers(db, account, access_token, yesterday)
    await _sync_articles(
        db, account, access_token, yesterday, settings.stats_backfill_days
    )


async def _sync_one_by_id(account_id: uuid.UUID) -> None:
    engine = make_engine()
    sm = async_sessionmaker(engine, expire_on_commit=False)
    async with sm() as db:
        account = await db.get(Account, account_id)
        if account is None:
            logger.warning("sync_one_account_stats: account %s not found", account_id)
            await engine.dispose()
            return
        try:
            await _sync_one_account(db, account)
        except Exception:
            logger.exception("sync_one_account_stats failed: %s", account_id)
    await engine.dispose()


@shared_task(name="app.tasks.stats.sync_one_account_stats")
def sync_one_account_stats(account_id: str) -> dict[str, str]:
    asyncio.run(_sync_one_by_id(uuid.UUID(account_id)))
    return {"account_id": account_id, "status": "done"}


async def _sync_all(db: AsyncSession) -> None:
    result = await db.execute(select(Account).where(Account.is_active.is_(True)))
    accounts = list(result.scalars().all())
    for account in accounts:
        try:
            await _sync_one_account(db, account)
        except Exception:
            logger.exception("_sync_all: account %s failed", account.id)


async def _sync_all_open_session() -> None:
    engine = make_engine()
    sm = async_sessionmaker(engine, expire_on_commit=False)
    async with sm() as db:
        await _sync_all(db)
    await engine.dispose()


@shared_task(name="app.tasks.stats.sync_all_accounts_stats")
def sync_all_accounts_stats() -> dict[str, str]:
    asyncio.run(_sync_all_open_session())
    return {"status": "done"}
