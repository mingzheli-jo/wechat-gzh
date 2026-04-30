import asyncio
import os
from collections.abc import AsyncGenerator, Generator

import pytest
import pytest_asyncio
from cryptography.fernet import Fernet
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from testcontainers.postgres import PostgresContainer

from app.accounts.models import Account  # noqa: F401
from app.auth.password import hash_password
from app.config import get_settings
from app.db.base import Base


@pytest.fixture(scope="session")
def event_loop() -> Generator:
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest.fixture(scope="session")
def pg_container() -> Generator[PostgresContainer, None, None]:
    c = PostgresContainer("postgres:16-alpine")
    c.start()
    yield c
    c.stop()


@pytest.fixture(scope="session")
def database_url(pg_container: PostgresContainer) -> str:
    return pg_container.get_connection_url().replace(
        "postgresql+psycopg2", "postgresql+asyncpg"
    )


@pytest.fixture(scope="session", autouse=True)
def env_setup(database_url: str) -> None:
    os.environ["DATABASE_URL"] = database_url
    os.environ["ENCRYPTION_KEY"] = Fernet.generate_key().decode()
    os.environ["JWT_SECRET"] = "integration-secret"
    os.environ["ADMIN_USERNAME"] = "admin"
    os.environ["ADMIN_PASSWORD_HASH"] = hash_password("hunter2")
    get_settings.cache_clear()


@pytest_asyncio.fixture
async def db_engine(database_url: str):
    engine = create_async_engine(database_url, future=True)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield engine
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()


@pytest_asyncio.fixture
async def db_session(db_engine) -> AsyncGenerator[AsyncSession, None]:
    sm = async_sessionmaker(db_engine, expire_on_commit=False, class_=AsyncSession)
    async with sm() as session:
        yield session
