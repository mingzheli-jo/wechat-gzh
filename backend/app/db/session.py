from collections.abc import AsyncGenerator
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from app.config import get_settings


def make_engine(url: str | None = None):
    return create_async_engine(url or get_settings().database_url, echo=False, future=True)


_sessionmaker: async_sessionmaker[AsyncSession] | None = None


def init_engine() -> None:
    global _sessionmaker
    _sessionmaker = async_sessionmaker(make_engine(), expire_on_commit=False, class_=AsyncSession)


async def get_session() -> AsyncGenerator[AsyncSession, None]:
    if _sessionmaker is None:
        init_engine()
    assert _sessionmaker is not None
    async with _sessionmaker() as session:
        yield session
