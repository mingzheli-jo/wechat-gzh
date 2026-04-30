import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.accounts import service
from app.accounts.schemas import AccountIn, AccountOut, AccountUpdate
from app.api.deps import get_db
from app.auth.dependencies import get_current_username

router = APIRouter(prefix="/accounts", tags=["accounts"])


@router.post("", response_model=AccountOut, status_code=201)
async def create(
    payload: AccountIn,
    db: AsyncSession = Depends(get_db),
    _: str = Depends(get_current_username),
) -> AccountOut:
    return AccountOut.model_validate(await service.create_account(db, payload))


@router.get("", response_model=list[AccountOut])
async def list_all(
    db: AsyncSession = Depends(get_db),
    _: str = Depends(get_current_username),
) -> list[AccountOut]:
    return [AccountOut.model_validate(r) for r in await service.list_accounts(db)]


@router.get("/{account_id}", response_model=AccountOut)
async def get_one(
    account_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    _: str = Depends(get_current_username),
) -> AccountOut:
    obj = await service.get_account(db, account_id)
    if obj is None:
        raise HTTPException(404, "Account not found")
    return AccountOut.model_validate(obj)


@router.patch("/{account_id}", response_model=AccountOut)
async def update(
    account_id: uuid.UUID,
    payload: AccountUpdate,
    db: AsyncSession = Depends(get_db),
    _: str = Depends(get_current_username),
) -> AccountOut:
    obj = await service.get_account(db, account_id)
    if obj is None:
        raise HTTPException(404, "Account not found")
    return AccountOut.model_validate(await service.update_account(db, obj, payload))


@router.delete("/{account_id}", status_code=204)
async def delete(
    account_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    _: str = Depends(get_current_username),
) -> None:
    obj = await service.get_account(db, account_id)
    if obj is None:
        raise HTTPException(404, "Account not found")
    await service.delete_account(db, obj)
