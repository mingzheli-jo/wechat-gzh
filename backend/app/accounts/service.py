import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.accounts.models import Account
from app.accounts.schemas import AccountIn, AccountUpdate


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
    await db.delete(account)
    await db.commit()
