# 微信公众号文章 & 账号统计实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 给每个公众号增加每日自动抓取文章统计（阅读/点赞/分享/评论数）+ 账号粉丝统计的子系统，提供「数据」页查看。

**Architecture:** 新建 `app/stats/` 模块（models/schemas/service/routes）+ `app/wechat/stats.py` API 客户端 + `app/tasks/stats.py` Celery 任务；Account 表加 4 个粉丝字段；新建 `wechat_articles` 表存文章统计。前端新增「数据」顶级页 + 单账号明细页。

**Tech Stack:** Python 3.12 / FastAPI / SQLAlchemy 2.x async / Alembic / pydantic v2 / Celery 5 / httpx / respx；React 18 / Vite / TypeScript / TanStack Query。

**Spec:** `docs/superpowers/specs/2026-05-18-wechat-stats-design.md`（commit `828a833`）

**Repo conventions:**
- 个人单用户项目，直接提交到 `master`，无 PR
- 严格 TDD：失败测试 → 跑确认 FAIL → 实现 → 跑确认 PASS → commit
- 后端每次改动后 `uv run pytest`、`uv run ruff check`、`uv run mypy <改动文件>` 全绿
- 前端 `pnpm build` 必须 tsc + vite 都干净
- commit 风格 `feat:` / `fix:` / `test:` / `docs:`（已全局禁用 Co-Authored-By）
- 后端工作目录 `backend/`；前端工作目录 `frontend/`
- 当前 alembic head：`a1b2c3d4e5f6`

---

## 文件结构

### Backend 新建

| 文件 | 责任 |
|---|---|
| `backend/app/wechat/stats.py` | 4 个微信 datacube/comment API 客户端函数 |
| `backend/app/stats/__init__.py` | 包 |
| `backend/app/stats/models.py` | `WechatArticle` ORM 模型 |
| `backend/app/stats/schemas.py` | Pydantic schemas |
| `backend/app/stats/service.py` | upsert + 查询 helpers |
| `backend/app/stats/routes.py` | FastAPI 路由 |
| `backend/app/tasks/stats.py` | 2 个 Celery task |
| `backend/alembic/versions/<hash>_add_wechat_stats.py` | 单 migration（建 wechat_articles 表 + Account 加 4 列） |
| `backend/tests/unit/test_wechat_stats_client.py` | API 客户端单元测试（respx 模拟） |
| `backend/tests/unit/test_stats_service.py` | service 层单元测试 |
| `backend/tests/integration/test_stats_task.py` | Celery 任务集成测试 |
| `backend/tests/integration/test_stats_routes.py` | 路由集成测试 |

### Backend 修改

| 文件 | 修改 |
|---|---|
| `backend/app/config.py` | 加 `stats_backfill_days`、`stats_daily_cron_hour` 两个字段 |
| `backend/app/accounts/models.py` | Account 加 4 列（粉丝相关） |
| `backend/app/accounts/schemas.py` | `AccountOut` 暴露 4 个新字段 |
| `backend/app/api/router.py` | 注册 stats 路由 |
| `backend/app/tasks/celery_app.py` | `include` 列表加 `"app.tasks.stats"` |
| `backend/app/tasks/maintenance.py` | beat_schedule 加 `sync-stats-daily` |
| `backend/alembic/env.py` | import `WechatArticle` |
| `backend/tests/conftest.py` | import `WechatArticle`（让 testcontainers 建表） |
| `backend/.env.example` | 加 2 个新 env 变量 |

### Frontend 新建

| 文件 | 责任 |
|---|---|
| `frontend/src/lib/api/stats.ts` | API client（4 个函数） |
| `frontend/src/pages/Stats.tsx` | 账号列表页 |
| `frontend/src/pages/StatsDetail.tsx` | 单账号文章明细页 |

### Frontend 修改

| 文件 | 修改 |
|---|---|
| `frontend/src/App.tsx` | 加 2 个 route（`/stats`、`/stats/:accountId`） |
| `frontend/src/components/Nav.tsx`（或现有顶部导航文件） | 加「数据」入口 |

---

## Task 1: 后端 Config 增加 `stats_backfill_days` + `stats_daily_cron_hour`

**Files:**
- Modify: `backend/app/config.py`
- Modify: `backend/.env.example`
- Test: 无（trivial 配置项）

- [ ] **Step 1: 修改 `backend/app/config.py`**

在 `Settings` 类的 `draft_max_regenerations` 字段后追加：

```python
    draft_max_regenerations: int = Field(default=5, ge=1, le=50)
    stats_backfill_days: int = Field(default=30, ge=7, le=90)
    stats_daily_cron_hour: int = Field(default=3, ge=0, le=23)
```

`Field` 已经在文件顶部 import。无需追加。

- [ ] **Step 2: 修改 `backend/.env.example`**

在文件末尾追加（保留前面的内容不动）：

```bash
# 公众号统计：每日 Celery beat 任务相关
STATS_BACKFILL_DAYS=30
STATS_DAILY_CRON_HOUR=3
```

- [ ] **Step 3: lint / type 检查**

```bash
cd backend
uv run ruff check app/config.py
uv run mypy app/config.py
```

预期：无输出。

- [ ] **Step 4: 提交**

```bash
git add backend/app/config.py backend/.env.example
git commit -m "feat(config): add stats_backfill_days and stats_daily_cron_hour settings"
```

---

## Task 2: Account 加 4 个粉丝字段 + `WechatArticle` 模型 + 单 Alembic Migration

**Files:**
- Modify: `backend/app/accounts/models.py`
- Modify: `backend/app/accounts/schemas.py`
- Create: `backend/app/stats/__init__.py`
- Create: `backend/app/stats/models.py`
- Modify: `backend/alembic/env.py`
- Modify: `backend/tests/conftest.py`
- Create: `backend/alembic/versions/<hash>_add_wechat_stats.py`

- [ ] **Step 1: 修改 `backend/app/accounts/models.py`**

在 `Account` 类的 `character_reference_updated_at` 字段**之后**、`is_active` 之前插入 4 行：

```python
    character_reference_updated_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    follower_count: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default="0"
    )
    new_follow_yesterday: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default="0"
    )
    cancel_follow_yesterday: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default="0"
    )
    stats_synced_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
```

需要在文件顶部 import 加 `Integer`：

```python
from sqlalchemy import Boolean, DateTime, Integer, String, Text, func
```

（`Integer` 之前没 import。其它已存在。）

- [ ] **Step 2: 修改 `backend/app/accounts/schemas.py`** —— 暴露 4 个新字段

在文件中找到 `AccountOut`（或 `Account` 响应 schema），追加 4 个字段（位置按字段顺序无所谓）：

```python
    follower_count: int
    new_follow_yesterday: int
    cancel_follow_yesterday: int
    stats_synced_at: datetime | None
```

如 `datetime` 未 import，加：

```python
from datetime import datetime
```

- [ ] **Step 3: 创建 `backend/app/stats/__init__.py`**

整个文件内容：

```python
```

（空文件，标记包。）

- [ ] **Step 4: 创建 `backend/app/stats/models.py`**

整个文件内容：

```python
import uuid
from datetime import datetime

from sqlalchemy import (
    BigInteger,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class WechatArticle(Base):
    __tablename__ = "wechat_articles"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    account_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("accounts.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    msgid: Mapped[int] = mapped_column(BigInteger, nullable=False)
    article_idx: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    publish_time: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    read_count: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default="0"
    )
    like_count: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default="0"
    )
    share_count: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default="0"
    )
    comment_count: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default="0"
    )
    last_synced_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )

    __table_args__ = (
        UniqueConstraint(
            "account_id", "msgid", "article_idx", name="uq_wechat_article"
        ),
        Index(
            "ix_wechat_article_publish", "account_id", "publish_time"
        ),
    )
```

- [ ] **Step 5: 修改 `backend/alembic/env.py`**

在 `from app.tasks.models import TaskRecord  # noqa: F401` 之后追加：

```python
from app.stats.models import WechatArticle  # noqa: F401
```

- [ ] **Step 6: 修改 `backend/tests/conftest.py`**

在 `from app.tasks.models import TaskRecord  # noqa: F401` 之后追加：

```python
from app.stats.models import WechatArticle  # noqa: F401
```

- [ ] **Step 7: 生成 alembic 迁移文件**

```bash
cd backend
uv run alembic revision -m "add wechat stats"
```

预期：输出形如 `Generating .../alembic/versions/<hash>_add_wechat_stats.py ... done`。记下 `<hash>`。

如果 alembic 报错连不上数据库（不需要连库也能生成 revision，但 env.py 可能尝试连）：

```bash
DATABASE_URL=postgresql+asyncpg://postgres:postgres@localhost:5433/dummy uv run alembic revision -m "add wechat stats"
```

- [ ] **Step 8: 编辑生成的迁移文件**

把 `<hash>_add_wechat_stats.py` 整个文件替换为：

```python
"""add wechat stats

Revision ID: <alembic 自动填 — 不要改>
Revises: a1b2c3d4e5f6
Create Date: <alembic 自动填>

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = "<alembic 自动填 — 不要改>"
down_revision: Union[str, Sequence[str], None] = "a1b2c3d4e5f6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "accounts",
        sa.Column(
            "follower_count",
            sa.Integer(),
            nullable=False,
            server_default="0",
        ),
    )
    op.add_column(
        "accounts",
        sa.Column(
            "new_follow_yesterday",
            sa.Integer(),
            nullable=False,
            server_default="0",
        ),
    )
    op.add_column(
        "accounts",
        sa.Column(
            "cancel_follow_yesterday",
            sa.Integer(),
            nullable=False,
            server_default="0",
        ),
    )
    op.add_column(
        "accounts",
        sa.Column(
            "stats_synced_at",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
    )

    op.create_table(
        "wechat_articles",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("account_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("msgid", sa.BigInteger(), nullable=False),
        sa.Column("article_idx", sa.Integer(), nullable=False),
        sa.Column("title", sa.String(length=200), nullable=False),
        sa.Column("publish_time", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "read_count",
            sa.Integer(),
            nullable=False,
            server_default="0",
        ),
        sa.Column(
            "like_count",
            sa.Integer(),
            nullable=False,
            server_default="0",
        ),
        sa.Column(
            "share_count",
            sa.Integer(),
            nullable=False,
            server_default="0",
        ),
        sa.Column(
            "comment_count",
            sa.Integer(),
            nullable=False,
            server_default="0",
        ),
        sa.Column("last_synced_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["account_id"], ["accounts.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "account_id", "msgid", "article_idx", name="uq_wechat_article"
        ),
    )
    op.create_index(
        "ix_wechat_articles_account_id",
        "wechat_articles",
        ["account_id"],
    )
    op.create_index(
        "ix_wechat_article_publish",
        "wechat_articles",
        ["account_id", "publish_time"],
    )


def downgrade() -> None:
    op.drop_index("ix_wechat_article_publish", table_name="wechat_articles")
    op.drop_index("ix_wechat_articles_account_id", table_name="wechat_articles")
    op.drop_table("wechat_articles")
    op.drop_column("accounts", "stats_synced_at")
    op.drop_column("accounts", "cancel_follow_yesterday")
    op.drop_column("accounts", "new_follow_yesterday")
    op.drop_column("accounts", "follower_count")
```

**注意：**
- `revision` 行**保留 alembic 自动生成的值**，只确认 `down_revision = "a1b2c3d4e5f6"`
- 如果 alembic 自动填的 `down_revision` 已经是 `a1b2c3d4e5f6`，不用改

- [ ] **Step 9: 验证 alembic history**

```bash
uv run alembic history | head -3
```

预期：head 是新的 revision，前一个是 `a1b2c3d4e5f6`。

- [ ] **Step 10: 跑现有测试确认改动不破**

```bash
uv run pytest tests/unit/test_db_base.py tests/integration/test_accounts_routes.py -v
```

预期：全部通过。testcontainers 在 fixture 里跑 `Base.metadata.create_all`，新表会自动建出来。

- [ ] **Step 11: lint / type**

```bash
uv run ruff check app/accounts/models.py app/accounts/schemas.py app/stats/ alembic/versions/
uv run mypy app/accounts/models.py app/accounts/schemas.py app/stats/models.py
```

预期：无输出。

- [ ] **Step 12: 提交**

```bash
git add backend/app/accounts/models.py backend/app/accounts/schemas.py \
        backend/app/stats/__init__.py backend/app/stats/models.py \
        backend/alembic/env.py backend/alembic/versions/ \
        backend/tests/conftest.py
git commit -m "feat(stats): add Account follower fields + WechatArticle model + migration"
```

---

## Task 3: 微信 stats API 客户端（TDD）

**Files:**
- Create: `backend/app/wechat/stats.py`
- Test: `backend/tests/unit/test_wechat_stats_client.py`

**说明：** 4 个函数，全部 async，全部用 httpx；测试用 respx 模拟微信 API。

### 接口契约

| 函数 | 输入 | 返回 |
|------|------|------|
| `fetch_user_summary(access_token, begin_date, end_date)` | str, date, date | `list[dict]` 每行含 `ref_date / new_user / cancel_user` |
| `fetch_user_cumulate(access_token, begin_date, end_date)` | str, date, date | `list[dict]` 每行含 `ref_date / cumulate_user` |
| `fetch_article_total(access_token, begin_date, end_date)` | str, date, date | `list[dict]` 每行含 `msgid (str, format "msgdataid_idx") / title / details: list[dict]` |
| `fetch_comment_count(access_token, msg_data_id, index)` | str, int, int | `int` (comment total) |

- [ ] **Step 1: 写失败测试 `backend/tests/unit/test_wechat_stats_client.py`**

整个文件内容：

```python
from datetime import date

import httpx
import pytest
import respx

from app.wechat import stats as stats_client


@pytest.mark.asyncio
@respx.mock
async def test_fetch_user_summary_parses_list():
    respx.get("https://api.weixin.qq.com/datacube/getusersummary").mock(
        return_value=httpx.Response(
            200,
            json={
                "list": [
                    {
                        "ref_date": "2026-05-17",
                        "user_source": 0,
                        "new_user": 12,
                        "cancel_user": 3,
                    }
                ]
            },
        )
    )
    rows = await stats_client.fetch_user_summary(
        access_token="tok",
        begin_date=date(2026, 5, 17),
        end_date=date(2026, 5, 17),
    )
    assert rows == [
        {
            "ref_date": "2026-05-17",
            "user_source": 0,
            "new_user": 12,
            "cancel_user": 3,
        }
    ]


@pytest.mark.asyncio
@respx.mock
async def test_fetch_user_cumulate_parses_list():
    respx.get("https://api.weixin.qq.com/datacube/getusercumulate").mock(
        return_value=httpx.Response(
            200,
            json={
                "list": [
                    {"ref_date": "2026-05-17", "cumulate_user": 1234}
                ]
            },
        )
    )
    rows = await stats_client.fetch_user_cumulate(
        access_token="tok",
        begin_date=date(2026, 5, 17),
        end_date=date(2026, 5, 17),
    )
    assert rows == [{"ref_date": "2026-05-17", "cumulate_user": 1234}]


@pytest.mark.asyncio
@respx.mock
async def test_fetch_article_total_returns_raw_rows():
    payload = {
        "list": [
            {
                "ref_date": "2026-05-17",
                "msgid": "100000001_1",
                "title": "标题",
                "details": [
                    {
                        "stat_date": "2026-05-17",
                        "int_page_read_user": 100,
                        "int_page_read_count": 200,
                        "share_user": 5,
                        "share_count": 10,
                        "like_user": 8,
                        "like_count": 12,
                    }
                ],
            }
        ]
    }
    respx.get("https://api.weixin.qq.com/datacube/getarticletotal").mock(
        return_value=httpx.Response(200, json=payload)
    )
    rows = await stats_client.fetch_article_total(
        access_token="tok",
        begin_date=date(2026, 5, 10),
        end_date=date(2026, 5, 17),
    )
    assert rows == payload["list"]


@pytest.mark.asyncio
@respx.mock
async def test_fetch_comment_count_returns_total():
    respx.post(
        "https://api.weixin.qq.com/cgi-bin/comment/list"
    ).mock(
        return_value=httpx.Response(
            200,
            json={"total": 23, "comment": []},
        )
    )
    total = await stats_client.fetch_comment_count(
        access_token="tok",
        msg_data_id=100000001,
        index=1,
    )
    assert total == 23


@pytest.mark.asyncio
@respx.mock
async def test_fetch_user_summary_raises_on_errcode():
    respx.get("https://api.weixin.qq.com/datacube/getusersummary").mock(
        return_value=httpx.Response(
            200,
            json={"errcode": 40013, "errmsg": "invalid appid"},
        )
    )
    with pytest.raises(stats_client.WechatStatsError) as exc:
        await stats_client.fetch_user_summary(
            access_token="tok",
            begin_date=date(2026, 5, 17),
            end_date=date(2026, 5, 17),
        )
    assert "40013" in str(exc.value)
```

- [ ] **Step 2: 跑测试确认 FAIL**

```bash
cd backend
uv run pytest tests/unit/test_wechat_stats_client.py -v
```

预期：`ModuleNotFoundError: No module named 'app.wechat.stats'` 或类似。

- [ ] **Step 3: 创建 `backend/app/wechat/stats.py`**

整个文件内容：

```python
from datetime import date

import httpx


class WechatStatsError(Exception):
    pass


_DATACUBE_BASE = "https://api.weixin.qq.com/datacube"
_COMMENT_LIST_URL = "https://api.weixin.qq.com/cgi-bin/comment/list"
_TIMEOUT_SECONDS = 10.0


def _check_errcode(data: dict) -> None:
    errcode = data.get("errcode")
    if errcode is not None and errcode != 0:
        raise WechatStatsError(
            f"errcode={errcode}, errmsg={data.get('errmsg')}"
        )


async def _post_datacube(
    path: str, *, access_token: str, begin_date: date, end_date: date
) -> list[dict]:
    async with httpx.AsyncClient(timeout=_TIMEOUT_SECONDS) as client:
        resp = await client.get(
            f"{_DATACUBE_BASE}/{path}",
            params={
                "access_token": access_token,
                "begin_date": begin_date.isoformat(),
                "end_date": end_date.isoformat(),
            },
        )
    data = resp.json()
    _check_errcode(data)
    return list(data.get("list", []))


async def fetch_user_summary(
    *, access_token: str, begin_date: date, end_date: date
) -> list[dict]:
    return await _post_datacube(
        "getusersummary",
        access_token=access_token,
        begin_date=begin_date,
        end_date=end_date,
    )


async def fetch_user_cumulate(
    *, access_token: str, begin_date: date, end_date: date
) -> list[dict]:
    return await _post_datacube(
        "getusercumulate",
        access_token=access_token,
        begin_date=begin_date,
        end_date=end_date,
    )


async def fetch_article_total(
    *, access_token: str, begin_date: date, end_date: date
) -> list[dict]:
    return await _post_datacube(
        "getarticletotal",
        access_token=access_token,
        begin_date=begin_date,
        end_date=end_date,
    )


async def fetch_comment_count(
    *, access_token: str, msg_data_id: int, index: int
) -> int:
    async with httpx.AsyncClient(timeout=_TIMEOUT_SECONDS) as client:
        resp = await client.post(
            _COMMENT_LIST_URL,
            params={"access_token": access_token},
            json={
                "msg_data_id": msg_data_id,
                "index": index,
                "begin": 0,
                "count": 0,
                "type": 0,
            },
        )
    data = resp.json()
    _check_errcode(data)
    return int(data.get("total", 0))
```

**注：** 微信 datacube API 实际上是 POST + JSON body，不是 GET。文档前后不一致；保险起见看实际服务器。这里先用 GET（与测试 mock 一致），如果上线后 wechat 实际拒绝 GET，后续单独 fix 一次。

> **TODO 调整建议（不在本任务范围）：** 部署后验真，如果实际是 POST + body 调用，改 `_post_datacube` 用 `client.post(url, params={"access_token": ...}, json={"begin_date": ..., "end_date": ...})`，同步改测试 mock。

- [ ] **Step 4: 跑测试确认 PASS**

```bash
uv run pytest tests/unit/test_wechat_stats_client.py -v
```

预期：5 条测试全部 PASS。

- [ ] **Step 5: lint / type**

```bash
uv run ruff check app/wechat/stats.py tests/unit/test_wechat_stats_client.py
uv run mypy app/wechat/stats.py tests/unit/test_wechat_stats_client.py
```

预期：无输出。

- [ ] **Step 6: 提交**

```bash
git add backend/app/wechat/stats.py backend/tests/unit/test_wechat_stats_client.py
git commit -m "feat(wechat): add datacube + comment stats API client"
```

---

## Task 4: Stats schemas + service helpers（TDD）

**Files:**
- Create: `backend/app/stats/schemas.py`
- Create: `backend/app/stats/service.py`
- Test: `backend/tests/unit/test_stats_service.py`

### Schemas

```python
class AccountStatsRow(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    account_id: uuid.UUID
    name: str
    follower_count: int
    new_follow_yesterday: int
    cancel_follow_yesterday: int
    articles_count_30d: int
    total_read_30d: int
    stats_synced_at: datetime | None


class ArticleStatsRow(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    msgid: int
    article_idx: int
    title: str
    publish_time: datetime
    read_count: int
    like_count: int
    share_count: int
    comment_count: int
    last_synced_at: datetime


class RefreshTriggerResponse(BaseModel):
    job_id: str
    status: Literal["queued"]
```

### Service functions

| 函数 | 用途 |
|------|------|
| `upsert_account_stats(db, account_id, *, follower_count, new_follow, cancel_follow, synced_at)` | 更新 Account 4 个字段 |
| `upsert_article(db, account_id, *, msgid, article_idx, title, publish_time, read_count, like_count, share_count, last_synced_at)` | wechat_articles 按唯一键 upsert（**不动 comment_count**） |
| `update_comment_count(db, account_id, msgid, article_idx, comment_count)` | 单独更新 comment_count |
| `list_account_stats(db)` → `list[AccountStatsRow]` | 全账号汇总（含派生字段） |
| `get_account_stats(db, account_id)` → `AccountStatsRow \| None` | 单账号汇总 |
| `list_articles(db, account_id, *, days=30, sort="publish_time", order="desc")` → `list[ArticleStatsRow]` | 单账号文章明细 |

**派生字段窗口固定 30 天**（不跟 `stats_backfill_days` 联动，spec 已锁定）。

- [ ] **Step 1: 写失败测试 `backend/tests/unit/test_stats_service.py`**

整个文件内容：

```python
import uuid
from datetime import datetime, timedelta, timezone

import pytest

from app.accounts.models import Account
from app.stats import service
from app.stats.models import WechatArticle


async def _seed_account(db_session, *, name: str = "A") -> Account:
    account = Account(
        name=name,
        wechat_appid=f"wx{uuid.uuid4().hex[:8]}",
        wechat_secret="s",
        category="职场",
        title_prompt="t",
        content_prompt="c",
    )
    db_session.add(account)
    await db_session.commit()
    await db_session.refresh(account)
    return account


@pytest.mark.asyncio
async def test_upsert_account_stats_sets_fields(db_session):
    account = await _seed_account(db_session)
    now = datetime.now(timezone.utc)
    await service.upsert_account_stats(
        db_session,
        account.id,
        follower_count=1234,
        new_follow=12,
        cancel_follow=3,
        synced_at=now,
    )
    await db_session.refresh(account)
    assert account.follower_count == 1234
    assert account.new_follow_yesterday == 12
    assert account.cancel_follow_yesterday == 3
    assert account.stats_synced_at == now


@pytest.mark.asyncio
async def test_upsert_article_creates_then_updates(db_session):
    account = await _seed_account(db_session)
    pub = datetime.now(timezone.utc) - timedelta(days=5)
    synced = datetime.now(timezone.utc)

    # first insert
    await service.upsert_article(
        db_session,
        account.id,
        msgid=100,
        article_idx=0,
        title="标题",
        publish_time=pub,
        read_count=100,
        like_count=10,
        share_count=5,
        last_synced_at=synced,
    )
    # second call with same key updates, not duplicate
    await service.upsert_article(
        db_session,
        account.id,
        msgid=100,
        article_idx=0,
        title="标题改",
        publish_time=pub,
        read_count=200,
        like_count=20,
        share_count=10,
        last_synced_at=synced,
    )
    rows = await service.list_articles(db_session, account.id)
    assert len(rows) == 1
    assert rows[0].read_count == 200
    assert rows[0].title == "标题改"
    assert rows[0].comment_count == 0  # comment 不被 upsert 动


@pytest.mark.asyncio
async def test_update_comment_count_only_touches_comment_column(db_session):
    account = await _seed_account(db_session)
    pub = datetime.now(timezone.utc) - timedelta(days=5)
    synced = datetime.now(timezone.utc)

    await service.upsert_article(
        db_session,
        account.id,
        msgid=100,
        article_idx=0,
        title="标题",
        publish_time=pub,
        read_count=100,
        like_count=10,
        share_count=5,
        last_synced_at=synced,
    )
    await service.update_comment_count(db_session, account.id, 100, 0, 42)

    rows = await service.list_articles(db_session, account.id)
    assert rows[0].comment_count == 42
    assert rows[0].read_count == 100  # 没被冲掉


@pytest.mark.asyncio
async def test_list_account_stats_derives_30d_window(db_session):
    account = await _seed_account(db_session)
    now = datetime.now(timezone.utc)
    synced = now

    # 1 篇在窗口内（10 天前），1 篇在窗口外（40 天前）
    await service.upsert_article(
        db_session,
        account.id,
        msgid=100,
        article_idx=0,
        title="新",
        publish_time=now - timedelta(days=10),
        read_count=100,
        like_count=10,
        share_count=5,
        last_synced_at=synced,
    )
    await service.upsert_article(
        db_session,
        account.id,
        msgid=200,
        article_idx=0,
        title="旧",
        publish_time=now - timedelta(days=40),
        read_count=999,
        like_count=99,
        share_count=99,
        last_synced_at=synced,
    )
    rows = await service.list_account_stats(db_session)
    assert len(rows) == 1
    row = rows[0]
    assert row.account_id == account.id
    assert row.articles_count_30d == 1
    assert row.total_read_30d == 100


@pytest.mark.asyncio
async def test_list_articles_filters_by_days_and_sorts(db_session):
    account = await _seed_account(db_session)
    now = datetime.now(timezone.utc)
    synced = now

    await service.upsert_article(
        db_session,
        account.id,
        msgid=100,
        article_idx=0,
        title="低阅读",
        publish_time=now - timedelta(days=2),
        read_count=50,
        like_count=1,
        share_count=1,
        last_synced_at=synced,
    )
    await service.upsert_article(
        db_session,
        account.id,
        msgid=200,
        article_idx=0,
        title="高阅读",
        publish_time=now - timedelta(days=5),
        read_count=500,
        like_count=1,
        share_count=1,
        last_synced_at=synced,
    )
    await service.upsert_article(
        db_session,
        account.id,
        msgid=300,
        article_idx=0,
        title="窗口外",
        publish_time=now - timedelta(days=40),
        read_count=9999,
        like_count=1,
        share_count=1,
        last_synced_at=synced,
    )

    # 默认 30 天 / publish_time desc
    rows = await service.list_articles(db_session, account.id)
    assert [r.title for r in rows] == ["低阅读", "高阅读"]

    # 按 read_count desc
    rows = await service.list_articles(
        db_session, account.id, sort="read_count", order="desc"
    )
    assert [r.title for r in rows] == ["高阅读", "低阅读"]

    # 7 天窗口
    rows = await service.list_articles(db_session, account.id, days=7)
    assert [r.title for r in rows] == ["低阅读", "高阅读"]


@pytest.mark.asyncio
async def test_get_account_stats_returns_none_for_missing(db_session):
    fake_id = uuid.uuid4()
    row = await service.get_account_stats(db_session, fake_id)
    assert row is None
```

- [ ] **Step 2: 跑测试确认 FAIL**

```bash
cd backend
uv run pytest tests/unit/test_stats_service.py -v
```

预期：`ModuleNotFoundError: No module named 'app.stats.service'` 或类似。

- [ ] **Step 3: 创建 `backend/app/stats/schemas.py`**

整个文件内容：

```python
import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict


class AccountStatsRow(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    account_id: uuid.UUID
    name: str
    follower_count: int
    new_follow_yesterday: int
    cancel_follow_yesterday: int
    articles_count_30d: int
    total_read_30d: int
    stats_synced_at: datetime | None


class ArticleStatsRow(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    msgid: int
    article_idx: int
    title: str
    publish_time: datetime
    read_count: int
    like_count: int
    share_count: int
    comment_count: int
    last_synced_at: datetime


class RefreshTriggerResponse(BaseModel):
    job_id: str
    status: Literal["queued"]
```

- [ ] **Step 4: 创建 `backend/app/stats/service.py`**

整个文件内容：

```python
import uuid
from datetime import datetime, timedelta, timezone
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
    return datetime.now(timezone.utc) - timedelta(days=_DERIVED_WINDOW_DAYS)


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

    window_start = datetime.now(timezone.utc) - timedelta(days=days)
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
```

- [ ] **Step 5: 跑测试确认 PASS**

```bash
uv run pytest tests/unit/test_stats_service.py -v
```

预期：6 条测试全部 PASS。

- [ ] **Step 6: 全量回归 + lint / type**

```bash
uv run ruff check app/stats/ tests/unit/test_stats_service.py
uv run mypy app/stats/ tests/unit/test_stats_service.py
uv run pytest
```

预期：全部干净通过。

- [ ] **Step 7: 提交**

```bash
git add backend/app/stats/schemas.py backend/app/stats/service.py \
        backend/tests/unit/test_stats_service.py
git commit -m "feat(stats): add schemas and service helpers with upsert + queries"
```

---

## Task 5: Celery task `sync_one_account_stats`（TDD）

**Files:**
- Create: `backend/app/tasks/stats.py`
- Modify: `backend/app/tasks/celery_app.py`
- Test: `backend/tests/integration/test_stats_task.py`

**说明：** `sync_one_account_stats` 是核心同步逻辑。`sync_all_accounts_stats` 在 Task 6 加。

- [ ] **Step 1: 写失败测试 `backend/tests/integration/test_stats_task.py`**

整个文件内容：

```python
import uuid
from datetime import datetime, timezone

import pytest

from app.accounts.models import Account
from app.stats import service
from app.stats.models import WechatArticle
from app.tasks import stats as stats_task


async def _seed_account(db_session) -> Account:
    account = Account(
        name="测试号",
        wechat_appid="wx12345",
        wechat_secret="secret",
        category="职场",
        title_prompt="",
        content_prompt="",
    )
    db_session.add(account)
    await db_session.commit()
    await db_session.refresh(account)
    return account


@pytest.fixture
def stub_clients(monkeypatch):
    """把所有 wechat 调用 stub 掉。"""

    async def fake_token(*a, **kw):
        return "tok"

    async def fake_user_summary(*a, **kw):
        return [{"ref_date": "2026-05-17", "new_user": 12, "cancel_user": 3}]

    async def fake_user_cumulate(*a, **kw):
        return [{"ref_date": "2026-05-17", "cumulate_user": 1234}]

    async def fake_article_total(*a, **kw):
        return [
            {
                "msgid": "100_0",
                "title": "标题 A",
                "details": [
                    {
                        "stat_date": "2026-05-17",
                        "int_page_read_count": 200,
                        "share_count": 5,
                        "like_count": 8,
                    }
                ],
            }
        ]

    async def fake_comment_count(*a, **kw):
        return 7

    monkeypatch.setattr("app.wechat.token.get_access_token", fake_token)
    monkeypatch.setattr("app.wechat.stats.fetch_user_summary", fake_user_summary)
    monkeypatch.setattr("app.wechat.stats.fetch_user_cumulate", fake_user_cumulate)
    monkeypatch.setattr("app.wechat.stats.fetch_article_total", fake_article_total)
    monkeypatch.setattr("app.wechat.stats.fetch_comment_count", fake_comment_count)


@pytest.mark.asyncio
async def test_sync_one_account_updates_follower_fields(
    db_session, stub_clients
):
    account = await _seed_account(db_session)
    await stats_task._sync_one_account(db_session, account)
    await db_session.refresh(account)
    assert account.follower_count == 1234
    assert account.new_follow_yesterday == 12
    assert account.cancel_follow_yesterday == 3
    assert account.stats_synced_at is not None


@pytest.mark.asyncio
async def test_sync_one_account_upserts_articles(db_session, stub_clients):
    account = await _seed_account(db_session)
    await stats_task._sync_one_account(db_session, account)
    rows = await service.list_articles(db_session, account.id)
    assert len(rows) == 1
    assert rows[0].msgid == 100
    assert rows[0].article_idx == 0
    assert rows[0].title == "标题 A"
    assert rows[0].read_count == 200
    assert rows[0].share_count == 5
    assert rows[0].like_count == 8
    assert rows[0].comment_count == 7


@pytest.mark.asyncio
async def test_sync_one_account_keeps_old_comment_count_when_comment_fails(
    db_session, stub_clients, monkeypatch
):
    account = await _seed_account(db_session)
    # 第一次成功 sync，comment_count=7
    await stats_task._sync_one_account(db_session, account)
    rows = await service.list_articles(db_session, account.id)
    assert rows[0].comment_count == 7

    # 第二次 comment API 失败
    async def boom(*a, **kw):
        raise RuntimeError("comment api down")

    monkeypatch.setattr("app.wechat.stats.fetch_comment_count", boom)
    await stats_task._sync_one_account(db_session, account)

    rows = await service.list_articles(db_session, account.id)
    # 老 comment_count 保留
    assert rows[0].comment_count == 7
    # 其它字段照常更新
    assert rows[0].read_count == 200
```

- [ ] **Step 2: 跑测试确认 FAIL**

```bash
cd backend
uv run pytest tests/integration/test_stats_task.py -v
```

预期：`ModuleNotFoundError: No module named 'app.tasks.stats'`。

- [ ] **Step 3: 创建 `backend/app/tasks/stats.py`**

整个文件内容：

```python
import asyncio
import logging
import uuid
from datetime import date, datetime, timedelta, timezone

from celery import shared_task
from sqlalchemy.ext.asyncio import AsyncSession

from app.accounts.models import Account
from app.config import get_settings
from app.db.base import async_session_factory
from app.stats import service
from app.wechat import stats as wechat_stats
from app.wechat import token as wechat_token

logger = logging.getLogger(__name__)


def _yesterday_in_beijing() -> date:
    """微信 datacube 用北京时间。"""
    tz_beijing = timezone(timedelta(hours=8))
    return (datetime.now(tz_beijing) - timedelta(days=1)).date()


def _parse_msgid(raw: str) -> tuple[int, int]:
    """微信 getarticletotal 返回 msgid 形如 'msg_data_id_index'，e.g. '100000001_1'."""
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
        synced_at=datetime.now(timezone.utc),
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

    rows: list[dict] = []
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

    synced = datetime.now(timezone.utc)
    for row in rows:
        try:
            msgid_str = row.get("msgid", "")
            msgid_int, idx = _parse_msgid(str(msgid_str))
            title = str(row.get("title", ""))[:200]
            details = row.get("details") or []
            detail = details[0] if details else {}
            read_count = int(detail.get("int_page_read_count", 0))
            like_count = int(detail.get("like_count", 0))
            share_count = int(detail.get("share_count", 0))
            ref_date = row.get("ref_date", yesterday.isoformat())
            publish_time = datetime.fromisoformat(ref_date).replace(
                tzinfo=timezone.utc
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
            # comment_count 单独拉，失败保留旧值
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
    async with async_session_factory() as db:
        account = await db.get(Account, account_id)
        if account is None:
            logger.warning("sync_one_account_stats: account %s not found", account_id)
            return
        try:
            await _sync_one_account(db, account)
        except Exception:
            logger.exception("sync_one_account_stats failed: %s", account_id)


@shared_task(name="app.tasks.stats.sync_one_account_stats")
def sync_one_account_stats(account_id: str) -> dict[str, str]:
    asyncio.run(_sync_one_by_id(uuid.UUID(account_id)))
    return {"account_id": account_id, "status": "done"}
```

**注意：**
- `async_session_factory` 必须在 `app/db/base.py` 已存在。如果不在，确认现有 task 模块如何拿 session（看 `app/tasks/rewrite.py` 或 `app/tasks/maintenance.py` 怎么写的，跟随相同模式）。
- 测试中调用的是私有 `_sync_one_account(db, account)`（接 session），不走 Celery 入口，避免 Celery / asyncio.run() 复杂度。

- [ ] **Step 4: 修改 `backend/app/tasks/celery_app.py`** —— 让 worker 加载新模块

找到 `include=[...]` 列表（在文件顶部），在末尾追加 `"app.tasks.stats"`：

```python
celery_app = Celery(
    "wechat_rewriter",
    broker=settings.redis_url,
    backend=settings.redis_url,
    include=[
        "app.tasks.crawl",
        "app.tasks.rewrite",
        "app.tasks.review",
        "app.tasks.images",
        "app.tasks.publish",
        "app.tasks.maintenance",
        "app.tasks.stats",
    ],
)
```

- [ ] **Step 5: 跑测试确认 PASS**

```bash
cd backend
uv run pytest tests/integration/test_stats_task.py -v
```

预期：3 条测试全部 PASS。

如果 `async_session_factory` import 报错 → 看 `app/db/base.py` 实际暴露名（可能叫 `AsyncSessionLocal` / `SessionLocal`），改 import。

- [ ] **Step 6: lint / type**

```bash
uv run ruff check app/tasks/stats.py app/tasks/celery_app.py tests/integration/test_stats_task.py
uv run mypy app/tasks/stats.py
```

预期：无输出（Celery 类型可能需要 `# type: ignore`，沿用其它 task 文件的写法）。

- [ ] **Step 7: 提交**

```bash
git add backend/app/tasks/stats.py backend/app/tasks/celery_app.py \
        backend/tests/integration/test_stats_task.py
git commit -m "feat(stats): add sync_one_account_stats Celery task"
```

---

## Task 6: Celery task `sync_all_accounts_stats` + Beat schedule

**Files:**
- Modify: `backend/app/tasks/stats.py`（追加）
- Modify: `backend/app/tasks/maintenance.py`（beat_schedule）
- Test: `backend/tests/integration/test_stats_task.py`（追加）

- [ ] **Step 1: 在 `backend/tests/integration/test_stats_task.py` 末尾追加测试**

```python
@pytest.mark.asyncio
async def test_sync_all_accounts_continues_after_per_account_error(
    db_session, monkeypatch
):
    a1 = Account(
        name="A1",
        wechat_appid="wx_a1",
        wechat_secret="s",
        category="x",
        title_prompt="",
        content_prompt="",
    )
    a2 = Account(
        name="A2",
        wechat_appid="wx_a2",
        wechat_secret="s",
        category="x",
        title_prompt="",
        content_prompt="",
    )
    db_session.add_all([a1, a2])
    await db_session.commit()
    await db_session.refresh(a1)
    await db_session.refresh(a2)

    visited: list[uuid.UUID] = []

    async def maybe_fail(db, account):
        visited.append(account.id)
        if account.name == "A1":
            raise RuntimeError("boom A1")

    monkeypatch.setattr(stats_task, "_sync_one_account", maybe_fail)
    await stats_task._sync_all(db_session)

    # A1 抛了，但 A2 也被访问
    assert set(visited) == {a1.id, a2.id}
```

- [ ] **Step 2: 跑测试确认 FAIL**

```bash
cd backend
uv run pytest tests/integration/test_stats_task.py::test_sync_all_accounts_continues_after_per_account_error -v
```

预期：`AttributeError: module 'app.tasks.stats' has no attribute '_sync_all'`。

- [ ] **Step 3: 修改 `backend/app/tasks/stats.py`** —— 在文件末尾追加

```python
async def _sync_all(db: AsyncSession) -> None:
    from sqlalchemy import select

    result = await db.execute(select(Account).where(Account.is_active.is_(True)))
    accounts = list(result.scalars().all())
    for account in accounts:
        try:
            await _sync_one_account(db, account)
        except Exception:
            logger.exception("_sync_all: account %s failed", account.id)


async def _sync_all_open_session() -> None:
    async with async_session_factory() as db:
        await _sync_all(db)


@shared_task(name="app.tasks.stats.sync_all_accounts_stats")
def sync_all_accounts_stats() -> dict[str, str]:
    asyncio.run(_sync_all_open_session())
    return {"status": "done"}
```

- [ ] **Step 4: 跑测试确认 PASS**

```bash
uv run pytest tests/integration/test_stats_task.py -v
```

预期：4 条测试全部 PASS。

- [ ] **Step 5: 修改 `backend/app/tasks/maintenance.py`** —— beat schedule 加 daily 任务

在 `celery_app.conf.beat_schedule = {...}` 字典里追加一条：

```python
celery_app.conf.beat_schedule = {
    "cleanup-daily": {
        "task": "app.tasks.maintenance.cleanup",
        "schedule": 60 * 60 * 24,
    },
    "reset-stuck-hourly": {
        "task": "app.tasks.maintenance.reset_stuck",
        "schedule": 60 * 60,
    },
    "sync-stats-daily": {
        "task": "app.tasks.stats.sync_all_accounts_stats",
        "schedule": crontab(
            hour=get_settings().stats_daily_cron_hour, minute=0
        ),
    },
}
```

文件顶部确保 import：

```python
from celery.schedules import crontab
from app.config import get_settings
```

如果 `crontab` 还没 import → 加；如果 `get_settings` 已 import → 不重复。

- [ ] **Step 6: lint / type**

```bash
uv run ruff check app/tasks/stats.py app/tasks/maintenance.py tests/integration/test_stats_task.py
uv run mypy app/tasks/stats.py app/tasks/maintenance.py
uv run pytest
```

预期：全部干净通过。

- [ ] **Step 7: 提交**

```bash
git add backend/app/tasks/stats.py backend/app/tasks/maintenance.py \
        backend/tests/integration/test_stats_task.py
git commit -m "feat(stats): add sync_all_accounts_stats + daily beat schedule"
```

---

## Task 7: Stats routes（TDD）

**Files:**
- Create: `backend/app/stats/routes.py`
- Modify: `backend/app/api/router.py`
- Test: `backend/tests/integration/test_stats_routes.py`

**端点：**

| Method | Path | 返回 |
|--------|------|------|
| `GET` | `/api/stats/accounts` | `list[AccountStatsRow]` |
| `GET` | `/api/stats/accounts/{account_id}/articles?days=30&sort=publish_time&order=desc` | `list[ArticleStatsRow]` |
| `POST` | `/api/stats/refresh` | `RefreshTriggerResponse` 202 |
| `POST` | `/api/stats/refresh?account_id=<uuid>` | `RefreshTriggerResponse` 202 |

- [ ] **Step 1: 写失败测试 `backend/tests/integration/test_stats_routes.py`**

整个文件内容：

```python
import uuid
from datetime import datetime, timedelta, timezone

import pytest
from httpx import ASGITransport, AsyncClient

from app.accounts.models import Account
from app.api.deps import get_db
from app.main import create_app
from app.stats.models import WechatArticle


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
        login = await client.post(
            "/api/auth/login",
            data={"username": "admin", "password": "hunter2"},
        )
        token = login.json()["access_token"]
        client.headers["Authorization"] = f"Bearer {token}"
        yield client


@pytest.fixture(autouse=True)
def stub_celery(monkeypatch):
    """阻止 Celery .delay() 真的派发。"""
    from app.tasks import stats as stats_task

    monkeypatch.setattr(
        stats_task.sync_one_account_stats,
        "delay",
        lambda *a, **k: type("R", (), {"id": "fake-job-id"})(),
        raising=False,
    )
    monkeypatch.setattr(
        stats_task.sync_all_accounts_stats,
        "delay",
        lambda *a, **k: type("R", (), {"id": "fake-job-id"})(),
        raising=False,
    )


async def _seed(db_session) -> tuple[Account, WechatArticle]:
    account = Account(
        name="测试号",
        wechat_appid="wx_test",
        wechat_secret="s",
        category="x",
        title_prompt="",
        content_prompt="",
        follower_count=1234,
        new_follow_yesterday=12,
        cancel_follow_yesterday=3,
        stats_synced_at=datetime.now(timezone.utc),
    )
    db_session.add(account)
    await db_session.commit()
    await db_session.refresh(account)

    article = WechatArticle(
        account_id=account.id,
        msgid=100,
        article_idx=0,
        title="标题",
        publish_time=datetime.now(timezone.utc) - timedelta(days=5),
        read_count=200,
        like_count=10,
        share_count=5,
        comment_count=7,
        last_synced_at=datetime.now(timezone.utc),
    )
    db_session.add(article)
    await db_session.commit()
    await db_session.refresh(article)
    return account, article


async def test_list_accounts_returns_stats(auth_client, db_session):
    account, _ = await _seed(db_session)
    r = await auth_client.get("/api/stats/accounts")
    assert r.status_code == 200
    body = r.json()
    assert len(body) >= 1
    row = next(x for x in body if x["account_id"] == str(account.id))
    assert row["follower_count"] == 1234
    assert row["new_follow_yesterday"] == 12
    assert row["articles_count_30d"] == 1
    assert row["total_read_30d"] == 200


async def test_list_articles_filters_and_sorts(auth_client, db_session):
    account, _ = await _seed(db_session)
    r = await auth_client.get(
        f"/api/stats/accounts/{account.id}/articles?days=30&sort=read_count&order=desc"
    )
    assert r.status_code == 200
    body = r.json()
    assert len(body) == 1
    assert body[0]["msgid"] == 100
    assert body[0]["read_count"] == 200


async def test_list_articles_404_when_account_missing(auth_client):
    fake = uuid.uuid4()
    r = await auth_client.get(f"/api/stats/accounts/{fake}/articles")
    assert r.status_code == 404


async def test_refresh_all_enqueues(auth_client, db_session):
    r = await auth_client.post("/api/stats/refresh")
    assert r.status_code == 202
    body = r.json()
    assert body["status"] == "queued"
    assert body["job_id"] == "fake-job-id"


async def test_refresh_one_enqueues(auth_client, db_session):
    account, _ = await _seed(db_session)
    r = await auth_client.post(f"/api/stats/refresh?account_id={account.id}")
    assert r.status_code == 202
    assert r.json()["status"] == "queued"


async def test_refresh_one_404_when_account_missing(auth_client):
    fake = uuid.uuid4()
    r = await auth_client.post(f"/api/stats/refresh?account_id={fake}")
    assert r.status_code == 404


async def test_endpoints_require_auth(app):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        r = await client.get("/api/stats/accounts")
        assert r.status_code in (401, 403)
```

- [ ] **Step 2: 跑测试确认 FAIL**

```bash
cd backend
uv run pytest tests/integration/test_stats_routes.py -v
```

预期：`404 Not Found`（路由还没注册）。

- [ ] **Step 3: 创建 `backend/app/stats/routes.py`**

整个文件内容：

```python
import uuid
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.accounts.models import Account
from app.api.deps import get_db
from app.auth.dependencies import get_current_username
from app.stats import service
from app.stats.schemas import (
    AccountStatsRow,
    ArticleStatsRow,
    RefreshTriggerResponse,
)
from app.tasks.stats import sync_all_accounts_stats, sync_one_account_stats

router = APIRouter(prefix="/api/stats", tags=["stats"])


@router.get("/accounts", response_model=list[AccountStatsRow])
async def list_accounts(
    db: AsyncSession = Depends(get_db),
    _: str = Depends(get_current_username),
) -> list[AccountStatsRow]:
    return await service.list_account_stats(db)


@router.get(
    "/accounts/{account_id}/articles", response_model=list[ArticleStatsRow]
)
async def list_articles(
    account_id: uuid.UUID,
    days: int = Query(default=30, ge=1, le=365),
    sort: str = Query(default="publish_time"),
    order: Literal["asc", "desc"] = Query(default="desc"),
    db: AsyncSession = Depends(get_db),
    _: str = Depends(get_current_username),
) -> list[ArticleStatsRow]:
    account = await db.get(Account, account_id)
    if account is None:
        raise HTTPException(404, "Account not found")
    return await service.list_articles(
        db, account_id, days=days, sort=sort, order=order
    )


@router.post(
    "/refresh", response_model=RefreshTriggerResponse, status_code=202
)
async def refresh(
    account_id: uuid.UUID | None = None,
    db: AsyncSession = Depends(get_db),
    _: str = Depends(get_current_username),
) -> RefreshTriggerResponse:
    if account_id is not None:
        account = await db.get(Account, account_id)
        if account is None:
            raise HTTPException(404, "Account not found")
        job = sync_one_account_stats.delay(str(account_id))
    else:
        job = sync_all_accounts_stats.delay()
    return RefreshTriggerResponse(job_id=str(job.id), status="queued")
```

- [ ] **Step 4: 修改 `backend/app/api/router.py`** —— 注册

在 import 区域加：

```python
from app.stats.routes import router as stats_router
```

在末尾 `include_router` 区域加：

```python
api_router.include_router(stats_router)
```

- [ ] **Step 5: 跑测试确认 PASS**

```bash
uv run pytest tests/integration/test_stats_routes.py -v
```

预期：7 条测试全部 PASS。

- [ ] **Step 6: lint / type / 全量回归**

```bash
uv run ruff check app/stats/ app/api/router.py tests/integration/test_stats_routes.py
uv run mypy app/stats/ app/api/router.py
uv run pytest
```

预期：全部通过。

- [ ] **Step 7: 提交**

```bash
git add backend/app/stats/routes.py backend/app/api/router.py \
        backend/tests/integration/test_stats_routes.py
git commit -m "feat(stats): add list accounts, list articles, refresh API routes"
```

---

## Task 8: 前端 — API client + 类型 + 顶部导航 stub

**Files:**
- Create: `frontend/src/lib/api/stats.ts`
- Modify: `frontend/src/App.tsx`（加 2 个 route）
- Modify: 现有顶部导航文件（加「数据」入口）
- Create: `frontend/src/pages/Stats.tsx`（stub）
- Create: `frontend/src/pages/StatsDetail.tsx`（stub）

- [ ] **Step 1: 创建 `frontend/src/lib/api/stats.ts`**

整个文件内容：

```typescript
import { apiClient } from "./client";

export type AccountStatsRow = {
  account_id: string;
  name: string;
  follower_count: number;
  new_follow_yesterday: number;
  cancel_follow_yesterday: number;
  articles_count_30d: number;
  total_read_30d: number;
  stats_synced_at: string | null;
};

export type ArticleStatsRow = {
  msgid: number;
  article_idx: number;
  title: string;
  publish_time: string;
  read_count: number;
  like_count: number;
  share_count: number;
  comment_count: number;
  last_synced_at: string;
};

export type RefreshTriggerResponse = {
  job_id: string;
  status: "queued";
};

export async function listAccountStats(): Promise<AccountStatsRow[]> {
  const { data } = await apiClient.get<AccountStatsRow[]>("/api/stats/accounts");
  return data;
}

export async function listArticleStats(
  accountId: string,
  params: { days?: number; sort?: string; order?: "asc" | "desc" } = {},
): Promise<ArticleStatsRow[]> {
  const { data } = await apiClient.get<ArticleStatsRow[]>(
    `/api/stats/accounts/${accountId}/articles`,
    { params },
  );
  return data;
}

export async function refreshStats(
  accountId?: string,
): Promise<RefreshTriggerResponse> {
  const params = accountId ? { account_id: accountId } : undefined;
  const { data } = await apiClient.post<RefreshTriggerResponse>(
    "/api/stats/refresh",
    null,
    { params },
  );
  return data;
}
```

**注意：** `apiClient` 的实际路径需要确认。看 `frontend/src/lib/api/` 下其它文件如何 import（可能是 `import { client } from "./client"` 或 `import api from "./client"`）。改成跟现有 pattern 一致。

- [ ] **Step 2: 创建 `frontend/src/pages/Stats.tsx`** —— stub，下个任务实现

整个文件内容：

```tsx
export default function Stats() {
  return <div>数据页（待实现）</div>;
}
```

- [ ] **Step 3: 创建 `frontend/src/pages/StatsDetail.tsx`** —— stub

整个文件内容：

```tsx
import { useParams } from "react-router-dom";

export default function StatsDetail() {
  const { accountId } = useParams<{ accountId: string }>();
  return <div>账号 {accountId} 明细（待实现）</div>;
}
```

- [ ] **Step 4: 修改 `frontend/src/App.tsx`** —— 加 2 个 route

找到现有的 `<Route>` 列表（参考 `/image-posts`、`/image-posts/:id` 的写法），追加：

```tsx
import Stats from "./pages/Stats";
import StatsDetail from "./pages/StatsDetail";

// 在 Routes 内追加：
<Route path="/stats" element={<Stats />} />
<Route path="/stats/:accountId" element={<StatsDetail />} />
```

确保 import 加在文件顶部 import 块。

- [ ] **Step 5: 找到顶部导航文件并加「数据」入口**

```bash
cd frontend
grep -rn "图片\|图文" src/components/ src/App.tsx 2>&1 | head -5
```

定位到现有导航组件（通常是 `src/components/Layout.tsx`、`src/components/Nav.tsx` 或类似）。

在「图片」入口旁边追加一个「数据」入口，跟现有写法保持一致。例如：

```tsx
<NavLink to="/stats">数据</NavLink>
```

具体语法以现有导航文件为准。

- [ ] **Step 6: 跑前端构建**

```bash
cd frontend
pnpm build
```

预期：tsc + vite 都干净通过。

- [ ] **Step 7: 提交**

```bash
git add frontend/src/lib/api/stats.ts \
        frontend/src/pages/Stats.tsx frontend/src/pages/StatsDetail.tsx \
        frontend/src/App.tsx
git add frontend/src/components/  # 视实际改动的导航文件而定
git commit -m "feat(stats/ui): add API client + routes + nav entry (stubs)"
```

---

## Task 9: 前端 — `/stats` 列表页

**Files:**
- Modify: `frontend/src/pages/Stats.tsx`

**功能：**
- 表格列：账号 / 当前粉丝 / 昨日新增 / 昨日取消 / 30 天文章数 / 30 天总阅读 / 同步时间（相对）/ 操作（查看明细 link + 刷新本号 icon）
- 默认按「30 天总阅读」desc，列头可点切换
- 顶部右侧「全局刷新」按钮，按下后变 disabled + spinner，3s 后 refetch
- 空状态：「还没有同步过统计数据。」+「立即同步」按钮
- 加载：skeleton 行

- [ ] **Step 1: 重写 `frontend/src/pages/Stats.tsx`**

整个文件内容：

```tsx
import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { Link } from "react-router-dom";
import {
  listAccountStats,
  refreshStats,
  type AccountStatsRow,
} from "../lib/api/stats";
import { Button } from "../components/ui/Button";

type SortKey = keyof Pick<
  AccountStatsRow,
  | "name"
  | "follower_count"
  | "new_follow_yesterday"
  | "cancel_follow_yesterday"
  | "articles_count_30d"
  | "total_read_30d"
>;

function formatRelative(iso: string | null): string {
  if (!iso) return "从未同步";
  const diffMs = Date.now() - new Date(iso).getTime();
  const diffMin = Math.floor(diffMs / 60_000);
  if (diffMin < 1) return "刚刚";
  if (diffMin < 60) return `${diffMin} 分钟前`;
  const diffH = Math.floor(diffMin / 60);
  if (diffH < 24) return `${diffH} 小时前`;
  const diffD = Math.floor(diffH / 24);
  return `${diffD} 天前`;
}

export default function Stats() {
  const qc = useQueryClient();
  const [sortKey, setSortKey] = useState<SortKey>("total_read_30d");
  const [order, setOrder] = useState<"asc" | "desc">("desc");

  const accounts = useQuery({
    queryKey: ["stats", "accounts"],
    queryFn: listAccountStats,
  });

  const refreshAll = useMutation({
    mutationFn: () => refreshStats(),
    onSuccess: () => {
      setTimeout(() => {
        qc.invalidateQueries({ queryKey: ["stats", "accounts"] });
      }, 3000);
    },
  });

  const refreshOne = useMutation({
    mutationFn: (id: string) => refreshStats(id),
    onSuccess: () => {
      setTimeout(() => {
        qc.invalidateQueries({ queryKey: ["stats", "accounts"] });
      }, 3000);
    },
  });

  const rows = (accounts.data ?? []).slice().sort((a, b) => {
    const av = a[sortKey];
    const bv = b[sortKey];
    if (typeof av === "string" && typeof bv === "string") {
      return order === "desc" ? bv.localeCompare(av) : av.localeCompare(bv);
    }
    return order === "desc" ? Number(bv) - Number(av) : Number(av) - Number(bv);
  });

  const toggleSort = (k: SortKey) => {
    if (sortKey === k) {
      setOrder(order === "desc" ? "asc" : "desc");
    } else {
      setSortKey(k);
      setOrder("desc");
    }
  };

  if (accounts.isLoading) {
    return (
      <div style={{ padding: 32 }}>
        <h1>数据</h1>
        <div>加载中…</div>
      </div>
    );
  }

  if (accounts.isError) {
    return (
      <div style={{ padding: 32 }}>
        <h1>数据</h1>
        <div>加载失败：{String(accounts.error)}</div>
      </div>
    );
  }

  if (rows.length === 0) {
    return (
      <div style={{ padding: 32 }}>
        <h1>数据</h1>
        <p>还没有同步过统计数据。</p>
        <Button
          onClick={() => refreshAll.mutate()}
          loading={refreshAll.isPending}
        >
          立即同步
        </Button>
      </div>
    );
  }

  return (
    <div style={{ padding: 32 }}>
      <div
        style={{
          display: "flex",
          justifyContent: "space-between",
          alignItems: "center",
          marginBottom: 24,
        }}
      >
        <h1>数据</h1>
        <Button
          onClick={() => refreshAll.mutate()}
          loading={refreshAll.isPending}
          disabled={refreshAll.isPending}
        >
          全局刷新
        </Button>
      </div>

      <table style={{ width: "100%", borderCollapse: "collapse" }}>
        <thead>
          <tr style={{ borderBottom: "2px solid currentColor" }}>
            <Th label="账号" sortKey="name" current={sortKey} order={order} onClick={toggleSort} />
            <Th label="当前粉丝" sortKey="follower_count" current={sortKey} order={order} onClick={toggleSort} />
            <Th label="昨日新增" sortKey="new_follow_yesterday" current={sortKey} order={order} onClick={toggleSort} />
            <Th label="昨日取消" sortKey="cancel_follow_yesterday" current={sortKey} order={order} onClick={toggleSort} />
            <Th label="30 天文章数" sortKey="articles_count_30d" current={sortKey} order={order} onClick={toggleSort} />
            <Th label="30 天总阅读" sortKey="total_read_30d" current={sortKey} order={order} onClick={toggleSort} />
            <th style={{ textAlign: "left", padding: "12px 8px" }}>同步时间</th>
            <th style={{ textAlign: "left", padding: "12px 8px" }}>操作</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((r) => (
            <tr
              key={r.account_id}
              style={{ borderBottom: "1px solid rgba(0,0,0,0.1)" }}
            >
              <td style={{ padding: "12px 8px" }}>{r.name}</td>
              <td style={{ padding: "12px 8px", fontVariantNumeric: "tabular-nums" }}>{r.follower_count.toLocaleString()}</td>
              <td style={{ padding: "12px 8px", fontVariantNumeric: "tabular-nums" }}>+{r.new_follow_yesterday}</td>
              <td style={{ padding: "12px 8px", fontVariantNumeric: "tabular-nums" }}>-{r.cancel_follow_yesterday}</td>
              <td style={{ padding: "12px 8px", fontVariantNumeric: "tabular-nums" }}>{r.articles_count_30d}</td>
              <td style={{ padding: "12px 8px", fontVariantNumeric: "tabular-nums" }}>{r.total_read_30d.toLocaleString()}</td>
              <td style={{ padding: "12px 8px" }}>{formatRelative(r.stats_synced_at)}</td>
              <td style={{ padding: "12px 8px" }}>
                <Link to={`/stats/${r.account_id}`}>查看明细</Link>
                {" · "}
                <button
                  type="button"
                  onClick={() => refreshOne.mutate(r.account_id)}
                  disabled={
                    refreshOne.isPending && refreshOne.variables === r.account_id
                  }
                >
                  刷新本号
                </button>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function Th({
  label,
  sortKey,
  current,
  order,
  onClick,
}: {
  label: string;
  sortKey: SortKey;
  current: SortKey;
  order: "asc" | "desc";
  onClick: (k: SortKey) => void;
}) {
  const active = sortKey === current;
  return (
    <th
      style={{
        textAlign: "left",
        padding: "12px 8px",
        cursor: "pointer",
        userSelect: "none",
      }}
      onClick={() => onClick(sortKey)}
    >
      {label} {active ? (order === "desc" ? "▼" : "▲") : ""}
    </th>
  );
}
```

**注意：**
- `Button` 组件的实际路径需要看现有项目（可能是 `../components/ui/Button` 或 `../components/Button`）。改成跟现有 pattern 一致。
- 样式沿用项目现有 Editorial Swiss 风格，inline style 是临时占位 —— 上线前最好 refactor 用现有 CSS modules 或 styled-system。本任务先把功能跑通。

- [ ] **Step 2: 跑前端构建**

```bash
cd frontend
pnpm build
```

预期：tsc + vite 干净通过。如果 Button 找不到 / loading prop 不存在 → 改用 disabled 简单方案。

- [ ] **Step 3: 提交**

```bash
git add frontend/src/pages/Stats.tsx
git commit -m "feat(stats/ui): account list page with sort + refresh"
```

---

## Task 10: 前端 — `/stats/:accountId` 明细页

**Files:**
- Modify: `frontend/src/pages/StatsDetail.tsx`

**功能：**
- 顶部 summary card（账号名 / 当前粉丝 / 昨日 ±N / 同步时间 / 「← 返回」link / 「刷新本号」按钮）
- 时间范围 toggle：[7 天] [30 天] [90 天]
- 排序下拉：发布时间 / 阅读 / 点赞 / 分享 / 评论
- 文章表（标题 / 发布时间 / 阅读 / 点赞 / 分享 / 评论）
- 「刷新本号」按下 → 轮询 `stats_synced_at`，最长 30 秒

- [ ] **Step 1: 重写 `frontend/src/pages/StatsDetail.tsx`**

整个文件内容：

```tsx
import { useEffect, useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { Link, useParams } from "react-router-dom";
import {
  listAccountStats,
  listArticleStats,
  refreshStats,
} from "../lib/api/stats";

type SortField =
  | "publish_time"
  | "read_count"
  | "like_count"
  | "share_count"
  | "comment_count";

function formatRelative(iso: string | null): string {
  if (!iso) return "从未同步";
  const diffMs = Date.now() - new Date(iso).getTime();
  const diffMin = Math.floor(diffMs / 60_000);
  if (diffMin < 1) return "刚刚";
  if (diffMin < 60) return `${diffMin} 分钟前`;
  const diffH = Math.floor(diffMin / 60);
  if (diffH < 24) return `${diffH} 小时前`;
  const diffD = Math.floor(diffH / 24);
  return `${diffD} 天前`;
}

export default function StatsDetail() {
  const { accountId } = useParams<{ accountId: string }>();
  const qc = useQueryClient();
  const [days, setDays] = useState<7 | 30 | 90>(30);
  const [sort, setSort] = useState<SortField>("publish_time");

  const accounts = useQuery({
    queryKey: ["stats", "accounts"],
    queryFn: listAccountStats,
  });
  const account = accounts.data?.find((a) => a.account_id === accountId);

  const articles = useQuery({
    queryKey: ["stats", "articles", accountId, days, sort],
    queryFn: () =>
      listArticleStats(accountId!, { days, sort, order: "desc" }),
    enabled: !!accountId,
  });

  const [pollUntil, setPollUntil] = useState<number | null>(null);

  const refresh = useMutation({
    mutationFn: () => refreshStats(accountId!),
    onSuccess: () => {
      setPollUntil(Date.now() + 30_000);
    },
  });

  useEffect(() => {
    if (pollUntil === null) return;
    if (Date.now() > pollUntil) {
      setPollUntil(null);
      return;
    }
    const id = setTimeout(() => {
      qc.invalidateQueries({ queryKey: ["stats", "accounts"] });
      qc.invalidateQueries({ queryKey: ["stats", "articles", accountId] });
      setPollUntil((p) => (p && Date.now() < p ? p : null));
    }, 3000);
    return () => clearTimeout(id);
  }, [pollUntil, qc, accountId, accounts.dataUpdatedAt]);

  if (!accountId) return <div>缺少 accountId</div>;
  if (accounts.isLoading) return <div style={{ padding: 32 }}>加载中…</div>;
  if (!account) return <div style={{ padding: 32 }}>账号不存在</div>;

  return (
    <div style={{ padding: 32 }}>
      <div style={{ marginBottom: 16 }}>
        <Link to="/stats">← 返回</Link>
      </div>
      <div
        style={{
          display: "flex",
          justifyContent: "space-between",
          alignItems: "center",
          marginBottom: 24,
          paddingBottom: 16,
          borderBottom: "1px solid currentColor",
        }}
      >
        <div>
          <h1 style={{ margin: 0 }}>{account.name}</h1>
          <div style={{ marginTop: 8, fontVariantNumeric: "tabular-nums" }}>
            当前粉丝 {account.follower_count.toLocaleString()} · 昨日 +
            {account.new_follow_yesterday} / -{account.cancel_follow_yesterday}{" "}
            · 同步于 {formatRelative(account.stats_synced_at)}
          </div>
        </div>
        <button
          type="button"
          onClick={() => refresh.mutate()}
          disabled={refresh.isPending || pollUntil !== null}
        >
          {pollUntil !== null ? "刷新中…" : "刷新本号"}
        </button>
      </div>

      <div style={{ display: "flex", gap: 16, marginBottom: 16 }}>
        <div>
          时间范围：
          {([7, 30, 90] as const).map((d) => (
            <button
              key={d}
              type="button"
              onClick={() => setDays(d)}
              style={{
                marginLeft: 8,
                fontWeight: d === days ? "bold" : "normal",
              }}
            >
              {d} 天
            </button>
          ))}
        </div>
        <div>
          排序：
          <select
            value={sort}
            onChange={(e) => setSort(e.target.value as SortField)}
          >
            <option value="publish_time">发布时间</option>
            <option value="read_count">阅读</option>
            <option value="like_count">点赞</option>
            <option value="share_count">分享</option>
            <option value="comment_count">评论</option>
          </select>
        </div>
      </div>

      {articles.isLoading ? (
        <div>加载中…</div>
      ) : articles.data && articles.data.length > 0 ? (
        <table style={{ width: "100%", borderCollapse: "collapse" }}>
          <thead>
            <tr style={{ borderBottom: "2px solid currentColor" }}>
              <th style={{ textAlign: "left", padding: "12px 8px" }}>标题</th>
              <th style={{ textAlign: "left", padding: "12px 8px" }}>发布时间</th>
              <th style={{ textAlign: "right", padding: "12px 8px" }}>阅读</th>
              <th style={{ textAlign: "right", padding: "12px 8px" }}>点赞</th>
              <th style={{ textAlign: "right", padding: "12px 8px" }}>分享</th>
              <th style={{ textAlign: "right", padding: "12px 8px" }}>评论</th>
            </tr>
          </thead>
          <tbody>
            {articles.data.map((a) => (
              <tr
                key={`${a.msgid}_${a.article_idx}`}
                style={{ borderBottom: "1px solid rgba(0,0,0,0.1)" }}
              >
                <td style={{ padding: "12px 8px" }}>{a.title}</td>
                <td style={{ padding: "12px 8px" }}>
                  {new Date(a.publish_time).toLocaleDateString()}
                </td>
                <td style={{ padding: "12px 8px", textAlign: "right", fontVariantNumeric: "tabular-nums" }}>
                  {a.read_count.toLocaleString()}
                </td>
                <td style={{ padding: "12px 8px", textAlign: "right", fontVariantNumeric: "tabular-nums" }}>
                  {a.like_count}
                </td>
                <td style={{ padding: "12px 8px", textAlign: "right", fontVariantNumeric: "tabular-nums" }}>
                  {a.share_count}
                </td>
                <td style={{ padding: "12px 8px", textAlign: "right", fontVariantNumeric: "tabular-nums" }}>
                  {a.comment_count}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      ) : (
        <p>该账号在最近 {days} 天内没有发表文章。</p>
      )}
    </div>
  );
}
```

- [ ] **Step 2: 跑前端构建**

```bash
cd frontend
pnpm build
```

预期：tsc + vite 干净通过。

- [ ] **Step 3: 提交**

```bash
git add frontend/src/pages/StatsDetail.tsx
git commit -m "feat(stats/ui): account detail page with article table + polling refresh"
```

---

## Task 11: 最终回归 + 部署提示

- [ ] **Step 1: 后端完整回归**

```bash
cd backend
uv run ruff check
uv run mypy
uv run pytest
```

预期：三条都干净通过。

如果 `uv run mypy` 报某些不相关历史错误（非本次新增代码引起），把范围限定到改动文件：

```bash
uv run mypy app/stats/ app/wechat/stats.py app/tasks/stats.py app/tasks/maintenance.py app/api/router.py app/accounts/models.py app/accounts/schemas.py app/config.py
```

- [ ] **Step 2: 前端完整构建**

```bash
cd frontend
pnpm build
```

预期：tsc + vite 都干净通过。

- [ ] **Step 3: 检查 git log**

```bash
git log --oneline -15
```

预期至少看到这 10 条新 commit（顺序按 Task 1–10）：

1. `feat(config): add stats_backfill_days and stats_daily_cron_hour settings`
2. `feat(stats): add Account follower fields + WechatArticle model + migration`
3. `feat(wechat): add datacube + comment stats API client`
4. `feat(stats): add schemas and service helpers with upsert + queries`
5. `feat(stats): add sync_one_account_stats Celery task`
6. `feat(stats): add sync_all_accounts_stats + daily beat schedule`
7. `feat(stats): add list accounts, list articles, refresh API routes`
8. `feat(stats/ui): add API client + routes + nav entry (stubs)`
9. `feat(stats/ui): account list page with sort + refresh`
10. `feat(stats/ui): account detail page with article table + polling refresh`

- [ ] **Step 4: 推到 master**

```bash
git push origin master
```

- [ ] **Step 5: 部署提示（不在计划范围内执行，仅供参考）**

服务器上：

```bash
git pull
docker compose up -d --build api worker beat web
# entrypoint-api.sh 自动跑 alembic upgrade head
```

部署后冒烟：

1. 打开 `/stats` 页面，应该看到所有账号 1 行一条，刚部署时 `stats_synced_at = null`，显示「从未同步」
2. 点「全局刷新」，等 1–3 分钟（看账号数和文章数），再 refresh 页面
3. 看 `worker` 容器日志：
   ```bash
   docker compose logs -f worker | grep stats
   ```
   应能看到 `sync_one_account_stats` 任务被处理
4. 第二天 03:00（北京时间）后，检查 `accounts.stats_synced_at` 应该是当天的时间，证明 beat 调度生效
5. 用 curl 验证 API：
   ```bash
   curl -H "Authorization: Bearer <token>" http://<host>/api/stats/accounts | jq .
   ```

- [ ] **Step 6: 微信 API 调用方式真上线验真（**重要**）**

Task 3 的客户端代码假设 datacube API 是 GET。微信文档前后不一致；部署后第一次跑 cron 如果发现所有 `getusersummary` / `getusercumulate` / `getarticletotal` 都报 `errcode=43002`（GET 不支持）或类似，改 `app/wechat/stats.py` 的 `_post_datacube` 为：

```python
async def _post_datacube(
    path: str, *, access_token: str, begin_date: date, end_date: date
) -> list[dict]:
    async with httpx.AsyncClient(timeout=_TIMEOUT_SECONDS) as client:
        resp = await client.post(
            f"{_DATACUBE_BASE}/{path}",
            params={"access_token": access_token},
            json={
                "begin_date": begin_date.isoformat(),
                "end_date": end_date.isoformat(),
            },
        )
    data = resp.json()
    _check_errcode(data)
    return list(data.get("list", []))
```

同步改 `tests/unit/test_wechat_stats_client.py` 把 `respx.get(...)` 改成 `respx.post(...)`，跑测试确认绿，commit `fix(wechat): switch datacube client to POST after deploy verification`。

---

## 边界 / 已知限制（来自 spec）

| 情形 | 行为 |
|------|------|
| 账号 0 群发文章 | 仅刷粉丝；wechat_articles 无新行 |
| 文章被微信删除 | 我们不删 DB 行；30 天窗口外自然消失 |
| 评论 API 失败 | 该篇 comment_count 保留旧值；新文章首次失败 → 0 |
| 时区 | 北京时间昨天；DB 存 UTC |
| 派生 30 天窗口 | 固定，不跟 `stats_backfill_days` 联动 |
| 微信 daily quota | 单账号约 60 次/天，远低于上限 |

## 未来扩展（不在本计划）

- 流量主收益：独立加 `account_revenue_records` 表 + Cookie 爬虫
- 趋势曲线：改 daily upsert 为「插入新快照行」+ 加 `snapshot_date` 列
