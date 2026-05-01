import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai_providers.models import AIProvider, RoleBinding
from app.ai_providers.schemas import ProviderIn, ProviderUpdate, RoleBindingIn


async def create_provider(db: AsyncSession, payload: ProviderIn) -> AIProvider:
    obj = AIProvider(**payload.model_dump())
    db.add(obj)
    await db.commit()
    await db.refresh(obj)
    return obj


async def list_providers(db: AsyncSession) -> list[AIProvider]:
    return list((await db.execute(select(AIProvider))).scalars().all())


async def get_provider(
    db: AsyncSession, pid: uuid.UUID
) -> AIProvider | None:
    return await db.get(AIProvider, pid)


async def update_provider(
    db: AsyncSession, obj: AIProvider, payload: ProviderUpdate
) -> AIProvider:
    for k, v in payload.model_dump(exclude_none=True).items():
        setattr(obj, k, v)
    await db.commit()
    await db.refresh(obj)
    return obj


async def delete_provider(db: AsyncSession, obj: AIProvider) -> None:
    await db.delete(obj)
    await db.commit()


async def upsert_role_binding(
    db: AsyncSession, payload: RoleBindingIn
) -> RoleBinding:
    existing = (
        await db.execute(
            select(RoleBinding).where(RoleBinding.role == payload.role)
        )
    ).scalar_one_or_none()
    if existing is None:
        obj = RoleBinding(**payload.model_dump())
        db.add(obj)
    else:
        existing.provider_id = payload.provider_id
        existing.model = payload.model
        obj = existing
    await db.commit()
    await db.refresh(obj)
    return obj


async def list_role_bindings(db: AsyncSession) -> list[RoleBinding]:
    return list((await db.execute(select(RoleBinding))).scalars().all())
