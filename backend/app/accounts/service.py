import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.accounts.models import Account
from app.accounts.schemas import AccountIn, AccountUpdate
from app.drafts import service as draft_service
from app.drafts.models import Draft


async def create_account(db: AsyncSession, payload: AccountIn) -> Account:
    obj = Account(**payload.model_dump())
    db.add(obj)
    await db.commit()
    await db.refresh(obj)
    return obj


async def list_accounts(db: AsyncSession) -> list[Account]:
    result = await db.execute(select(Account).order_by(Account.created_at.desc()))
    return list(result.scalars().all())


async def get_account(db: AsyncSession, account_id: uuid.UUID) -> Account | None:
    return await db.get(Account, account_id)


async def update_account(
    db: AsyncSession, account: Account, payload: AccountUpdate
) -> Account:
    for key, value in payload.model_dump(exclude_none=True).items():
        setattr(account, key, value)
    await db.commit()
    await db.refresh(account)
    return account


async def delete_account(db: AsyncSession, account: Account) -> None:
    # 先清理该账号下的草稿及其依赖（图片、审核报告、磁盘文件）。
    # drafts.account_id 是 RESTRICT 外键，直接删账号会抛 IntegrityError(500)；
    # 复用 delete_draft_with_cleanup 处理 drafts↔review_reports 的循环外键。
    drafts = list(
        (
            await db.execute(
                select(Draft).where(Draft.account_id == account.id)
            )
        )
        .scalars()
        .all()
    )
    for draft in drafts:
        await draft_service.delete_draft_with_cleanup(db, draft)
    await db.delete(account)
    await db.commit()
