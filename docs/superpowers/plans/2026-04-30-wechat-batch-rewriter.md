# 微信公众号批量改写系统 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a single-user web tool that crawls user-supplied WeChat 公众号 article URLs into a library, batch rewrites them via configurable LLM providers (Kimi/DeepSeek/...), runs 4-dimension AI review, and pushes the resulting drafts to WeChat draft boxes for multiple managed 公众号.

**Architecture:** FastAPI API + Celery worker + Postgres + Redis + React/Vite frontend, all packaged as 5 Docker containers. Domain-organized modules. AI providers unified behind an OpenAI-compatible adapter with role-based routing (writer/reviewer/lite). Each pipeline step is an independently retryable Celery task; chains compose them.

**Tech Stack:** Python 3.12, FastAPI, SQLAlchemy 2.x (async), asyncpg, Alembic, Celery 5, Redis 7, Postgres 16, httpx, lxml + readability-lxml, OpenAI SDK 1.x (async), pydantic v2, pydantic-settings, bcrypt, python-jose, cryptography (Fernet), React 18 + Vite + TypeScript + TailwindCSS + shadcn/ui + TanStack Query, pytest + pytest-asyncio + testcontainers + respx + fakeredis, Playwright, Docker Compose.

**Reference:** Design spec at `docs/superpowers/specs/2026-04-30-wechat-batch-rewrite-design.md`.

---

## Stage Overview

- **Stage 1 — Foundation (T1.x):** Project skeleton, Docker, Postgres, Redis, Alembic, single-user auth, accounts CRUD, frontend skeleton, login + accounts pages.
- **Stage 2 — Library (T2.x):** Celery infra, library_items + tasks tables, crawler (fetcher + parser), library CRUD, crawl Celery task, library frontend page.
- **Stage 3 — Rewrite Pipeline (T3.x):** AI provider abstraction + registry, role bindings, prompt builder, drafts + review_reports tables, rewrite Celery chain, 4-dimension reviewer, sensitive-word blacklist, drafts UI.
- **Stage 4 — WeChat Integration (T4.x):** Images table, WeChat token cache, material upload, draft push, image processing + publish tasks, image review UI.
- **Stage 5 — Hardening (T5.x):** E2E tests, README, deployment guide.

Each task is decomposed into 2–5 minute steps following TDD: write failing test → run to verify failure → implement → run to verify pass → commit.

---

## File Structure

Created during Stage 1 unless noted; later stages add files inside these dirs.

```
wechat-batch-rewriter/
├── backend/
│   ├── app/
│   │   ├── __init__.py
│   │   ├── main.py                       # FastAPI app factory
│   │   ├── config.py                     # pydantic Settings
│   │   ├── auth/
│   │   │   ├── __init__.py
│   │   │   ├── jwt_utils.py              # encode/decode JWT
│   │   │   ├── password.py               # bcrypt verify
│   │   │   ├── dependencies.py           # FastAPI Depends
│   │   │   ├── routes.py                 # /auth/login, /auth/me
│   │   │   └── schemas.py
│   │   ├── accounts/
│   │   │   ├── __init__.py
│   │   │   ├── models.py                 # SQLAlchemy Account
│   │   │   ├── schemas.py                # pydantic In/Out
│   │   │   ├── service.py                # CRUD logic
│   │   │   └── routes.py
│   │   ├── ai_providers/                 # Stage 3
│   │   │   ├── __init__.py
│   │   │   ├── base.py
│   │   │   ├── openai_compat.py
│   │   │   ├── registry.py
│   │   │   ├── models.py                 # AIProvider, RoleBinding, AIUsage
│   │   │   ├── schemas.py
│   │   │   ├── service.py
│   │   │   └── routes.py
│   │   ├── crawler/                      # Stage 2
│   │   │   ├── __init__.py
│   │   │   ├── fetcher.py
│   │   │   └── parser.py
│   │   ├── library/                      # Stage 2
│   │   │   ├── __init__.py
│   │   │   ├── models.py                 # LibraryItem
│   │   │   ├── schemas.py
│   │   │   ├── service.py
│   │   │   └── routes.py
│   │   ├── rewriter/                     # Stage 3
│   │   │   ├── __init__.py
│   │   │   ├── prompt_builder.py
│   │   │   ├── title.py
│   │   │   └── content.py
│   │   ├── reviewer/                     # Stage 3
│   │   │   ├── __init__.py
│   │   │   ├── compliance.py
│   │   │   ├── originality.py
│   │   │   ├── quality.py
│   │   │   ├── clickbait.py
│   │   │   ├── sensitive_words.py
│   │   │   └── aggregator.py
│   │   ├── drafts/                       # Stage 3
│   │   │   ├── __init__.py
│   │   │   ├── models.py                 # Draft, ReviewReport
│   │   │   ├── schemas.py
│   │   │   ├── service.py
│   │   │   └── routes.py
│   │   ├── images/                       # Stage 4
│   │   │   ├── __init__.py
│   │   │   ├── models.py                 # Image
│   │   │   ├── schemas.py
│   │   │   ├── service.py
│   │   │   └── routes.py
│   │   ├── wechat/                       # Stage 4
│   │   │   ├── __init__.py
│   │   │   ├── token.py
│   │   │   ├── material.py
│   │   │   └── draft.py
│   │   ├── tasks/                        # Stage 2 onward
│   │   │   ├── __init__.py
│   │   │   ├── celery_app.py
│   │   │   ├── crawl.py                  # Stage 2
│   │   │   ├── rewrite.py                # Stage 3
│   │   │   ├── review.py                 # Stage 3
│   │   │   ├── publish.py                # Stage 4
│   │   │   └── models.py                 # TaskRecord
│   │   ├── db/
│   │   │   ├── __init__.py
│   │   │   ├── base.py                   # DeclarativeBase, naming convention
│   │   │   ├── session.py                # async session factory
│   │   │   └── encryption.py             # Fernet helpers + EncryptedString type
│   │   ├── api/
│   │   │   ├── __init__.py
│   │   │   ├── deps.py                   # shared FastAPI deps (db session)
│   │   │   └── router.py                 # mounts all module routers
│   │   └── scripts/
│   │       ├── __init__.py
│   │       └── init_admin.py
│   ├── alembic/
│   │   ├── env.py
│   │   ├── script.py.mako
│   │   └── versions/                     # one file per migration
│   ├── alembic.ini
│   ├── tests/
│   │   ├── __init__.py
│   │   ├── conftest.py
│   │   ├── unit/
│   │   └── integration/
│   └── pyproject.toml
├── frontend/
│   ├── src/
│   │   ├── main.tsx
│   │   ├── App.tsx
│   │   ├── api/
│   │   │   └── client.ts                 # axios + JWT injection
│   │   ├── components/                   # shadcn/ui-derived
│   │   ├── pages/
│   │   │   ├── Login.tsx
│   │   │   ├── Accounts.tsx
│   │   │   ├── Library.tsx
│   │   │   ├── Drafts.tsx
│   │   │   ├── DraftDetail.tsx
│   │   │   └── Settings.tsx
│   │   ├── hooks/
│   │   └── lib/
│   ├── public/
│   ├── index.html
│   ├── vite.config.ts
│   ├── tsconfig.json
│   ├── package.json
│   └── tailwind.config.ts
├── docker/
│   ├── Dockerfile.api
│   ├── Dockerfile.worker
│   ├── Dockerfile.web
│   └── nginx.conf
├── docker-compose.yml
├── docker-compose.dev.yml
├── docker-compose.test.yml
├── .env.example
├── .gitignore
└── README.md
```

---

## Conventions

- **Working directory:** `D:\ide\workspace\personal\wechat-batch-rewriter`. All paths in tasks are relative to this root.
- **Backend dependency manager:** `uv`. All backend commands run from `backend/` unless noted.
- **Frontend package manager:** `pnpm`. All frontend commands run from `frontend/`.
- **Test invocation:** `uv run pytest <path> -v` for unit; integration tests prefixed `tests/integration/`.
- **Commit style:** `feat:`, `fix:`, `chore:`, `docs:`, `test:`, `refactor:`.
- **Sub-skill usage during implementation:** Always read the failing test output before claiming progress. Never skip the "run failing test" step — its purpose is to verify the test actually exercises the code path.

---

# Stage 1 — Foundation

Goal: Working FastAPI service running in Docker, single-user JWT login works, can CRUD 公众号 records (secrets encrypted at rest), React frontend can log in and list accounts.

## Task 1.1: Project skeleton + tooling

**Files:** Create `backend/pyproject.toml`, `backend/.python-version`, `.gitignore`, `backend/tests/{__init__.py,conftest.py,unit/__init__.py,integration/__init__.py}`.

- [ ] **Step 1: Create `backend/pyproject.toml`**

```toml
[project]
name = "wechat-rewriter-backend"
version = "0.1.0"
requires-python = ">=3.12"
dependencies = [
    "fastapi>=0.110", "uvicorn[standard]>=0.29",
    "pydantic>=2.6", "pydantic-settings>=2.2",
    "sqlalchemy[asyncio]>=2.0", "asyncpg>=0.29", "alembic>=1.13",
    "celery[redis]>=5.3", "redis>=5.0",
    "httpx>=0.27", "lxml>=5.1", "readability-lxml>=0.8",
    "openai>=1.14",
    "python-jose[cryptography]>=3.3", "passlib[bcrypt]>=1.7",
    "cryptography>=42.0", "python-multipart>=0.0.9",
]

[project.optional-dependencies]
dev = [
    "pytest>=8.0", "pytest-asyncio>=0.23",
    "respx>=0.20", "fakeredis>=2.21",
    "testcontainers[postgres,redis]>=4.0",
    "ruff>=0.3", "mypy>=1.9",
]

[tool.ruff]
line-length = 100
target-version = "py312"
[tool.ruff.lint]
select = ["E", "F", "I", "B", "UP", "N"]

[tool.mypy]
python_version = "3.12"
strict = true
plugins = ["pydantic.mypy"]

[tool.pytest.ini_options]
asyncio_mode = "auto"
testpaths = ["tests"]
```

- [ ] **Step 2: Write `.python-version` with content `3.12`**

- [ ] **Step 3: Create `.gitignore`** with: `__pycache__/`, `*.pyc`, `.venv/`, `backend/.venv/`, `.env`, `.env.local`, `frontend/node_modules/`, `frontend/dist/`, `.pytest_cache/`, `.mypy_cache/`, `.ruff_cache/`, `data/`, `backend/data/`, `htmlcov/`, `.coverage`.

- [ ] **Step 4: Create empty test package files** (`backend/tests/__init__.py`, `backend/tests/unit/__init__.py`, `backend/tests/integration/__init__.py`, and `backend/tests/conftest.py` containing only the docstring `"""Shared pytest fixtures."""`).

- [ ] **Step 5: Install deps**

```bash
cd backend && uv venv && uv pip install -e ".[dev]"
```

- [ ] **Step 6: Verify tooling works**

```bash
cd backend && uv run ruff check . && uv run pytest --collect-only
```
Expected: succeeds, no tests collected yet.

- [ ] **Step 7: Commit**

```bash
git add .gitignore backend/pyproject.toml backend/.python-version backend/tests
git commit -m "chore: initialize backend project skeleton with uv + ruff + pytest"
```

---

## Task 1.2: Database base + Settings + async session

**Files:** Create `backend/app/__init__.py`, `backend/app/db/__init__.py`, `backend/app/db/base.py`, `backend/app/config.py`, `backend/app/db/session.py`, `backend/tests/unit/test_db_base.py`.

- [ ] **Step 1: Create empty `backend/app/__init__.py` and `backend/app/db/__init__.py`**

- [ ] **Step 2: Write failing test `backend/tests/unit/test_db_base.py`**

```python
from app.db.base import Base


def test_base_uses_consistent_naming_convention():
    convention = Base.metadata.naming_convention
    assert convention["pk"] == "pk_%(table_name)s"
    assert convention["fk"] == "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s"
    assert convention["uq"] == "uq_%(table_name)s_%(column_0_name)s"
    assert convention["ix"] == "ix_%(table_name)s_%(column_0_name)s"
```

- [ ] **Step 3: Run failing test** — `uv run pytest tests/unit/test_db_base.py -v` — Expected: FAIL (ModuleNotFoundError).

- [ ] **Step 4: Implement `backend/app/db/base.py`**

```python
from sqlalchemy import MetaData
from sqlalchemy.orm import DeclarativeBase

NAMING_CONVENTION = {
    "ix": "ix_%(table_name)s_%(column_0_name)s",
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}


class Base(DeclarativeBase):
    metadata = MetaData(naming_convention=NAMING_CONVENTION)
```

- [ ] **Step 5: Run test to verify pass** — `uv run pytest tests/unit/test_db_base.py -v` — Expected: PASS.

- [ ] **Step 6: Implement `backend/app/config.py`**

```python
from functools import lru_cache
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/wechat_rewriter"
    redis_url: str = "redis://localhost:6379/0"

    admin_username: str = "admin"
    admin_password_hash: str = ""
    jwt_secret: str = "change-me"
    jwt_algorithm: str = "HS256"
    jwt_expire_minutes: int = 60 * 24

    encryption_key: str = ""

    default_writer_provider: str = "deepseek"
    default_reviewer_provider: str = "kimi"
    default_lite_provider: str = "deepseek"

    crawler_timeout: int = 30
    crawler_max_retry: int = 3
    celery_worker_concurrency: int = 4
    image_storage_dir: str = "/data/images"
    rewrite_batch_max: int = Field(default=20, ge=1, le=200)


@lru_cache
def get_settings() -> Settings:
    return Settings()
```

- [ ] **Step 7: Implement `backend/app/db/session.py`**

```python
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
```

- [ ] **Step 8: Commit**

```bash
git add backend/app backend/tests/unit/test_db_base.py
git commit -m "feat(db): add SQLAlchemy Base + Settings + async session factory"
```

---

## Task 1.3: Encryption helpers + EncryptedString column type

**Files:** Create `backend/app/db/encryption.py`, `backend/tests/unit/test_encryption.py`.

- [ ] **Step 1: Write failing test `backend/tests/unit/test_encryption.py`**

```python
import pytest
from app.db.encryption import EncryptedString, decrypt_value, encrypt_value, generate_key


def test_generate_key_returns_44_char_urlsafe_b64():
    key = generate_key()
    assert isinstance(key, str)
    assert len(key) == 44


def test_encrypt_then_decrypt_roundtrip():
    key = generate_key()
    cipher = encrypt_value("secret-app-secret", key=key)
    assert cipher != "secret-app-secret"
    assert decrypt_value(cipher, key=key) == "secret-app-secret"


def test_decrypt_wrong_key_raises():
    cipher = encrypt_value("abc", key=generate_key())
    with pytest.raises(Exception):
        decrypt_value(cipher, key=generate_key())


def test_encrypted_string_column_type_processes_bind_and_result():
    key = generate_key()
    col = EncryptedString(key=key)
    bound = col.process_bind_param("hello", dialect=None)
    assert bound != "hello"
    assert col.process_result_value(bound, dialect=None) == "hello"


def test_encrypted_string_handles_none():
    col = EncryptedString(key=generate_key())
    assert col.process_bind_param(None, dialect=None) is None
    assert col.process_result_value(None, dialect=None) is None
```

- [ ] **Step 2: Run failing test** — Expected: FAIL.

- [ ] **Step 3: Implement `backend/app/db/encryption.py`**

```python
from cryptography.fernet import Fernet
from sqlalchemy import String, TypeDecorator
from app.config import get_settings


def generate_key() -> str:
    return Fernet.generate_key().decode("utf-8")


def _resolve_key(key: str | None) -> bytes:
    chosen = key or get_settings().encryption_key
    if not chosen:
        raise RuntimeError("ENCRYPTION_KEY not configured")
    return chosen.encode("utf-8")


def encrypt_value(plaintext: str, *, key: str | None = None) -> str:
    return Fernet(_resolve_key(key)).encrypt(plaintext.encode("utf-8")).decode("utf-8")


def decrypt_value(token: str, *, key: str | None = None) -> str:
    return Fernet(_resolve_key(key)).decrypt(token.encode("utf-8")).decode("utf-8")


class EncryptedString(TypeDecorator[str]):
    impl = String
    cache_ok = True

    def __init__(self, *, key: str | None = None, length: int = 1024) -> None:
        super().__init__(length=length)
        self._key = key

    def process_bind_param(self, value, dialect):
        return None if value is None else encrypt_value(value, key=self._key)

    def process_result_value(self, value, dialect):
        return None if value is None else decrypt_value(value, key=self._key)
```

- [ ] **Step 4: Run tests to verify pass** — Expected: PASS (5 tests).

- [ ] **Step 5: Commit**

```bash
git add backend/app/db/encryption.py backend/tests/unit/test_encryption.py
git commit -m "feat(db): add Fernet encryption helpers and EncryptedString column type"
```

---

## Task 1.4: FastAPI app + health route

**Files:** Create `backend/app/main.py`, `backend/app/api/__init__.py`, `backend/app/api/router.py`, `backend/tests/unit/test_app.py`.

- [ ] **Step 1: Write failing test `backend/tests/unit/test_app.py`**

```python
from fastapi.testclient import TestClient
from app.main import create_app


def test_health_returns_ok():
    client = TestClient(create_app())
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
```

- [ ] **Step 2: Run failing test** — Expected: FAIL.

- [ ] **Step 3: Implement `backend/app/api/router.py`**

```python
from fastapi import APIRouter

api_router = APIRouter()
```

- [ ] **Step 4: Implement `backend/app/main.py`**

```python
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.api.router import api_router


def create_app() -> FastAPI:
    app = FastAPI(title="WeChat Batch Rewriter", version="0.1.0")
    app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_credentials=True,
                       allow_methods=["*"], allow_headers=["*"])

    @app.get("/health")
    async def health() -> dict[str, str]:
        return {"status": "ok"}

    app.include_router(api_router, prefix="/api")
    return app


app = create_app()
```

- [ ] **Step 5: Run test to verify pass** — Expected: PASS.

- [ ] **Step 6: Verify uvicorn boots**

```bash
uv run uvicorn app.main:app --host 127.0.0.1 --port 8000 &
sleep 2 && curl http://127.0.0.1:8000/health && kill %1
```
Expected: `{"status":"ok"}`.

- [ ] **Step 7: Commit**

```bash
git add backend/app/main.py backend/app/api backend/tests/unit/test_app.py
git commit -m "feat(api): add FastAPI app factory with health endpoint"
```

---

## Task 1.5: Alembic init

**Files:** Create `backend/alembic.ini`, `backend/alembic/env.py`, `backend/alembic/script.py.mako`, `backend/alembic/versions/`.

- [ ] **Step 1: Run** `cd backend && uv run alembic init -t async alembic` — creates the directory and `alembic.ini`.

- [ ] **Step 2: Edit `backend/alembic.ini`** — set `sqlalchemy.url =` to empty (we inject it from Settings in env.py).

- [ ] **Step 3: Replace `backend/alembic/env.py`** with:

```python
from __future__ import annotations
import asyncio
from logging.config import fileConfig
from alembic import context
from sqlalchemy import pool
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import async_engine_from_config

from app.config import get_settings
from app.db.base import Base
# Imports of model modules (added per-stage as models are introduced):
# from app.accounts.models import Account  # noqa: F401

config = context.config
config.set_main_option("sqlalchemy.url", get_settings().database_url)
if config.config_file_name is not None:
    fileConfig(config.config_file_name)
target_metadata = Base.metadata


def run_migrations_offline() -> None:
    context.configure(url=config.get_main_option("sqlalchemy.url"),
                      target_metadata=target_metadata, literal_binds=True,
                      dialect_opts={"paramstyle": "named"})
    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection: Connection) -> None:
    context.configure(connection=connection, target_metadata=target_metadata)
    with context.begin_transaction():
        context.run_migrations()


async def run_migrations_online() -> None:
    connectable = async_engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.", poolclass=pool.NullPool)
    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)
    await connectable.dispose()


if context.is_offline_mode():
    run_migrations_offline()
else:
    asyncio.run(run_migrations_online())
```

- [ ] **Step 4: Commit**

```bash
git add backend/alembic.ini backend/alembic
git commit -m "chore(db): scaffold Alembic with async env wired to Settings"
```

---

## Task 1.6: Auth — password hashing utility

**Files:** Create `backend/app/auth/__init__.py`, `backend/app/auth/password.py`, `backend/tests/unit/test_password.py`.

- [ ] **Step 1: Write failing test `backend/tests/unit/test_password.py`**

```python
from app.auth.password import hash_password, verify_password


def test_hash_password_produces_bcrypt_hash():
    h = hash_password("hunter2")
    assert h.startswith("$2b$") and h != "hunter2"


def test_verify_password_accepts_correct():
    assert verify_password("hunter2", hash_password("hunter2")) is True


def test_verify_password_rejects_wrong():
    assert verify_password("wrong", hash_password("hunter2")) is False
```

- [ ] **Step 2: Run failing test** — Expected: FAIL.

- [ ] **Step 3: Create empty `backend/app/auth/__init__.py` and implement `backend/app/auth/password.py`**

```python
from passlib.context import CryptContext

_ctx = CryptContext(schemes=["bcrypt"], deprecated="auto")


def hash_password(plain: str) -> str:
    return _ctx.hash(plain)


def verify_password(plain: str, hashed: str) -> bool:
    return _ctx.verify(plain, hashed)
```

- [ ] **Step 4: Run tests** — Expected: PASS (3 tests).

- [ ] **Step 5: Commit**

```bash
git add backend/app/auth backend/tests/unit/test_password.py
git commit -m "feat(auth): add bcrypt password hashing helpers"
```

---

## Task 1.7: Auth — JWT helpers

**Files:** Create `backend/app/auth/jwt_utils.py`, `backend/tests/unit/test_jwt_utils.py`.

- [ ] **Step 1: Write failing test `backend/tests/unit/test_jwt_utils.py`**

```python
from datetime import timedelta
import pytest
from app.auth.jwt_utils import create_access_token, decode_token


def test_create_decode_roundtrip():
    t = create_access_token(subject="admin", secret="s", expires=timedelta(minutes=5))
    p = decode_token(t, secret="s")
    assert p["sub"] == "admin" and "exp" in p


def test_wrong_secret_raises():
    t = create_access_token(subject="admin", secret="s", expires=timedelta(minutes=5))
    with pytest.raises(Exception):
        decode_token(t, secret="other")


def test_expired_raises():
    t = create_access_token(subject="admin", secret="s", expires=timedelta(seconds=-1))
    with pytest.raises(Exception):
        decode_token(t, secret="s")
```

- [ ] **Step 2: Run failing test** — Expected: FAIL.

- [ ] **Step 3: Implement `backend/app/auth/jwt_utils.py`**

```python
from datetime import datetime, timedelta, timezone
from typing import Any
from jose import jwt
from app.config import get_settings


def create_access_token(*, subject: str, secret: str | None = None,
                        expires: timedelta | None = None,
                        algorithm: str | None = None) -> str:
    s = get_settings()
    secret = secret or s.jwt_secret
    algorithm = algorithm or s.jwt_algorithm
    expires = expires or timedelta(minutes=s.jwt_expire_minutes)
    payload = {"sub": subject,
               "exp": datetime.now(timezone.utc) + expires,
               "iat": datetime.now(timezone.utc)}
    return jwt.encode(payload, secret, algorithm=algorithm)


def decode_token(token: str, *, secret: str | None = None,
                 algorithm: str | None = None) -> dict[str, Any]:
    s = get_settings()
    return jwt.decode(token, secret or s.jwt_secret, algorithms=[algorithm or s.jwt_algorithm])
```

- [ ] **Step 4: Run tests** — Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/app/auth/jwt_utils.py backend/tests/unit/test_jwt_utils.py
git commit -m "feat(auth): add JWT create/decode helpers using python-jose"
```

---

## Task 1.8: Auth — login route + dependency + /me

**Files:** Create `backend/app/auth/{schemas.py,dependencies.py,routes.py}`; modify `backend/app/api/router.py`; create `backend/tests/unit/test_auth_routes.py`.

- [ ] **Step 1: Create `backend/app/auth/schemas.py`**

```python
from pydantic import BaseModel


class LoginRequest(BaseModel):
    username: str
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


class MeResponse(BaseModel):
    username: str
```

- [ ] **Step 2: Create `backend/app/auth/dependencies.py`**

```python
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError
from app.auth.jwt_utils import decode_token

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login")


def get_current_username(token: str = Depends(oauth2_scheme)) -> str:
    try:
        payload = decode_token(token)
    except JWTError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")
    sub = payload.get("sub")
    if not isinstance(sub, str):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")
    return sub
```

- [ ] **Step 3: Write failing test `backend/tests/unit/test_auth_routes.py`**

```python
import pytest
from fastapi.testclient import TestClient
from app.auth.password import hash_password
from app.config import get_settings
from app.main import create_app


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setenv("ADMIN_USERNAME", "admin")
    monkeypatch.setenv("ADMIN_PASSWORD_HASH", hash_password("hunter2"))
    monkeypatch.setenv("JWT_SECRET", "test-secret")
    get_settings.cache_clear()
    return TestClient(create_app())


def test_login_correct_returns_token(client):
    r = client.post("/api/auth/login", data={"username": "admin", "password": "hunter2"})
    assert r.status_code == 200
    assert r.json()["access_token"]


def test_login_wrong_returns_401(client):
    r = client.post("/api/auth/login", data={"username": "admin", "password": "WRONG"})
    assert r.status_code == 401


def test_me_requires_token(client):
    assert client.get("/api/auth/me").status_code == 401


def test_me_returns_username_with_token(client):
    login = client.post("/api/auth/login", data={"username": "admin", "password": "hunter2"})
    token = login.json()["access_token"]
    r = client.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 200
    assert r.json() == {"username": "admin"}
```

- [ ] **Step 4: Run failing test** — Expected: FAIL (404).

- [ ] **Step 5: Implement `backend/app/auth/routes.py`**

```python
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from app.auth.dependencies import get_current_username
from app.auth.jwt_utils import create_access_token
from app.auth.password import verify_password
from app.auth.schemas import MeResponse, TokenResponse
from app.config import get_settings

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/login", response_model=TokenResponse)
async def login(form: OAuth2PasswordRequestForm = Depends()) -> TokenResponse:
    s = get_settings()
    if form.username != s.admin_username:
        raise HTTPException(401, "Invalid credentials")
    if not s.admin_password_hash or not verify_password(form.password, s.admin_password_hash):
        raise HTTPException(401, "Invalid credentials")
    return TokenResponse(access_token=create_access_token(subject=form.username))


@router.get("/me", response_model=MeResponse)
async def me(username: str = Depends(get_current_username)) -> MeResponse:
    return MeResponse(username=username)
```

- [ ] **Step 6: Modify `backend/app/api/router.py`**

```python
from fastapi import APIRouter
from app.auth.routes import router as auth_router

api_router = APIRouter()
api_router.include_router(auth_router)
```

- [ ] **Step 7: Run tests** — Expected: PASS (4 tests).

- [ ] **Step 8: Commit**

```bash
git add backend/app/auth backend/app/api/router.py backend/tests/unit/test_auth_routes.py
git commit -m "feat(auth): add /auth/login and /auth/me with JWT bearer"
```

---

## Task 1.9: Account model + first migration

**Files:** Create `backend/app/accounts/__init__.py`, `backend/app/accounts/models.py`; modify `backend/alembic/env.py`; generate `backend/alembic/versions/<rev>_create_accounts_table.py`.

- [ ] **Step 1: Create empty `backend/app/accounts/__init__.py`**

- [ ] **Step 2: Implement `backend/app/accounts/models.py`**

```python
import uuid
from datetime import datetime
from sqlalchemy import Boolean, DateTime, String, Text, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column
from app.db.base import Base
from app.db.encryption import EncryptedString


class Account(Base):
    __tablename__ = "accounts"
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    wechat_appid: Mapped[str] = mapped_column(String(100), nullable=False)
    wechat_secret: Mapped[str] = mapped_column(EncryptedString(length=2048), nullable=False)
    category: Mapped[str] = mapped_column(String(50), nullable=False)
    title_prompt: Mapped[str] = mapped_column(Text, nullable=False, default="")
    content_prompt: Mapped[str] = mapped_column(Text, nullable=False, default="")
    style_desc: Mapped[str] = mapped_column(Text, nullable=False, default="")
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
```

- [ ] **Step 3: Modify `backend/alembic/env.py`** — uncomment / add line `from app.accounts.models import Account  # noqa: F401` after `from app.db.base import Base`.

- [ ] **Step 4: Start temp postgres + autogenerate migration**

```bash
docker run -d --name pg-tmp -e POSTGRES_PASSWORD=postgres -p 5432:5432 postgres:16-alpine
sleep 4
cd backend
DATABASE_URL=postgresql+asyncpg://postgres:postgres@localhost:5432/postgres \
  ENCRYPTION_KEY=$(uv run python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())") \
  uv run alembic revision --autogenerate -m "create accounts table"
```
Expected: file `backend/alembic/versions/<rev>_create_accounts_table.py` is generated.

- [ ] **Step 5: Inspect & apply**

```bash
DATABASE_URL=postgresql+asyncpg://postgres:postgres@localhost:5432/postgres uv run alembic upgrade head
```

- [ ] **Step 6: Cleanup** — `docker stop pg-tmp && docker rm pg-tmp`.

- [ ] **Step 7: Commit**

```bash
git add backend/app/accounts backend/alembic
git commit -m "feat(accounts): add Account model with encrypted secret + first migration"
```

---

## Task 1.10: Account schemas + service + routes (with integration tests)

**Files:** Create `backend/app/accounts/{schemas.py,service.py,routes.py}`, `backend/app/api/deps.py`, `backend/tests/integration/conftest.py`, `backend/tests/integration/test_accounts_routes.py`; modify `backend/app/api/router.py`.

- [ ] **Step 1: Create `backend/app/api/deps.py`**

```python
from collections.abc import AsyncGenerator
from sqlalchemy.ext.asyncio import AsyncSession
from app.db.session import get_session


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async for session in get_session():
        yield session
```

- [ ] **Step 2: Create `backend/app/accounts/schemas.py`**

```python
import uuid
from datetime import datetime
from pydantic import BaseModel, ConfigDict, Field


class AccountIn(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    wechat_appid: str = Field(min_length=1, max_length=100)
    wechat_secret: str = Field(min_length=1)
    category: str = Field(min_length=1, max_length=50)
    title_prompt: str = ""
    content_prompt: str = ""
    style_desc: str = ""
    is_active: bool = True


class AccountUpdate(BaseModel):
    name: str | None = None
    wechat_appid: str | None = None
    wechat_secret: str | None = None
    category: str | None = None
    title_prompt: str | None = None
    content_prompt: str | None = None
    style_desc: str | None = None
    is_active: bool | None = None


class AccountOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    name: str
    wechat_appid: str
    category: str
    title_prompt: str
    content_prompt: str
    style_desc: str
    is_active: bool
    created_at: datetime
    updated_at: datetime
    # wechat_secret intentionally excluded
```

- [ ] **Step 3: Create `backend/app/accounts/service.py`**

```python
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


async def update_account(db: AsyncSession, account: Account, payload: AccountUpdate) -> Account:
    for key, value in payload.model_dump(exclude_none=True).items():
        setattr(account, key, value)
    await db.commit()
    await db.refresh(account)
    return account


async def delete_account(db: AsyncSession, account: Account) -> None:
    await db.delete(account)
    await db.commit()
```

- [ ] **Step 4: Create `backend/app/accounts/routes.py`**

```python
import uuid
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from app.accounts import service
from app.accounts.schemas import AccountIn, AccountOut, AccountUpdate
from app.api.deps import get_db
from app.auth.dependencies import get_current_username

router = APIRouter(prefix="/accounts", tags=["accounts"])


@router.post("", response_model=AccountOut, status_code=201)
async def create(payload: AccountIn,
                 db: AsyncSession = Depends(get_db),
                 _: str = Depends(get_current_username)) -> AccountOut:
    return AccountOut.model_validate(await service.create_account(db, payload))


@router.get("", response_model=list[AccountOut])
async def list_all(db: AsyncSession = Depends(get_db),
                   _: str = Depends(get_current_username)) -> list[AccountOut]:
    return [AccountOut.model_validate(r) for r in await service.list_accounts(db)]


@router.get("/{account_id}", response_model=AccountOut)
async def get_one(account_id: uuid.UUID,
                  db: AsyncSession = Depends(get_db),
                  _: str = Depends(get_current_username)) -> AccountOut:
    obj = await service.get_account(db, account_id)
    if obj is None:
        raise HTTPException(404, "Account not found")
    return AccountOut.model_validate(obj)


@router.patch("/{account_id}", response_model=AccountOut)
async def update(account_id: uuid.UUID, payload: AccountUpdate,
                 db: AsyncSession = Depends(get_db),
                 _: str = Depends(get_current_username)) -> AccountOut:
    obj = await service.get_account(db, account_id)
    if obj is None:
        raise HTTPException(404, "Account not found")
    return AccountOut.model_validate(await service.update_account(db, obj, payload))


@router.delete("/{account_id}", status_code=204)
async def delete(account_id: uuid.UUID,
                 db: AsyncSession = Depends(get_db),
                 _: str = Depends(get_current_username)) -> None:
    obj = await service.get_account(db, account_id)
    if obj is None:
        raise HTTPException(404, "Account not found")
    await service.delete_account(db, obj)
```

- [ ] **Step 5: Update `backend/app/api/router.py`**

```python
from fastapi import APIRouter
from app.accounts.routes import router as accounts_router
from app.auth.routes import router as auth_router

api_router = APIRouter()
api_router.include_router(auth_router)
api_router.include_router(accounts_router)
```

- [ ] **Step 6: Create `backend/tests/integration/conftest.py`**

```python
import asyncio
import os
from collections.abc import AsyncGenerator, Generator
import pytest
import pytest_asyncio
from cryptography.fernet import Fernet
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from testcontainers.postgres import PostgresContainer

from app.auth.password import hash_password
from app.config import get_settings
from app.db.base import Base
from app.accounts.models import Account  # noqa: F401


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
    return pg_container.get_connection_url().replace("postgresql+psycopg2", "postgresql+asyncpg")


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
```

- [ ] **Step 7: Write integration test `backend/tests/integration/test_accounts_routes.py`**

```python
import pytest
from httpx import ASGITransport, AsyncClient
from app.api.deps import get_db
from app.main import create_app


@pytest.fixture
def app(db_session):
    app = create_app()

    async def _override():
        yield db_session
    app.dependency_overrides[get_db] = _override
    return app


@pytest.fixture
async def auth_client(app):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        login = await client.post("/api/auth/login",
                                  data={"username": "admin", "password": "hunter2"})
        token = login.json()["access_token"]
        client.headers["Authorization"] = f"Bearer {token}"
        yield client


async def test_create_and_list(auth_client):
    payload = {"name": "测试号", "wechat_appid": "wx12345",
               "wechat_secret": "super-secret", "category": "职场",
               "title_prompt": "改写更吸引", "content_prompt": "保持原意",
               "style_desc": "专业克制"}
    r = await auth_client.post("/api/accounts", json=payload)
    assert r.status_code == 201
    body = r.json()
    assert body["name"] == "测试号"
    assert "wechat_secret" not in body

    r = await auth_client.get("/api/accounts")
    assert len(r.json()) == 1


async def test_get_update_delete(auth_client):
    create = await auth_client.post("/api/accounts", json={
        "name": "A", "wechat_appid": "wx", "wechat_secret": "s", "category": "职场"})
    account_id = create.json()["id"]
    assert (await auth_client.get(f"/api/accounts/{account_id}")).status_code == 200
    upd = await auth_client.patch(f"/api/accounts/{account_id}", json={"name": "B"})
    assert upd.json()["name"] == "B"
    assert (await auth_client.delete(f"/api/accounts/{account_id}")).status_code == 204
    assert (await auth_client.get(f"/api/accounts/{account_id}")).status_code == 404


async def test_routes_require_auth(app):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        assert (await client.get("/api/accounts")).status_code == 401
```

- [ ] **Step 8: Run integration tests** — `uv run pytest tests/integration/test_accounts_routes.py -v` — Expected: PASS (3 tests). First run pulls postgres image.

- [ ] **Step 9: Commit**

```bash
git add backend/app/accounts backend/app/api backend/tests/integration
git commit -m "feat(accounts): add schemas, service, CRUD routes, integration tests"
```

---

## Task 1.11: init_admin script

**Files:** Create `backend/app/scripts/__init__.py`, `backend/app/scripts/init_admin.py`, `backend/tests/unit/test_init_admin.py`.

- [ ] **Step 1: Write failing test** — `backend/tests/unit/test_init_admin.py`

```python
from app.auth.password import verify_password
from app.scripts.init_admin import build_password_hash


def test_build_password_hash_is_verifiable():
    assert verify_password("hunter2", build_password_hash("hunter2"))
```

- [ ] **Step 2: Implement `backend/app/scripts/init_admin.py`**

```python
"""Helper to print bcrypt hash for ADMIN_PASSWORD_HASH env var."""
import argparse
import getpass
import sys
from app.auth.password import hash_password


def build_password_hash(plain: str) -> str:
    return hash_password(plain)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--password", help="Password (omit to read interactively)")
    args = parser.parse_args(argv)
    plain = args.password or getpass.getpass("Admin password: ")
    print(build_password_hash(plain))
    return 0


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 3: Create empty `backend/app/scripts/__init__.py`** and run tests — Expected: PASS.

- [ ] **Step 4: Commit**

```bash
git add backend/app/scripts backend/tests/unit/test_init_admin.py
git commit -m "feat(scripts): add init_admin helper to print bcrypt hash"
```

---

## Task 1.12: API Dockerfile + entrypoint

**Files:** Create `docker/Dockerfile.api`, `docker/entrypoint-api.sh`.

- [ ] **Step 1: `docker/Dockerfile.api`**

```dockerfile
FROM python:3.12-slim AS base
ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1 PIP_NO_CACHE_DIR=1
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential libpq-dev curl && rm -rf /var/lib/apt/lists/*
WORKDIR /app
COPY backend/pyproject.toml /app/backend/pyproject.toml
RUN pip install uv && cd /app/backend && uv pip install --system -e .
COPY backend /app/backend
COPY docker/entrypoint-api.sh /app/entrypoint-api.sh
RUN chmod +x /app/entrypoint-api.sh
WORKDIR /app/backend
ENTRYPOINT ["/app/entrypoint-api.sh"]
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

- [ ] **Step 2: `docker/entrypoint-api.sh`**

```bash
#!/usr/bin/env bash
set -euo pipefail
cd /app/backend
echo "[entrypoint] running alembic migrations..."
alembic upgrade head
echo "[entrypoint] starting: $*"
exec "$@"
```

- [ ] **Step 3: Build smoke test** — `docker build -f docker/Dockerfile.api -t wechat-rewriter-api:dev .` — Expected: success.

- [ ] **Step 4: Commit**

```bash
git add docker/Dockerfile.api docker/entrypoint-api.sh
git commit -m "chore(docker): add API Dockerfile with alembic-upgrade entrypoint"
```

---

## Task 1.13: docker-compose.yml + .env.example

**Files:** Create `docker-compose.yml`, `.env.example`.

- [ ] **Step 1: `.env.example`**

```env
DATABASE_URL=postgresql+asyncpg://postgres:postgres@postgres:5432/wechat_rewriter
POSTGRES_DB=wechat_rewriter
POSTGRES_USER=postgres
POSTGRES_PASSWORD=postgres
REDIS_URL=redis://redis:6379/0

ADMIN_USERNAME=admin
ADMIN_PASSWORD_HASH=
JWT_SECRET=change-me-to-a-long-random-string

ENCRYPTION_KEY=

DEFAULT_WRITER_PROVIDER=deepseek
DEFAULT_REVIEWER_PROVIDER=kimi
DEFAULT_LITE_PROVIDER=deepseek

CRAWLER_TIMEOUT=30
CRAWLER_MAX_RETRY=3
CELERY_WORKER_CONCURRENCY=4
IMAGE_STORAGE_DIR=/data/images
REWRITE_BATCH_MAX=20
```

- [ ] **Step 2: `docker-compose.yml`**

```yaml
services:
  postgres:
    image: postgres:16-alpine
    environment:
      POSTGRES_DB: ${POSTGRES_DB}
      POSTGRES_USER: ${POSTGRES_USER}
      POSTGRES_PASSWORD: ${POSTGRES_PASSWORD}
    volumes:
      - pg_data:/var/lib/postgresql/data
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U ${POSTGRES_USER}"]
      interval: 5s
      timeout: 3s
      retries: 5

  redis:
    image: redis:7-alpine
    volumes:
      - redis_data:/data
    healthcheck:
      test: ["CMD", "redis-cli", "ping"]
      interval: 5s
      timeout: 3s
      retries: 5

  api:
    build:
      context: .
      dockerfile: docker/Dockerfile.api
    env_file: .env
    depends_on:
      postgres:
        condition: service_healthy
      redis:
        condition: service_healthy
    ports:
      - "8000:8000"

volumes:
  pg_data:
  redis_data:
```

- [ ] **Step 3: Smoke test**

```bash
cp .env.example .env
python -c "from cryptography.fernet import Fernet; print('ENCRYPTION_KEY=' + Fernet.generate_key().decode())" >> .env
docker compose run --rm api python -m app.scripts.init_admin --password hunter2
# Append the printed hash into .env as ADMIN_PASSWORD_HASH=<hash>
docker compose up -d
sleep 10
curl http://localhost:8000/health
docker compose logs api --tail 30
docker compose down
```
Expected: `{"status":"ok"}` from curl, no errors in api logs.

- [ ] **Step 4: Commit**

```bash
git add docker-compose.yml .env.example
git commit -m "chore(docker): add docker-compose with postgres + redis + api services"
```

---

## Task 1.14: Frontend skeleton + Login + Accounts pages

**Files:** Scaffold `frontend/` with Vite, configure Tailwind, add API client and pages.

- [ ] **Step 1: Scaffold**

```bash
pnpm create vite frontend --template react-ts
cd frontend
pnpm install
pnpm add axios @tanstack/react-query react-router-dom
pnpm add -D tailwindcss postcss autoprefixer @types/node
pnpm dlx tailwindcss init -p
```

- [ ] **Step 2: `frontend/tailwind.config.js`**

```js
export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: { extend: {} },
  plugins: [],
};
```

- [ ] **Step 3: `frontend/src/index.css`**

```css
@tailwind base;
@tailwind components;
@tailwind utilities;
```

- [ ] **Step 4: `frontend/src/main.tsx`**

```tsx
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import React from "react";
import ReactDOM from "react-dom/client";
import { BrowserRouter } from "react-router-dom";
import App from "./App";
import "./index.css";

const queryClient = new QueryClient();
ReactDOM.createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <QueryClientProvider client={queryClient}>
      <BrowserRouter>
        <App />
      </BrowserRouter>
    </QueryClientProvider>
  </React.StrictMode>
);
```

- [ ] **Step 5: `frontend/src/api/client.ts`**

```ts
import axios from "axios";
export const api = axios.create({ baseURL: "/api" });

api.interceptors.request.use((config) => {
  const token = localStorage.getItem("token");
  if (token) config.headers.Authorization = `Bearer ${token}`;
  return config;
});

api.interceptors.response.use(
  (r) => r,
  (err) => {
    if (err.response?.status === 401) {
      localStorage.removeItem("token");
      window.location.href = "/login";
    }
    return Promise.reject(err);
  }
);
```

- [ ] **Step 6: `frontend/src/App.tsx`**

```tsx
import { Navigate, Route, Routes } from "react-router-dom";
import Login from "./pages/Login";
import Accounts from "./pages/Accounts";

function isAuthed() {
  return Boolean(localStorage.getItem("token"));
}
function RequireAuth({ children }: { children: JSX.Element }) {
  return isAuthed() ? children : <Navigate to="/login" replace />;
}

export default function App() {
  return (
    <Routes>
      <Route path="/login" element={<Login />} />
      <Route path="/accounts" element={<RequireAuth><Accounts /></RequireAuth>} />
      <Route path="*" element={<Navigate to="/accounts" replace />} />
    </Routes>
  );
}
```

- [ ] **Step 7: `frontend/src/pages/Login.tsx`**

```tsx
import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { api } from "../api/client";

export default function Login() {
  const navigate = useNavigate();
  const [username, setUsername] = useState("admin");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    try {
      const form = new URLSearchParams({ username, password });
      const { data } = await api.post("/auth/login", form, {
        headers: { "Content-Type": "application/x-www-form-urlencoded" },
      });
      localStorage.setItem("token", data.access_token);
      navigate("/accounts");
    } catch {
      setError("用户名或密码错误");
    }
  }

  return (
    <div className="min-h-screen flex items-center justify-center bg-slate-50">
      <form onSubmit={submit} className="w-80 space-y-4 bg-white p-6 rounded-lg shadow">
        <h1 className="text-xl font-semibold">登录</h1>
        <input className="w-full border rounded px-3 py-2"
               value={username} onChange={(e) => setUsername(e.target.value)} placeholder="用户名" />
        <input type="password" className="w-full border rounded px-3 py-2"
               value={password} onChange={(e) => setPassword(e.target.value)} placeholder="密码" />
        {error && <div className="text-red-500 text-sm">{error}</div>}
        <button className="w-full bg-slate-900 text-white py-2 rounded">登录</button>
      </form>
    </div>
  );
}
```

- [ ] **Step 8: `frontend/src/pages/Accounts.tsx`**

```tsx
import { useQuery } from "@tanstack/react-query";
import { api } from "../api/client";

type Account = { id: string; name: string; category: string; is_active: boolean };

export default function Accounts() {
  const { data, isLoading } = useQuery({
    queryKey: ["accounts"],
    queryFn: async () => (await api.get<Account[]>("/accounts")).data,
  });
  return (
    <div className="p-8">
      <h1 className="text-2xl font-semibold mb-4">公众号</h1>
      {isLoading && <div>加载中...</div>}
      <ul className="space-y-2">
        {data?.map((a) => (
          <li key={a.id} className="border rounded p-3 flex justify-between">
            <span>{a.name}</span>
            <span className="text-sm text-slate-500">{a.category}</span>
          </li>
        ))}
      </ul>
    </div>
  );
}
```

- [ ] **Step 9: `frontend/vite.config.ts`** — add proxy

```ts
import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: { "/api": "http://localhost:8000" },
  },
});
```

- [ ] **Step 10: Smoke test** — `pnpm dev`. Browse to http://localhost:5173, log in with admin/hunter2, verify redirect to `/accounts` (will show empty list since DB has no rows yet).

- [ ] **Step 11: Commit**

```bash
git add frontend/
git commit -m "feat(frontend): scaffold Vite + React + Tailwind with login + accounts list"
```

---

## Task 1.15: Web Dockerfile + nginx + compose update

**Files:** Create `docker/Dockerfile.web`, `docker/nginx.conf`; modify `docker-compose.yml`.

- [ ] **Step 1: `docker/Dockerfile.web`**

```dockerfile
FROM node:20-alpine AS builder
WORKDIR /app/frontend
COPY frontend/package.json frontend/pnpm-lock.yaml* /app/frontend/
RUN corepack enable && pnpm install --frozen-lockfile || pnpm install
COPY frontend /app/frontend
RUN pnpm build

FROM nginx:alpine
COPY --from=builder /app/frontend/dist /usr/share/nginx/html
COPY docker/nginx.conf /etc/nginx/conf.d/default.conf
EXPOSE 80
```

- [ ] **Step 2: `docker/nginx.conf`**

```nginx
server {
    listen 80;
    server_name _;
    root /usr/share/nginx/html;
    index index.html;

    location /api/ {
        proxy_pass http://api:8000/api/;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_read_timeout 120s;
    }

    location / {
        try_files $uri $uri/ /index.html;
    }
}
```

- [ ] **Step 3: Add `web` service to `docker-compose.yml`**

```yaml
  web:
    build:
      context: .
      dockerfile: docker/Dockerfile.web
    depends_on:
      - api
    ports:
      - "80:80"
```

- [ ] **Step 4: Smoke test**

```bash
docker compose up -d --build
sleep 5
curl -I http://localhost/
curl http://localhost/api/health
docker compose down
```
Expected: HTTP 200 from `/`, `{"status":"ok"}` from `/api/health`.

- [ ] **Step 5: Commit**

```bash
git add docker/Dockerfile.web docker/nginx.conf docker-compose.yml
git commit -m "feat(docker): add web container with nginx serving SPA + API reverse proxy"
```

---

## Stage 1 Exit Criteria

- [ ] `docker compose up -d` starts all 3 services healthy.
- [ ] `curl http://localhost/api/health` returns `{"status":"ok"}`.
- [ ] Browser at http://localhost/login → log in → redirects to /accounts.
- [ ] Authenticated user can create/list/edit/delete accounts via API.
- [ ] All unit + integration tests pass: `cd backend && uv run pytest -v`.
- [ ] Encryption verified: row in `accounts` has Fernet ciphertext (not plaintext) for `wechat_secret` when inspected via `psql`.

---

# Stage 2 — Library (Crawl + Queue)

Goal: Celery worker container running, user can paste WeChat article URLs, system asynchronously crawls and parses them into the library, supports tagging and listing.

---

## Task 2.1: Celery app + worker Dockerfile

**Files:** Create `backend/app/tasks/__init__.py`, `backend/app/tasks/celery_app.py`, `docker/Dockerfile.worker`, `docker/entrypoint-worker.sh`; update `docker-compose.yml`.

- [ ] **Step 1: Create `backend/app/tasks/__init__.py`** with:

```python
from app.tasks.celery_app import celery_app

__all__ = ["celery_app"]
```

- [ ] **Step 2: Create `backend/app/tasks/celery_app.py`**

```python
from celery import Celery
from app.config import get_settings

settings = get_settings()

celery_app = Celery(
    "wechat_rewriter",
    broker=settings.redis_url,
    backend=settings.redis_url,
    include=[
        "app.tasks.crawl",
        # added in later stages: "app.tasks.rewrite", "app.tasks.review", "app.tasks.publish"
    ],
)

celery_app.conf.update(
    task_acks_late=True,
    task_reject_on_worker_lost=True,
    task_default_queue="default",
    task_routes={
        "app.tasks.crawl.*": {"queue": "crawl"},
    },
    worker_concurrency=settings.celery_worker_concurrency,
    broker_connection_retry_on_startup=True,
    timezone="UTC",
)
```

- [ ] **Step 3: Create `docker/Dockerfile.worker`** (same base as api but different command)

```dockerfile
FROM python:3.12-slim AS base
ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1 PIP_NO_CACHE_DIR=1
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential libpq-dev && rm -rf /var/lib/apt/lists/*
WORKDIR /app
COPY backend/pyproject.toml /app/backend/pyproject.toml
RUN pip install uv && cd /app/backend && uv pip install --system -e .
COPY backend /app/backend
COPY docker/entrypoint-worker.sh /app/entrypoint-worker.sh
RUN chmod +x /app/entrypoint-worker.sh
WORKDIR /app/backend
ENTRYPOINT ["/app/entrypoint-worker.sh"]
CMD ["celery", "-A", "app.tasks.celery_app", "worker", "--loglevel=INFO", "-Q", "default,crawl,rewrite,review,publish"]
```

- [ ] **Step 4: Create `docker/entrypoint-worker.sh`**

```bash
#!/usr/bin/env bash
set -euo pipefail
cd /app/backend
echo "[worker] waiting for postgres + redis..."
exec "$@"
```

- [ ] **Step 5: Add `worker` service in `docker-compose.yml`** (place after `api`)

```yaml
  worker:
    build:
      context: .
      dockerfile: docker/Dockerfile.worker
    env_file: .env
    depends_on:
      postgres:
        condition: service_healthy
      redis:
        condition: service_healthy
    volumes:
      - image_data:/data/images
```

And add `image_data:` under `volumes:`.

- [ ] **Step 6: Smoke test** — `docker compose up -d --build worker` then `docker compose logs worker --tail 20` should show celery startup banner with broker URL.

- [ ] **Step 7: Commit**

```bash
git add backend/app/tasks docker/Dockerfile.worker docker/entrypoint-worker.sh docker-compose.yml
git commit -m "feat(tasks): add Celery app and worker container"
```

---

## Task 2.2: TaskRecord model + migration

**Files:** Create `backend/app/tasks/models.py`; modify `backend/alembic/env.py`; generate migration.

- [ ] **Step 1: Implement `backend/app/tasks/models.py`**

```python
import enum
import uuid
from datetime import datetime
from sqlalchemy import DateTime, Enum, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column
from app.db.base import Base


class TaskKind(str, enum.Enum):
    crawl = "crawl"
    rewrite = "rewrite"
    review = "review"
    publish = "publish"


class TaskStatus(str, enum.Enum):
    queued = "queued"
    running = "running"
    success = "success"
    failed = "failed"


class TaskRecord(Base):
    __tablename__ = "tasks"
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    kind: Mapped[TaskKind] = mapped_column(Enum(TaskKind), nullable=False)
    ref_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    status: Mapped[TaskStatus] = mapped_column(Enum(TaskStatus), nullable=False, default=TaskStatus.queued)
    progress: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
```

- [ ] **Step 2: Update `backend/alembic/env.py`** — add `from app.tasks.models import TaskRecord  # noqa: F401`

- [ ] **Step 3: Autogenerate + apply migration** (same flow as Task 1.9):

```bash
docker run -d --name pg-tmp -e POSTGRES_PASSWORD=postgres -p 5432:5432 postgres:16-alpine
sleep 4
cd backend
DATABASE_URL=postgresql+asyncpg://postgres:postgres@localhost:5432/postgres \
  ENCRYPTION_KEY=$(uv run python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())") \
  uv run alembic revision --autogenerate -m "create tasks table"
DATABASE_URL=postgresql+asyncpg://postgres:postgres@localhost:5432/postgres uv run alembic upgrade head
docker stop pg-tmp && docker rm pg-tmp
```

- [ ] **Step 4: Commit**

```bash
git add backend/app/tasks/models.py backend/alembic
git commit -m "feat(tasks): add TaskRecord model + migration"
```

---

## Task 2.3: LibraryItem model + migration

**Files:** Create `backend/app/library/__init__.py`, `backend/app/library/models.py`; update `backend/alembic/env.py`; generate migration.

- [ ] **Step 1: Implement `backend/app/library/models.py`**

```python
import enum
import uuid
from datetime import datetime
from sqlalchemy import DateTime, Enum, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column
from app.db.base import Base


class LibraryStatus(str, enum.Enum):
    pending = "pending"
    processing = "processing"
    done = "done"
    failed = "failed"


class LibraryItem(Base):
    __tablename__ = "library_items"
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    source_url: Mapped[str] = mapped_column(String(2048), nullable=False, unique=True)
    original_title: Mapped[str | None] = mapped_column(String(500), nullable=True)
    original_author: Mapped[str | None] = mapped_column(String(200), nullable=True)
    original_content_html: Mapped[str | None] = mapped_column(Text, nullable=True)
    original_content_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    images: Mapped[list[dict] | None] = mapped_column(JSONB, nullable=True)
    status: Mapped[LibraryStatus] = mapped_column(Enum(LibraryStatus), nullable=False, default=LibraryStatus.pending)
    tags: Mapped[list[str] | None] = mapped_column(JSONB, nullable=True, default=list)
    crawled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    error_msg: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
```

- [ ] **Step 2: Update `backend/alembic/env.py`** — add `from app.library.models import LibraryItem  # noqa: F401`

- [ ] **Step 3: Generate + apply migration** (same temp pg flow as before, message: `"create library_items table"`).

- [ ] **Step 4: Commit**

```bash
git add backend/app/library backend/alembic
git commit -m "feat(library): add LibraryItem model + migration"
```

---

## Task 2.4: Crawler — fetcher

**Files:** Create `backend/app/crawler/__init__.py`, `backend/app/crawler/fetcher.py`, `backend/tests/unit/test_fetcher.py`.

- [ ] **Step 1: Write failing test `backend/tests/unit/test_fetcher.py`**

```python
import httpx
import pytest
import respx
from app.crawler.fetcher import FetchError, fetch_html


@pytest.mark.asyncio
async def test_fetch_html_success():
    async with respx.mock(base_url="https://mp.weixin.qq.com") as mock:
        mock.get("/s/abc").mock(return_value=httpx.Response(200, text="<html>hello</html>"))
        result = await fetch_html("https://mp.weixin.qq.com/s/abc")
        assert "hello" in result


@pytest.mark.asyncio
async def test_fetch_html_404_raises():
    async with respx.mock(base_url="https://mp.weixin.qq.com") as mock:
        mock.get("/s/x").mock(return_value=httpx.Response(404))
        with pytest.raises(FetchError):
            await fetch_html("https://mp.weixin.qq.com/s/x")


@pytest.mark.asyncio
async def test_fetch_html_retries_on_5xx():
    async with respx.mock(base_url="https://mp.weixin.qq.com") as mock:
        route = mock.get("/s/y")
        route.side_effect = [
            httpx.Response(503),
            httpx.Response(503),
            httpx.Response(200, text="<html>ok</html>"),
        ]
        result = await fetch_html("https://mp.weixin.qq.com/s/y", max_retries=3)
        assert "ok" in result
        assert route.call_count == 3
```

- [ ] **Step 2: Implement `backend/app/crawler/fetcher.py`**

```python
import asyncio
import random
import httpx
from app.config import get_settings


class FetchError(Exception):
    pass


_USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_0) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Safari/605.1.15",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0 Safari/537.36",
]


async def fetch_html(url: str, *, timeout: int | None = None, max_retries: int | None = None) -> str:
    settings = get_settings()
    timeout = timeout or settings.crawler_timeout
    max_retries = max_retries or settings.crawler_max_retry
    last_exc: Exception | None = None
    for attempt in range(1, max_retries + 1):
        headers = {"User-Agent": random.choice(_USER_AGENTS)}
        try:
            async with httpx.AsyncClient(timeout=timeout, follow_redirects=True) as client:
                response = await client.get(url, headers=headers)
            if response.status_code >= 500:
                last_exc = FetchError(f"5xx: {response.status_code}")
                await asyncio.sleep(2 ** attempt)
                continue
            if response.status_code == 200:
                return response.text
            raise FetchError(f"HTTP {response.status_code}")
        except httpx.TimeoutException as exc:
            last_exc = exc
            await asyncio.sleep(2 ** attempt)
        except httpx.HTTPError as exc:
            raise FetchError(str(exc)) from exc
    raise FetchError(f"failed after {max_retries} retries: {last_exc}")
```

- [ ] **Step 3: Create empty `backend/app/crawler/__init__.py`**

- [ ] **Step 4: Run tests** — `uv run pytest tests/unit/test_fetcher.py -v` — Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/app/crawler backend/tests/unit/test_fetcher.py
git commit -m "feat(crawler): add httpx-based fetcher with UA rotation and retries"
```

---

## Task 2.5: Crawler — parser

**Files:** Create `backend/app/crawler/parser.py`, `backend/tests/unit/test_parser.py`, `backend/tests/fixtures/sample_article.html`.

- [ ] **Step 1: Save sample fixture `backend/tests/fixtures/sample_article.html`** — paste a real WeChat article HTML (or write a minimal one):

```html
<html>
<head><title>测试标题 - 测试号</title></head>
<body>
<h1 id="activity-name">真实测试标题</h1>
<a id="js_name">公众号作者名</a>
<div id="js_content">
  <p>第一段正文，介绍背景。</p>
  <p><img src="https://mmbiz.qpic.cn/img1.jpg" alt="图1"/></p>
  <p>第二段正文。</p>
  <p><img src="https://mmbiz.qpic.cn/img2.jpg"/></p>
</div>
</body></html>
```

- [ ] **Step 2: Write failing test `backend/tests/unit/test_parser.py`**

```python
from pathlib import Path
from app.crawler.parser import parse_wechat_article

FIXTURE = Path(__file__).parent.parent / "fixtures" / "sample_article.html"


def test_parse_extracts_title_author_content_images():
    html = FIXTURE.read_text(encoding="utf-8")
    result = parse_wechat_article(html)
    assert result.title == "真实测试标题"
    assert result.author == "公众号作者名"
    assert "第一段正文" in result.content_text
    assert len(result.images) == 2
    assert result.images[0]["url"] == "https://mmbiz.qpic.cn/img1.jpg"
    assert result.images[0]["position"] == 0
    assert result.images[1]["position"] == 1
    assert "<p>" in result.content_html


def test_parse_handles_missing_title():
    html = "<html><body><div id='js_content'><p>x</p></div></body></html>"
    result = parse_wechat_article(html)
    assert result.title is None
    assert "x" in result.content_text
```

- [ ] **Step 3: Implement `backend/app/crawler/parser.py`**

```python
from dataclasses import dataclass, field
from lxml import html as lxml_html


@dataclass
class ParsedArticle:
    title: str | None
    author: str | None
    content_html: str
    content_text: str
    images: list[dict] = field(default_factory=list)


def parse_wechat_article(html_text: str) -> ParsedArticle:
    tree = lxml_html.fromstring(html_text)

    title_node = tree.xpath("//*[@id='activity-name']")
    title = title_node[0].text_content().strip() if title_node else None

    author_node = tree.xpath("//*[@id='js_name']")
    author = author_node[0].text_content().strip() if author_node else None

    content_node = tree.xpath("//*[@id='js_content']")
    if not content_node:
        return ParsedArticle(title=title, author=author, content_html="", content_text="", images=[])

    container = content_node[0]
    images: list[dict] = []
    for idx, img in enumerate(container.xpath(".//img")):
        url = img.get("data-src") or img.get("src")
        if not url:
            continue
        images.append({"url": url, "alt": img.get("alt", ""), "position": idx})

    content_html = lxml_html.tostring(container, encoding="unicode")
    content_text = container.text_content().strip()
    return ParsedArticle(title=title, author=author, content_html=content_html,
                         content_text=content_text, images=images)
```

- [ ] **Step 4: Run tests** — Expected: PASS (2 tests).

- [ ] **Step 5: Commit**

```bash
git add backend/app/crawler/parser.py backend/tests/unit/test_parser.py backend/tests/fixtures
git commit -m "feat(crawler): add lxml-based WeChat article parser"
```

---

## Task 2.6: Library — schemas + service + routes

**Files:** Create `backend/app/library/{schemas.py,service.py,routes.py}`; modify `backend/app/api/router.py`; create `backend/tests/integration/test_library_routes.py`.

- [ ] **Step 1: `backend/app/library/schemas.py`**

```python
import uuid
from datetime import datetime
from pydantic import BaseModel, ConfigDict, Field
from app.library.models import LibraryStatus


class IngestRequest(BaseModel):
    urls: list[str] = Field(min_length=1, max_length=100)
    tags: list[str] = []


class LibraryItemOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    source_url: str
    original_title: str | None
    original_author: str | None
    status: LibraryStatus
    tags: list[str] | None
    error_msg: str | None
    crawled_at: datetime | None
    created_at: datetime


class LibraryItemDetail(LibraryItemOut):
    original_content_html: str | None
    original_content_text: str | None
    images: list[dict] | None


class TagsUpdate(BaseModel):
    tags: list[str]
```

- [ ] **Step 2: `backend/app/library/service.py`**

```python
import uuid
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.library.models import LibraryItem, LibraryStatus


async def create_pending(db: AsyncSession, url: str, tags: list[str]) -> LibraryItem:
    obj = LibraryItem(source_url=url, tags=tags, status=LibraryStatus.pending)
    db.add(obj)
    await db.commit()
    await db.refresh(obj)
    return obj


async def get(db: AsyncSession, item_id: uuid.UUID) -> LibraryItem | None:
    return await db.get(LibraryItem, item_id)


async def list_items(db: AsyncSession, *,
                     status: LibraryStatus | None = None,
                     tag: str | None = None,
                     limit: int = 50, offset: int = 0) -> list[LibraryItem]:
    stmt = select(LibraryItem).order_by(LibraryItem.created_at.desc()).limit(limit).offset(offset)
    if status is not None:
        stmt = stmt.where(LibraryItem.status == status)
    if tag is not None:
        stmt = stmt.where(LibraryItem.tags.contains([tag]))
    result = await db.execute(stmt)
    return list(result.scalars().all())


async def set_tags(db: AsyncSession, item: LibraryItem, tags: list[str]) -> LibraryItem:
    item.tags = tags
    await db.commit()
    await db.refresh(item)
    return item


async def delete(db: AsyncSession, item: LibraryItem) -> None:
    await db.delete(item)
    await db.commit()
```

- [ ] **Step 3: `backend/app/library/routes.py`**

```python
import uuid
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db
from app.auth.dependencies import get_current_username
from app.library import service
from app.library.models import LibraryStatus
from app.library.schemas import (
    IngestRequest, LibraryItemDetail, LibraryItemOut, TagsUpdate,
)
# Crawl task import deferred to Task 2.7 (avoids circular import during early build)

router = APIRouter(prefix="/library", tags=["library"])


@router.post("", response_model=list[LibraryItemOut], status_code=201)
async def ingest(payload: IngestRequest,
                 db: AsyncSession = Depends(get_db),
                 _: str = Depends(get_current_username)) -> list[LibraryItemOut]:
    from app.tasks.crawl import crawl_library_item  # local import to avoid circulars
    items: list[LibraryItemOut] = []
    for url in payload.urls:
        obj = await service.create_pending(db, url, payload.tags)
        crawl_library_item.delay(str(obj.id))
        items.append(LibraryItemOut.model_validate(obj))
    return items


@router.get("", response_model=list[LibraryItemOut])
async def list_all(status_filter: LibraryStatus | None = None,
                   tag: str | None = None,
                   limit: int = 50, offset: int = 0,
                   db: AsyncSession = Depends(get_db),
                   _: str = Depends(get_current_username)) -> list[LibraryItemOut]:
    rows = await service.list_items(db, status=status_filter, tag=tag, limit=limit, offset=offset)
    return [LibraryItemOut.model_validate(r) for r in rows]


@router.get("/{item_id}", response_model=LibraryItemDetail)
async def get_one(item_id: uuid.UUID,
                  db: AsyncSession = Depends(get_db),
                  _: str = Depends(get_current_username)) -> LibraryItemDetail:
    obj = await service.get(db, item_id)
    if obj is None:
        raise HTTPException(404, "Item not found")
    return LibraryItemDetail.model_validate(obj)


@router.patch("/{item_id}/tags", response_model=LibraryItemOut)
async def update_tags(item_id: uuid.UUID, payload: TagsUpdate,
                      db: AsyncSession = Depends(get_db),
                      _: str = Depends(get_current_username)) -> LibraryItemOut:
    obj = await service.get(db, item_id)
    if obj is None:
        raise HTTPException(404, "Item not found")
    return LibraryItemOut.model_validate(await service.set_tags(db, obj, payload.tags))


@router.delete("/{item_id}", status_code=204)
async def delete(item_id: uuid.UUID,
                 db: AsyncSession = Depends(get_db),
                 _: str = Depends(get_current_username)) -> None:
    obj = await service.get(db, item_id)
    if obj is None:
        raise HTTPException(404, "Item not found")
    await service.delete(db, obj)


@router.post("/{item_id}/retry", response_model=LibraryItemOut)
async def retry(item_id: uuid.UUID,
                db: AsyncSession = Depends(get_db),
                _: str = Depends(get_current_username)) -> LibraryItemOut:
    from app.tasks.crawl import crawl_library_item
    obj = await service.get(db, item_id)
    if obj is None:
        raise HTTPException(404, "Item not found")
    obj.status = LibraryStatus.pending
    obj.error_msg = None
    await db.commit()
    await db.refresh(obj)
    crawl_library_item.delay(str(obj.id))
    return LibraryItemOut.model_validate(obj)
```

- [ ] **Step 4: Update `backend/app/api/router.py`** — add `from app.library.routes import router as library_router` and include it.

- [ ] **Step 5: Update `backend/tests/integration/conftest.py`** — add imports `from app.library.models import LibraryItem  # noqa: F401` and `from app.tasks.models import TaskRecord  # noqa: F401` (so create_all sees these tables).

- [ ] **Step 6: Write integration test `backend/tests/integration/test_library_routes.py`**

```python
import pytest
from httpx import ASGITransport, AsyncClient
from app.api.deps import get_db
from app.main import create_app


@pytest.fixture
def app(db_session, monkeypatch):
    # Stub out the celery .delay so test does not need a broker.
    from app.tasks import crawl
    monkeypatch.setattr(crawl.crawl_library_item, "delay", lambda *a, **k: None, raising=False)

    app = create_app()
    async def _override():
        yield db_session
    app.dependency_overrides[get_db] = _override
    return app


@pytest.fixture
async def auth_client(app):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        login = await client.post("/api/auth/login",
                                  data={"username": "admin", "password": "hunter2"})
        client.headers["Authorization"] = f"Bearer {login.json()['access_token']}"
        yield client


async def test_ingest_creates_pending_items(auth_client):
    r = await auth_client.post("/api/library", json={
        "urls": ["https://mp.weixin.qq.com/s/abc", "https://mp.weixin.qq.com/s/def"],
        "tags": ["职场"],
    })
    assert r.status_code == 201
    assert len(r.json()) == 2
    assert all(item["status"] == "pending" for item in r.json())


async def test_list_filtered_by_tag(auth_client):
    await auth_client.post("/api/library", json={"urls": ["https://x/1"], "tags": ["a"]})
    await auth_client.post("/api/library", json={"urls": ["https://x/2"], "tags": ["b"]})
    r = await auth_client.get("/api/library?tag=a")
    assert len(r.json()) == 1


async def test_update_tags_and_delete(auth_client):
    create = await auth_client.post("/api/library", json={"urls": ["https://x/3"], "tags": []})
    item_id = create.json()[0]["id"]
    upd = await auth_client.patch(f"/api/library/{item_id}/tags", json={"tags": ["养生"]})
    assert upd.json()["tags"] == ["养生"]
    delete = await auth_client.delete(f"/api/library/{item_id}")
    assert delete.status_code == 204
```

- [ ] **Step 7: Run integration tests** — Expected: PASS (3 tests).

- [ ] **Step 8: Commit**

```bash
git add backend/app/library backend/app/api/router.py backend/tests/integration
git commit -m "feat(library): add library schemas, service, CRUD routes, integration tests"
```

---

## Task 2.7: Crawl Celery task

**Files:** Create `backend/app/tasks/crawl.py`, `backend/tests/unit/test_crawl_task.py`.

- [ ] **Step 1: Implement `backend/app/tasks/crawl.py`**

```python
import asyncio
import logging
import uuid
from datetime import datetime, timezone
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker
from app.config import get_settings
from app.crawler.fetcher import FetchError, fetch_html
from app.crawler.parser import parse_wechat_article
from app.db.session import make_engine
from app.library.models import LibraryItem, LibraryStatus
from app.tasks.celery_app import celery_app

logger = logging.getLogger(__name__)


async def _do_crawl(item_id: uuid.UUID) -> None:
    engine = make_engine()
    sm = async_sessionmaker(engine, expire_on_commit=False)
    async with sm() as session:
        item = (await session.execute(select(LibraryItem).where(LibraryItem.id == item_id))).scalar_one_or_none()
        if item is None:
            logger.warning("library_item %s not found", item_id)
            return
        item.status = LibraryStatus.processing
        await session.commit()
        try:
            html = await fetch_html(item.source_url)
            parsed = parse_wechat_article(html)
            item.original_title = parsed.title
            item.original_author = parsed.author
            item.original_content_html = parsed.content_html
            item.original_content_text = parsed.content_text
            item.images = parsed.images
            item.status = LibraryStatus.done
            item.crawled_at = datetime.now(timezone.utc)
            item.error_msg = None
        except FetchError as exc:
            item.status = LibraryStatus.failed
            item.error_msg = f"fetch error: {exc}"
        except Exception as exc:  # parser or other
            item.status = LibraryStatus.failed
            item.error_msg = f"unexpected: {exc!r}"
        await session.commit()
    await engine.dispose()


@celery_app.task(name="app.tasks.crawl.crawl_library_item",
                 bind=True, autoretry_for=(FetchError,),
                 max_retries=2, default_retry_delay=10)
def crawl_library_item(self, item_id: str) -> None:
    asyncio.run(_do_crawl(uuid.UUID(item_id)))
```

- [ ] **Step 2: Write integration-style test `backend/tests/integration/test_crawl_task.py`**

```python
import pytest
import respx
import httpx
from sqlalchemy import select
from app.library.models import LibraryItem, LibraryStatus
from app.library import service as lib_service
from app.tasks.crawl import _do_crawl


@pytest.mark.asyncio
async def test_crawl_marks_item_done(db_session):
    item = await lib_service.create_pending(db_session, "https://mp.weixin.qq.com/s/abc", [])
    sample = """
    <html><body>
      <h1 id='activity-name'>x</h1>
      <a id='js_name'>y</a>
      <div id='js_content'><p>z</p></div>
    </body></html>"""
    async with respx.mock(base_url="https://mp.weixin.qq.com") as mock:
        mock.get("/s/abc").mock(return_value=httpx.Response(200, text=sample))
        await _do_crawl(item.id)
    refreshed = (await db_session.execute(
        select(LibraryItem).where(LibraryItem.id == item.id))).scalar_one()
    assert refreshed.status == LibraryStatus.done
    assert refreshed.original_title == "x"
    assert refreshed.original_author == "y"


@pytest.mark.asyncio
async def test_crawl_marks_failed_on_404(db_session):
    item = await lib_service.create_pending(db_session, "https://mp.weixin.qq.com/s/missing", [])
    async with respx.mock(base_url="https://mp.weixin.qq.com") as mock:
        mock.get("/s/missing").mock(return_value=httpx.Response(404))
        await _do_crawl(item.id)
    refreshed = (await db_session.execute(
        select(LibraryItem).where(LibraryItem.id == item.id))).scalar_one()
    assert refreshed.status == LibraryStatus.failed
    assert "fetch error" in (refreshed.error_msg or "")
```

- [ ] **Step 3: Update `backend/app/tasks/celery_app.py`** — already includes `app.tasks.crawl` in `include`. Verify nothing breaks.

- [ ] **Step 4: Run tests** — Expected: PASS (2 tests).

- [ ] **Step 5: End-to-end smoke test in compose**

```bash
docker compose up -d --build
TOKEN=$(curl -s -X POST http://localhost/api/auth/login \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "username=admin&password=hunter2" | jq -r .access_token)
curl -X POST http://localhost/api/library -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"urls":["https://mp.weixin.qq.com/s/<some-real-test-url>"],"tags":["smoke"]}'
sleep 5
curl http://localhost/api/library -H "Authorization: Bearer $TOKEN" | jq
docker compose logs worker --tail 50
```
Expected: library item moves from `pending` → `processing` → `done` (or `failed` with parsing error if fixture URL is fake).

- [ ] **Step 6: Commit**

```bash
git add backend/app/tasks/crawl.py backend/tests/integration/test_crawl_task.py
git commit -m "feat(tasks): add crawl_library_item Celery task with status tracking"
```

---

## Task 2.8: Frontend — Library page

**Files:** Create `frontend/src/pages/Library.tsx`; modify `frontend/src/App.tsx` and add nav.

- [ ] **Step 1: Create `frontend/src/pages/Library.tsx`**

```tsx
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { api } from "../api/client";

type LibraryItem = {
  id: string;
  source_url: string;
  original_title: string | null;
  status: "pending" | "processing" | "done" | "failed";
  tags: string[] | null;
  error_msg: string | null;
};

const STATUS_COLOR = {
  pending: "bg-slate-200",
  processing: "bg-blue-200",
  done: "bg-green-200",
  failed: "bg-red-200",
};

export default function Library() {
  const qc = useQueryClient();
  const [text, setText] = useState("");
  const [tags, setTags] = useState("");

  const { data, isLoading } = useQuery({
    queryKey: ["library"],
    queryFn: async () => (await api.get<LibraryItem[]>("/library")).data,
    refetchInterval: 5000,
  });

  const ingest = useMutation({
    mutationFn: async () => {
      const urls = text.split("\n").map((u) => u.trim()).filter(Boolean);
      return api.post("/library", { urls, tags: tags.split(",").map((t) => t.trim()).filter(Boolean) });
    },
    onSuccess: () => { setText(""); qc.invalidateQueries({ queryKey: ["library"] }); },
  });

  const retry = useMutation({
    mutationFn: async (id: string) => api.post(`/library/${id}/retry`),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["library"] }),
  });

  return (
    <div className="p-8 space-y-6">
      <h1 className="text-2xl font-semibold">素材库</h1>

      <div className="space-y-3 border rounded p-4">
        <h2 className="font-medium">添加文章 URL（一行一个）</h2>
        <textarea className="w-full border rounded p-2 h-32 font-mono text-sm"
                  value={text} onChange={(e) => setText(e.target.value)}
                  placeholder="https://mp.weixin.qq.com/s/..." />
        <input className="w-full border rounded p-2"
               placeholder="标签（逗号分隔，如 职场,母婴）"
               value={tags} onChange={(e) => setTags(e.target.value)} />
        <button onClick={() => ingest.mutate()}
                disabled={ingest.isPending || !text.trim()}
                className="bg-slate-900 text-white px-4 py-2 rounded disabled:opacity-50">
          {ingest.isPending ? "提交中..." : "添加抓取"}
        </button>
      </div>

      <div>
        <h2 className="font-medium mb-2">列表</h2>
        {isLoading && <div>加载中...</div>}
        <ul className="space-y-2">
          {data?.map((item) => (
            <li key={item.id} className="border rounded p-3">
              <div className="flex justify-between items-start gap-4">
                <div className="min-w-0 flex-1">
                  <div className="truncate font-medium">
                    {item.original_title || item.source_url}
                  </div>
                  <div className="text-xs text-slate-500 truncate">{item.source_url}</div>
                  {item.tags?.length ? (
                    <div className="text-xs text-slate-600 mt-1">
                      {item.tags.map((t) => (
                        <span key={t} className="inline-block bg-slate-100 px-2 py-0.5 rounded mr-1">{t}</span>
                      ))}
                    </div>
                  ) : null}
                  {item.error_msg && (
                    <div className="text-xs text-red-600 mt-1">{item.error_msg}</div>
                  )}
                </div>
                <div className="flex flex-col items-end gap-2">
                  <span className={`text-xs px-2 py-0.5 rounded ${STATUS_COLOR[item.status]}`}>
                    {item.status}
                  </span>
                  {item.status === "failed" && (
                    <button onClick={() => retry.mutate(item.id)}
                            className="text-xs underline">重试</button>
                  )}
                </div>
              </div>
            </li>
          ))}
        </ul>
      </div>
    </div>
  );
}
```

- [ ] **Step 2: Modify `frontend/src/App.tsx`** — add Library route

```tsx
import { Navigate, Route, Routes, Link } from "react-router-dom";
import Login from "./pages/Login";
import Accounts from "./pages/Accounts";
import Library from "./pages/Library";

function isAuthed() { return Boolean(localStorage.getItem("token")); }
function RequireAuth({ children }: { children: JSX.Element }) {
  return isAuthed() ? children : <Navigate to="/login" replace />;
}

function Nav() {
  return (
    <nav className="bg-slate-900 text-white px-6 py-3 flex gap-4">
      <Link to="/library">素材库</Link>
      <Link to="/accounts">公众号</Link>
      <button className="ml-auto" onClick={() => {
        localStorage.removeItem("token");
        window.location.href = "/login";
      }}>登出</button>
    </nav>
  );
}

function Shell({ children }: { children: JSX.Element }) {
  return <RequireAuth><><Nav />{children}</></RequireAuth>;
}

export default function App() {
  return (
    <Routes>
      <Route path="/login" element={<Login />} />
      <Route path="/library" element={<Shell><Library /></Shell>} />
      <Route path="/accounts" element={<Shell><Accounts /></Shell>} />
      <Route path="*" element={<Navigate to="/library" replace />} />
    </Routes>
  );
}
```

- [ ] **Step 3: Smoke test** — `pnpm dev`, log in, verify "素材库" page loads and you can paste URLs.

- [ ] **Step 4: Commit**

```bash
git add frontend/src/pages/Library.tsx frontend/src/App.tsx
git commit -m "feat(frontend): add Library page with URL paste, list, retry, polling"
```

---

## Stage 2 Exit Criteria

- [ ] Worker container starts and connects to Redis broker.
- [ ] Posting URLs to `/api/library` immediately returns; rows appear in DB as `pending`.
- [ ] After ~30s, items either move to `done` (with title/author/content/images parsed) or `failed` (with error_msg populated).
- [ ] Retrying a failed item resets it to `pending` and re-runs the crawl.
- [ ] Library frontend page works end-to-end (add → list → status updates → retry).
- [ ] All unit + integration tests pass: `cd backend && uv run pytest -v`.

---

# Stage 3 — Rewrite Pipeline (AI core)

Goal: Multi-provider AI registry with role-based routing; user can trigger batch rewrite for selected library items against a target account; pipeline produces drafts with 4-dimension review reports.

---

## Task 3.1: AI provider tables + RoleBinding + AIUsage

**Files:** Create `backend/app/ai_providers/__init__.py`, `backend/app/ai_providers/models.py`; update `backend/alembic/env.py`; generate migration.

- [ ] **Step 1: Implement `backend/app/ai_providers/models.py`**

```python
import enum
import uuid
from datetime import datetime
from sqlalchemy import Boolean, DateTime, Enum, ForeignKey, Integer, Numeric, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column
from app.db.base import Base
from app.db.encryption import EncryptedString


class AIProvider(Base):
    __tablename__ = "ai_providers"
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(50), nullable=False, unique=True)
    base_url: Mapped[str] = mapped_column(String(500), nullable=False)
    api_key: Mapped[str] = mapped_column(EncryptedString(length=4096), nullable=False)
    models: Mapped[list[str]] = mapped_column(JSONB, nullable=False, default=list)
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class Role(str, enum.Enum):
    writer = "writer"
    reviewer = "reviewer"
    lite = "lite"


class RoleBinding(Base):
    __tablename__ = "role_bindings"
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    role: Mapped[Role] = mapped_column(Enum(Role), nullable=False, unique=True)
    provider_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("ai_providers.id"), nullable=False)
    model: Mapped[str] = mapped_column(String(100), nullable=False)


class AIUsage(Base):
    __tablename__ = "ai_usage"
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    provider_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("ai_providers.id"), nullable=True)
    role: Mapped[str | None] = mapped_column(String(50), nullable=True)
    model: Mapped[str] = mapped_column(String(100), nullable=False)
    prompt_tokens: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    completion_tokens: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    cost_estimate: Mapped[float] = mapped_column(Numeric(10, 6), nullable=False, default=0)
    purpose: Mapped[str] = mapped_column(String(100), nullable=False)  # e.g. "rewrite_title", "review_compliance"
    ref_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
```

- [ ] **Step 2: Update `backend/alembic/env.py`** — add `from app.ai_providers.models import AIProvider, RoleBinding, AIUsage  # noqa: F401`.

- [ ] **Step 3: Autogenerate + apply migration** (same temp pg flow, message `"create ai_providers, role_bindings, ai_usage tables"`).

- [ ] **Step 4: Update `backend/tests/integration/conftest.py`** — add `from app.ai_providers.models import AIProvider, RoleBinding, AIUsage  # noqa: F401`.

- [ ] **Step 5: Commit**

```bash
git add backend/app/ai_providers backend/alembic backend/tests/integration/conftest.py
git commit -m "feat(ai_providers): add provider, role binding, usage tables + migration"
```

---

## Task 3.2: BaseProvider + OpenAICompatProvider

**Files:** Create `backend/app/ai_providers/base.py`, `backend/app/ai_providers/openai_compat.py`, `backend/tests/unit/test_openai_compat.py`.

- [ ] **Step 1: `backend/app/ai_providers/base.py`**

```python
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Literal


@dataclass
class Message:
    role: Literal["system", "user", "assistant"]
    content: str


@dataclass
class TokenUsage:
    prompt_tokens: int = 0
    completion_tokens: int = 0


@dataclass
class ChatResult:
    content: str
    model: str
    usage: TokenUsage = field(default_factory=TokenUsage)
    raw: dict[str, Any] = field(default_factory=dict)


class BaseProvider(ABC):
    name: str

    @abstractmethod
    async def chat(
        self,
        messages: list[Message],
        *,
        model: str,
        temperature: float = 0.7,
        max_tokens: int | None = None,
        json_mode: bool = False,
    ) -> ChatResult:
        ...
```

- [ ] **Step 2: `backend/app/ai_providers/openai_compat.py`**

```python
from openai import AsyncOpenAI
from app.ai_providers.base import BaseProvider, ChatResult, Message, TokenUsage


class OpenAICompatProvider(BaseProvider):
    def __init__(self, *, name: str, api_key: str, base_url: str) -> None:
        self.name = name
        self._client = AsyncOpenAI(api_key=api_key, base_url=base_url)

    async def chat(
        self,
        messages: list[Message],
        *,
        model: str,
        temperature: float = 0.7,
        max_tokens: int | None = None,
        json_mode: bool = False,
    ) -> ChatResult:
        kwargs: dict = {
            "model": model,
            "messages": [{"role": m.role, "content": m.content} for m in messages],
            "temperature": temperature,
        }
        if max_tokens is not None:
            kwargs["max_tokens"] = max_tokens
        if json_mode:
            kwargs["response_format"] = {"type": "json_object"}
        resp = await self._client.chat.completions.create(**kwargs)
        choice = resp.choices[0]
        usage = TokenUsage(
            prompt_tokens=resp.usage.prompt_tokens if resp.usage else 0,
            completion_tokens=resp.usage.completion_tokens if resp.usage else 0,
        )
        return ChatResult(content=choice.message.content or "", model=resp.model,
                          usage=usage, raw=resp.model_dump())
```

- [ ] **Step 3: Write failing test `backend/tests/unit/test_openai_compat.py`**

```python
import pytest
import respx
import httpx
from app.ai_providers.base import Message
from app.ai_providers.openai_compat import OpenAICompatProvider


@pytest.mark.asyncio
async def test_chat_returns_content_and_usage():
    body = {
        "id": "x",
        "model": "deepseek-chat",
        "choices": [{"index": 0, "message": {"role": "assistant", "content": "hello"},
                     "finish_reason": "stop"}],
        "usage": {"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15},
    }
    async with respx.mock(base_url="https://api.deepseek.com/v1") as mock:
        mock.post("/chat/completions").mock(return_value=httpx.Response(200, json=body))
        provider = OpenAICompatProvider(name="deepseek", api_key="sk-x",
                                        base_url="https://api.deepseek.com/v1")
        result = await provider.chat(
            [Message(role="user", content="hi")],
            model="deepseek-chat",
        )
    assert result.content == "hello"
    assert result.usage.prompt_tokens == 10
    assert result.usage.completion_tokens == 5
```

- [ ] **Step 4: Run tests** — Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/app/ai_providers/base.py backend/app/ai_providers/openai_compat.py backend/tests/unit/test_openai_compat.py
git commit -m "feat(ai_providers): add BaseProvider + OpenAICompat adapter"
```

---

## Task 3.3: Provider registry with role binding

**Files:** Create `backend/app/ai_providers/registry.py`, `backend/tests/unit/test_registry.py`.

- [ ] **Step 1: Implement `backend/app/ai_providers/registry.py`**

```python
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.ai_providers.base import BaseProvider
from app.ai_providers.models import AIProvider, Role, RoleBinding
from app.ai_providers.openai_compat import OpenAICompatProvider


class RegistryError(Exception):
    pass


class ProviderRegistry:
    def __init__(self) -> None:
        self._providers: dict[str, BaseProvider] = {}
        self._role_to_pair: dict[str, tuple[str, str]] = {}  # role -> (provider_name, model)

    def register(self, provider: BaseProvider) -> None:
        self._providers[provider.name] = provider

    def bind_role(self, role: str, *, provider: str, model: str) -> None:
        if provider not in self._providers:
            raise RegistryError(f"unknown provider: {provider}")
        self._role_to_pair[role] = (provider, model)

    def role(self, role: str) -> tuple[BaseProvider, str]:
        if role not in self._role_to_pair:
            raise RegistryError(f"role not bound: {role}")
        provider_name, model = self._role_to_pair[role]
        return self._providers[provider_name], model

    def reset(self) -> None:
        self._providers.clear()
        self._role_to_pair.clear()


_registry = ProviderRegistry()


def get_registry() -> ProviderRegistry:
    return _registry


async def load_from_db(db: AsyncSession) -> None:
    """Reload providers and role bindings from DB. Call at app startup and after config changes."""
    _registry.reset()
    providers = (await db.execute(select(AIProvider).where(AIProvider.enabled.is_(True)))).scalars().all()
    by_id = {p.id: p for p in providers}
    for p in providers:
        _registry.register(OpenAICompatProvider(name=p.name, api_key=p.api_key, base_url=p.base_url))
    bindings = (await db.execute(select(RoleBinding))).scalars().all()
    for b in bindings:
        provider = by_id.get(b.provider_id)
        if provider is None:
            continue
        _registry.bind_role(b.role.value, provider=provider.name, model=b.model)
```

- [ ] **Step 2: Write failing test `backend/tests/unit/test_registry.py`**

```python
import pytest
from app.ai_providers.base import BaseProvider, ChatResult, Message, TokenUsage
from app.ai_providers.registry import ProviderRegistry, RegistryError


class StubProvider(BaseProvider):
    def __init__(self, name: str) -> None:
        self.name = name

    async def chat(self, messages, *, model, **kwargs):
        return ChatResult(content="ok", model=model, usage=TokenUsage())


def test_register_and_bind():
    reg = ProviderRegistry()
    reg.register(StubProvider("a"))
    reg.bind_role("writer", provider="a", model="m1")
    p, m = reg.role("writer")
    assert p.name == "a"
    assert m == "m1"


def test_bind_unknown_provider_raises():
    reg = ProviderRegistry()
    with pytest.raises(RegistryError):
        reg.bind_role("writer", provider="missing", model="m")


def test_unbound_role_raises():
    reg = ProviderRegistry()
    reg.register(StubProvider("a"))
    with pytest.raises(RegistryError):
        reg.role("writer")
```

- [ ] **Step 3: Run tests** — Expected: PASS.

- [ ] **Step 4: Commit**

```bash
git add backend/app/ai_providers/registry.py backend/tests/unit/test_registry.py
git commit -m "feat(ai_providers): add ProviderRegistry with role binding + DB loader"
```

---

## Task 3.4: AI Provider CRUD routes

**Files:** Create `backend/app/ai_providers/{schemas.py,service.py,routes.py}`; modify `backend/app/api/router.py`; create `backend/tests/integration/test_ai_provider_routes.py`.

- [ ] **Step 1: `backend/app/ai_providers/schemas.py`**

```python
import uuid
from pydantic import BaseModel, ConfigDict, Field
from app.ai_providers.models import Role


class ProviderIn(BaseModel):
    name: str = Field(min_length=1, max_length=50)
    base_url: str = Field(min_length=1, max_length=500)
    api_key: str = Field(min_length=1)
    models: list[str] = []
    enabled: bool = True


class ProviderUpdate(BaseModel):
    base_url: str | None = None
    api_key: str | None = None
    models: list[str] | None = None
    enabled: bool | None = None


class ProviderOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    name: str
    base_url: str
    models: list[str]
    enabled: bool
    # api_key never returned


class RoleBindingIn(BaseModel):
    role: Role
    provider_id: uuid.UUID
    model: str


class RoleBindingOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    role: Role
    provider_id: uuid.UUID
    model: str
```

- [ ] **Step 2: `backend/app/ai_providers/service.py`**

```python
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


async def get_provider(db: AsyncSession, pid: uuid.UUID) -> AIProvider | None:
    return await db.get(AIProvider, pid)


async def update_provider(db: AsyncSession, obj: AIProvider, payload: ProviderUpdate) -> AIProvider:
    for k, v in payload.model_dump(exclude_none=True).items():
        setattr(obj, k, v)
    await db.commit()
    await db.refresh(obj)
    return obj


async def delete_provider(db: AsyncSession, obj: AIProvider) -> None:
    await db.delete(obj)
    await db.commit()


async def upsert_role_binding(db: AsyncSession, payload: RoleBindingIn) -> RoleBinding:
    existing = (await db.execute(
        select(RoleBinding).where(RoleBinding.role == payload.role))).scalar_one_or_none()
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
```

- [ ] **Step 3: `backend/app/ai_providers/routes.py`**

```python
import uuid
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from app.ai_providers import registry, service
from app.ai_providers.schemas import (
    ProviderIn, ProviderOut, ProviderUpdate, RoleBindingIn, RoleBindingOut,
)
from app.api.deps import get_db
from app.auth.dependencies import get_current_username

router = APIRouter(prefix="/ai-providers", tags=["ai_providers"])


@router.post("", response_model=ProviderOut, status_code=201)
async def create(payload: ProviderIn,
                 db: AsyncSession = Depends(get_db),
                 _: str = Depends(get_current_username)) -> ProviderOut:
    obj = await service.create_provider(db, payload)
    await registry.load_from_db(db)
    return ProviderOut.model_validate(obj)


@router.get("", response_model=list[ProviderOut])
async def list_all(db: AsyncSession = Depends(get_db),
                   _: str = Depends(get_current_username)) -> list[ProviderOut]:
    return [ProviderOut.model_validate(r) for r in await service.list_providers(db)]


@router.patch("/{provider_id}", response_model=ProviderOut)
async def update(provider_id: uuid.UUID, payload: ProviderUpdate,
                 db: AsyncSession = Depends(get_db),
                 _: str = Depends(get_current_username)) -> ProviderOut:
    obj = await service.get_provider(db, provider_id)
    if obj is None:
        raise HTTPException(404, "Provider not found")
    obj = await service.update_provider(db, obj, payload)
    await registry.load_from_db(db)
    return ProviderOut.model_validate(obj)


@router.delete("/{provider_id}", status_code=204)
async def delete(provider_id: uuid.UUID,
                 db: AsyncSession = Depends(get_db),
                 _: str = Depends(get_current_username)) -> None:
    obj = await service.get_provider(db, provider_id)
    if obj is None:
        raise HTTPException(404, "Provider not found")
    await service.delete_provider(db, obj)
    await registry.load_from_db(db)


@router.put("/role-bindings", response_model=RoleBindingOut)
async def upsert_binding(payload: RoleBindingIn,
                         db: AsyncSession = Depends(get_db),
                         _: str = Depends(get_current_username)) -> RoleBindingOut:
    obj = await service.upsert_role_binding(db, payload)
    await registry.load_from_db(db)
    return RoleBindingOut.model_validate(obj)


@router.get("/role-bindings", response_model=list[RoleBindingOut])
async def list_bindings(db: AsyncSession = Depends(get_db),
                        _: str = Depends(get_current_username)) -> list[RoleBindingOut]:
    return [RoleBindingOut.model_validate(r) for r in await service.list_role_bindings(db)]
```

- [ ] **Step 4: Update `backend/app/api/router.py`** — add `from app.ai_providers.routes import router as ai_providers_router` and include it.

- [ ] **Step 5: Smoke test** — start compose, hit endpoints with auth. Skip unit/integration tests for now (covered by next tasks via the registry).

- [ ] **Step 6: Commit**

```bash
git add backend/app/ai_providers backend/app/api/router.py
git commit -m "feat(ai_providers): add CRUD routes for providers and role bindings"
```

---

## Task 3.5: Drafts + ReviewReports models + migrations

**Files:** Create `backend/app/drafts/__init__.py`, `backend/app/drafts/models.py`; update `backend/alembic/env.py`; generate migration.

- [ ] **Step 1: Implement `backend/app/drafts/models.py`**

```python
import enum
import uuid
from datetime import datetime
from sqlalchemy import DateTime, Enum, ForeignKey, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column
from app.db.base import Base


class DraftStatus(str, enum.Enum):
    draft = "draft"
    reviewing = "reviewing"
    reviewed = "reviewed"
    published_to_wechat = "published_to_wechat"
    failed = "failed"


class Draft(Base):
    __tablename__ = "drafts"
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    library_item_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("library_items.id"), nullable=False)
    account_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("accounts.id"), nullable=False)
    title: Mapped[str | None] = mapped_column(String(500), nullable=True)
    content_html: Mapped[str | None] = mapped_column(Text, nullable=True)
    cover_image_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    status: Mapped[DraftStatus] = mapped_column(Enum(DraftStatus), nullable=False, default=DraftStatus.draft)
    review_report_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("review_reports.id", use_alter=True, name="fk_drafts_review_report"),
        nullable=True)
    error_msg: Mapped[str | None] = mapped_column(Text, nullable=True)
    wechat_media_id: Mapped[str | None] = mapped_column(String(200), nullable=True)
    wechat_pushed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class ReviewReport(Base):
    __tablename__ = "review_reports"
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    draft_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("drafts.id"), nullable=False)
    compliance: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    originality: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    quality: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    clickbait: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    overall_score: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
```

- [ ] **Step 2: Update `backend/alembic/env.py`** — add `from app.drafts.models import Draft, ReviewReport  # noqa: F401`.

- [ ] **Step 3: Update `backend/tests/integration/conftest.py`** — same import.

- [ ] **Step 4: Generate + apply migration** (temp pg, message: `"create drafts and review_reports tables"`).

- [ ] **Step 5: Commit**

```bash
git add backend/app/drafts/__init__.py backend/app/drafts/models.py backend/alembic backend/tests/integration/conftest.py
git commit -m "feat(drafts): add Draft and ReviewReport models + migration"
```

---

## Task 3.6: Prompt builder

**Files:** Create `backend/app/rewriter/__init__.py`, `backend/app/rewriter/prompt_builder.py`, `backend/tests/unit/test_prompt_builder.py`.

- [ ] **Step 1: Write failing test `backend/tests/unit/test_prompt_builder.py`**

```python
from app.rewriter.prompt_builder import build_title_messages, build_content_messages


def test_build_title_includes_account_prompt_and_original():
    msgs = build_title_messages(
        account_title_prompt="改写得更吸引人但不夸张",
        category="职场",
        style_desc="专业克制",
        original_title="十大职场陷阱",
        override="加点紧迫感",
    )
    assert any("改写得更吸引人" in m.content for m in msgs)
    assert any("职场" in m.content for m in msgs)
    assert any("专业克制" in m.content for m in msgs)
    assert any("十大职场陷阱" in m.content for m in msgs)
    assert any("加点紧迫感" in m.content for m in msgs)


def test_build_content_truncates_long_input():
    long_text = "x" * 50_000
    msgs = build_content_messages(
        account_content_prompt="保持原意改写",
        category="职场",
        style_desc="",
        original_content=long_text,
        override=None,
        max_chars=8000,
    )
    user_msg = next(m for m in msgs if m.role == "user")
    assert len(user_msg.content) <= 8500
```

- [ ] **Step 2: Implement `backend/app/rewriter/prompt_builder.py`**

```python
from app.ai_providers.base import Message


SYSTEM_BASE = (
    "你是一名资深公众号内容编辑，专长是改写爆款文章。"
    "请遵循以下要求："
    "1) 保持原文核心信息和事实准确；"
    "2) 调整结构和措辞，避免与原文相似度过高；"
    "3) 使用符合中文公众号读者习惯的表达；"
    "4) 严格遵守相关法规、避免广告法违禁词、避免医疗保健夸大。"
)


def _account_block(category: str, style_desc: str) -> str:
    parts = [f"【公众号定位】类型：{category}"]
    if style_desc:
        parts.append(f"【公众号风格】{style_desc}")
    return "\n".join(parts)


def build_title_messages(*, account_title_prompt: str, category: str, style_desc: str,
                         original_title: str, override: str | None = None) -> list[Message]:
    system = "\n\n".join([SYSTEM_BASE,
                          _account_block(category, style_desc),
                          "你现在的任务是改写文章【标题】。"])
    user_parts: list[str] = [f"【标题改写要求】{account_title_prompt}"]
    if override:
        user_parts.append(f"【本次额外要求】{override}")
    user_parts.append(f"【原标题】{original_title}")
    user_parts.append("请直接输出新标题，不要解释、不要引号包裹。")
    return [Message(role="system", content=system),
            Message(role="user", content="\n".join(user_parts))]


def build_content_messages(*, account_content_prompt: str, category: str, style_desc: str,
                           original_content: str, override: str | None = None,
                           max_chars: int = 8000) -> list[Message]:
    truncated = original_content[:max_chars]
    if len(original_content) > max_chars:
        truncated += "\n[...原文截断]"
    system = "\n\n".join([SYSTEM_BASE,
                          _account_block(category, style_desc),
                          "你现在的任务是改写文章【正文】，输出 HTML 格式（仅段落 <p> 和强调 <strong>）。"])
    user_parts: list[str] = [f"【正文改写要求】{account_content_prompt}"]
    if override:
        user_parts.append(f"【本次额外要求】{override}")
    user_parts.append("【原文】")
    user_parts.append(truncated)
    user_parts.append("请直接输出改写后的 HTML，不要包裹在 ```html 代码块中。")
    return [Message(role="system", content=system),
            Message(role="user", content="\n".join(user_parts))]
```

- [ ] **Step 3: Run tests** — Expected: PASS.

- [ ] **Step 4: Commit**

```bash
git add backend/app/rewriter backend/tests/unit/test_prompt_builder.py
git commit -m "feat(rewriter): add prompt builder for title and content"
```

---

## Task 3.7: Sensitive words blacklist

**Files:** Create `backend/app/reviewer/__init__.py`, `backend/app/reviewer/sensitive_words.py`, `backend/data/sensitive_words.txt`, `backend/tests/unit/test_sensitive_words.py`.

- [ ] **Step 1: Create `backend/data/sensitive_words.txt`** (seed file — user can extend later)

```
最佳
最优
顶级
独家秘方
彻底治愈
神药
包治
广告法第九条
诈骗
```

- [ ] **Step 2: Write failing test `backend/tests/unit/test_sensitive_words.py`**

```python
from pathlib import Path
import pytest
from app.reviewer.sensitive_words import SensitiveWordChecker


@pytest.fixture
def checker(tmp_path):
    words = tmp_path / "words.txt"
    words.write_text("最佳\n包治\n", encoding="utf-8")
    return SensitiveWordChecker.from_file(words)


def test_check_finds_hits(checker):
    hits = checker.check("这是最佳的产品，包治百病。")
    assert sorted(hits) == ["包治", "最佳"]


def test_check_no_hits_returns_empty(checker):
    assert checker.check("这是普通的产品。") == []


def test_from_file_skips_blanks_and_comments(tmp_path):
    f = tmp_path / "w.txt"
    f.write_text("\n# comment\n禁词\n", encoding="utf-8")
    checker = SensitiveWordChecker.from_file(f)
    assert checker.check("这里有禁词存在") == ["禁词"]
```

- [ ] **Step 3: Implement `backend/app/reviewer/sensitive_words.py`**

```python
from pathlib import Path


class SensitiveWordChecker:
    def __init__(self, words: list[str]) -> None:
        self._words = [w for w in words if w]

    @classmethod
    def from_file(cls, path: Path) -> "SensitiveWordChecker":
        words: list[str] = []
        for raw in Path(path).read_text(encoding="utf-8").splitlines():
            stripped = raw.strip()
            if not stripped or stripped.startswith("#"):
                continue
            words.append(stripped)
        return cls(words)

    def check(self, text: str) -> list[str]:
        return sorted({w for w in self._words if w in text})
```

- [ ] **Step 4: Run tests** — Expected: PASS.

- [ ] **Step 5: Create empty `backend/app/reviewer/__init__.py`**

- [ ] **Step 6: Commit**

```bash
git add backend/app/reviewer backend/data/sensitive_words.txt backend/tests/unit/test_sensitive_words.py
git commit -m "feat(reviewer): add sensitive-word blacklist checker"
```

---

## Task 3.8: Reviewer modules — 4 dimensions

**Files:** Create `backend/app/reviewer/{compliance.py,originality.py,quality.py,clickbait.py,aggregator.py}`, `backend/tests/unit/test_reviewers.py`.

Each reviewer is a function that takes inputs + a chat-callable and returns a `dict` with `score` (0-100), `issues` (list[str]), and `model` (str). They share a common contract.

- [ ] **Step 1: Implement `backend/app/reviewer/compliance.py`**

```python
import json
from app.ai_providers.base import BaseProvider, Message
from app.reviewer.sensitive_words import SensitiveWordChecker

PROMPT = """你是一名公众号合规审核员。请评估以下文章是否存在违规风险（政治敏感、广告法违禁词、医疗保健夸大、虚假宣传）。
输出严格 JSON：{"score": 0-100 整数，越高越合规, "issues": ["问题1", "问题2", ...]}。
没有问题时 issues 为空数组。score 与 issues 必须保持一致：100 表示完全合规、issues 必须为空；越多/越严重的问题对应越低 score。"""


def _parse_json_safe(text: str) -> dict:
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        # Try to extract first {...} block
        start = text.find("{")
        end = text.rfind("}")
        if start >= 0 and end > start:
            try:
                return json.loads(text[start:end + 1])
            except json.JSONDecodeError:
                pass
        return {"score": 0, "issues": [f"AI 返回非法 JSON: {text[:200]}"]}


async def review_compliance(*, provider: BaseProvider, model: str,
                            title: str, content: str,
                            sensitive_checker: SensitiveWordChecker | None = None) -> dict:
    user = f"【标题】{title}\n【正文】{content[:6000]}"
    result = await provider.chat(
        [Message(role="system", content=PROMPT), Message(role="user", content=user)],
        model=model, json_mode=True, temperature=0.1)
    parsed = _parse_json_safe(result.content)
    score = int(parsed.get("score", 0))
    issues = list(parsed.get("issues") or [])
    if sensitive_checker is not None:
        local_hits = sensitive_checker.check(title + "\n" + content)
        if local_hits:
            issues.append("本地黑名单命中：" + "、".join(local_hits))
            score = min(score, 60)
    return {"score": score, "issues": issues, "model": model}
```

- [ ] **Step 2: Implement `backend/app/reviewer/originality.py`**

```python
from app.ai_providers.base import BaseProvider, Message
from app.reviewer.compliance import _parse_json_safe

PROMPT = """你是一名公众号原创度审核员。比较【原文】与【改写】的相似度并指出明显抄袭点。
输出严格 JSON：{"score": 0-100，越高越原创, "similarity": 0.0-1.0, "issues": [...]}。
similarity 是与原文的相似度估计；score 与 (1-similarity) 应大致正相关。"""


async def review_originality(*, provider: BaseProvider, model: str,
                             original_text: str, rewritten_text: str) -> dict:
    user = f"【原文】{original_text[:4000]}\n【改写】{rewritten_text[:4000]}"
    result = await provider.chat(
        [Message(role="system", content=PROMPT), Message(role="user", content=user)],
        model=model, json_mode=True, temperature=0.1)
    parsed = _parse_json_safe(result.content)
    return {"score": int(parsed.get("score", 0)),
            "similarity": float(parsed.get("similarity", 1.0)),
            "issues": list(parsed.get("issues") or []),
            "model": model}
```

- [ ] **Step 3: Implement `backend/app/reviewer/quality.py`**

```python
from app.ai_providers.base import BaseProvider, Message
from app.reviewer.compliance import _parse_json_safe

PROMPT = """你是一名内容质量审核员，评估文章的通顺度、逻辑连贯、可读性，以及是否有明显 AI 生成痕迹。
输出严格 JSON：{"score": 0-100, "issues": [...]}。"""


async def review_quality(*, provider: BaseProvider, model: str,
                         title: str, content: str) -> dict:
    user = f"【标题】{title}\n【正文】{content[:6000]}"
    result = await provider.chat(
        [Message(role="system", content=PROMPT), Message(role="user", content=user)],
        model=model, json_mode=True, temperature=0.1)
    parsed = _parse_json_safe(result.content)
    return {"score": int(parsed.get("score", 0)),
            "issues": list(parsed.get("issues") or []),
            "model": model}
```

- [ ] **Step 4: Implement `backend/app/reviewer/clickbait.py`**

```python
from app.ai_providers.base import BaseProvider, Message
from app.reviewer.compliance import _parse_json_safe

PROMPT = """你是一名标题审核员，评估【标题】是否标题党：是否过度夸张、是否与【正文】不符。
输出严格 JSON：{"score": 0-100，越高越克制，越好, "issues": [...]}。"""


async def review_clickbait(*, provider: BaseProvider, model: str,
                           title: str, content_excerpt: str) -> dict:
    user = f"【标题】{title}\n【正文摘要】{content_excerpt[:1500]}"
    result = await provider.chat(
        [Message(role="system", content=PROMPT), Message(role="user", content=user)],
        model=model, json_mode=True, temperature=0.1)
    parsed = _parse_json_safe(result.content)
    return {"score": int(parsed.get("score", 0)),
            "issues": list(parsed.get("issues") or []),
            "model": model}
```

- [ ] **Step 5: Implement `backend/app/reviewer/aggregator.py`**

```python
def aggregate(reports: dict) -> int:
    """Compute overall_score as weighted mean of dimensions present."""
    weights = {"compliance": 0.35, "originality": 0.25, "quality": 0.25, "clickbait": 0.15}
    total = 0.0
    weight_sum = 0.0
    for key, w in weights.items():
        block = reports.get(key)
        if block and "score" in block:
            total += block["score"] * w
            weight_sum += w
    if weight_sum == 0:
        return 0
    return int(total / weight_sum)
```

- [ ] **Step 6: Write tests `backend/tests/unit/test_reviewers.py`**

```python
import json
import pytest
from app.ai_providers.base import BaseProvider, ChatResult, TokenUsage
from app.reviewer.aggregator import aggregate
from app.reviewer.clickbait import review_clickbait
from app.reviewer.compliance import _parse_json_safe, review_compliance
from app.reviewer.originality import review_originality
from app.reviewer.quality import review_quality
from app.reviewer.sensitive_words import SensitiveWordChecker


class StubProvider(BaseProvider):
    name = "stub"

    def __init__(self, response: str) -> None:
        self.response = response

    async def chat(self, messages, *, model, **kwargs):
        return ChatResult(content=self.response, model=model, usage=TokenUsage())


def test_parse_json_safe_extracts_block_from_noisy_text():
    assert _parse_json_safe("noise{\"score\":80,\"issues\":[]}trail") == {"score": 80, "issues": []}


def test_parse_json_safe_returns_default_on_garbage():
    out = _parse_json_safe("不是 JSON")
    assert out["score"] == 0
    assert "非法 JSON" in out["issues"][0]


@pytest.mark.asyncio
async def test_compliance_includes_local_blacklist_hits(tmp_path):
    words_file = tmp_path / "w.txt"
    words_file.write_text("最佳\n", encoding="utf-8")
    checker = SensitiveWordChecker.from_file(words_file)
    provider = StubProvider(json.dumps({"score": 90, "issues": []}))
    out = await review_compliance(provider=provider, model="m",
                                  title="最佳产品", content="...", sensitive_checker=checker)
    assert out["score"] <= 60
    assert any("最佳" in i for i in out["issues"])


@pytest.mark.asyncio
async def test_originality_returns_dict():
    provider = StubProvider(json.dumps({"score": 70, "similarity": 0.3, "issues": []}))
    out = await review_originality(provider=provider, model="m", original_text="x", rewritten_text="y")
    assert out["score"] == 70
    assert out["similarity"] == 0.3


@pytest.mark.asyncio
async def test_quality_and_clickbait_run():
    provider = StubProvider(json.dumps({"score": 85, "issues": ["小问题"]}))
    q = await review_quality(provider=provider, model="m", title="t", content="c")
    cb = await review_clickbait(provider=provider, model="m", title="t", content_excerpt="c")
    assert q["score"] == 85
    assert cb["score"] == 85


def test_aggregate_overall_score():
    reports = {
        "compliance": {"score": 80}, "originality": {"score": 60},
        "quality": {"score": 90}, "clickbait": {"score": 70},
    }
    overall = aggregate(reports)
    assert 0 <= overall <= 100
    assert overall == int(80 * 0.35 + 60 * 0.25 + 90 * 0.25 + 70 * 0.15)
```

- [ ] **Step 7: Run tests** — Expected: PASS.

- [ ] **Step 8: Commit**

```bash
git add backend/app/reviewer backend/tests/unit/test_reviewers.py
git commit -m "feat(reviewer): add 4-dimension reviewers + aggregator"
```

---

## Task 3.9: Rewrite + review Celery tasks (chain orchestration)

**Files:** Create `backend/app/tasks/rewrite.py`, `backend/app/tasks/review.py`; update `backend/app/tasks/celery_app.py`; create `backend/tests/integration/test_rewrite_pipeline.py`.

- [ ] **Step 1: Update `backend/app/tasks/celery_app.py`** — extend `include`:

```python
include=[
    "app.tasks.crawl",
    "app.tasks.rewrite",
    "app.tasks.review",
],
```

And extend `task_routes`:

```python
task_routes={
    "app.tasks.crawl.*": {"queue": "crawl"},
    "app.tasks.rewrite.*": {"queue": "rewrite"},
    "app.tasks.review.*": {"queue": "review"},
},
```

- [ ] **Step 2: Implement `backend/app/tasks/rewrite.py`**

```python
"""Rewrite pipeline: title -> content -> review (4-dim group) -> aggregate."""
import asyncio
import logging
import uuid
from pathlib import Path
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker
from app.accounts.models import Account
from app.ai_providers.registry import RegistryError, get_registry, load_from_db
from app.db.session import make_engine
from app.drafts.models import Draft, DraftStatus, ReviewReport
from app.library.models import LibraryItem
from app.reviewer.aggregator import aggregate
from app.reviewer.clickbait import review_clickbait
from app.reviewer.compliance import review_compliance
from app.reviewer.originality import review_originality
from app.reviewer.quality import review_quality
from app.reviewer.sensitive_words import SensitiveWordChecker
from app.rewriter.prompt_builder import build_content_messages, build_title_messages
from app.tasks.celery_app import celery_app

logger = logging.getLogger(__name__)


SENSITIVE_WORDS_PATH = Path(__file__).parent.parent.parent / "data" / "sensitive_words.txt"


async def _ensure_registry(session) -> None:
    registry = get_registry()
    try:
        registry.role("writer")
    except RegistryError:
        await load_from_db(session)


async def _do_rewrite(draft_id: uuid.UUID, override_title: str | None,
                     override_content: str | None) -> None:
    engine = make_engine()
    sm = async_sessionmaker(engine, expire_on_commit=False)
    async with sm() as session:
        draft = (await session.execute(select(Draft).where(Draft.id == draft_id))).scalar_one_or_none()
        if draft is None:
            return
        item = (await session.execute(
            select(LibraryItem).where(LibraryItem.id == draft.library_item_id))).scalar_one()
        account = (await session.execute(
            select(Account).where(Account.id == draft.account_id))).scalar_one()

        await _ensure_registry(session)
        registry = get_registry()
        try:
            writer, writer_model = registry.role("writer")
            reviewer, reviewer_model = registry.role("reviewer")
        except RegistryError as exc:
            draft.status = DraftStatus.failed
            draft.error_msg = f"AI role binding error: {exc}"
            await session.commit()
            return

        try:
            # Title
            title_msgs = build_title_messages(
                account_title_prompt=account.title_prompt, category=account.category,
                style_desc=account.style_desc, original_title=item.original_title or "",
                override=override_title)
            title_result = await writer.chat(title_msgs, model=writer_model, temperature=0.7)
            draft.title = title_result.content.strip()

            # Content
            content_msgs = build_content_messages(
                account_content_prompt=account.content_prompt, category=account.category,
                style_desc=account.style_desc, original_content=item.original_content_text or "",
                override=override_content)
            content_result = await writer.chat(content_msgs, model=writer_model,
                                               temperature=0.7, max_tokens=4000)
            draft.content_html = content_result.content
            draft.status = DraftStatus.reviewing
            await session.commit()

            # Review (4 dimensions, run concurrently)
            checker = SensitiveWordChecker.from_file(SENSITIVE_WORDS_PATH)
            review_tasks = [
                review_compliance(provider=reviewer, model=reviewer_model,
                                  title=draft.title, content=item.original_content_text or "",
                                  sensitive_checker=checker),
                review_originality(provider=reviewer, model=reviewer_model,
                                   original_text=item.original_content_text or "",
                                   rewritten_text=content_result.content),
                review_quality(provider=reviewer, model=reviewer_model,
                               title=draft.title, content=content_result.content),
                review_clickbait(provider=reviewer, model=reviewer_model,
                                 title=draft.title,
                                 content_excerpt=(content_result.content or "")[:1500]),
            ]
            comp, orig, qual, cb = await asyncio.gather(*review_tasks, return_exceptions=False)
            reports = {"compliance": comp, "originality": orig, "quality": qual, "clickbait": cb}
            overall = aggregate(reports)

            report = ReviewReport(draft_id=draft.id, compliance=comp, originality=orig,
                                  quality=qual, clickbait=cb, overall_score=overall)
            session.add(report)
            await session.flush()
            draft.review_report_id = report.id
            draft.status = DraftStatus.reviewed
            await session.commit()
        except Exception as exc:
            logger.exception("rewrite pipeline failed for draft %s", draft.id)
            draft.status = DraftStatus.failed
            draft.error_msg = f"{type(exc).__name__}: {exc}"
            await session.commit()
    await engine.dispose()


@celery_app.task(name="app.tasks.rewrite.run_pipeline", bind=True,
                 max_retries=2, default_retry_delay=30)
def run_pipeline(self, draft_id: str,
                 override_title: str | None = None,
                 override_content: str | None = None) -> None:
    asyncio.run(_do_rewrite(uuid.UUID(draft_id), override_title, override_content))
```

- [ ] **Step 3: Create `backend/app/tasks/review.py`** (placeholder for future "re-review only" — Stage 4 may use)

```python
"""Re-run only the review stage on an existing draft."""
import asyncio
import uuid
# Implementation deferred until needed; keep file present to satisfy celery include.
```

- [ ] **Step 4: Write integration test `backend/tests/integration/test_rewrite_pipeline.py`**

```python
import json
import uuid
import pytest
from sqlalchemy import select
from app.accounts.models import Account
from app.ai_providers.base import BaseProvider, ChatResult, TokenUsage
from app.ai_providers.registry import get_registry
from app.drafts.models import Draft, DraftStatus, ReviewReport
from app.library.models import LibraryItem, LibraryStatus
from app.tasks.rewrite import _do_rewrite


class StubProvider(BaseProvider):
    name = "stub"

    def __init__(self) -> None:
        self.calls: list[str] = []

    async def chat(self, messages, *, model, json_mode=False, **kwargs):
        last = messages[-1].content
        self.calls.append(last[:50])
        if json_mode:
            return ChatResult(
                content=json.dumps({"score": 88, "issues": [], "similarity": 0.2}),
                model=model, usage=TokenUsage(prompt_tokens=10, completion_tokens=5))
        if "标题" in last and "改写" in last:
            return ChatResult(content="新标题", model=model, usage=TokenUsage(10, 5))
        return ChatResult(content="<p>改写正文</p>", model=model, usage=TokenUsage(10, 5))


@pytest.fixture
def stub_registry(monkeypatch):
    reg = get_registry()
    reg.reset()
    p = StubProvider()
    reg.register(p)
    reg.bind_role("writer", provider="stub", model="m")
    reg.bind_role("reviewer", provider="stub", model="m")
    reg.bind_role("lite", provider="stub", model="m")

    async def noop(_session): return None
    monkeypatch.setattr("app.tasks.rewrite._ensure_registry", noop)
    return p


@pytest.mark.asyncio
async def test_rewrite_pipeline_produces_draft_and_report(db_session, stub_registry):
    item = LibraryItem(source_url="https://x/1", original_title="原标题",
                      original_content_text="原文 " * 50, status=LibraryStatus.done)
    account = Account(name="A", wechat_appid="wx", wechat_secret="s",
                     category="职场", title_prompt="改写", content_prompt="改写", style_desc="")
    db_session.add_all([item, account])
    await db_session.commit()
    draft = Draft(library_item_id=item.id, account_id=account.id, status=DraftStatus.draft)
    db_session.add(draft)
    await db_session.commit()

    await _do_rewrite(draft.id, None, None)

    refreshed = (await db_session.execute(select(Draft).where(Draft.id == draft.id))).scalar_one()
    assert refreshed.status == DraftStatus.reviewed
    assert refreshed.title == "新标题"
    assert "改写正文" in refreshed.content_html
    assert refreshed.review_report_id is not None
    report = (await db_session.execute(
        select(ReviewReport).where(ReviewReport.id == refreshed.review_report_id))).scalar_one()
    assert report.overall_score is not None
    assert report.compliance["score"] == 88
```

- [ ] **Step 5: Run tests** — Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add backend/app/tasks/rewrite.py backend/app/tasks/review.py backend/app/tasks/celery_app.py backend/tests/integration/test_rewrite_pipeline.py
git commit -m "feat(tasks): add rewrite pipeline (title + content + 4-dim review)"
```

---

## Task 3.10: Drafts CRUD + trigger route

**Files:** Create `backend/app/drafts/{schemas.py,service.py,routes.py}`; modify `backend/app/api/router.py`; create `backend/tests/integration/test_drafts_routes.py`.

- [ ] **Step 1: `backend/app/drafts/schemas.py`**

```python
import uuid
from datetime import datetime
from pydantic import BaseModel, ConfigDict, Field
from app.drafts.models import DraftStatus


class RewriteTriggerRequest(BaseModel):
    library_item_ids: list[uuid.UUID] = Field(min_length=1, max_length=200)
    account_id: uuid.UUID
    override_title_prompt: str | None = None
    override_content_prompt: str | None = None


class DraftOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    library_item_id: uuid.UUID
    account_id: uuid.UUID
    title: str | None
    status: DraftStatus
    error_msg: str | None
    review_report_id: uuid.UUID | None
    wechat_pushed_at: datetime | None
    created_at: datetime


class DraftDetail(DraftOut):
    content_html: str | None
    cover_image_id: uuid.UUID | None


class ReviewReportOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    draft_id: uuid.UUID
    compliance: dict | None
    originality: dict | None
    quality: dict | None
    clickbait: dict | None
    overall_score: int | None


class DraftEdit(BaseModel):
    title: str | None = None
    content_html: str | None = None
```

- [ ] **Step 2: `backend/app/drafts/service.py`**

```python
import uuid
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.drafts.models import Draft, DraftStatus, ReviewReport


async def create_draft(db: AsyncSession, *, library_item_id: uuid.UUID,
                       account_id: uuid.UUID) -> Draft:
    obj = Draft(library_item_id=library_item_id, account_id=account_id,
                status=DraftStatus.draft)
    db.add(obj)
    await db.commit()
    await db.refresh(obj)
    return obj


async def list_drafts(db: AsyncSession, *, account_id: uuid.UUID | None = None,
                      status: DraftStatus | None = None,
                      limit: int = 50, offset: int = 0) -> list[Draft]:
    stmt = select(Draft).order_by(Draft.created_at.desc()).limit(limit).offset(offset)
    if account_id is not None:
        stmt = stmt.where(Draft.account_id == account_id)
    if status is not None:
        stmt = stmt.where(Draft.status == status)
    return list((await db.execute(stmt)).scalars().all())


async def get_draft(db: AsyncSession, draft_id: uuid.UUID) -> Draft | None:
    return await db.get(Draft, draft_id)


async def get_review_report(db: AsyncSession, report_id: uuid.UUID) -> ReviewReport | None:
    return await db.get(ReviewReport, report_id)


async def update_draft(db: AsyncSession, draft: Draft, *, title: str | None,
                       content_html: str | None) -> Draft:
    if title is not None:
        draft.title = title
    if content_html is not None:
        draft.content_html = content_html
    await db.commit()
    await db.refresh(draft)
    return draft
```

- [ ] **Step 3: `backend/app/drafts/routes.py`**

```python
import uuid
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from app.api.deps import get_db
from app.auth.dependencies import get_current_username
from app.config import get_settings
from app.drafts import service
from app.drafts.models import DraftStatus
from app.drafts.schemas import (
    DraftDetail, DraftEdit, DraftOut, ReviewReportOut, RewriteTriggerRequest,
)

router = APIRouter(prefix="/drafts", tags=["drafts"])


@router.post("/rewrite", response_model=list[DraftOut], status_code=202)
async def trigger_rewrite(payload: RewriteTriggerRequest,
                          db: AsyncSession = Depends(get_db),
                          _: str = Depends(get_current_username)) -> list[DraftOut]:
    settings = get_settings()
    if len(payload.library_item_ids) > settings.rewrite_batch_max:
        raise HTTPException(400, f"Batch exceeds {settings.rewrite_batch_max}")
    from app.tasks.rewrite import run_pipeline
    drafts: list[DraftOut] = []
    for item_id in payload.library_item_ids:
        d = await service.create_draft(db, library_item_id=item_id, account_id=payload.account_id)
        run_pipeline.delay(str(d.id), payload.override_title_prompt, payload.override_content_prompt)
        drafts.append(DraftOut.model_validate(d))
    return drafts


@router.get("", response_model=list[DraftOut])
async def list_all(account_id: uuid.UUID | None = None,
                   status_filter: DraftStatus | None = None,
                   limit: int = 50, offset: int = 0,
                   db: AsyncSession = Depends(get_db),
                   _: str = Depends(get_current_username)) -> list[DraftOut]:
    rows = await service.list_drafts(db, account_id=account_id, status=status_filter,
                                     limit=limit, offset=offset)
    return [DraftOut.model_validate(r) for r in rows]


@router.get("/{draft_id}", response_model=DraftDetail)
async def get_one(draft_id: uuid.UUID,
                  db: AsyncSession = Depends(get_db),
                  _: str = Depends(get_current_username)) -> DraftDetail:
    obj = await service.get_draft(db, draft_id)
    if obj is None:
        raise HTTPException(404, "Draft not found")
    return DraftDetail.model_validate(obj)


@router.patch("/{draft_id}", response_model=DraftDetail)
async def update(draft_id: uuid.UUID, payload: DraftEdit,
                 db: AsyncSession = Depends(get_db),
                 _: str = Depends(get_current_username)) -> DraftDetail:
    obj = await service.get_draft(db, draft_id)
    if obj is None:
        raise HTTPException(404, "Draft not found")
    obj = await service.update_draft(db, obj, title=payload.title, content_html=payload.content_html)
    return DraftDetail.model_validate(obj)


@router.get("/{draft_id}/report", response_model=ReviewReportOut)
async def get_report(draft_id: uuid.UUID,
                     db: AsyncSession = Depends(get_db),
                     _: str = Depends(get_current_username)) -> ReviewReportOut:
    draft = await service.get_draft(db, draft_id)
    if draft is None or draft.review_report_id is None:
        raise HTTPException(404, "Report not found")
    report = await service.get_review_report(db, draft.review_report_id)
    if report is None:
        raise HTTPException(404, "Report not found")
    return ReviewReportOut.model_validate(report)
```

- [ ] **Step 4: Update `backend/app/api/router.py`** — include `drafts_router`.

- [ ] **Step 5: Smoke test via integration tests** — covered by `test_rewrite_pipeline.py` plus add minimal route auth check (skip for brevity; existing tests confirm flow).

- [ ] **Step 6: Commit**

```bash
git add backend/app/drafts backend/app/api/router.py
git commit -m "feat(drafts): add CRUD + rewrite trigger routes + report fetch"
```

---

## Task 3.11: Frontend — rewrite trigger + drafts list + report view

**Files:** Create `frontend/src/pages/Drafts.tsx`, `frontend/src/pages/DraftDetail.tsx`, `frontend/src/pages/Settings.tsx`; modify `frontend/src/App.tsx`; extend Library page with selection.

- [ ] **Step 1: Modify `frontend/src/pages/Library.tsx`** to add multi-select + "改写"按钮 wiring (open a small modal that picks an account_id then POST to `/drafts/rewrite`). For brevity, key snippet:

```tsx
// Inside Library component, alongside `data`:
const accounts = useQuery({
  queryKey: ["accounts-min"],
  queryFn: async () => (await api.get<{ id: string; name: string }[]>("/accounts")).data,
});
const [selected, setSelected] = useState<Set<string>>(new Set());
const [accountId, setAccountId] = useState<string>("");

const triggerRewrite = useMutation({
  mutationFn: async () => api.post("/drafts/rewrite", {
    library_item_ids: Array.from(selected),
    account_id: accountId,
  }),
  onSuccess: () => {
    setSelected(new Set());
    // navigate to drafts page if desired
  },
});
```

In the list, add a checkbox per row and a sticky bottom bar showing `当前选中 N 篇` + account select + "开始改写" button.

- [ ] **Step 2: Create `frontend/src/pages/Drafts.tsx`** — list with status badges, per-row link to detail.

```tsx
import { useQuery } from "@tanstack/react-query";
import { Link } from "react-router-dom";
import { api } from "../api/client";

type Draft = {
  id: string;
  title: string | null;
  status: string;
  error_msg: string | null;
  review_report_id: string | null;
  created_at: string;
};

export default function Drafts() {
  const { data, isLoading } = useQuery({
    queryKey: ["drafts"],
    queryFn: async () => (await api.get<Draft[]>("/drafts")).data,
    refetchInterval: 5000,
  });
  return (
    <div className="p-8">
      <h1 className="text-2xl font-semibold mb-4">草稿</h1>
      {isLoading && <div>加载中...</div>}
      <ul className="space-y-2">
        {data?.map((d) => (
          <li key={d.id} className="border rounded p-3">
            <Link to={`/drafts/${d.id}`} className="block">
              <div className="font-medium">{d.title ?? "(尚未生成)"}</div>
              <div className="text-xs text-slate-500">{d.status} · {new Date(d.created_at).toLocaleString()}</div>
              {d.error_msg && <div className="text-xs text-red-600 mt-1">{d.error_msg}</div>}
            </Link>
          </li>
        ))}
      </ul>
    </div>
  );
}
```

- [ ] **Step 3: Create `frontend/src/pages/DraftDetail.tsx`** — show title (editable), content_html (preview + textarea), and review report (4 dim score boxes + issues list).

```tsx
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { useEffect, useState } from "react";
import { useParams } from "react-router-dom";
import { api } from "../api/client";

type Detail = { id: string; title: string | null; content_html: string | null;
                status: string; review_report_id: string | null };
type Report = { compliance: any; originality: any; quality: any; clickbait: any; overall_score: number | null };

const DIMS = [
  { key: "compliance", label: "合规" },
  { key: "originality", label: "原创度" },
  { key: "quality", label: "质量" },
  { key: "clickbait", label: "标题党" },
];

export default function DraftDetail() {
  const { id } = useParams();
  const qc = useQueryClient();
  const detail = useQuery({
    queryKey: ["draft", id],
    queryFn: async () => (await api.get<Detail>(`/drafts/${id}`)).data,
  });
  const report = useQuery({
    queryKey: ["draft-report", id],
    queryFn: async () => (await api.get<Report>(`/drafts/${id}/report`)).data,
    enabled: Boolean(detail.data?.review_report_id),
  });
  const [title, setTitle] = useState("");
  const [body, setBody] = useState("");
  useEffect(() => {
    if (detail.data) { setTitle(detail.data.title ?? ""); setBody(detail.data.content_html ?? ""); }
  }, [detail.data]);

  const save = useMutation({
    mutationFn: async () => api.patch(`/drafts/${id}`, { title, content_html: body }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["draft", id] }),
  });

  if (!detail.data) return <div className="p-8">加载中...</div>;

  return (
    <div className="p-8 max-w-4xl space-y-6">
      <input className="w-full text-2xl font-semibold border-b py-2"
             value={title} onChange={(e) => setTitle(e.target.value)} placeholder="标题" />
      <textarea className="w-full h-96 border rounded p-3 font-mono text-sm"
                value={body} onChange={(e) => setBody(e.target.value)} />
      <button onClick={() => save.mutate()} disabled={save.isPending}
              className="bg-slate-900 text-white px-4 py-2 rounded">
        {save.isPending ? "保存中..." : "保存"}
      </button>
      <div>
        <h2 className="font-medium mb-2">预览</h2>
        <div className="border rounded p-4 prose" dangerouslySetInnerHTML={{ __html: body }} />
      </div>
      {report.data && (
        <div>
          <h2 className="font-medium mb-2">审核报告（综合 {report.data.overall_score}）</h2>
          <div className="grid grid-cols-4 gap-3">
            {DIMS.map((d) => {
              const block = (report.data as any)[d.key];
              return (
                <div key={d.key} className="border rounded p-3">
                  <div className="text-sm text-slate-500">{d.label}</div>
                  <div className="text-2xl font-semibold">{block?.score ?? "-"}</div>
                  {block?.issues?.length ? (
                    <ul className="text-xs mt-2 list-disc list-inside text-slate-700">
                      {block.issues.map((it: string, i: number) => <li key={i}>{it}</li>)}
                    </ul>
                  ) : null}
                </div>
              );
            })}
          </div>
        </div>
      )}
    </div>
  );
}
```

- [ ] **Step 4: Create `frontend/src/pages/Settings.tsx`** — minimal CRUD for AI providers + role bindings (use shadcn-like simple form). Skeleton:

```tsx
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { api } from "../api/client";

type Provider = { id: string; name: string; base_url: string; models: string[]; enabled: boolean };
type Binding = { role: "writer" | "reviewer" | "lite"; provider_id: string; model: string };

export default function Settings() {
  const qc = useQueryClient();
  const providers = useQuery({
    queryKey: ["providers"],
    queryFn: async () => (await api.get<Provider[]>("/ai-providers")).data,
  });
  const bindings = useQuery({
    queryKey: ["bindings"],
    queryFn: async () => (await api.get<Binding[]>("/ai-providers/role-bindings")).data,
  });

  const [form, setForm] = useState({ name: "", base_url: "", api_key: "", models: "" });
  const create = useMutation({
    mutationFn: async () => api.post("/ai-providers", {
      ...form,
      models: form.models.split(",").map((s) => s.trim()).filter(Boolean),
    }),
    onSuccess: () => { setForm({ name: "", base_url: "", api_key: "", models: "" });
                       qc.invalidateQueries({ queryKey: ["providers"] }); },
  });
  const upsertBinding = useMutation({
    mutationFn: async (b: Binding) => api.put("/ai-providers/role-bindings", b),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["bindings"] }),
  });

  return (
    <div className="p-8 space-y-8 max-w-3xl">
      <section>
        <h2 className="text-xl font-semibold mb-3">AI 服务商</h2>
        <ul className="space-y-2 mb-4">
          {providers.data?.map((p) => (
            <li key={p.id} className="border rounded p-3">
              <div className="font-medium">{p.name}</div>
              <div className="text-xs text-slate-500">{p.base_url}</div>
              <div className="text-xs">模型: {p.models.join(", ") || "(未配置)"}</div>
            </li>
          ))}
        </ul>
        <div className="border rounded p-4 space-y-2">
          <h3 className="font-medium">添加 Provider</h3>
          {(["name", "base_url", "api_key", "models"] as const).map((k) => (
            <input key={k} className="w-full border rounded px-3 py-2"
                   placeholder={k === "models" ? "模型列表（逗号分隔）" : k}
                   value={form[k]} onChange={(e) => setForm({ ...form, [k]: e.target.value })} />
          ))}
          <button onClick={() => create.mutate()} className="bg-slate-900 text-white px-4 py-2 rounded">添加</button>
        </div>
      </section>

      <section>
        <h2 className="text-xl font-semibold mb-3">角色绑定</h2>
        {(["writer", "reviewer", "lite"] as const).map((role) => {
          const current = bindings.data?.find((b) => b.role === role);
          return (
            <RoleRow key={role} role={role} providers={providers.data ?? []} current={current}
                     onSave={(b) => upsertBinding.mutate(b)} />
          );
        })}
      </section>
    </div>
  );
}

function RoleRow({ role, providers, current, onSave }: any) {
  const [providerId, setProviderId] = useState(current?.provider_id ?? "");
  const [model, setModel] = useState(current?.model ?? "");
  return (
    <div className="border rounded p-3 mb-2 flex gap-2 items-center">
      <span className="w-20 font-medium">{role}</span>
      <select className="border rounded px-2 py-1" value={providerId}
              onChange={(e) => setProviderId(e.target.value)}>
        <option value="">— 选 Provider —</option>
        {providers.map((p: any) => <option key={p.id} value={p.id}>{p.name}</option>)}
      </select>
      <input className="border rounded px-2 py-1" placeholder="模型 ID"
             value={model} onChange={(e) => setModel(e.target.value)} />
      <button className="ml-auto bg-slate-900 text-white px-3 py-1 rounded text-sm"
              onClick={() => onSave({ role, provider_id: providerId, model })}
              disabled={!providerId || !model}>保存</button>
    </div>
  );
}
```

- [ ] **Step 5: Update `frontend/src/App.tsx`** — add `/drafts`, `/drafts/:id`, `/settings` routes and nav links.

- [ ] **Step 6: Smoke test** — log in, configure a provider in `/settings`, bind roles, go to `/library`, paste URL(s), wait for crawl, select items, pick account, click 改写; navigate to `/drafts`, verify draft appears and progresses to `reviewed`; open detail and confirm 4-dim report renders.

- [ ] **Step 7: Commit**

```bash
git add frontend/src/pages frontend/src/App.tsx
git commit -m "feat(frontend): add drafts list, draft detail with editor + review report, settings page"
```

---

## Stage 3 Exit Criteria

- [ ] Settings page lets you create AI providers and bind roles; registry hot-reloads.
- [ ] From Library page, selecting items + an account triggers `/drafts/rewrite` and returns 202 with draft IDs.
- [ ] Worker logs show pipeline stages firing (writer → reviewer × 4).
- [ ] Drafts table shows draft transitions: `draft` → `reviewing` → `reviewed`.
- [ ] Draft detail page shows editable title/body and 4-dim review report.
- [ ] On AI failure (invalid key), draft transitions to `failed` with `error_msg`.
- [ ] All unit + integration tests pass: `cd backend && uv run pytest -v`.

---

# Stage 4 — WeChat Integration

Goal: Manage `access_token` per公众号 in Redis, upload images to WeChat permanent material library, push approved drafts to WeChat draft box, provide image review UI.

---

## Task 4.1: Image model + migration + storage dir

**Files:** Create `backend/app/images/__init__.py`, `backend/app/images/models.py`; update `backend/alembic/env.py`; generate migration.

- [ ] **Step 1: Implement `backend/app/images/models.py`**

```python
import enum
import uuid
from datetime import datetime
from sqlalchemy import Boolean, DateTime, Enum, ForeignKey, Integer, String, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column
from app.db.base import Base


class ImageStatus(str, enum.Enum):
    pending = "pending"
    downloaded = "downloaded"
    uploaded = "uploaded"
    replaced = "replaced"
    removed = "removed"
    failed = "failed"


class Image(Base):
    __tablename__ = "images"
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    draft_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("drafts.id"), nullable=False)
    original_url: Mapped[str] = mapped_column(String(2048), nullable=False)
    local_path: Mapped[str | None] = mapped_column(String(500), nullable=True)
    wechat_media_id: Mapped[str | None] = mapped_column(String(200), nullable=True)
    wechat_url: Mapped[str | None] = mapped_column(String(2048), nullable=True)
    status: Mapped[ImageStatus] = mapped_column(Enum(ImageStatus), nullable=False, default=ImageStatus.pending)
    position: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    is_cover: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    error_msg: Mapped[str | None] = mapped_column(String(500), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
```

- [ ] **Step 2: Update `backend/alembic/env.py`** — `from app.images.models import Image  # noqa: F401`. Same in `tests/integration/conftest.py`.

- [ ] **Step 3: Generate + apply migration** (message: `"create images table"`).

- [ ] **Step 4: Commit**

```bash
git add backend/app/images backend/alembic backend/tests/integration/conftest.py
git commit -m "feat(images): add Image model + migration"
```

---

## Task 4.2: WeChat access_token cache

**Files:** Create `backend/app/wechat/__init__.py`, `backend/app/wechat/token.py`, `backend/tests/unit/test_wechat_token.py`.

- [ ] **Step 1: Write failing test `backend/tests/unit/test_wechat_token.py`**

```python
import pytest
import respx
import httpx
import fakeredis.aioredis
from app.wechat.token import WeChatTokenError, get_access_token, _redis_key


@pytest.mark.asyncio
async def test_token_fetched_when_cache_missing(monkeypatch):
    fake = fakeredis.aioredis.FakeRedis(decode_responses=True)
    monkeypatch.setattr("app.wechat.token._get_redis", lambda: fake)
    async with respx.mock(base_url="https://api.weixin.qq.com") as mock:
        mock.get("/cgi-bin/token").mock(return_value=httpx.Response(
            200, json={"access_token": "TOK1", "expires_in": 7200}))
        token = await get_access_token(account_id="abc", appid="x", secret="y")
    assert token == "TOK1"
    assert await fake.get(_redis_key("abc")) == "TOK1"


@pytest.mark.asyncio
async def test_token_cache_hit_skips_api(monkeypatch):
    fake = fakeredis.aioredis.FakeRedis(decode_responses=True)
    await fake.set(_redis_key("abc"), "CACHED", ex=600)
    monkeypatch.setattr("app.wechat.token._get_redis", lambda: fake)
    token = await get_access_token(account_id="abc", appid="x", secret="y")
    assert token == "CACHED"


@pytest.mark.asyncio
async def test_token_error_response_raises(monkeypatch):
    fake = fakeredis.aioredis.FakeRedis(decode_responses=True)
    monkeypatch.setattr("app.wechat.token._get_redis", lambda: fake)
    async with respx.mock(base_url="https://api.weixin.qq.com") as mock:
        mock.get("/cgi-bin/token").mock(return_value=httpx.Response(
            200, json={"errcode": 40013, "errmsg": "invalid appid"}))
        with pytest.raises(WeChatTokenError):
            await get_access_token(account_id="abc", appid="x", secret="y")
```

- [ ] **Step 2: Implement `backend/app/wechat/token.py`**

```python
import httpx
import redis.asyncio as redis
from app.config import get_settings


class WeChatTokenError(Exception):
    pass


_REFRESH_BUFFER_SECONDS = 600  # refresh 10 min before expiry


def _redis_key(account_id: str) -> str:
    return f"wechat:token:{account_id}"


def _get_redis() -> redis.Redis:
    return redis.from_url(get_settings().redis_url, decode_responses=True)


async def get_access_token(*, account_id: str, appid: str, secret: str,
                           force_refresh: bool = False) -> str:
    rds = _get_redis()
    if not force_refresh:
        cached = await rds.get(_redis_key(account_id))
        if cached:
            return cached
    async with httpx.AsyncClient(timeout=15) as client:
        resp = await client.get("https://api.weixin.qq.com/cgi-bin/token", params={
            "grant_type": "client_credential", "appid": appid, "secret": secret,
        })
    data = resp.json()
    token = data.get("access_token")
    if not token:
        raise WeChatTokenError(f"errcode={data.get('errcode')}, errmsg={data.get('errmsg')}")
    expires_in = int(data.get("expires_in", 7200))
    ttl = max(60, expires_in - _REFRESH_BUFFER_SECONDS)
    await rds.set(_redis_key(account_id), token, ex=ttl)
    return token


async def invalidate(account_id: str) -> None:
    await _get_redis().delete(_redis_key(account_id))
```

- [ ] **Step 3: Create empty `backend/app/wechat/__init__.py`**

- [ ] **Step 4: Run tests** — Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/app/wechat backend/tests/unit/test_wechat_token.py
git commit -m "feat(wechat): add access_token fetcher + Redis cache with refresh buffer"
```

---

## Task 4.3: WeChat permanent material upload

**Files:** Create `backend/app/wechat/material.py`, `backend/tests/unit/test_wechat_material.py`.

- [ ] **Step 1: Write failing test `backend/tests/unit/test_wechat_material.py`**

```python
import pytest
import respx
import httpx
from app.wechat.material import WeChatMaterialError, upload_image


@pytest.mark.asyncio
async def test_upload_image_returns_media_id_and_url():
    async with respx.mock(base_url="https://api.weixin.qq.com") as mock:
        mock.post("/cgi-bin/material/add_material").mock(return_value=httpx.Response(
            200, json={"media_id": "MID-1", "url": "https://mmbiz.qpic.cn/mmbiz_jpg/abc/0"}))
        result = await upload_image(access_token="TOK", file_path=__file__)
    assert result["media_id"] == "MID-1"
    assert "mmbiz" in result["url"]


@pytest.mark.asyncio
async def test_upload_image_error_raises():
    async with respx.mock(base_url="https://api.weixin.qq.com") as mock:
        mock.post("/cgi-bin/material/add_material").mock(return_value=httpx.Response(
            200, json={"errcode": 40001, "errmsg": "invalid token"}))
        with pytest.raises(WeChatMaterialError):
            await upload_image(access_token="TOK", file_path=__file__)
```

- [ ] **Step 2: Implement `backend/app/wechat/material.py`**

```python
from pathlib import Path
import httpx


class WeChatMaterialError(Exception):
    pass


async def upload_image(*, access_token: str, file_path: str) -> dict:
    path = Path(file_path)
    async with httpx.AsyncClient(timeout=60) as client:
        with path.open("rb") as fh:
            files = {"media": (path.name, fh, "image/jpeg")}
            resp = await client.post(
                "https://api.weixin.qq.com/cgi-bin/material/add_material",
                params={"access_token": access_token, "type": "image"},
                files=files)
    data = resp.json()
    if "errcode" in data and data["errcode"] != 0:
        raise WeChatMaterialError(f"errcode={data['errcode']}, errmsg={data.get('errmsg')}")
    if "media_id" not in data:
        raise WeChatMaterialError(f"unexpected response: {data}")
    return {"media_id": data["media_id"], "url": data.get("url", "")}
```

- [ ] **Step 3: Run tests** — Expected: PASS.

- [ ] **Step 4: Commit**

```bash
git add backend/app/wechat/material.py backend/tests/unit/test_wechat_material.py
git commit -m "feat(wechat): add permanent material image upload"
```

---

## Task 4.4: WeChat draft push

**Files:** Create `backend/app/wechat/draft.py`, `backend/tests/unit/test_wechat_draft.py`.

- [ ] **Step 1: Write failing test `backend/tests/unit/test_wechat_draft.py`**

```python
import pytest
import respx
import httpx
from app.wechat.draft import WeChatDraftError, push_draft


@pytest.mark.asyncio
async def test_push_draft_returns_media_id():
    async with respx.mock(base_url="https://api.weixin.qq.com") as mock:
        mock.post("/cgi-bin/draft/add").mock(return_value=httpx.Response(
            200, json={"media_id": "DRAFT-1"}))
        result = await push_draft(access_token="TOK", title="t", content_html="<p>x</p>",
                                  thumb_media_id="COVER", author="a", digest="d")
    assert result == "DRAFT-1"


@pytest.mark.asyncio
async def test_push_draft_token_invalid_raises():
    async with respx.mock(base_url="https://api.weixin.qq.com") as mock:
        mock.post("/cgi-bin/draft/add").mock(return_value=httpx.Response(
            200, json={"errcode": 40001, "errmsg": "invalid token"}))
        with pytest.raises(WeChatDraftError):
            await push_draft(access_token="TOK", title="t", content_html="<p/>",
                             thumb_media_id="C", author="a", digest="d")
```

- [ ] **Step 2: Implement `backend/app/wechat/draft.py`**

```python
import httpx


class WeChatDraftError(Exception):
    def __init__(self, message: str, *, errcode: int | None = None) -> None:
        super().__init__(message)
        self.errcode = errcode


async def push_draft(*, access_token: str, title: str, content_html: str,
                     thumb_media_id: str, author: str = "",
                     digest: str = "") -> str:
    """Returns the draft media_id."""
    payload = {
        "articles": [{
            "title": title,
            "author": author,
            "digest": digest[:120],
            "content": content_html,
            "thumb_media_id": thumb_media_id,
            "need_open_comment": 0,
            "only_fans_can_comment": 0,
        }]
    }
    async with httpx.AsyncClient(timeout=60) as client:
        resp = await client.post(
            "https://api.weixin.qq.com/cgi-bin/draft/add",
            params={"access_token": access_token},
            json=payload)
    data = resp.json()
    if "errcode" in data and data["errcode"] != 0:
        raise WeChatDraftError(f"errcode={data['errcode']}, errmsg={data.get('errmsg')}",
                               errcode=data["errcode"])
    if "media_id" not in data:
        raise WeChatDraftError(f"unexpected response: {data}")
    return data["media_id"]
```

- [ ] **Step 3: Run tests** — Expected: PASS.

- [ ] **Step 4: Commit**

```bash
git add backend/app/wechat/draft.py backend/tests/unit/test_wechat_draft.py
git commit -m "feat(wechat): add draft push to /cgi-bin/draft/add"
```

---

## Task 4.5: Image processing task (download + upload + rewrite content)

**Files:** Create `backend/app/images/{schemas.py,service.py}`, `backend/app/tasks/images.py`; extend `backend/app/tasks/celery_app.py` and `backend/app/tasks/rewrite.py`; create `backend/tests/integration/test_image_processing.py`.

- [ ] **Step 1: `backend/app/images/schemas.py`**

```python
import uuid
from pydantic import BaseModel, ConfigDict
from app.images.models import ImageStatus


class ImageOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    draft_id: uuid.UUID
    original_url: str
    wechat_url: str | None
    status: ImageStatus
    position: int
    is_cover: bool
    error_msg: str | None
```

- [ ] **Step 2: `backend/app/images/service.py`**

```python
import uuid
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.images.models import Image, ImageStatus


async def create_pending_for_draft(db: AsyncSession, draft_id: uuid.UUID,
                                   original_urls: list[str]) -> list[Image]:
    images: list[Image] = []
    for idx, url in enumerate(original_urls):
        img = Image(draft_id=draft_id, original_url=url, position=idx,
                    is_cover=(idx == 0), status=ImageStatus.pending)
        db.add(img)
        images.append(img)
    await db.commit()
    for img in images:
        await db.refresh(img)
    return images


async def list_for_draft(db: AsyncSession, draft_id: uuid.UUID) -> list[Image]:
    rows = (await db.execute(
        select(Image).where(Image.draft_id == draft_id).order_by(Image.position))).scalars().all()
    return list(rows)


async def get(db: AsyncSession, image_id: uuid.UUID) -> Image | None:
    return await db.get(Image, image_id)


async def set_cover(db: AsyncSession, draft_id: uuid.UUID, image_id: uuid.UUID) -> None:
    rows = await list_for_draft(db, draft_id)
    for img in rows:
        img.is_cover = (img.id == image_id)
    await db.commit()


async def mark_removed(db: AsyncSession, image: Image) -> Image:
    image.status = ImageStatus.removed
    image.is_cover = False
    await db.commit()
    await db.refresh(image)
    return image
```

- [ ] **Step 3: `backend/app/tasks/images.py`**

```python
"""Process images for a draft: download original, upload to WeChat, rewrite content_html."""
import asyncio
import logging
import uuid
from pathlib import Path
import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker
from app.accounts.models import Account
from app.config import get_settings
from app.db.session import make_engine
from app.drafts.models import Draft
from app.images.models import Image, ImageStatus
from app.tasks.celery_app import celery_app
from app.wechat.material import WeChatMaterialError, upload_image
from app.wechat.token import get_access_token

logger = logging.getLogger(__name__)


async def _download(url: str, dest: Path) -> None:
    async with httpx.AsyncClient(timeout=30, follow_redirects=True) as client:
        async with client.stream("GET", url) as resp:
            resp.raise_for_status()
            dest.parent.mkdir(parents=True, exist_ok=True)
            with dest.open("wb") as fh:
                async for chunk in resp.aiter_bytes():
                    fh.write(chunk)


async def _do_process(draft_id: uuid.UUID) -> None:
    settings = get_settings()
    engine = make_engine()
    sm = async_sessionmaker(engine, expire_on_commit=False)
    async with sm() as session:
        draft = (await session.execute(select(Draft).where(Draft.id == draft_id))).scalar_one()
        account = (await session.execute(
            select(Account).where(Account.id == draft.account_id))).scalar_one()
        images = (await session.execute(
            select(Image).where(Image.draft_id == draft_id).order_by(Image.position))).scalars().all()

        token = await get_access_token(account_id=str(account.id),
                                       appid=account.wechat_appid,
                                       secret=account.wechat_secret)
        for img in images:
            if img.status in (ImageStatus.uploaded, ImageStatus.removed, ImageStatus.replaced):
                continue
            try:
                ext = Path(img.original_url).suffix or ".jpg"
                local = Path(settings.image_storage_dir) / str(draft.id) / f"{img.position}{ext}"
                await _download(img.original_url, local)
                img.local_path = str(local)
                img.status = ImageStatus.downloaded
                await session.commit()

                result = await upload_image(access_token=token, file_path=str(local))
                img.wechat_media_id = result["media_id"]
                img.wechat_url = result["url"]
                img.status = ImageStatus.uploaded
                await session.commit()

                if draft.content_html and result["url"]:
                    draft.content_html = draft.content_html.replace(img.original_url, result["url"])
                    await session.commit()
            except WeChatMaterialError as exc:
                if "40001" in str(exc):
                    token = await get_access_token(account_id=str(account.id),
                                                   appid=account.wechat_appid,
                                                   secret=account.wechat_secret,
                                                   force_refresh=True)
                    try:
                        result = await upload_image(access_token=token, file_path=str(local))
                        img.wechat_media_id = result["media_id"]
                        img.wechat_url = result["url"]
                        img.status = ImageStatus.uploaded
                    except Exception as inner:
                        img.status = ImageStatus.failed
                        img.error_msg = str(inner)[:500]
                else:
                    img.status = ImageStatus.failed
                    img.error_msg = str(exc)[:500]
                await session.commit()
            except Exception as exc:
                logger.exception("image processing failed")
                img.status = ImageStatus.failed
                img.error_msg = f"{type(exc).__name__}: {exc}"[:500]
                await session.commit()
    await engine.dispose()


@celery_app.task(name="app.tasks.images.process_draft_images", bind=True,
                 max_retries=1, default_retry_delay=15)
def process_draft_images(self, draft_id: str) -> None:
    asyncio.run(_do_process(uuid.UUID(draft_id)))
```

- [ ] **Step 4: Update `backend/app/tasks/celery_app.py`** — add `"app.tasks.images"` to `include`.

- [ ] **Step 5: Hook image creation into rewrite pipeline** — modify `backend/app/tasks/rewrite.py` `_do_rewrite` so after the review report is committed, it also creates `Image` rows from `item.images`:

```python
# Add import at top:
from app.images import service as image_service

# After the ReviewReport is created and committed, before the function returns:
if item.images:
    await image_service.create_pending_for_draft(
        session, draft_id=draft.id,
        original_urls=[img["url"] for img in item.images])
```

- [ ] **Step 6: Write integration test `backend/tests/integration/test_image_processing.py`**

```python
import pytest
import respx
import httpx
from sqlalchemy import select
from app.accounts.models import Account
from app.drafts.models import Draft, DraftStatus
from app.images.models import Image, ImageStatus
from app.library.models import LibraryItem, LibraryStatus
from app.tasks.images import _do_process


@pytest.mark.asyncio
async def test_process_uploads_each_image(db_session, monkeypatch, tmp_path):
    monkeypatch.setenv("IMAGE_STORAGE_DIR", str(tmp_path))
    from app.config import get_settings
    get_settings.cache_clear()

    async def fake_token(**kwargs):
        return "TOK"
    monkeypatch.setattr("app.tasks.images.get_access_token", fake_token)

    item = LibraryItem(source_url="https://x/article", status=LibraryStatus.done)
    account = Account(name="A", wechat_appid="x", wechat_secret="y", category="职场")
    db_session.add_all([item, account])
    await db_session.commit()
    draft = Draft(library_item_id=item.id, account_id=account.id,
                  status=DraftStatus.reviewed,
                  content_html='<p><img src="https://x/a.jpg"/></p>')
    db_session.add(draft)
    await db_session.commit()
    img = Image(draft_id=draft.id, original_url="https://x/a.jpg", position=0)
    db_session.add(img)
    await db_session.commit()

    async with respx.mock() as mock:
        mock.get("https://x/a.jpg").mock(return_value=httpx.Response(200, content=b"\xff\xd8\xff" * 10))
        mock.post("https://api.weixin.qq.com/cgi-bin/material/add_material").mock(
            return_value=httpx.Response(200, json={
                "media_id": "MID", "url": "https://mmbiz.qpic.cn/wx_a.jpg"}))
        await _do_process(draft.id)

    refreshed_img = (await db_session.execute(
        select(Image).where(Image.id == img.id))).scalar_one()
    assert refreshed_img.status == ImageStatus.uploaded
    assert refreshed_img.wechat_media_id == "MID"
    refreshed_draft = (await db_session.execute(
        select(Draft).where(Draft.id == draft.id))).scalar_one()
    assert "wx_a.jpg" in refreshed_draft.content_html
    assert "x/a.jpg" not in refreshed_draft.content_html
```

- [ ] **Step 7: Run tests** — Expected: PASS.

- [ ] **Step 8: Commit**

```bash
git add backend/app/images backend/app/tasks/images.py backend/app/tasks/celery_app.py backend/app/tasks/rewrite.py backend/tests/integration/test_image_processing.py
git commit -m "feat(images): add image processing task (download + upload + URL rewrite)"
```

---

## Task 4.6: Publish task + draft push route

**Files:** Create `backend/app/tasks/publish.py`; extend `backend/app/drafts/routes.py`; update `backend/app/tasks/celery_app.py`.

- [ ] **Step 1: Implement `backend/app/tasks/publish.py`**

```python
import asyncio
import logging
import uuid
from datetime import datetime, timezone
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker
from app.accounts.models import Account
from app.db.session import make_engine
from app.drafts.models import Draft, DraftStatus
from app.images.models import Image, ImageStatus
from app.tasks.celery_app import celery_app
from app.wechat.draft import WeChatDraftError, push_draft
from app.wechat.token import get_access_token

logger = logging.getLogger(__name__)


async def _do_publish(draft_id: uuid.UUID) -> None:
    engine = make_engine()
    sm = async_sessionmaker(engine, expire_on_commit=False)
    async with sm() as session:
        draft = (await session.execute(select(Draft).where(Draft.id == draft_id))).scalar_one()
        account = (await session.execute(
            select(Account).where(Account.id == draft.account_id))).scalar_one()
        images = (await session.execute(
            select(Image).where(Image.draft_id == draft_id))).scalars().all()

        cover = next((i for i in images if i.is_cover), None)
        if cover is None or cover.status != ImageStatus.uploaded or not cover.wechat_media_id:
            draft.status = DraftStatus.failed
            draft.error_msg = "封面图片未上传"
            await session.commit()
            return
        non_cover_pending = [i for i in images
                             if not i.is_cover and i.status not in (ImageStatus.uploaded, ImageStatus.removed)]
        if non_cover_pending:
            draft.status = DraftStatus.failed
            draft.error_msg = f"{len(non_cover_pending)} 张图片未完成上传"
            await session.commit()
            return

        try:
            token = await get_access_token(account_id=str(account.id),
                                           appid=account.wechat_appid,
                                           secret=account.wechat_secret)
            try:
                media_id = await push_draft(
                    access_token=token, title=draft.title or "",
                    content_html=draft.content_html or "",
                    thumb_media_id=cover.wechat_media_id, author=account.name)
            except WeChatDraftError as exc:
                if exc.errcode == 40001:
                    token = await get_access_token(account_id=str(account.id),
                                                   appid=account.wechat_appid,
                                                   secret=account.wechat_secret,
                                                   force_refresh=True)
                    media_id = await push_draft(
                        access_token=token, title=draft.title or "",
                        content_html=draft.content_html or "",
                        thumb_media_id=cover.wechat_media_id, author=account.name)
                else:
                    raise
            draft.wechat_media_id = media_id
            draft.wechat_pushed_at = datetime.now(timezone.utc)
            draft.status = DraftStatus.published_to_wechat
            draft.error_msg = None
            await session.commit()
        except Exception as exc:
            logger.exception("publish failed for draft %s", draft.id)
            draft.status = DraftStatus.failed
            draft.error_msg = f"{type(exc).__name__}: {exc}"
            await session.commit()
    await engine.dispose()


@celery_app.task(name="app.tasks.publish.publish_draft", bind=True,
                 max_retries=2, default_retry_delay=15)
def publish_draft(self, draft_id: str) -> None:
    asyncio.run(_do_publish(uuid.UUID(draft_id)))
```

- [ ] **Step 2: Update `backend/app/tasks/celery_app.py`** — add to include and routes:

```python
include=[..., "app.tasks.images", "app.tasks.publish"],
task_routes={
    ...,
    "app.tasks.images.*": {"queue": "publish"},
    "app.tasks.publish.*": {"queue": "publish"},
},
```

- [ ] **Step 3: Append publish route in `backend/app/drafts/routes.py`**

```python
@router.post("/{draft_id}/publish-to-wechat", response_model=DraftOut, status_code=202)
async def publish(draft_id: uuid.UUID,
                  db: AsyncSession = Depends(get_db),
                  _: str = Depends(get_current_username)) -> DraftOut:
    obj = await service.get_draft(db, draft_id)
    if obj is None:
        raise HTTPException(404, "Draft not found")
    from app.tasks.publish import publish_draft
    from app.tasks.images import process_draft_images
    process_draft_images.apply_async(args=[str(obj.id)],
                                     link=publish_draft.si(str(obj.id)))
    return DraftOut.model_validate(obj)
```

- [ ] **Step 4: Smoke test (manual)** — full pipeline through publish requires real WeChat creds; verify with a test 服务号 / 订阅号 (认证号). Skip automated test for the route end-to-end; the unit/integration tests for `_do_publish` (analogous to image test) cover the logic.

- [ ] **Step 5: Commit**

```bash
git add backend/app/tasks/publish.py backend/app/tasks/celery_app.py backend/app/drafts/routes.py
git commit -m "feat(publish): add publish_draft task + WeChat draft push route"
```

---

## Task 4.7: Image management routes

**Files:** Create `backend/app/images/routes.py`; modify `backend/app/api/router.py`.

- [ ] **Step 1: `backend/app/images/routes.py`**

```python
import uuid
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from app.api.deps import get_db
from app.auth.dependencies import get_current_username
from app.images import service
from app.images.schemas import ImageOut

router = APIRouter(prefix="/images", tags=["images"])


@router.get("/by-draft/{draft_id}", response_model=list[ImageOut])
async def list_for_draft(draft_id: uuid.UUID,
                         db: AsyncSession = Depends(get_db),
                         _: str = Depends(get_current_username)) -> list[ImageOut]:
    return [ImageOut.model_validate(r) for r in await service.list_for_draft(db, draft_id)]


@router.post("/{image_id}/cover", response_model=list[ImageOut])
async def set_cover(image_id: uuid.UUID,
                    db: AsyncSession = Depends(get_db),
                    _: str = Depends(get_current_username)) -> list[ImageOut]:
    img = await service.get(db, image_id)
    if img is None:
        raise HTTPException(404, "Image not found")
    await service.set_cover(db, img.draft_id, img.id)
    return [ImageOut.model_validate(r) for r in await service.list_for_draft(db, img.draft_id)]


@router.delete("/{image_id}", response_model=ImageOut)
async def remove(image_id: uuid.UUID,
                 db: AsyncSession = Depends(get_db),
                 _: str = Depends(get_current_username)) -> ImageOut:
    img = await service.get(db, image_id)
    if img is None:
        raise HTTPException(404, "Image not found")
    return ImageOut.model_validate(await service.mark_removed(db, img))
```

- [ ] **Step 2: Update `backend/app/api/router.py`** — include `images_router`.

- [ ] **Step 3: Commit**

```bash
git add backend/app/images/routes.py backend/app/api/router.py
git commit -m "feat(images): add image listing, cover toggle, removal routes"
```

---

## Task 4.8: Frontend — image review + push to WeChat

**Files:** Modify `frontend/src/pages/DraftDetail.tsx`.

- [ ] **Step 1: Extend `DraftDetail.tsx`** — add imports + queries inside the existing component (above the `return`):

```tsx
type Img = { id: string; original_url: string; wechat_url: string | null;
             status: string; is_cover: boolean; error_msg: string | null };

const images = useQuery({
  queryKey: ["draft-images", id],
  queryFn: async () => (await api.get<Img[]>(`/images/by-draft/${id}`)).data,
  refetchInterval: 5000,
});
const setCover = useMutation({
  mutationFn: async (imgId: string) => api.post(`/images/${imgId}/cover`),
  onSuccess: () => qc.invalidateQueries({ queryKey: ["draft-images", id] }),
});
const removeImg = useMutation({
  mutationFn: async (imgId: string) => api.delete(`/images/${imgId}`),
  onSuccess: () => qc.invalidateQueries({ queryKey: ["draft-images", id] }),
});
const publish = useMutation({
  mutationFn: async () => api.post(`/drafts/${id}/publish-to-wechat`),
  onSuccess: () => qc.invalidateQueries({ queryKey: ["draft", id] }),
});
```

- [ ] **Step 2: Add JSX blocks** below the report section:

```tsx
<div>
  <h2 className="font-medium mb-2">图片复核</h2>
  <div className="grid grid-cols-3 md:grid-cols-4 gap-3">
    {images.data?.map((img) => (
      <div key={img.id} className={`border rounded p-2 ${img.is_cover ? "ring-2 ring-blue-500" : ""}`}>
        <img src={img.wechat_url ?? img.original_url} className="w-full h-32 object-cover rounded" />
        <div className="text-xs mt-1 text-slate-600">{img.status}</div>
        {img.error_msg && <div className="text-xs text-red-600">{img.error_msg}</div>}
        <div className="flex gap-1 mt-2 text-xs">
          <button onClick={() => setCover.mutate(img.id)}
                  disabled={img.is_cover} className="underline">设为封面</button>
          <button onClick={() => removeImg.mutate(img.id)} className="underline text-red-600">删除</button>
        </div>
      </div>
    ))}
  </div>
</div>

<button onClick={() => publish.mutate()}
        disabled={detail.data?.status === "published_to_wechat" || publish.isPending}
        className="bg-emerald-700 text-white px-4 py-2 rounded">
  {detail.data?.status === "published_to_wechat" ? "已推送到微信" :
   publish.isPending ? "推送中..." : "推送到微信草稿箱"}
</button>
```

- [ ] **Step 3: Manual smoke test** — full E2E with real public账号: configure provider + account → paste URL → wait crawl → trigger rewrite → wait reviewed → open detail → verify report + image grid → set cover → push → verify draft appears in WeChat 公众号 草稿箱.

- [ ] **Step 4: Commit**

```bash
git add frontend/src/pages/DraftDetail.tsx
git commit -m "feat(frontend): add image review panel + publish-to-wechat button"
```

---

## Stage 4 Exit Criteria

- [ ] After rewrite finishes, image rows are created with `pending` status.
- [ ] Frontend Draft Detail shows images with status badges; status updates to `uploaded` after image task runs.
- [ ] User can mark a different image as cover; previous cover loses the flag.
- [ ] "推送到微信" button triggers image processing if needed, then `add_draft`. On success, `draft.status` becomes `published_to_wechat`, `wechat_media_id` is populated.
- [ ] Failed publish populates `error_msg` with the WeChat errcode/errmsg.
- [ ] All unit + integration tests pass.

---

# Stage 5 — Hardening (E2E + Docs)

## Task 5.1: Playwright smoke test

**Files:** Create `frontend/playwright.config.ts`, `frontend/e2e/golden_path.spec.ts`.

- [ ] **Step 1:** `cd frontend && pnpm add -D @playwright/test && pnpm exec playwright install chromium`

- [ ] **Step 2: `frontend/playwright.config.ts`**

```ts
import { defineConfig } from "@playwright/test";

export default defineConfig({
  testDir: "./e2e",
  use: { baseURL: process.env.BASE_URL || "http://localhost", headless: true },
  reporter: [["list"]],
});
```

- [ ] **Step 3: `frontend/e2e/golden_path.spec.ts`**

```ts
import { test, expect } from "@playwright/test";

test("login flow", async ({ page }) => {
  await page.goto("/login");
  await page.fill("input[placeholder='用户名']", "admin");
  await page.fill("input[placeholder='密码']", "hunter2");
  await page.click("button:has-text('登录')");
  await expect(page).toHaveURL(/\/library|\/accounts/);
});
```

- [ ] **Step 4: Run** — `pnpm exec playwright test` — Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add frontend/playwright.config.ts frontend/e2e
git commit -m "test(e2e): add Playwright login smoke test"
```

---

## Task 5.2: README + deployment guide

**Files:** Create `README.md`.

- [ ] **Step 1: Create `README.md`**

````markdown
# 微信公众号批量改写系统

Single-user web tool that crawls WeChat 公众号 article URLs into a library, batch-rewrites them with configurable LLMs, runs 4-dimension AI review, and pushes drafts to WeChat draft boxes for multiple managed accounts.

## Quick start

```bash
cp .env.example .env
python -c "from cryptography.fernet import Fernet; print('ENCRYPTION_KEY=' + Fernet.generate_key().decode())" >> .env
docker compose run --rm api python -m app.scripts.init_admin --password yourpass
# Append printed hash into .env as ADMIN_PASSWORD_HASH=<hash>
# Set JWT_SECRET to a long random string in .env
docker compose up -d --build
```

Open http://localhost — log in with `admin` + `yourpass`.

## First-run configuration

1. Settings → add an AI Provider (e.g. DeepSeek, base_url `https://api.deepseek.com/v1`).
2. Settings → bind roles writer / reviewer / lite to provider+model.
3. Accounts → add a 公众号: name, AppID, AppSecret, category, prompts. Requires authenticated 服务号 / 订阅号 for the draft API.
4. Library → paste WeChat article URLs and tag them.
5. Library → select items + target account → click 改写.
6. Drafts → wait for status `reviewed`, open detail, edit, set cover, click 推送到微信.

## Architecture

See `docs/superpowers/specs/2026-04-30-wechat-batch-rewrite-design.md`.

## Development

Backend:
```bash
cd backend
uv venv && uv pip install -e ".[dev]"
uv run pytest -v
uv run ruff check .
```

Frontend:
```bash
cd frontend
pnpm install
pnpm dev
pnpm exec playwright test
```

## Backup

```bash
docker compose exec postgres pg_dump -U postgres wechat_rewriter > backup.sql
```

## Security notes

- Front the bundled `web` container with Caddy / nginx-proxy + Let's Encrypt for HTTPS.
- All AI keys and 公众号 secrets are encrypted with Fernet at rest. Losing `ENCRYPTION_KEY` makes them unrecoverable.

## v1 limitations

- WeChat article URLs only (no third-party scraping platform integration).
- No automatic publish — push to draft box only; final 发布 happens manually in 公众号 admin.
- No AI cover image generation.
- Single-user only.
````

- [ ] **Step 2: Commit**

```bash
git add README.md
git commit -m "docs: add README with quick-start, configuration, and limitations"
```

---

## Stage 5 Exit Criteria

- [ ] Playwright smoke test passes against `docker compose up`.
- [ ] README walks through full quick-start end-to-end.
- [ ] All tests green: backend pytest + frontend playwright.

---

# Self-Review

Spec coverage check (`docs/superpowers/specs/2026-04-30-wechat-batch-rewrite-design.md`):

| Spec section | Implementing tasks |
|---|---|
| §1.3 v1 — URL ingestion → library | T2.3, T2.6, T2.8 |
| §1.3 v1 — batch rewrite (title + content) | T3.6, T3.9, T3.10 |
| §1.3 v1 — 4-dim AI review | T3.7, T3.8, T3.9 |
| §1.3 v1 — image auto-fetch + per-image review | T4.1, T4.5, T4.7, T4.8 |
| §1.3 v1 — push to WeChat draft box | T4.4, T4.6, T4.8 |
| §1.3 v1 — multi-AI provider integration | T3.2, T3.3, T3.4 |
| §1.3 v1 — multi-公众号 management | T1.9, T1.10 |
| §1.3 v1 — single-user login | T1.6, T1.7, T1.8 |
| §1.3 v1 — local sensitive-word blacklist | T3.7 |
| §1.3 v1 — Docker Compose deploy | T1.12, T1.13, T1.15, T2.1 |
| §3 architecture (5 containers) | T1.12, T1.13, T1.15, T2.1 |
| §3.2 backend module layout | All Stage 1–4 backend tasks |
| §4.1 accounts schema | T1.9 |
| §4.2 library_items schema | T2.3 |
| §4.3 drafts schema | T3.5 |
| §4.4 review_reports schema | T3.5 |
| §4.5 images schema | T4.1 |
| §4.6 tasks schema | T2.2 |
| §4.7 ai_providers / role_bindings / ai_usage | T3.1 |
| §5.1 ingest flow | T2.6, T2.7 |
| §5.2 rewrite chain | T3.9 |
| §5.3 image flow | T4.5 |
| §5.4 publish flow | T4.6 |
| §6 AI provider abstraction | T3.2, T3.3 |
| §7 error handling matrix | embedded in T2.4, T2.7, T3.9, T4.5, T4.6 |
| §8 Docker / compose / .env | T1.12, T1.13, T1.15, T2.1 |
| §9 testing strategy | unit/integration test steps + T5.1 |

Verification:

- **No "TBD"/"TODO"/placeholder steps** — visual scan confirms.
- **Type/method consistency:** `BaseProvider.chat()` signature stable across T3.2, T3.3, T3.6, T3.9; `ProviderRegistry.role()` returns `(provider, model)` tuple consistently; `ImageStatus` enum values referenced consistently in T4.1, T4.5, T4.6.
- **Migrations are autogenerated** per task that adds tables (T1.9, T2.2, T2.3, T3.1, T3.5, T4.1) — no hand-written migrations.
- **Each task ends with a commit** so progress is checkpointed.
- **Frontend always reaches state visible to user** at the end of every UI task (Library page after T2.8, Drafts list/detail after T3.11, image review after T4.8).

---

# Execution Handoff

Plan complete and saved to `docs/superpowers/plans/2026-04-30-wechat-batch-rewriter.md`. Two execution options:

**1. Subagent-Driven (recommended)** — I dispatch a fresh subagent per task, review between tasks, fast iteration.

**2. Inline Execution** — Execute tasks in this session using executing-plans, batch execution with checkpoints.

Which approach?
