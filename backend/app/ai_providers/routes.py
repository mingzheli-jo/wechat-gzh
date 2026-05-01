import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai_providers import registry, service
from app.ai_providers.schemas import (
    ProviderIn,
    ProviderOut,
    ProviderUpdate,
    RoleBindingIn,
    RoleBindingOut,
)
from app.api.deps import get_db
from app.auth.dependencies import get_current_username

router = APIRouter(prefix="/ai-providers", tags=["ai_providers"])


@router.post("", response_model=ProviderOut, status_code=201)
async def create(
    payload: ProviderIn,
    db: AsyncSession = Depends(get_db),
    _: str = Depends(get_current_username),
) -> ProviderOut:
    obj = await service.create_provider(db, payload)
    await registry.load_from_db(db)
    return ProviderOut.model_validate(obj)


@router.get("", response_model=list[ProviderOut])
async def list_all(
    db: AsyncSession = Depends(get_db),
    _: str = Depends(get_current_username),
) -> list[ProviderOut]:
    return [
        ProviderOut.model_validate(r) for r in await service.list_providers(db)
    ]


@router.patch("/{provider_id}", response_model=ProviderOut)
async def update(
    provider_id: uuid.UUID,
    payload: ProviderUpdate,
    db: AsyncSession = Depends(get_db),
    _: str = Depends(get_current_username),
) -> ProviderOut:
    obj = await service.get_provider(db, provider_id)
    if obj is None:
        raise HTTPException(404, "Provider not found")
    obj = await service.update_provider(db, obj, payload)
    await registry.load_from_db(db)
    return ProviderOut.model_validate(obj)


@router.delete("/{provider_id}", status_code=204)
async def delete(
    provider_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    _: str = Depends(get_current_username),
) -> None:
    obj = await service.get_provider(db, provider_id)
    if obj is None:
        raise HTTPException(404, "Provider not found")
    await service.delete_provider(db, obj)
    await registry.load_from_db(db)


@router.put("/role-bindings", response_model=RoleBindingOut)
async def upsert_binding(
    payload: RoleBindingIn,
    db: AsyncSession = Depends(get_db),
    _: str = Depends(get_current_username),
) -> RoleBindingOut:
    obj = await service.upsert_role_binding(db, payload)
    await registry.load_from_db(db)
    return RoleBindingOut.model_validate(obj)


@router.get("/role-bindings", response_model=list[RoleBindingOut])
async def list_bindings(
    db: AsyncSession = Depends(get_db),
    _: str = Depends(get_current_username),
) -> list[RoleBindingOut]:
    return [
        RoleBindingOut.model_validate(r)
        for r in await service.list_role_bindings(db)
    ]
