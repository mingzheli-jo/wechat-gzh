# 草稿改写次数上限（每个草稿最多 5 次）实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 给 `Draft` 表新增 `regenerate_count` 字段，每次「重新改写」按钮触发自增 1；达 5 次后路由返回 409、前端按钮禁用并显示 `已达 5 次改写上限`。

**Architecture:** 后端单字段 + 单条 UPDATE 原子自增，路由侧加一个 409 守门；前端只改 `DraftDetail.tsx` 的按钮标签和 disabled 条件。无版本历史、无重置接口。

**Tech Stack:** Python 3.12 / FastAPI / SQLAlchemy 2.x async / Alembic / pydantic v2；React 18 / Vite / TanStack Query。后端用 `uv run`，前端用 `pnpm`。

**Spec:** `docs/superpowers/specs/2026-05-11-rewrite-cap-design.md`（commit `f4e3b5d`）

**Repo conventions:**
- 个人单用户项目，直接提交到 `master`，无 PR
- 严格 TDD：先写失败测试 → 跑确认 FAIL → 实现 → 跑确认 PASS → commit
- 后端每次改动后 `uv run pytest`、`uv run ruff check`、`uv run mypy` 全绿才能 commit
- 前端 `pnpm build` 必须 tsc + vite 都干净
- commit 风格 `feat:` / `fix:` / `test:` / `docs:`（已全局禁用 Co-Authored-By）
- 后端工作目录 `backend/`；前端工作目录 `frontend/`

---

## 文件结构

| 文件 | 动作 | 责任 |
|------|------|------|
| `backend/app/config.py` | 修改 | 新增 `draft_max_regenerations: int = 5` |
| `backend/app/drafts/models.py` | 修改 | 新增列 `regenerate_count: int` |
| `backend/app/drafts/service.py` | 修改 | `reset_for_rewrite` 在 UPDATE 里 `regenerate_count = regenerate_count + 1` |
| `backend/app/drafts/routes.py` | 修改 | `rewrite_again` 在状态校验后加 409 守门；`get_one` 在 model_validate 时注入 `max_regenerations` |
| `backend/app/drafts/schemas.py` | 修改 | `DraftOut.regenerate_count: int`；`DraftDetail.max_regenerations: int` |
| `backend/alembic/versions/<新文件>.py` | 新建 | 加 `regenerate_count` 列，server_default="0" |
| `backend/tests/unit/test_drafts_service.py` | 新建 | 验 `reset_for_rewrite` 自增计数器 |
| `backend/tests/integration/test_drafts_routes.py` | 新建 | 验 409 拦截 + 计数不再增 + 字段暴露 |
| `frontend/src/pages/DraftDetail.tsx` | 修改 | Detail type 加 2 个字段；按钮显示 (n/5)；到上限禁用 + 提示 |

---

## Task 1: 后端 Settings 增加 `draft_max_regenerations`

**Files:**
- Modify: `backend/app/config.py`
- Test: 无（trivial 配置项；通过 Task 4 的集成测试间接覆盖）

- [ ] **Step 1: 修改 `backend/app/config.py`**

在 `Settings` 类的 `rewrite_batch_max` 字段后面新增一行：

```python
    rewrite_batch_max: int = Field(default=20, ge=1, le=200)
    draft_max_regenerations: int = Field(default=5, ge=1, le=50)
```

注意：`Field` 已在文件顶部导入（`from pydantic import Field`），无需追加 import。

- [ ] **Step 2: 验证 lint / type 通过**

```bash
cd backend
uv run ruff check app/config.py
uv run mypy app/config.py
```

预期：两条命令都无输出（成功）。

- [ ] **Step 3: 提交**

```bash
git add backend/app/config.py
git commit -m "feat(config): add draft_max_regenerations setting (default 5)"
```

---

## Task 2: Draft 模型新增 `regenerate_count` 列

**Files:**
- Modify: `backend/app/drafts/models.py`
- Test: 通过 Task 3 的服务层测试间接覆盖

- [ ] **Step 1: 修改 `backend/app/drafts/models.py`**

在 `Draft` 类的 `error_msg` 字段**之后**（约第 52 行附近，位于 `wechat_media_id` 之前更合适，但顺序不影响功能）新增一行：

```python
    error_msg: Mapped[str | None] = mapped_column(Text, nullable=True)
    regenerate_count: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default="0"
    )
    wechat_media_id: Mapped[str | None] = mapped_column(String(200), nullable=True)
```

`Integer` 类型已在 `from sqlalchemy import DateTime, Enum, ForeignKey, Integer, String, Text, func` 中导入，无需追加。

- [ ] **Step 2: 跑现有测试确认模型变更不破坏既有套件**

```bash
cd backend
uv run pytest tests/unit/test_db_base.py tests/integration/test_rewrite_pipeline.py -v
```

预期：全部通过。testcontainers 在 fixture 里跑 `Base.metadata.create_all`，会自动把新列建出来。

- [ ] **Step 3: lint / type 检查**

```bash
uv run ruff check app/drafts/models.py
uv run mypy app/drafts/models.py
```

预期：无输出。

- [ ] **Step 4: 提交**

```bash
git add backend/app/drafts/models.py
git commit -m "feat(drafts): add regenerate_count column to Draft model"
```

---

## Task 3: 服务层 `reset_for_rewrite` 自增计数器（TDD）

**Files:**
- Modify: `backend/app/drafts/service.py:156-168`
- Test: `backend/tests/unit/test_drafts_service.py`（新建）

- [ ] **Step 1: 新建失败测试 `backend/tests/unit/test_drafts_service.py`**

整个文件内容：

```python
import uuid

import pytest

from app.accounts.models import Account
from app.drafts import service
from app.drafts.models import Draft, DraftStatus
from app.library.models import LibraryItem, LibraryStatus


async def _seed_draft(db_session, *, regenerate_count: int = 0) -> Draft:
    item = LibraryItem(
        source_url=f"https://x/{uuid.uuid4()}",
        original_title="原标题",
        original_content_text="原文 " * 30,
        status=LibraryStatus.done,
    )
    account = Account(
        name="A",
        wechat_appid="wx",
        wechat_secret="s",
        category="职场",
        title_prompt="t",
        content_prompt="c",
    )
    db_session.add_all([item, account])
    await db_session.commit()
    await db_session.refresh(item)
    await db_session.refresh(account)

    draft = Draft(
        library_item_id=item.id,
        account_id=account.id,
        status=DraftStatus.reviewed,
        title="旧标题",
        content_html="<p>旧正文</p>",
        regenerate_count=regenerate_count,
    )
    db_session.add(draft)
    await db_session.commit()
    await db_session.refresh(draft)
    return draft


@pytest.mark.asyncio
async def test_reset_for_rewrite_increments_regenerate_count(db_session):
    draft = await _seed_draft(db_session, regenerate_count=2)
    reset = await service.reset_for_rewrite(db_session, draft)
    assert reset.regenerate_count == 3


@pytest.mark.asyncio
async def test_reset_for_rewrite_clears_generated_fields(db_session):
    draft = await _seed_draft(db_session, regenerate_count=0)
    reset = await service.reset_for_rewrite(db_session, draft)
    assert reset.title is None
    assert reset.content_html is None
    assert reset.status == DraftStatus.draft
    assert reset.regenerate_count == 1
```

- [ ] **Step 2: 跑测试确认 FAIL**

```bash
cd backend
uv run pytest tests/unit/test_drafts_service.py -v
```

预期：`test_reset_for_rewrite_increments_regenerate_count` 失败，输出类似 `assert 2 == 3`；`test_reset_for_rewrite_clears_generated_fields` 失败在 `assert 0 == 1`。

- [ ] **Step 3: 修改 `backend/app/drafts/service.py` 加自增**

找到 `reset_for_rewrite` 中的 `await db.execute(update(Draft).where(...).values(...))` 块（当前约第 156–168 行），在 `values(...)` 内追加一行 `regenerate_count=Draft.regenerate_count + 1`：

```python
    await db.execute(
        update(Draft)
        .where(Draft.id == draft_id)
        .values(
            title=None,
            content_html=None,
            cover_image_id=None,
            error_msg=None,
            wechat_media_id=None,
            wechat_pushed_at=None,
            status=DraftStatus.draft,
            regenerate_count=Draft.regenerate_count + 1,
        )
    )
```

- [ ] **Step 4: 跑测试确认 PASS**

```bash
uv run pytest tests/unit/test_drafts_service.py -v
```

预期：两条测试都 PASS。

- [ ] **Step 5: lint / type / 全量回归**

```bash
uv run ruff check app/drafts/service.py tests/unit/test_drafts_service.py
uv run mypy app/drafts/service.py tests/unit/test_drafts_service.py
uv run pytest
```

预期：lint / mypy 无输出；pytest 全套通过。

- [ ] **Step 6: 提交**

```bash
git add backend/app/drafts/service.py backend/tests/unit/test_drafts_service.py
git commit -m "feat(drafts): increment regenerate_count in reset_for_rewrite"
```

---

## Task 4: 路由加 409 守门（TDD）

**Files:**
- Modify: `backend/app/drafts/routes.py:115-132`
- Test: `backend/tests/integration/test_drafts_routes.py`（新建）

- [ ] **Step 1: 新建失败测试 `backend/tests/integration/test_drafts_routes.py`**

整个文件内容（参考 `test_library_routes.py` 的 `auth_client` 用法）：

```python
import uuid

import pytest

from app.accounts.models import Account
from app.drafts.models import Draft, DraftStatus
from app.library.models import LibraryItem, LibraryStatus


@pytest.fixture(autouse=True)
def stub_rewrite_pipeline(monkeypatch):
    """阻止 Celery .delay() 真的派发任务。"""
    from app.tasks import rewrite as rewrite_module

    monkeypatch.setattr(
        rewrite_module.run_pipeline,
        "delay",
        lambda *a, **k: None,
        raising=False,
    )


async def _seed(db_session, *, status: DraftStatus, regenerate_count: int = 0) -> Draft:
    item = LibraryItem(
        source_url=f"https://x/{uuid.uuid4()}",
        original_title="原标题",
        original_content_text="原文 " * 30,
        status=LibraryStatus.done,
    )
    account = Account(
        name="A",
        wechat_appid="wx",
        wechat_secret="s",
        category="职场",
        title_prompt="t",
        content_prompt="c",
    )
    db_session.add_all([item, account])
    await db_session.commit()
    await db_session.refresh(item)
    await db_session.refresh(account)

    draft = Draft(
        library_item_id=item.id,
        account_id=account.id,
        status=status,
        title="旧标题",
        content_html="<p>旧正文</p>",
        regenerate_count=regenerate_count,
    )
    db_session.add(draft)
    await db_session.commit()
    await db_session.refresh(draft)
    return draft


async def test_rewrite_again_blocked_at_cap(auth_client, db_session):
    draft = await _seed(
        db_session, status=DraftStatus.reviewed, regenerate_count=5
    )
    r = await auth_client.post(f"/api/drafts/{draft.id}/rewrite")
    assert r.status_code == 409
    assert "已达 5 次改写上限" in r.json()["detail"]

    # 被拦截时计数不应再增
    await db_session.refresh(draft)
    assert draft.regenerate_count == 5


async def test_rewrite_again_increments_counter(auth_client, db_session):
    draft = await _seed(
        db_session, status=DraftStatus.reviewed, regenerate_count=2
    )
    r = await auth_client.post(f"/api/drafts/{draft.id}/rewrite")
    assert r.status_code == 202

    await db_session.refresh(draft)
    assert draft.regenerate_count == 3
```

- [ ] **Step 2: 跑测试确认 FAIL**

```bash
cd backend
uv run pytest tests/integration/test_drafts_routes.py -v
```

预期：`test_rewrite_again_blocked_at_cap` 失败 —— 当前路由返回 202 而不是 409。

- [ ] **Step 3: 修改 `backend/app/drafts/routes.py` 的 `rewrite_again`**

找到 `rewrite_again` 函数（约第 115–132 行），在 `obj.status == DraftStatus.published_to_wechat` 检查之后、`reset_for_rewrite` 之前，插入 cap 检查。最终函数体：

```python
@router.post("/{draft_id}/rewrite", response_model=DraftOut, status_code=202)
async def rewrite_again(
    draft_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    _: str = Depends(get_current_username),
) -> DraftOut:
    obj = await service.get_draft(db, draft_id)
    if obj is None:
        raise HTTPException(404, "Draft not found")
    if obj.status in (DraftStatus.draft, DraftStatus.reviewing):
        raise HTTPException(409, "进行中的草稿不能重写")
    if obj.status == DraftStatus.published_to_wechat:
        raise HTTPException(409, "已推送至微信的草稿不能重写")
    settings = get_settings()
    if obj.regenerate_count >= settings.draft_max_regenerations:
        raise HTTPException(
            409,
            f"已达 {settings.draft_max_regenerations} 次改写上限",
        )
    obj = await service.reset_for_rewrite(db, obj)
    from app.tasks.rewrite import run_pipeline

    run_pipeline.delay(str(obj.id), None, None)
    return DraftOut.model_validate(obj)
```

`get_settings` 已在文件顶部导入（`from app.config import get_settings`），无需追加。

- [ ] **Step 4: 跑测试确认 PASS**

```bash
uv run pytest tests/integration/test_drafts_routes.py -v
```

预期：两条测试都 PASS。

- [ ] **Step 5: lint / type / 全量回归**

```bash
uv run ruff check app/drafts/routes.py tests/integration/test_drafts_routes.py
uv run mypy app/drafts/routes.py tests/integration/test_drafts_routes.py
uv run pytest
```

预期：全部干净通过。

- [ ] **Step 6: 提交**

```bash
git add backend/app/drafts/routes.py backend/tests/integration/test_drafts_routes.py
git commit -m "feat(drafts): reject rewrite when regenerate_count hits cap"
```

---

## Task 5: Schemas 暴露 `regenerate_count` + `max_regenerations`（TDD）

**Files:**
- Modify: `backend/app/drafts/schemas.py`
- Modify: `backend/app/drafts/routes.py`（仅 `get_one` 端点）
- Test: 扩展 `backend/tests/integration/test_drafts_routes.py`

- [ ] **Step 1: 在测试文件末尾追加两条新测试**

向 `backend/tests/integration/test_drafts_routes.py` 末尾追加：

```python
async def test_rewrite_response_exposes_regenerate_count(auth_client, db_session):
    draft = await _seed(
        db_session, status=DraftStatus.reviewed, regenerate_count=1
    )
    r = await auth_client.post(f"/api/drafts/{draft.id}/rewrite")
    assert r.status_code == 202
    body = r.json()
    assert "regenerate_count" in body
    assert body["regenerate_count"] == 2


async def test_draft_detail_exposes_max_regenerations(auth_client, db_session):
    draft = await _seed(
        db_session, status=DraftStatus.reviewed, regenerate_count=0
    )
    r = await auth_client.get(f"/api/drafts/{draft.id}")
    assert r.status_code == 200
    body = r.json()
    assert body["regenerate_count"] == 0
    assert body["max_regenerations"] == 5
```

- [ ] **Step 2: 跑测试确认 FAIL**

```bash
cd backend
uv run pytest tests/integration/test_drafts_routes.py::test_rewrite_response_exposes_regenerate_count tests/integration/test_drafts_routes.py::test_draft_detail_exposes_max_regenerations -v
```

预期：两条都失败 —— `regenerate_count` / `max_regenerations` 不在响应里。

- [ ] **Step 3: 修改 `backend/app/drafts/schemas.py`**

把 `DraftOut` 加 `regenerate_count: int`，`DraftDetail` 加 `max_regenerations: int`。最终文件相关部分：

```python
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
    regenerate_count: int


class DraftDetail(DraftOut):
    content_html: str | None
    cover_image_id: uuid.UUID | None
    max_regenerations: int
```

- [ ] **Step 4: 修改 `backend/app/drafts/routes.py` 的 `get_one` 端点**

找到 `get_one`（约第 73–82 行），改成构造 dict 注入 `max_regenerations` 后再 validate：

```python
@router.get("/{draft_id}", response_model=DraftDetail)
async def get_one(
    draft_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    _: str = Depends(get_current_username),
) -> DraftDetail:
    obj = await service.get_draft(db, draft_id)
    if obj is None:
        raise HTTPException(404, "Draft not found")
    settings = get_settings()
    return DraftDetail.model_validate(
        {
            "id": obj.id,
            "library_item_id": obj.library_item_id,
            "account_id": obj.account_id,
            "title": obj.title,
            "status": obj.status,
            "error_msg": obj.error_msg,
            "review_report_id": obj.review_report_id,
            "wechat_pushed_at": obj.wechat_pushed_at,
            "created_at": obj.created_at,
            "regenerate_count": obj.regenerate_count,
            "content_html": obj.content_html,
            "cover_image_id": obj.cover_image_id,
            "max_regenerations": settings.draft_max_regenerations,
        }
    )
```

注：同文件中 `update` 端点也返回 `DraftDetail`，需要同样改造。把 `update` 端点最后一行 `return DraftDetail.model_validate(obj)` 替换为：

```python
    settings = get_settings()
    return DraftDetail.model_validate(
        {
            "id": obj.id,
            "library_item_id": obj.library_item_id,
            "account_id": obj.account_id,
            "title": obj.title,
            "status": obj.status,
            "error_msg": obj.error_msg,
            "review_report_id": obj.review_report_id,
            "wechat_pushed_at": obj.wechat_pushed_at,
            "created_at": obj.created_at,
            "regenerate_count": obj.regenerate_count,
            "content_html": obj.content_html,
            "cover_image_id": obj.cover_image_id,
            "max_regenerations": settings.draft_max_regenerations,
        }
    )
```

- [ ] **Step 5: 跑测试确认 PASS**

```bash
uv run pytest tests/integration/test_drafts_routes.py -v
```

预期：所有 4 条测试都 PASS。

- [ ] **Step 6: lint / type / 全量回归**

```bash
uv run ruff check app/drafts
uv run mypy app/drafts
uv run pytest
```

预期：全部干净通过。

- [ ] **Step 7: 提交**

```bash
git add backend/app/drafts/schemas.py backend/app/drafts/routes.py backend/tests/integration/test_drafts_routes.py
git commit -m "feat(drafts): expose regenerate_count and max_regenerations in API"
```

---

## Task 6: Alembic 迁移文件

**Files:**
- Create: `backend/alembic/versions/<生成的 hash>_add_regenerate_count_to_drafts.py`

- [ ] **Step 1: 用 alembic 生成迁移文件骨架**

```bash
cd backend
uv run alembic revision -m "add regenerate count to drafts"
```

预期：alembic 输出形如 `Generating .../alembic/versions/<hash>_add_regenerate_count_to_drafts.py ... done`。记下文件名。

如果 alembic 报错说连不上数据库，那是因为 `env.py` 走 `DATABASE_URL` 但本机 5432 被占用。`alembic revision`（不带 `--autogenerate`）实际上不需要连库，应该能直接生成。如果仍失败，临时设 env：

```bash
DATABASE_URL=postgresql+asyncpg://postgres:postgres@localhost:5433/dummy uv run alembic revision -m "add regenerate count to drafts"
```

- [ ] **Step 2: 编辑生成的文件**

把 `<hash>_add_regenerate_count_to_drafts.py` 的 `upgrade` / `downgrade` 替换为：

```python
"""add regenerate count to drafts

Revision ID: <alembic 自动填>
Revises: b3a7f1c2e8d9
Create Date: <alembic 自动填>

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


# revision identifiers, used by Alembic.
revision: str = "<alembic 自动填 — 不要改>"
down_revision: Union[str, Sequence[str], None] = "b3a7f1c2e8d9"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "drafts",
        sa.Column(
            "regenerate_count",
            sa.Integer(),
            nullable=False,
            server_default="0",
        ),
    )


def downgrade() -> None:
    op.drop_column("drafts", "regenerate_count")
```

**注意：**
- `revision` 这一行**保留 alembic 自动生成的值**，只改 `down_revision` 为 `b3a7f1c2e8d9`（当前 head）。
- 若 alembic 生成时自动填了别的 `down_revision`（应该是 `b3a7f1c2e8d9`，因为是当前 head），不用改；否则强制改成 `b3a7f1c2e8d9`。
- 不需要 `import app.db.encryption`（不涉及 EncryptedString）。

- [ ] **Step 3: 验证 alembic 迁移链完整**

```bash
uv run alembic history
```

预期：能看到链尾是新生成的 revision，前一个是 `b3a7f1c2e8d9`。

- [ ] **Step 4: 在真实 Postgres 上跑 upgrade（可选但推荐）**

如果本机有可用 Postgres：

```bash
DATABASE_URL=postgresql+asyncpg://app:app@localhost:5432/wechat uv run alembic upgrade head
```

预期：执行完毕，`drafts` 表多了 `regenerate_count` 列。可用 `\d drafts` 在 psql 里确认。

如果不方便跑，跳过此 step；docker compose 启动时 entrypoint 会自动跑 upgrade。

- [ ] **Step 5: lint / 回归**

```bash
uv run ruff check alembic/versions/
uv run pytest
```

预期：全部通过。

- [ ] **Step 6: 提交**

```bash
git add backend/alembic/versions/
git commit -m "feat(drafts): alembic migration for regenerate_count column"
```

---

## Task 7: 前端 DraftDetail 显示 `(n/5)` + 到上限禁用

**Files:**
- Modify: `frontend/src/pages/DraftDetail.tsx`

- [ ] **Step 1: 扩展本地 `Detail` type（约第 22–29 行）**

把现有的：

```tsx
type Detail = {
  id: string;
  title: string | null;
  content_html: string | null;
  status: string;
  review_report_id: string | null;
  error_msg: string | null;
};
```

改为：

```tsx
type Detail = {
  id: string;
  title: string | null;
  content_html: string | null;
  status: string;
  review_report_id: string | null;
  error_msg: string | null;
  regenerate_count: number;
  max_regenerations: number;
};
```

- [ ] **Step 2: 修改「重新改写」按钮（约第 759–781 行）**

把整个 `<Button variant="secondary" onClick={...}>...重新改写</Button>` 块替换为：

```tsx
        <Button
          variant="secondary"
          onClick={() => {
            if (window.confirm("将清空当前标题、正文、评审报告和图片,重新改写。是否继续?")) {
              rewriteAgain.mutate();
            }
          }}
          disabled={
            rewriteAgain.isPending ||
            detail.data.status === "draft" ||
            detail.data.status === "reviewing" ||
            detail.data.status === "published_to_wechat" ||
            detail.data.regenerate_count >= detail.data.max_regenerations
          }
          loading={rewriteAgain.isPending}
          style={{
            backgroundColor: "rgba(255,255,255,0.12)",
            color: "var(--color-white)",
            border: "1px solid rgba(255,255,255,0.2)",
            flexShrink: 0,
          }}
        >
          {rewriteAgain.isPending
            ? "重写中…"
            : `重新改写 (${detail.data.regenerate_count}/${detail.data.max_regenerations})`}
        </Button>
```

- [ ] **Step 3: 跑前端类型检查 + 构建**

```bash
cd frontend
pnpm build
```

预期：tsc + vite 都干净通过。

- [ ] **Step 4: （可选）本地手动验证**

如果当前有 dev server 在跑：打开任意一个 status=reviewed 的草稿，按钮文案应是 `重新改写 (0/5)`。

- [ ] **Step 5: 提交**

```bash
git add frontend/src/pages/DraftDetail.tsx
git commit -m "feat(drafts): show regenerate count and disable at cap in UI"
```

---

## Task 8: 最终回归 + 部署提示

- [ ] **Step 1: 后端完整回归**

```bash
cd backend
uv run ruff check
uv run mypy
uv run pytest
```

预期：三条都干净通过。

- [ ] **Step 2: 前端完整构建**

```bash
cd frontend
pnpm build
```

预期：通过。

- [ ] **Step 3: 检查 git 日志**

```bash
git log --oneline -10
```

预期至少看到这 7 条新 commit（顺序按 Task 1–7）：
1. `feat(config): add draft_max_regenerations setting (default 5)`
2. `feat(drafts): add regenerate_count column to Draft model`
3. `feat(drafts): increment regenerate_count in reset_for_rewrite`
4. `feat(drafts): reject rewrite when regenerate_count hits cap`
5. `feat(drafts): expose regenerate_count and max_regenerations in API`
6. `feat(drafts): alembic migration for regenerate_count column`
7. `feat(drafts): show regenerate count and disable at cap in UI`

- [ ] **Step 4: 部署提示（不在计划范围内执行，仅供参考）**

用户需要在服务器上：

```bash
git pull
docker compose up -d --build api worker web
# 容器内的 entrypoint-api.sh 会自动跑 alembic upgrade head
```

部署后冒烟：
1. 打开任意 status=reviewed 草稿，按钮显示 `重新改写 (0/5)`
2. 点 5 次（每次等 LLM 完成），第 6 次按钮已 disabled、文案为 `重新改写 (5/5)`
3. 用 curl 直接打接口确认 409：
   ```bash
   curl -X POST -H "Authorization: Bearer <token>" \
     http://<host>/api/drafts/<draft_id>/rewrite
   ```
   预期返回 `{"detail": "已达 5 次改写上限"}`。

---

## 边界情况备忘（来自 spec）

| 情形 | 计划中的行为 |
|------|-----------|
| LLM 失败 (status=failed) | 计数 +1（增量在 reset_for_rewrite 内，跑在 enqueue 之前） |
| 手动 PATCH /drafts/{id} | 不计数 |
| 推送到微信 | 不计数；不重置计数 |
| 现有数据迁移后 | `regenerate_count=0`（server_default） |
| 重复双击 | 后端不防抖，前端用 `isPending` disabled；单用户场景可接受 |
| 失败 + 已 5 次 | 返回 409，需删除并重建草稿 |

## 风险提示（来自 spec，不在本计划修复）

- 2026-05-08 留下的「重写后正文串别的文章」bug 未修。5 次上限会让该 bug 更难复现/诊断。建议如果遇到，临时在 `.env` 加 `DRAFT_MAX_REGENERATIONS=20`，bug 修完后再调回 5。
