import uuid
from datetime import UTC, datetime, timedelta
from typing import Literal

from sqlalchemy import func, select, update
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.accounts.models import Account
from app.stats.models import WechatArticle
from app.stats.schemas import AccountStatsRow, ArticleStatsRow

_DERIVED_WINDOW_DAYS = 30
_VALID_SORTS = {
    "publish_time",
    "read_count",
    "like_count",
    "share_count",
    "comment_count",
}


async def upsert_account_stats(
    db: AsyncSession,
    account_id: uuid.UUID,
    *,
    follower_count: int,
    new_follow: int,
    cancel_follow: int,
    synced_at: datetime,
) -> None:
    await db.execute(
        update(Account)
        .where(Account.id == account_id)
        .values(
            follower_count=follower_count,
            new_follow_yesterday=new_follow,
            cancel_follow_yesterday=cancel_follow,
            stats_synced_at=synced_at,
        )
    )
    await db.commit()


async def upsert_article(
    db: AsyncSession,
    account_id: uuid.UUID,
    *,
    msgid: int,
    article_idx: int,
    title: str,
    publish_time: datetime,
    read_count: int,
    like_count: int,
    share_count: int,
    last_synced_at: datetime,
) -> None:
    stmt = pg_insert(WechatArticle).values(
        account_id=account_id,
        msgid=msgid,
        article_idx=article_idx,
        title=title,
        publish_time=publish_time,
        read_count=read_count,
        like_count=like_count,
        share_count=share_count,
        last_synced_at=last_synced_at,
    )
    stmt = stmt.on_conflict_do_update(
        constraint="uq_wechat_article",
        set_={
            "title": stmt.excluded.title,
            "publish_time": stmt.excluded.publish_time,
            "read_count": stmt.excluded.read_count,
            "like_count": stmt.excluded.like_count,
            "share_count": stmt.excluded.share_count,
            "last_synced_at": stmt.excluded.last_synced_at,
        },
    )
    await db.execute(stmt)
    await db.commit()


async def update_comment_count(
    db: AsyncSession,
    account_id: uuid.UUID,
    msgid: int,
    article_idx: int,
    comment_count: int,
) -> None:
    await db.execute(
        update(WechatArticle)
        .where(WechatArticle.account_id == account_id)
        .where(WechatArticle.msgid == msgid)
        .where(WechatArticle.article_idx == article_idx)
        .values(comment_count=comment_count)
    )
    await db.commit()


def _window_start() -> datetime:
    return datetime.now(UTC) - timedelta(days=_DERIVED_WINDOW_DAYS)


async def list_account_stats(db: AsyncSession) -> list[AccountStatsRow]:
    window_start = _window_start()
    stmt = (
        select(
            Account.id,
            Account.name,
            Account.follower_count,
            Account.new_follow_yesterday,
            Account.cancel_follow_yesterday,
            Account.stats_synced_at,
            func.coalesce(
                func.count(WechatArticle.id).filter(
                    WechatArticle.publish_time >= window_start
                ),
                0,
            ).label("articles_count_30d"),
            func.coalesce(
                func.sum(WechatArticle.read_count).filter(
                    WechatArticle.publish_time >= window_start
                ),
                0,
            ).label("total_read_30d"),
        )
        .outerjoin(WechatArticle, WechatArticle.account_id == Account.id)
        .group_by(Account.id)
        .order_by(Account.name)
    )
    result = await db.execute(stmt)
    rows = result.all()
    return [
        AccountStatsRow(
            account_id=r.id,
            name=r.name,
            follower_count=r.follower_count,
            new_follow_yesterday=r.new_follow_yesterday,
            cancel_follow_yesterday=r.cancel_follow_yesterday,
            articles_count_30d=int(r.articles_count_30d),
            total_read_30d=int(r.total_read_30d),
            stats_synced_at=r.stats_synced_at,
        )
        for r in rows
    ]


async def get_account_stats(
    db: AsyncSession, account_id: uuid.UUID
) -> AccountStatsRow | None:
    all_rows = await list_account_stats(db)
    for row in all_rows:
        if row.account_id == account_id:
            return row
    return None


async def list_articles(
    db: AsyncSession,
    account_id: uuid.UUID,
    *,
    days: int = 30,
    sort: str = "publish_time",
    order: Literal["asc", "desc"] = "desc",
) -> list[ArticleStatsRow]:
    if sort not in _VALID_SORTS:
        sort = "publish_time"

    window_start = datetime.now(UTC) - timedelta(days=days)
    sort_col = getattr(WechatArticle, sort)
    sort_expr = sort_col.desc() if order == "desc" else sort_col.asc()

    stmt = (
        select(WechatArticle)
        .where(WechatArticle.account_id == account_id)
        .where(WechatArticle.publish_time >= window_start)
        .order_by(sort_expr)
    )
    result = await db.execute(stmt)
    return [ArticleStatsRow.model_validate(row) for row in result.scalars().all()]
