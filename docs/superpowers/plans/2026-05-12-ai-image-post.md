# AI 场景图自动化生成实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 实现「主题 → AI 生成场景图 → 推送到微信公众号草稿箱」的完整子系统。

**Architecture:** 子系统独立模块 (`app/image_posts/`, `app/image_generator/`, `app/image_composer/`)，复用现有 Account / WeChat / Celery / 用量记录基础设施。两个 Celery task 串起 pipeline；前端新增「图片」顶级导航 + Canvas 实时叠字预览。

**Tech Stack:** Python 3.12 / FastAPI / SQLAlchemy 2.x async / Alembic / pydantic v2 / Pillow / httpx / Celery 5；React 18 / Vite / TypeScript / TanStack Query / HTML5 Canvas；豆包 Seedream 图像生成 API。

**Spec:** `docs/superpowers/specs/2026-05-12-ai-image-post-design.md`（commit `a632614`）

**Repo conventions:**
- 个人单用户项目，直接提交到 `master`，无 PR
- 严格 TDD：失败测试 → 跑确认 FAIL → 实现 → 跑确认 PASS → commit
- 后端每次改动后 `uv run pytest`、`uv run ruff check`、`uv run mypy <改动文件>` 全绿
- 前端 `pnpm build` 必须 tsc + vite 都干净
- commit 风格 `feat:` / `fix:` / `test:` / `docs:`
- 后端工作目录 `backend/`；前端工作目录 `frontend/`

---

## 文件结构

### Backend 新建

| 文件 | 责任 |
|---|---|
| `backend/app/image_generator/__init__.py` | 包 |
| `backend/app/image_generator/base.py` | `BaseImageProvider` 抽象 + `ImageGenRequest/Result` dataclass |
| `backend/app/image_generator/doubao.py` | `DoubaoImageProvider` 实现 |
| `backend/app/image_generator/factory.py` | `get_image_provider()` 工厂 |
| `backend/app/image_composer/__init__.py` | 包 |
| `backend/app/image_composer/compose.py` | Pillow 合成（拼图+叠字+水印） |
| `backend/app/image_composer/fonts/SourceHanSans-Bold.otf` | 中文字体（5 MB，提交进仓库） |
| `backend/app/image_posts/__init__.py` | 包 |
| `backend/app/image_posts/models.py` | `ImagePost` / `ImageAsset` / 两个 StrEnum |
| `backend/app/image_posts/schemas.py` | Pydantic schemas |
| `backend/app/image_posts/templates.py` | `TemplateConfig` + `TEMPLATES` dict |
| `backend/app/image_posts/service.py` | DB helpers |
| `backend/app/image_posts/routes.py` | API endpoints |
| `backend/app/image_assets/__init__.py` | 包 |
| `backend/app/image_assets/routes.py` | image_assets GET 端点 |
| `backend/app/tasks/image_pipeline.py` | `generate_image_post` + `compose_and_push_image_post` Celery tasks |
| `backend/alembic/versions/<hash>_add_image_post_tables.py` | 单 migration 文件 |
| `backend/tests/unit/test_image_templates.py` | TEMPLATES 单元测试 |
| `backend/tests/unit/test_image_composer.py` | Composer 单元测试 |
| `backend/tests/unit/test_doubao_provider.py` | DoubaoImageProvider 单元测试 |
| `backend/tests/integration/test_image_posts_routes.py` | 路由集成测试 |
| `backend/tests/integration/test_image_assets_routes.py` | image-assets 集成测试 |
| `backend/tests/integration/test_image_pipeline.py` | Celery pipeline 集成测试 |

### Backend 修改

| 文件 | 修改 |
|---|---|
| `backend/app/config.py` | 加 `doubao_api_key/base_url/image_model`, `image_posts_font_path` |
| `backend/app/accounts/models.py` | 加 `character_reference_path` / `character_reference_updated_at` |
| `backend/app/accounts/schemas.py` | 暴露上述字段 |
| `backend/app/accounts/routes.py` | 加 `POST/DELETE /accounts/{id}/character-reference` |
| `backend/app/api/router.py` | 注册 image_posts + image_assets 路由 |
| `backend/app/ai_providers/usage.py` | `record_usage()` 支持 `cost_cents`；新增 purpose 常量 |
| `.env.example` | 加豆包 env vars |
| `backend/pyproject.toml` | 加 `pillow` 依赖 |

### Frontend 新建

| 文件 | 责任 |
|---|---|
| `frontend/src/pages/ImagePosts.tsx` | 列表页 |
| `frontend/src/pages/ImagePostDetail.tsx` | 详情页 |
| `frontend/src/pages/ImageAssets.tsx` | 图库浏览页（只读） |
| `frontend/src/components/image-posts/CompositionCanvas.tsx` | Canvas 实时叠字渲染 |
| `frontend/src/components/image-posts/ImagePostFormModal.tsx` | 创建表单 modal |
| `frontend/src/components/image-posts/AssetPickerModal.tsx` | 图库选择 modal（阶段 2 用） |

### Frontend 修改

| 文件 | 修改 |
|---|---|
| `frontend/src/App.tsx` | 加 `/image-posts`, `/image-posts/:id`, `/image-assets` 路由 + 顶部导航 |
| `frontend/public/fonts/SourceHanSans-Bold.otf` | 复制字体到前端 public/ 供 Canvas 使用（运行时通过 CSS @font-face 加载） |

---

# 阶段 1：MVP（无图库复用）

预计 17 个 task，最终产出可端到端跑通的最简版本：填表单 → 后端出图 → UI 预览 → 推送到微信草稿箱。

## Task 1: Pillow 依赖 + 配置项 + 字体文件

**Files:**
- Modify: `backend/pyproject.toml`
- Modify: `backend/app/config.py`
- Modify: `.env.example`
- Create: `backend/app/image_composer/__init__.py`
- Create: `backend/app/image_composer/fonts/SourceHanSans-Bold.otf`

- [ ] **Step 1: 加 Pillow 依赖**

修改 `backend/pyproject.toml`，在 `[project] dependencies` 列表里追加 `"pillow>=10.0",`：

```toml
dependencies = [
    # ... 已有 ...
    "pillow>=10.0",
]
```

跑 `uv sync` 让锁文件更新：

```bash
cd backend
uv sync
```

- [ ] **Step 2: 下载思源黑体字体**

从开源镜像下载（免费商用，OFL License）：

```bash
mkdir -p backend/app/image_composer/fonts
curl -fL -o backend/app/image_composer/fonts/SourceHanSansSC-Bold.otf \
  "https://github.com/adobe-fonts/source-han-sans/raw/release/OTF/SimplifiedChinese/SourceHanSansSC-Bold.otf"
```

字体文件约 ~10 MB。建议在 `.gitignore` 同级目录加 `!fonts/*.otf` 确保不被忽略。

- [ ] **Step 3: 创建 image_composer 包占位**

```bash
mkdir -p backend/app/image_composer
echo '"""WeChat meme image composer (Pillow)."""' > backend/app/image_composer/__init__.py
```

- [ ] **Step 4: 加 settings 字段**

编辑 `backend/app/config.py`，在 `Settings` 类（保持已有字段顺序）追加：

```python
    # AI 图像生成（豆包 Seedream）
    doubao_api_key: str = ""
    doubao_base_url: str = "https://ark.cn-beijing.volces.com/api/v3"
    doubao_image_model: str = "doubao-seedream-3-0-t2i-250415"

    # AI 图像合成
    image_posts_font_path: str = "app/image_composer/fonts/SourceHanSansSC-Bold.otf"
```

- [ ] **Step 5: 更新 .env.example**

在 `.env.example` 末尾追加：

```bash
# AI Image Generation (Doubao Seedream)
DOUBAO_API_KEY=
DOUBAO_BASE_URL=https://ark.cn-beijing.volces.com/api/v3
DOUBAO_IMAGE_MODEL=doubao-seedream-3-0-t2i-250415

# AI Image Composition
IMAGE_POSTS_FONT_PATH=app/image_composer/fonts/SourceHanSansSC-Bold.otf
```

- [ ] **Step 6: 验证 lint + import**

```bash
cd backend
uv run ruff check app/config.py
uv run mypy app/config.py
uv run python -c "from app.image_composer import *"
uv run python -c "from app.config import get_settings; s=get_settings(); print(s.doubao_image_model)"
```

预期：lint/mypy 无输出，最后一行打印 `doubao-seedream-3-0-t2i-250415`。

- [ ] **Step 7: 提交**

```bash
git add backend/pyproject.toml backend/uv.lock backend/app/config.py \
  backend/app/image_composer/ .env.example
git commit -m "feat(image-posts): add Pillow dep + Doubao settings + font asset"
```

---

## Task 2: Account 加 `character_reference_path` 字段 + Migration

**Files:**
- Modify: `backend/app/accounts/models.py`
- Modify: `backend/app/accounts/schemas.py`
- Create: `backend/alembic/versions/<hash>_add_character_reference_to_accounts.py`

- [ ] **Step 1: Account 模型加 2 列**

在 `backend/app/accounts/models.py` 中，`default_thumb_media_id` 列**之后**插入：

```python
    default_thumb_media_id: Mapped[str | None] = mapped_column(
        String(200), nullable=True
    )
    character_reference_path: Mapped[str | None] = mapped_column(
        String(500), nullable=True
    )
    character_reference_updated_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
```

- [ ] **Step 2: 生成 migration**

```bash
cd backend
uv run alembic revision -m "add character_reference to accounts"
```

记下文件名（形如 `<hash>_add_character_reference_to_accounts.py`）。

- [ ] **Step 3: 编辑 migration**

把新生成的 migration 文件的 `upgrade` / `downgrade` 替换为：

```python
def upgrade() -> None:
    op.add_column(
        "accounts",
        sa.Column("character_reference_path", sa.String(length=500), nullable=True),
    )
    op.add_column(
        "accounts",
        sa.Column("character_reference_updated_at", sa.DateTime(timezone=True), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("accounts", "character_reference_updated_at")
    op.drop_column("accounts", "character_reference_path")
```

设置 `down_revision` 为当前 head（`uv run alembic history | head -1` 取最新 revision id）。

- [ ] **Step 4: 修复 ruff 警告**

```bash
uv run ruff check --fix alembic/versions/
```

预期：自动把 `Union[...]` / `from typing import Sequence` 转成现代风格。

- [ ] **Step 5: 暴露 schema 字段**

`backend/app/accounts/schemas.py`，`AccountOut` 末尾追加：

```python
    character_reference_path: str | None = None
    character_reference_updated_at: datetime | None = None
```

- [ ] **Step 6: 验证现有测试不破**

```bash
uv run pytest tests/integration/test_accounts_routes.py -v
```

预期：全部 PASS。

- [ ] **Step 7: lint + type**

```bash
uv run ruff check app/accounts alembic/versions/
uv run mypy app/accounts/models.py app/accounts/schemas.py
```

预期：无输出。

- [ ] **Step 8: 提交**

```bash
git add backend/app/accounts/models.py backend/app/accounts/schemas.py \
  backend/alembic/versions/
git commit -m "feat(accounts): add character_reference_path column + migration"
```

---

## Task 3: 角色参考图上传/清除端点（TDD）

**Files:**
- Modify: `backend/app/accounts/routes.py`
- Modify: `backend/tests/integration/test_accounts_routes.py`

- [ ] **Step 1: 追加失败测试**

在 `backend/tests/integration/test_accounts_routes.py` 末尾追加（仿照已有 `default-cover` 端点的测试结构）：

```python
async def test_upload_character_reference_success(auth_client, tmp_path, monkeypatch):
    monkeypatch.setenv("IMAGE_STORAGE_DIR", str(tmp_path))
    from app.config import get_settings
    get_settings.cache_clear()

    create = await auth_client.post(
        "/api/accounts",
        json={
            "name": "char-test",
            "wechat_appid": "wx_ch",
            "wechat_secret": "s",
            "category": "职场",
        },
    )
    account_id = create.json()["id"]
    files = {"file": ("char.png", b"\x89PNG\r\n\x1a\nfake", "image/png")}
    r = await auth_client.post(
        f"/api/accounts/{account_id}/character-reference", files=files
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["character_reference_path"]
    assert body["character_reference_updated_at"]


async def test_upload_character_reference_rejects_oversize(auth_client):
    create = await auth_client.post(
        "/api/accounts",
        json={"name": "big", "wechat_appid": "wx", "wechat_secret": "s", "category": "x"},
    )
    account_id = create.json()["id"]
    files = {"file": ("big.png", b"x" * (11 * 1024 * 1024), "image/png")}
    r = await auth_client.post(
        f"/api/accounts/{account_id}/character-reference", files=files
    )
    assert r.status_code == 413


async def test_upload_character_reference_rejects_non_image(auth_client):
    create = await auth_client.post(
        "/api/accounts",
        json={"name": "txt", "wechat_appid": "wx", "wechat_secret": "s", "category": "x"},
    )
    account_id = create.json()["id"]
    files = {"file": ("evil.txt", b"hello", "text/plain")}
    r = await auth_client.post(
        f"/api/accounts/{account_id}/character-reference", files=files
    )
    assert r.status_code == 415


async def test_clear_character_reference(auth_client, tmp_path, monkeypatch):
    monkeypatch.setenv("IMAGE_STORAGE_DIR", str(tmp_path))
    from app.config import get_settings
    get_settings.cache_clear()

    create = await auth_client.post(
        "/api/accounts",
        json={"name": "clear", "wechat_appid": "wx", "wechat_secret": "s", "category": "x"},
    )
    account_id = create.json()["id"]
    files = {"file": ("c.png", b"\x89PNG\r\n\x1a\nfake", "image/png")}
    await auth_client.post(
        f"/api/accounts/{account_id}/character-reference", files=files
    )
    r = await auth_client.delete(f"/api/accounts/{account_id}/character-reference")
    assert r.status_code == 200
    assert r.json()["character_reference_path"] is None
```

- [ ] **Step 2: 跑确认 FAIL**

```bash
cd backend
uv run pytest tests/integration/test_accounts_routes.py -k "character_reference" -v
```

预期：4 条 FAIL（端点不存在）。

- [ ] **Step 3: 实现端点**

在 `backend/app/accounts/routes.py`，紧挨现有 `clear_default_cover` 之后追加：

```python
_ALLOWED_CHAR_REF_MIME = {
    "image/jpeg",
    "image/jpg",
    "image/png",
}


@router.post("/{account_id}/character-reference", response_model=AccountOut)
async def upload_character_reference(
    account_id: uuid.UUID,
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
    _: str = Depends(get_current_username),
) -> AccountOut:
    from datetime import UTC, datetime

    obj = await service.get_account(db, account_id)
    if obj is None:
        raise HTTPException(404, "Account not found")
    if file.content_type not in _ALLOWED_CHAR_REF_MIME:
        raise HTTPException(415, f"不支持的图片格式: {file.content_type}")
    content = await file.read()
    if not content:
        raise HTTPException(400, "上传文件为空")
    if len(content) > _MAX_COVER_BYTES:
        raise HTTPException(
            413, f"图片超过 {_MAX_COVER_BYTES // 1024 // 1024}MB 限制"
        )

    settings = get_settings()
    storage_dir = Path(settings.image_storage_dir) / "accounts" / str(obj.id)
    storage_dir.mkdir(parents=True, exist_ok=True)
    suffix = Path(file.filename or "char.png").suffix or ".png"
    target = storage_dir / f"character{suffix}"
    target.write_bytes(content)

    obj.character_reference_path = str(target)
    obj.character_reference_updated_at = datetime.now(UTC)
    await db.commit()
    await db.refresh(obj)
    return AccountOut.model_validate(obj)


@router.delete("/{account_id}/character-reference", response_model=AccountOut)
async def clear_character_reference(
    account_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    _: str = Depends(get_current_username),
) -> AccountOut:
    obj = await service.get_account(db, account_id)
    if obj is None:
        raise HTTPException(404, "Account not found")
    if obj.character_reference_path:
        Path(obj.character_reference_path).unlink(missing_ok=True)
    obj.character_reference_path = None
    obj.character_reference_updated_at = None
    await db.commit()
    await db.refresh(obj)
    return AccountOut.model_validate(obj)
```

文件顶部如果还没 `from app.config import get_settings`，添加它。

- [ ] **Step 4: 跑测试确认 PASS**

```bash
uv run pytest tests/integration/test_accounts_routes.py -v
```

预期：所有 accounts 测试通过（约 9 + 4 = 13 条）。

- [ ] **Step 5: lint / type**

```bash
uv run ruff check app/accounts/routes.py tests/integration/test_accounts_routes.py
uv run mypy app/accounts/routes.py
```

预期：无输出。

- [ ] **Step 6: 提交**

```bash
git add backend/app/accounts/routes.py backend/tests/integration/test_accounts_routes.py
git commit -m "feat(accounts): endpoints to upload/clear character reference image"
```

---

## Task 4: ImagePost / ImageAsset 模型 + Migration

**Files:**
- Create: `backend/app/image_posts/__init__.py`
- Create: `backend/app/image_posts/models.py`
- Create: `backend/alembic/versions/<hash>_create_image_post_tables.py`

- [ ] **Step 1: 创建 image_posts 包**

```bash
mkdir -p backend/app/image_posts
echo '"""AI image post generation subsystem."""' > backend/app/image_posts/__init__.py
```

- [ ] **Step 2: 写 models**

创建 `backend/app/image_posts/models.py`：

```python
import enum
import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import (
    DateTime,
    Enum,
    ForeignKey,
    Integer,
    String,
    Text,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class ImagePostTemplate(enum.StrEnum):
    two_panel_contrast = "two_panel_contrast"
    single_panel_caption = "single_panel_caption"


class ImagePostStatus(enum.StrEnum):
    pending = "pending"
    generating = "generating"
    generated = "generated"
    composing = "composing"
    pushing = "pushing"
    pushed = "pushed"
    failed = "failed"


class ImageAssetSource(enum.StrEnum):
    ai_generated = "ai_generated"
    manual_upload = "manual_upload"


class ImagePost(Base):
    __tablename__ = "image_posts"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    account_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("accounts.id", ondelete="CASCADE"),
        nullable=False,
    )
    template: Mapped[ImagePostTemplate] = mapped_column(
        Enum(ImagePostTemplate, name="image_post_template"), nullable=False
    )
    topic: Mapped[str] = mapped_column(Text, nullable=False)
    tone: Mapped[str | None] = mapped_column(String(50), nullable=True)
    status: Mapped[ImagePostStatus] = mapped_column(
        Enum(ImagePostStatus, name="image_post_status"),
        nullable=False,
        default=ImagePostStatus.pending,
    )
    captions: Mapped[list[str] | None] = mapped_column(JSONB, nullable=True)
    panel_prompts: Mapped[list[str] | None] = mapped_column(JSONB, nullable=True)
    asset_ids: Mapped[list[str] | None] = mapped_column(JSONB, nullable=True)
    panel_asset_ids: Mapped[list[str] | None] = mapped_column(JSONB, nullable=True)
    composed_image_path: Mapped[str | None] = mapped_column(Text, nullable=True)
    wechat_thumb_media_id: Mapped[str | None] = mapped_column(String(200), nullable=True)
    wechat_draft_media_id: Mapped[str | None] = mapped_column(String(200), nullable=True)
    wechat_pushed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    error_msg: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class ImageAsset(Base):
    __tablename__ = "image_assets"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    account_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("accounts.id", ondelete="CASCADE"),
        nullable=False,
    )
    image_path: Mapped[str] = mapped_column(Text, nullable=False)
    scene_prompt: Mapped[str | None] = mapped_column(Text, nullable=True)
    tags: Mapped[list[str] | None] = mapped_column(JSONB, nullable=True)
    source: Mapped[ImageAssetSource] = mapped_column(
        Enum(ImageAssetSource, name="image_asset_source"),
        nullable=False,
        default=ImageAssetSource.ai_generated,
    )
    used_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
```

- [ ] **Step 3: 生成 migration**

```bash
cd backend
uv run alembic revision -m "create image post tables"
```

- [ ] **Step 4: 编辑 migration**

替换新文件 `upgrade()` / `downgrade()`：

```python
def upgrade() -> None:
    image_post_template = sa.Enum(
        "two_panel_contrast", "single_panel_caption",
        name="image_post_template",
    )
    image_post_status = sa.Enum(
        "pending", "generating", "generated",
        "composing", "pushing", "pushed", "failed",
        name="image_post_status",
    )
    image_asset_source = sa.Enum(
        "ai_generated", "manual_upload",
        name="image_asset_source",
    )
    image_post_template.create(op.get_bind(), checkfirst=False)
    image_post_status.create(op.get_bind(), checkfirst=False)
    image_asset_source.create(op.get_bind(), checkfirst=False)

    op.create_table(
        "image_posts",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("account_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("accounts.id", ondelete="CASCADE"), nullable=False),
        sa.Column("template", image_post_template, nullable=False),
        sa.Column("topic", sa.Text(), nullable=False),
        sa.Column("tone", sa.String(50), nullable=True),
        sa.Column("status", image_post_status, nullable=False,
                  server_default="pending"),
        sa.Column("captions", postgresql.JSONB(), nullable=True),
        sa.Column("panel_prompts", postgresql.JSONB(), nullable=True),
        sa.Column("asset_ids", postgresql.JSONB(), nullable=True),
        sa.Column("panel_asset_ids", postgresql.JSONB(), nullable=True),
        sa.Column("composed_image_path", sa.Text(), nullable=True),
        sa.Column("wechat_thumb_media_id", sa.String(200), nullable=True),
        sa.Column("wechat_draft_media_id", sa.String(200), nullable=True),
        sa.Column("wechat_pushed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("error_msg", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True),
                  server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True),
                  server_default=sa.func.now(), nullable=False),
    )

    op.create_table(
        "image_assets",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("account_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("accounts.id", ondelete="CASCADE"), nullable=False),
        sa.Column("image_path", sa.Text(), nullable=False),
        sa.Column("scene_prompt", sa.Text(), nullable=True),
        sa.Column("tags", postgresql.JSONB(), nullable=True),
        sa.Column("source", image_asset_source, nullable=False,
                  server_default="ai_generated"),
        sa.Column("used_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True),
                  server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_image_posts_account_id", "image_posts", ["account_id"])
    op.create_index("ix_image_assets_account_id", "image_assets", ["account_id"])


def downgrade() -> None:
    op.drop_index("ix_image_assets_account_id")
    op.drop_index("ix_image_posts_account_id")
    op.drop_table("image_assets")
    op.drop_table("image_posts")
    op.execute("DROP TYPE image_asset_source")
    op.execute("DROP TYPE image_post_status")
    op.execute("DROP TYPE image_post_template")
```

migration 文件顶部需要 `from sqlalchemy.dialects import postgresql`。

- [ ] **Step 5: ruff fix migration**

```bash
uv run ruff check --fix alembic/versions/
```

- [ ] **Step 6: 验证 import + alembic history**

```bash
uv run python -c "from app.image_posts.models import ImagePost, ImageAsset; print('ok')"
uv run alembic history | head -3
```

- [ ] **Step 7: 跑测试确认现有功能不破**

```bash
uv run pytest tests/integration/test_accounts_routes.py tests/integration/test_drafts_routes.py -v
```

预期：所有现有测试通过。新表通过 `Base.metadata.create_all` 自动建出来。

- [ ] **Step 8: lint / type**

```bash
uv run ruff check app/image_posts/ alembic/versions/
uv run mypy app/image_posts/models.py
```

- [ ] **Step 9: 提交**

```bash
git add backend/app/image_posts/ backend/alembic/versions/
git commit -m "feat(image-posts): add ImagePost + ImageAsset models + migration"
```

---

## Task 5: Templates 配置 + 测试

**Files:**
- Create: `backend/app/image_posts/templates.py`
- Create: `backend/tests/unit/test_image_templates.py`

- [ ] **Step 1: 写失败测试**

`backend/tests/unit/test_image_templates.py`：

```python
import pytest

from app.image_posts.models import ImagePostTemplate
from app.image_posts.templates import TEMPLATES, TemplateConfig


def test_templates_has_two_panel_contrast():
    assert ImagePostTemplate.two_panel_contrast in TEMPLATES
    cfg = TEMPLATES[ImagePostTemplate.two_panel_contrast]
    assert cfg.panel_count == 2
    assert cfg.caption_count == 2


def test_templates_has_single_panel_caption():
    assert ImagePostTemplate.single_panel_caption in TEMPLATES
    cfg = TEMPLATES[ImagePostTemplate.single_panel_caption]
    assert cfg.panel_count == 1
    assert cfg.caption_count == 1


def test_caption_prompt_format_contains_topic_and_tone():
    cfg = TEMPLATES[ImagePostTemplate.two_panel_contrast]
    prompt = cfg.caption_prompt_template.format(topic="测试主题", tone="自嘲")
    assert "测试主题" in prompt
    assert "自嘲" in prompt


def test_template_config_is_frozen():
    cfg = TEMPLATES[ImagePostTemplate.two_panel_contrast]
    with pytest.raises((AttributeError, Exception)):
        cfg.panel_count = 99  # type: ignore[misc]
```

- [ ] **Step 2: 跑确认 FAIL**

```bash
cd backend
uv run pytest tests/unit/test_image_templates.py -v
```

预期：ImportError（templates 模块不存在）。

- [ ] **Step 3: 写 templates 模块**

`backend/app/image_posts/templates.py`：

```python
"""Image post template configurations (caption prompts + composition layout)."""
from dataclasses import dataclass
from typing import Literal

from app.image_posts.models import ImagePostTemplate


@dataclass(frozen=True)
class TemplateConfig:
    key: ImagePostTemplate
    panel_count: int
    caption_count: int
    caption_max_chars: int
    caption_prompt_template: str
    composition: Literal["vertical_stack", "single"]
    caption_position: Literal["top_of_each_panel", "top_of_image"]
    output_size: tuple[int, int]      # (width, height)
    font_size_ratio: float


TWO_PANEL_CONTRAST_PROMPT = """你是一名公众号表情包文案作者。基于主题，生成两条对比/反差文案。

主题：{topic}
语气：{tone}
要求：
- 每条 8-14 个汉字
- 上下两条形成「前后/对立/反讽」结构
- 通俗、口语化、有梗
- 同时给出每格的英文场景描述（用于 AI 出图，要包含角色、动作、环境）

输出 JSON：
{{
  "captions": ["上文案", "下文案"],
  "scene_prompts": ["panel 1 scene in English", "panel 2 scene in English"]
}}
"""

SINGLE_PANEL_CAPTION_PROMPT = """你是一名公众号金句作者。基于主题，生成一句扎心/共鸣/自嘲的金句。

主题：{topic}
语气：{tone}
要求：
- 12-20 个汉字
- 单句独立成立，无需对仗
- 适合做封面大字
- 同时给出对应英文场景描述（用于 AI 出图，要包含角色、动作、情绪）

输出 JSON：
{{
  "captions": ["金句"],
  "scene_prompts": ["scene in English"]
}}
"""


TEMPLATES: dict[ImagePostTemplate, TemplateConfig] = {
    ImagePostTemplate.two_panel_contrast: TemplateConfig(
        key=ImagePostTemplate.two_panel_contrast,
        panel_count=2,
        caption_count=2,
        caption_max_chars=14,
        caption_prompt_template=TWO_PANEL_CONTRAST_PROMPT,
        composition="vertical_stack",
        caption_position="top_of_each_panel",
        output_size=(750, 1600),
        font_size_ratio=0.06,
    ),
    ImagePostTemplate.single_panel_caption: TemplateConfig(
        key=ImagePostTemplate.single_panel_caption,
        panel_count=1,
        caption_count=1,
        caption_max_chars=20,
        caption_prompt_template=SINGLE_PANEL_CAPTION_PROMPT,
        composition="single",
        caption_position="top_of_image",
        output_size=(1024, 1280),
        font_size_ratio=0.10,
    ),
}
```

- [ ] **Step 4: 跑测试确认 PASS**

```bash
uv run pytest tests/unit/test_image_templates.py -v
```

预期：4 条通过。

- [ ] **Step 5: lint / type**

```bash
uv run ruff check app/image_posts/templates.py tests/unit/test_image_templates.py
uv run mypy app/image_posts/templates.py
```

- [ ] **Step 6: 提交**

```bash
git add backend/app/image_posts/templates.py backend/tests/unit/test_image_templates.py
git commit -m "feat(image-posts): add TemplateConfig + 2 v1 templates"
```

---

## Task 6: ImageProvider 抽象 + Doubao 实现（TDD）

**Files:**
- Create: `backend/app/image_generator/__init__.py`
- Create: `backend/app/image_generator/base.py`
- Create: `backend/app/image_generator/doubao.py`
- Create: `backend/app/image_generator/factory.py`
- Create: `backend/tests/unit/test_doubao_provider.py`

- [ ] **Step 1: 创建包**

```bash
mkdir -p backend/app/image_generator
echo '"""AI image generation providers (Doubao Seedream et al)."""' > backend/app/image_generator/__init__.py
```

- [ ] **Step 2: 写 base.py**

`backend/app/image_generator/base.py`：

```python
"""Image provider abstraction."""
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any


@dataclass
class ImageGenRequest:
    prompt: str
    reference_image_b64: str | None = None
    size: str = "1024x1024"
    negative_prompt: str | None = None


@dataclass
class ImageGenResult:
    url: str
    raw: dict[str, Any] = field(default_factory=dict)


class BaseImageProvider(ABC):
    name: str

    @abstractmethod
    async def generate(self, req: ImageGenRequest) -> ImageGenResult: ...
```

- [ ] **Step 3: 写失败测试 (Doubao)**

`backend/tests/unit/test_doubao_provider.py`：

```python
import httpx
import pytest
import respx

from app.image_generator.base import ImageGenRequest
from app.image_generator.doubao import DoubaoImageProvider


@pytest.mark.asyncio
async def test_doubao_generate_text_only():
    provider = DoubaoImageProvider(
        api_key="test_key",
        base_url="https://ark.cn-beijing.volces.com/api/v3",
        model="doubao-seedream-3-0-t2i-250415",
    )
    async with respx.mock() as mock:
        mock.post(
            "https://ark.cn-beijing.volces.com/api/v3/images/generations"
        ).mock(
            return_value=httpx.Response(
                200,
                json={
                    "data": [{"url": "https://cdn.ark/img1.png"}],
                    "usage": {"generated_images": 1},
                },
            )
        )
        result = await provider.generate(
            ImageGenRequest(
                prompt="a cute capybara at desk",
                negative_prompt="text, captions",
            )
        )
    assert result.url == "https://cdn.ark/img1.png"
    assert "data" in result.raw


@pytest.mark.asyncio
async def test_doubao_generate_with_reference_image():
    provider = DoubaoImageProvider(
        api_key="k", base_url="https://x", model="m",
    )
    captured: dict = {}
    async with respx.mock() as mock:
        def _capture(req):
            import json as _json
            captured.update(_json.loads(req.content))
            return httpx.Response(200, json={"data": [{"url": "https://x/y.png"}]})
        mock.post("https://x/images/generations").mock(side_effect=_capture)
        await provider.generate(
            ImageGenRequest(prompt="p", reference_image_b64="BASE64DATA"),
        )
    assert "image" in captured
    assert captured["image"].startswith("data:image/png;base64,")


@pytest.mark.asyncio
async def test_doubao_generate_raises_on_error():
    from app.image_generator.doubao import DoubaoImageError

    provider = DoubaoImageProvider(api_key="k", base_url="https://x", model="m")
    async with respx.mock() as mock:
        mock.post("https://x/images/generations").mock(
            return_value=httpx.Response(
                400, json={"error": {"message": "invalid prompt"}}
            )
        )
        with pytest.raises(DoubaoImageError):
            await provider.generate(ImageGenRequest(prompt="bad"))
```

- [ ] **Step 4: 跑确认 FAIL**

```bash
cd backend
uv run pytest tests/unit/test_doubao_provider.py -v
```

预期：ImportError。

- [ ] **Step 5: 写 doubao.py**

`backend/app/image_generator/doubao.py`：

```python
"""Doubao Seedream image provider."""
from typing import Any

import httpx

from app.image_generator.base import (
    BaseImageProvider,
    ImageGenRequest,
    ImageGenResult,
)


class DoubaoImageError(Exception):
    pass


class DoubaoImageProvider(BaseImageProvider):
    name = "doubao"

    def __init__(self, *, api_key: str, base_url: str, model: str) -> None:
        self._api_key = api_key
        self._base_url = base_url.rstrip("/")
        self._model = model

    async def generate(self, req: ImageGenRequest) -> ImageGenResult:
        payload: dict[str, Any] = {
            "model": self._model,
            "prompt": req.prompt,
            "size": req.size,
            "response_format": "url",
        }
        if req.reference_image_b64:
            payload["image"] = f"data:image/png;base64,{req.reference_image_b64}"
        if req.negative_prompt:
            payload["negative_prompt"] = req.negative_prompt

        url = f"{self._base_url}/images/generations"
        headers = {
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type": "application/json",
        }
        async with httpx.AsyncClient(timeout=120) as client:
            resp = await client.post(url, json=payload, headers=headers)
        data = resp.json()
        if resp.status_code >= 400 or "error" in data:
            msg = data.get("error", {}).get("message") if isinstance(data, dict) else str(data)
            raise DoubaoImageError(f"doubao API failed: {msg} (status={resp.status_code})")
        if "data" not in data or not data["data"]:
            raise DoubaoImageError(f"unexpected response: {data}")
        image_url = data["data"][0].get("url")
        if not image_url:
            raise DoubaoImageError(f"no url in response: {data}")
        return ImageGenResult(url=image_url, raw=data)
```

- [ ] **Step 6: 写 factory.py**

`backend/app/image_generator/factory.py`：

```python
"""Image provider factory."""
from app.config import get_settings
from app.image_generator.base import BaseImageProvider
from app.image_generator.doubao import DoubaoImageProvider


def get_image_provider() -> BaseImageProvider:
    settings = get_settings()
    return DoubaoImageProvider(
        api_key=settings.doubao_api_key,
        base_url=settings.doubao_base_url,
        model=settings.doubao_image_model,
    )
```

- [ ] **Step 7: 跑测试确认 PASS**

```bash
uv run pytest tests/unit/test_doubao_provider.py -v
```

预期：3 条 PASS。

- [ ] **Step 8: lint / type**

```bash
uv run ruff check app/image_generator/ tests/unit/test_doubao_provider.py
uv run mypy app/image_generator/
```

- [ ] **Step 9: 提交**

```bash
git add backend/app/image_generator/ backend/tests/unit/test_doubao_provider.py
git commit -m "feat(image-gen): add BaseImageProvider abstraction + Doubao Seedream impl"
```

---

## Task 7: Composer — 双格反差（TDD）

**Files:**
- Create: `backend/app/image_composer/compose.py`
- Create: `backend/tests/unit/test_image_composer.py`

- [ ] **Step 1: 写失败测试**

`backend/tests/unit/test_image_composer.py`：

```python
from pathlib import Path

import pytest
from PIL import Image

from app.image_composer.compose import compose
from app.image_posts.models import ImagePostTemplate
from app.image_posts.templates import TEMPLATES


@pytest.fixture
def font_path() -> Path:
    return Path("app/image_composer/fonts/SourceHanSansSC-Bold.otf")


@pytest.fixture
def fake_panel(tmp_path) -> Path:
    """Create a simple solid-color square as a fake panel image."""
    img = Image.new("RGB", (1024, 1024), color=(200, 150, 100))
    p = tmp_path / "panel.png"
    img.save(p)
    return p


def test_compose_two_panel_contrast_produces_output(
    tmp_path, fake_panel, font_path
):
    template = TEMPLATES[ImagePostTemplate.two_panel_contrast]
    panel_paths = [fake_panel, fake_panel]
    captions = ["上文案", "下文案"]
    output = tmp_path / "out.png"
    compose(
        template=template,
        panel_paths=panel_paths,
        captions=captions,
        watermark="公众号·测试",
        font_path=font_path,
        output_path=output,
    )
    assert output.exists()
    img = Image.open(output)
    assert img.size == template.output_size
    assert img.mode == "RGB"


def test_compose_truncates_overly_long_caption(
    tmp_path, fake_panel, font_path
):
    template = TEMPLATES[ImagePostTemplate.two_panel_contrast]
    long_caption = "这是一个特别长的文案" * 10  # 100 字
    output = tmp_path / "long.png"
    # 不应抛异常
    compose(
        template=template,
        panel_paths=[fake_panel, fake_panel],
        captions=[long_caption, "短"],
        watermark="wm",
        font_path=font_path,
        output_path=output,
    )
    assert output.exists()
```

- [ ] **Step 2: 跑确认 FAIL**

```bash
cd backend
uv run pytest tests/unit/test_image_composer.py -v
```

预期：ImportError。

- [ ] **Step 3: 实现 compose.py**

`backend/app/image_composer/compose.py`：

```python
"""Pillow-based composition for AI image posts."""
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

from app.image_posts.templates import TemplateConfig

_PANEL_MARGIN_RATIO = 0.03
_CAPTION_VERTICAL_PADDING_RATIO = 0.02
_WATERMARK_FONT_RATIO = 0.018


def compose(
    *,
    template: TemplateConfig,
    panel_paths: list[Path],
    captions: list[str],
    watermark: str,
    font_path: Path,
    output_path: Path,
) -> None:
    if template.composition == "vertical_stack":
        _compose_vertical_stack(
            template, panel_paths, captions, watermark, font_path, output_path
        )
    elif template.composition == "single":
        _compose_single(
            template, panel_paths[0], captions[0], watermark, font_path, output_path
        )
    else:
        raise ValueError(f"unknown composition: {template.composition}")


def _measure_text_width(font: ImageFont.FreeTypeFont, text: str) -> int:
    bbox = font.getbbox(text)
    return bbox[2] - bbox[0]


def _fit_caption_to_width(
    font_path: Path, base_size: int, text: str, max_width: int
) -> tuple[ImageFont.FreeTypeFont, str]:
    """Shrink font and/or truncate so text fits in max_width."""
    size = base_size
    while size > 14:
        font = ImageFont.truetype(str(font_path), size)
        if _measure_text_width(font, text) <= max_width:
            return font, text
        size -= 2
    font = ImageFont.truetype(str(font_path), size)
    while text and _measure_text_width(font, text + "…") > max_width:
        text = text[:-1]
    return font, (text + "…" if text else "")


def _compose_vertical_stack(
    template: TemplateConfig,
    panel_paths: list[Path],
    captions: list[str],
    watermark: str,
    font_path: Path,
    output_path: Path,
) -> None:
    """[caption1][panel1][caption2][panel2][watermark]"""
    width, height = template.output_size
    panel_count = template.panel_count
    base_font_size = int(width * template.font_size_ratio)

    margin = int(width * _PANEL_MARGIN_RATIO)
    panel_w = width - 2 * margin
    panel_h = panel_w  # 正方形 panel
    caption_band_h = int(base_font_size * 2.2)  # 留单行余量
    watermark_h = int(base_font_size * 1.2)

    total_content_h = (caption_band_h + panel_h) * panel_count + watermark_h
    bg_color = (255, 255, 255)
    canvas = Image.new("RGB", (width, height), bg_color)

    if total_content_h > height:
        # 等比缩 panel
        avail_for_panels = height - watermark_h - caption_band_h * panel_count
        panel_h = max(50, avail_for_panels // panel_count)
        total_content_h = (caption_band_h + panel_h) * panel_count + watermark_h

    start_y = (height - total_content_h) // 2
    y = max(0, start_y)
    draw = ImageDraw.Draw(canvas)

    for i in range(panel_count):
        caption = captions[i] if i < len(captions) else ""
        font, fitted = _fit_caption_to_width(
            font_path, base_font_size, caption, int(width * 0.9)
        )
        text_w = _measure_text_width(font, fitted)
        text_x = (width - text_w) // 2
        text_y = y + (caption_band_h - font.size) // 2
        draw.text((text_x, text_y), fitted, font=font, fill=(20, 20, 20))
        y += caption_band_h

        panel = Image.open(panel_paths[i]).convert("RGB")
        panel = panel.resize((panel_w, panel_h), Image.Resampling.LANCZOS)
        canvas.paste(panel, (margin, y))
        y += panel_h

    # Watermark — half-transparent gray
    wm_size = max(10, int(width * _WATERMARK_FONT_RATIO))
    wm_font = ImageFont.truetype(str(font_path), wm_size)
    wm_w = _measure_text_width(wm_font, watermark)
    wm_x = (width - wm_w) // 2
    wm_y = height - watermark_h + (watermark_h - wm_size) // 2
    draw.text((wm_x, wm_y), watermark, font=wm_font, fill=(160, 160, 160))

    canvas.save(output_path, format="PNG")


def _compose_single(
    template: TemplateConfig,
    panel_path: Path,
    caption: str,
    watermark: str,
    font_path: Path,
    output_path: Path,
) -> None:
    """[big caption][panel][watermark]"""
    width, height = template.output_size
    base_font_size = int(width * template.font_size_ratio)

    margin = int(width * _PANEL_MARGIN_RATIO)
    panel_w = width - 2 * margin
    panel_h = panel_w
    caption_band_h = int(base_font_size * 2.5)
    watermark_h = int(base_font_size * 0.8)

    total_h = caption_band_h + panel_h + watermark_h
    if total_h > height:
        panel_h = max(50, height - caption_band_h - watermark_h)
        total_h = caption_band_h + panel_h + watermark_h

    start_y = (height - total_h) // 2
    y = max(0, start_y)

    canvas = Image.new("RGB", (width, height), (255, 255, 255))
    draw = ImageDraw.Draw(canvas)

    font, fitted = _fit_caption_to_width(
        font_path, base_font_size, caption, int(width * 0.9)
    )
    text_w = _measure_text_width(font, fitted)
    text_x = (width - text_w) // 2
    text_y = y + (caption_band_h - font.size) // 2
    draw.text((text_x, text_y), fitted, font=font, fill=(20, 20, 20))
    y += caption_band_h

    panel = Image.open(panel_path).convert("RGB")
    panel = panel.resize((panel_w, panel_h), Image.Resampling.LANCZOS)
    canvas.paste(panel, (margin, y))
    y += panel_h

    wm_size = max(10, int(width * _WATERMARK_FONT_RATIO))
    wm_font = ImageFont.truetype(str(font_path), wm_size)
    wm_w = _measure_text_width(wm_font, watermark)
    wm_x = (width - wm_w) // 2
    wm_y = y + (watermark_h - wm_size) // 2
    draw.text((wm_x, wm_y), watermark, font=wm_font, fill=(160, 160, 160))

    canvas.save(output_path, format="PNG")
```

- [ ] **Step 4: 跑测试确认 PASS**

```bash
uv run pytest tests/unit/test_image_composer.py -v
```

预期：2 条 PASS。

- [ ] **Step 5: 加单格测试**

在 `tests/unit/test_image_composer.py` 末尾追加：

```python
def test_compose_single_panel_caption(tmp_path, fake_panel, font_path):
    template = TEMPLATES[ImagePostTemplate.single_panel_caption]
    output = tmp_path / "single.png"
    compose(
        template=template,
        panel_paths=[fake_panel],
        captions=["还没下班 但已经累了"],
        watermark="公众号·测试",
        font_path=font_path,
        output_path=output,
    )
    assert output.exists()
    img = Image.open(output)
    assert img.size == template.output_size
```

- [ ] **Step 6: 跑全部 composer 测试**

```bash
uv run pytest tests/unit/test_image_composer.py -v
```

预期：3 条 PASS。

- [ ] **Step 7: lint / type**

```bash
uv run ruff check app/image_composer/compose.py tests/unit/test_image_composer.py
uv run mypy app/image_composer/compose.py
```

- [ ] **Step 8: 提交**

```bash
git add backend/app/image_composer/compose.py backend/tests/unit/test_image_composer.py
git commit -m "feat(image-composer): Pillow composer for two-panel + single-panel templates"
```

---

## Task 8: Schemas + Service helpers

**Files:**
- Create: `backend/app/image_posts/schemas.py`
- Create: `backend/app/image_posts/service.py`

- [ ] **Step 1: 写 schemas**

`backend/app/image_posts/schemas.py`：

```python
"""Pydantic schemas for image posts."""
import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.image_posts.models import ImagePostStatus, ImagePostTemplate


class ImagePostCreate(BaseModel):
    account_id: uuid.UUID
    template: ImagePostTemplate
    topic: str = Field(min_length=1, max_length=500)
    tone: str | None = None
    panel_asset_ids: list[uuid.UUID] | None = None  # 阶段 2 复用图库


class ImagePostUpdate(BaseModel):
    captions: list[str] | None = None


class ImagePostOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    account_id: uuid.UUID
    template: ImagePostTemplate
    topic: str
    tone: str | None
    status: ImagePostStatus
    error_msg: str | None
    wechat_pushed_at: datetime | None
    created_at: datetime


class ImagePostDetail(ImagePostOut):
    captions: list[str] | None
    panel_prompts: list[str] | None
    asset_ids: list[uuid.UUID] | None
    panel_asset_ids: list[uuid.UUID] | None
    composed_image_path: str | None
    wechat_thumb_media_id: str | None
    wechat_draft_media_id: str | None


class ImagePostListPage(BaseModel):
    items: list[ImagePostOut]
    total: int


class ImageAssetOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    account_id: uuid.UUID
    image_path: str
    scene_prompt: str | None
    tags: list[str] | None
    source: str
    used_count: int
    created_at: datetime


class ImageAssetListPage(BaseModel):
    items: list[ImageAssetOut]
    total: int
```

- [ ] **Step 2: 写 service**

`backend/app/image_posts/service.py`：

```python
"""Image post DB helpers."""
import uuid

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.image_posts.models import ImageAsset, ImagePost, ImagePostStatus


async def get_image_post(
    db: AsyncSession, post_id: uuid.UUID
) -> ImagePost | None:
    return (
        await db.execute(select(ImagePost).where(ImagePost.id == post_id))
    ).scalar_one_or_none()


async def list_image_posts(
    db: AsyncSession,
    *,
    account_id: uuid.UUID | None = None,
    status: ImagePostStatus | None = None,
    page: int = 1,
    page_size: int = 20,
) -> tuple[list[ImagePost], int]:
    stmt = select(ImagePost)
    count_stmt = select(func.count()).select_from(ImagePost)
    if account_id is not None:
        stmt = stmt.where(ImagePost.account_id == account_id)
        count_stmt = count_stmt.where(ImagePost.account_id == account_id)
    if status is not None:
        stmt = stmt.where(ImagePost.status == status)
        count_stmt = count_stmt.where(ImagePost.status == status)
    stmt = (
        stmt.order_by(ImagePost.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    items = (await db.execute(stmt)).scalars().all()
    total = (await db.execute(count_stmt)).scalar_one()
    return list(items), total


async def get_image_asset(
    db: AsyncSession, asset_id: uuid.UUID
) -> ImageAsset | None:
    return (
        await db.execute(select(ImageAsset).where(ImageAsset.id == asset_id))
    ).scalar_one_or_none()


async def list_image_assets(
    db: AsyncSession,
    *,
    account_id: uuid.UUID | None = None,
    page: int = 1,
    page_size: int = 24,
) -> tuple[list[ImageAsset], int]:
    stmt = select(ImageAsset)
    count_stmt = select(func.count()).select_from(ImageAsset)
    if account_id is not None:
        stmt = stmt.where(ImageAsset.account_id == account_id)
        count_stmt = count_stmt.where(ImageAsset.account_id == account_id)
    stmt = (
        stmt.order_by(ImageAsset.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    items = (await db.execute(stmt)).scalars().all()
    total = (await db.execute(count_stmt)).scalar_one()
    return list(items), total
```

- [ ] **Step 3: 验证 import**

```bash
cd backend
uv run python -c "from app.image_posts.schemas import ImagePostCreate; print('ok')"
uv run python -c "from app.image_posts.service import get_image_post; print('ok')"
```

- [ ] **Step 4: lint / type**

```bash
uv run ruff check app/image_posts/schemas.py app/image_posts/service.py
uv run mypy app/image_posts/schemas.py app/image_posts/service.py
```

- [ ] **Step 5: 提交**

```bash
git add backend/app/image_posts/schemas.py backend/app/image_posts/service.py
git commit -m "feat(image-posts): add Pydantic schemas + DB service helpers"
```

---

## Task 9: Celery Task — generate_image_post（TDD，新生成路径）

**Files:**
- Create: `backend/app/tasks/image_pipeline.py`
- Create: `backend/tests/integration/test_image_pipeline.py`

- [x] **Step 1: 写失败测试（仅成功路径，新生成）**

`backend/tests/integration/test_image_pipeline.py`：

```python
import json
import uuid
from pathlib import Path

import httpx
import pytest
import respx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker

from app.accounts.models import Account
from app.image_posts.models import (
    ImageAsset,
    ImagePost,
    ImagePostStatus,
    ImagePostTemplate,
)


@pytest.fixture(autouse=True)
def stub_providers(monkeypatch, tmp_path):
    """Provide a fake reference image + ensure storage dir."""
    monkeypatch.setenv("IMAGE_STORAGE_DIR", str(tmp_path))
    monkeypatch.setenv("DOUBAO_API_KEY", "test_key")
    monkeypatch.setenv("DOUBAO_BASE_URL", "https://ark.test/api/v3")
    monkeypatch.setenv("DOUBAO_IMAGE_MODEL", "test-model")
    from app.config import get_settings
    get_settings.cache_clear()

    # Fake reference image
    ref_dir = tmp_path / "accounts"
    ref_dir.mkdir(parents=True, exist_ok=True)


async def _seed_account_with_ref(db_session, ref_path: Path) -> Account:
    ref_path.write_bytes(b"\x89PNG\r\n\x1a\nfake_png_data")
    account = Account(
        name="A",
        wechat_appid="wx",
        wechat_secret="s",
        category="职场",
        character_reference_path=str(ref_path),
    )
    db_session.add(account)
    await db_session.commit()
    await db_session.refresh(account)
    return account


@pytest.mark.asyncio
async def test_generate_image_post_two_panel(
    db_engine, db_session, monkeypatch, tmp_path
):
    # Patch LLM registry
    from app.image_generator import factory as factory_module
    from app.tasks import image_pipeline

    async def fake_chat(messages, *, model, temperature, json_mode=False, **k):
        from app.ai_providers.base import ChatResult, TokenUsage
        return ChatResult(
            content=json.dumps({
                "captions": ["上文案", "下文案"],
                "scene_prompts": ["panel 1 scene", "panel 2 scene"],
            }),
            model=model,
            usage=TokenUsage(prompt_tokens=10, completion_tokens=20),
        )

    class FakeProvider:
        name = "fake"
        async def chat(self, *a, **k):
            return await fake_chat(*a, **k)

    fake_registry = type("R", (), {
        "role": lambda self, r: (FakeProvider(), "fake-model"),
    })()
    monkeypatch.setattr(
        image_pipeline, "get_registry", lambda: fake_registry, raising=False,
    )
    monkeypatch.setattr(
        image_pipeline, "_ensure_registry",
        lambda session: _noop_async(), raising=False,
    )

    account = await _seed_account_with_ref(
        db_session, tmp_path / "accounts" / "char.png"
    )
    post = ImagePost(
        account_id=account.id,
        template=ImagePostTemplate.two_panel_contrast,
        topic="测试主题",
        tone="self_mockery",
        status=ImagePostStatus.pending,
    )
    db_session.add(post)
    await db_session.commit()

    async with respx.mock() as mock:
        # mock doubao - returns 2 image URLs
        mock.post("https://ark.test/api/v3/images/generations").mock(
            return_value=httpx.Response(
                200,
                json={"data": [{"url": "https://cdn/img.png"}]},
            )
        )
        # mock the download
        mock.get("https://cdn/img.png").mock(
            return_value=httpx.Response(
                200, content=b"\x89PNG\r\n\x1a\nimg_bytes" * 100,
            )
        )
        await image_pipeline._generate_with_session(db_session, post.id)

    # Reload via fresh session
    fresh_sm = async_sessionmaker(db_engine, expire_on_commit=False)
    async with fresh_sm() as fresh:
        refreshed = (
            await fresh.execute(select(ImagePost).where(ImagePost.id == post.id))
        ).scalar_one()
        assert refreshed.status == ImagePostStatus.generated
        assert refreshed.captions == ["上文案", "下文案"]
        assert refreshed.panel_prompts == ["panel 1 scene", "panel 2 scene"]
        assert refreshed.asset_ids
        assert len(refreshed.asset_ids) == 2

        assets = (await fresh.execute(
            select(ImageAsset).where(ImageAsset.account_id == account.id)
        )).scalars().all()
        assert len(assets) == 2


async def _noop_async():
    return None
```

- [x] **Step 2: 跑确认 FAIL**

```bash
cd backend
uv run pytest tests/integration/test_image_pipeline.py -v
```

预期：ImportError（image_pipeline 模块不存在）。

- [x] **Step 3: 实现 image_pipeline.py**

`backend/app/tasks/image_pipeline.py`：

```python
"""AI image post Celery pipeline."""
import asyncio
import base64
import json
import logging
import uuid
from pathlib import Path
from typing import Any

import httpx
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.accounts.models import Account
from app.ai_providers.base import Message
from app.ai_providers.registry import RegistryError, get_registry, load_from_db
from app.config import get_settings
from app.db.session import make_engine
from app.image_composer.compose import compose
from app.image_generator.factory import get_image_provider
from app.image_generator.base import ImageGenRequest
from app.image_posts.models import (
    ImageAsset,
    ImageAssetSource,
    ImagePost,
    ImagePostStatus,
    ImagePostTemplate,
)
from app.image_posts.templates import TEMPLATES
from app.tasks.celery_app import celery_app

logger = logging.getLogger(__name__)


async def _ensure_registry(session: AsyncSession) -> None:
    await load_from_db(session)


def _parse_json_safe(content: str) -> dict[str, Any]:
    """Strip code fences if any then json.loads."""
    s = content.strip()
    if s.startswith("```"):
        s = s.strip("`")
        if s.startswith("json"):
            s = s[4:]
        s = s.strip()
    return json.loads(s)


async def _download_to_local(url: str, target_dir: Path) -> Path:
    target_dir.mkdir(parents=True, exist_ok=True)
    async with httpx.AsyncClient(timeout=60) as client:
        resp = await client.get(url)
        resp.raise_for_status()
    asset_id = uuid.uuid4()
    target = target_dir / f"{asset_id}.png"
    target.write_bytes(resp.content)
    return target


async def _generate_with_session(
    session: AsyncSession, post_id: uuid.UUID
) -> None:
    post = (
        await session.execute(select(ImagePost).where(ImagePost.id == post_id))
    ).scalar_one_or_none()
    if post is None:
        logger.warning("image_post %s not found", post_id)
        return
    account = (
        await session.execute(
            select(Account).where(Account.id == post.account_id)
        )
    ).scalar_one()

    if not account.character_reference_path:
        post.status = ImagePostStatus.failed
        post.error_msg = "该公众号未上传角色参考图"
        await session.commit()
        return

    post.status = ImagePostStatus.generating
    await session.commit()

    try:
        template = TEMPLATES[ImagePostTemplate(post.template)]

        # ── Caption stage ────────────────────────
        await _ensure_registry(session)
        try:
            writer, writer_model = get_registry().role("writer")
        except RegistryError as exc:
            post.status = ImagePostStatus.failed
            post.error_msg = f"AI role binding error: {exc}"
            await session.commit()
            return

        prompt = template.caption_prompt_template.format(
            topic=post.topic, tone=post.tone or "通用",
        )
        chat_result = await writer.chat(
            [Message(role="user", content=prompt)],
            model=writer_model,
            temperature=0.8,
            json_mode=True,
        )
        parsed = _parse_json_safe(chat_result.content)
        post.captions = parsed["captions"]
        post.panel_prompts = parsed["scene_prompts"]
        await session.commit()

        # ── Image stage ──────────────────────────
        if post.panel_asset_ids:
            # 复用路径（阶段 2 启用，阶段 1 不会触发）
            post.asset_ids = post.panel_asset_ids
            for aid in post.panel_asset_ids:
                await session.execute(
                    update(ImageAsset)
                    .where(ImageAsset.id == uuid.UUID(str(aid)))
                    .values(used_count=ImageAsset.used_count + 1)
                )
        else:
            provider = get_image_provider()
            ref_bytes = Path(account.character_reference_path).read_bytes()
            ref_b64 = base64.b64encode(ref_bytes).decode()
            settings = get_settings()
            storage_root = Path(settings.image_storage_dir) / "image_assets"

            asset_ids: list[str] = []
            for scene in post.panel_prompts:
                result = await provider.generate(
                    ImageGenRequest(
                        prompt=scene + " (style: flat cartoon, no text, no captions)",
                        reference_image_b64=ref_b64,
                        size="1024x1024",
                        negative_prompt="text, chinese characters, captions, letters",
                    )
                )
                local_path = await _download_to_local(result.url, storage_root)
                asset = ImageAsset(
                    account_id=account.id,
                    image_path=str(local_path),
                    scene_prompt=scene,
                    tags=[],
                    source=ImageAssetSource.ai_generated,
                )
                session.add(asset)
                await session.flush()
                asset_ids.append(str(asset.id))
            post.asset_ids = asset_ids

        post.status = ImagePostStatus.generated
        post.error_msg = None
        await session.commit()
    except Exception as exc:
        logger.exception("image post generation failed: %s", post.id)
        post.status = ImagePostStatus.failed
        post.error_msg = f"{type(exc).__name__}: {exc}"
        await session.commit()


async def _do_generate(post_id: uuid.UUID) -> None:
    engine = make_engine()
    sm = async_sessionmaker(engine, expire_on_commit=False)
    async with sm() as session:
        await _generate_with_session(session, post_id)
    await engine.dispose()


@celery_app.task(
    name="app.tasks.image_pipeline.generate_image_post",
    bind=True,
    max_retries=2,
    default_retry_delay=30,
)
def generate_image_post(self: Any, post_id: str) -> None:
    asyncio.run(_do_generate(uuid.UUID(post_id)))
```

- [x] **Step 4: 跑测试确认 PASS**

```bash
uv run pytest tests/integration/test_image_pipeline.py::test_generate_image_post_two_panel -v
```

预期：PASS。如果失败，检查 `_parse_json_safe` 解析、fake provider 注入路径。

- [x] **Step 5: lint / type**

```bash
uv run ruff check app/tasks/image_pipeline.py tests/integration/test_image_pipeline.py
uv run mypy app/tasks/image_pipeline.py
```

- [x] **Step 6: 提交**

```bash
git add backend/app/tasks/image_pipeline.py backend/tests/integration/test_image_pipeline.py
git commit -m "feat(image-posts): Celery generate_image_post task (LLM + Doubao)"
```

---

## Task 10: Celery Task — compose_and_push_image_post（TDD）

**Files:**
- Modify: `backend/app/tasks/image_pipeline.py`
- Modify: `backend/tests/integration/test_image_pipeline.py`

- [x] **Step 1: 追加失败测试**

在 `tests/integration/test_image_pipeline.py` 末尾追加：

```python
@pytest.mark.asyncio
async def test_compose_and_push_two_panel_success(
    db_engine, db_session, monkeypatch, tmp_path
):
    from app.image_posts.models import ImageAsset, ImageAssetSource
    from app.tasks import image_pipeline

    monkeypatch.setattr(
        "app.tasks.image_pipeline.get_access_token",
        lambda **k: _async_value("TOK"),
        raising=False,
    )

    account = await _seed_account_with_ref(
        db_session, tmp_path / "accounts" / "char.png"
    )
    # Pre-seed assets (simulating prior generation)
    from PIL import Image as _Img
    asset_paths = []
    for i in range(2):
        p = tmp_path / "image_assets" / f"a{i}.png"
        p.parent.mkdir(parents=True, exist_ok=True)
        _Img.new("RGB", (1024, 1024), (200, 150, 100)).save(p)
        asset = ImageAsset(
            account_id=account.id,
            image_path=str(p),
            scene_prompt=f"scene {i}",
            tags=[],
            source=ImageAssetSource.ai_generated,
        )
        db_session.add(asset)
        await db_session.commit()
        await db_session.refresh(asset)
        asset_paths.append(asset.id)

    post = ImagePost(
        account_id=account.id,
        template=ImagePostTemplate.two_panel_contrast,
        topic="t",
        status=ImagePostStatus.generated,
        captions=["上文案", "下文案"],
        panel_prompts=["s1", "s2"],
        asset_ids=[str(a) for a in asset_paths],
    )
    db_session.add(post)
    await db_session.commit()

    async with respx.mock(assert_all_called=False) as mock:
        mock.post(
            "https://api.weixin.qq.com/cgi-bin/material/add_material"
        ).mock(
            return_value=httpx.Response(
                200,
                json={"media_id": "MID", "url": "https://mmbiz/img.png"},
            )
        )
        mock.post("https://api.weixin.qq.com/cgi-bin/draft/add").mock(
            return_value=httpx.Response(
                200, json={"media_id": "DRAFT_MID"}
            )
        )
        await image_pipeline._compose_and_push_with_session(db_session, post.id)

    fresh_sm = async_sessionmaker(db_engine, expire_on_commit=False)
    async with fresh_sm() as fresh:
        refreshed = (
            await fresh.execute(select(ImagePost).where(ImagePost.id == post.id))
        ).scalar_one()
        assert refreshed.status == ImagePostStatus.pushed
        assert refreshed.wechat_thumb_media_id == "MID"
        assert refreshed.wechat_draft_media_id == "DRAFT_MID"
        assert refreshed.composed_image_path
        assert Path(refreshed.composed_image_path).exists()


async def _async_value(v):
    return v
```

- [x] **Step 2: 跑确认 FAIL**

```bash
cd backend
uv run pytest tests/integration/test_image_pipeline.py::test_compose_and_push_two_panel_success -v
```

预期：AttributeError（`_compose_and_push_with_session` 不存在）。

- [x] **Step 3: 扩展 image_pipeline.py**

在 `app/tasks/image_pipeline.py` 末尾追加（确保 `from app.wechat.token import get_access_token` 和 `from app.wechat.material import upload_image` 已 import；`from app.wechat.draft import push_draft, WeChatDraftError` 也要 import）：

```python
from app.wechat.token import get_access_token
from app.wechat.material import upload_image
from app.wechat.draft import push_draft, WeChatDraftError


async def _compose_and_push_with_session(
    session: AsyncSession, post_id: uuid.UUID
) -> None:
    post = (
        await session.execute(select(ImagePost).where(ImagePost.id == post_id))
    ).scalar_one_or_none()
    if post is None:
        return
    account = (
        await session.execute(
            select(Account).where(Account.id == post.account_id)
        )
    ).scalar_one()
    if post.status not in (
        ImagePostStatus.generated, ImagePostStatus.failed
    ):
        logger.warning(
            "cannot push image_post %s from status %s", post.id, post.status
        )
        return

    asset_ids = post.asset_ids or []
    asset_uuid_list = [uuid.UUID(str(a)) for a in asset_ids]
    assets = (await session.execute(
        select(ImageAsset).where(ImageAsset.id.in_(asset_uuid_list))
    )).scalars().all()
    # Preserve order from asset_ids
    by_id = {str(a.id): a for a in assets}
    ordered_paths = [Path(by_id[str(aid)].image_path) for aid in asset_ids]

    template = TEMPLATES[ImagePostTemplate(post.template)]
    post.status = ImagePostStatus.composing
    await session.commit()

    try:
        settings = get_settings()
        output_dir = Path(settings.image_storage_dir) / "image_posts"
        output_dir.mkdir(parents=True, exist_ok=True)
        output_path = output_dir / f"{post.id}.png"
        compose(
            template=template,
            panel_paths=ordered_paths,
            captions=post.captions or [],
            watermark=f"公众号·{account.name}",
            font_path=Path(settings.image_posts_font_path),
            output_path=output_path,
        )
        post.composed_image_path = str(output_path)
        post.status = ImagePostStatus.pushing
        await session.commit()

        token = await get_access_token(
            account_id=str(account.id),
            appid=account.wechat_appid,
            secret=account.wechat_secret,
        )
        upload_result = await upload_image(
            access_token=token, file_path=str(output_path),
        )
        post.wechat_thumb_media_id = upload_result["media_id"]

        title = (post.captions or ["未命名"])[0][:30]
        wechat_img_url = upload_result.get("url", "")
        content_html = (
            f'<p style="text-align:center;">'
            f'<img src="{wechat_img_url}" style="max-width:100%;"/>'
            f'</p>'
        )
        try:
            draft_media_id = await push_draft(
                access_token=token,
                title=title,
                content_html=content_html,
                thumb_media_id=post.wechat_thumb_media_id,
                author=account.name,
            )
        except WeChatDraftError as exc:
            if exc.errcode == 40001:
                token = await get_access_token(
                    account_id=str(account.id),
                    appid=account.wechat_appid,
                    secret=account.wechat_secret,
                    force_refresh=True,
                )
                draft_media_id = await push_draft(
                    access_token=token,
                    title=title,
                    content_html=content_html,
                    thumb_media_id=post.wechat_thumb_media_id,
                    author=account.name,
                )
            else:
                raise

        from datetime import UTC, datetime
        post.wechat_draft_media_id = draft_media_id
        post.wechat_pushed_at = datetime.now(UTC)
        post.status = ImagePostStatus.pushed
        post.error_msg = None
        await session.commit()
    except Exception as exc:
        logger.exception("compose_and_push failed for image_post %s", post.id)
        post.status = ImagePostStatus.failed
        post.error_msg = f"{type(exc).__name__}: {exc}"
        await session.commit()


async def _do_compose_and_push(post_id: uuid.UUID) -> None:
    engine = make_engine()
    sm = async_sessionmaker(engine, expire_on_commit=False)
    async with sm() as session:
        await _compose_and_push_with_session(session, post_id)
    await engine.dispose()


@celery_app.task(
    name="app.tasks.image_pipeline.compose_and_push_image_post",
    bind=True,
    max_retries=2,
    default_retry_delay=15,
)
def compose_and_push_image_post(self: Any, post_id: str) -> None:
    asyncio.run(_do_compose_and_push(uuid.UUID(post_id)))
```

- [x] **Step 4: 跑测试确认 PASS**

```bash
uv run pytest tests/integration/test_image_pipeline.py -v
```

预期：2 条都 PASS。

- [x] **Step 5: lint / type**

```bash
uv run ruff check app/tasks/image_pipeline.py
uv run mypy app/tasks/image_pipeline.py
```

- [x] **Step 6: 提交**

```bash
git add backend/app/tasks/image_pipeline.py backend/tests/integration/test_image_pipeline.py
git commit -m "feat(image-posts): Celery compose_and_push task (Pillow + WeChat push)"
```

---

## Task 11: ImagePost 路由（TDD：CRUD + 触发生成）

**Files:**
- Create: `backend/app/image_posts/routes.py`
- Modify: `backend/app/api/router.py`
- Create: `backend/tests/integration/test_image_posts_routes.py`

- [x] **Step 1: 写失败测试**

`backend/tests/integration/test_image_posts_routes.py`：

```python
import uuid
from pathlib import Path

import pytest
from httpx import ASGITransport, AsyncClient

from app.accounts.models import Account
from app.api.deps import get_db
from app.main import create_app


@pytest.fixture
def app(db_session, monkeypatch, tmp_path):
    from app.tasks import image_pipeline

    monkeypatch.setattr(
        image_pipeline.generate_image_post, "delay",
        lambda *a, **k: None, raising=False,
    )
    monkeypatch.setattr(
        image_pipeline.compose_and_push_image_post, "delay",
        lambda *a, **k: None, raising=False,
    )
    monkeypatch.setenv("IMAGE_STORAGE_DIR", str(tmp_path))
    from app.config import get_settings
    get_settings.cache_clear()

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
        client.headers["Authorization"] = f"Bearer {login.json()['access_token']}"
        yield client


async def _seed_account_with_ref(db_session, tmp_path) -> Account:
    ref_path = tmp_path / "accounts" / "char.png"
    ref_path.parent.mkdir(parents=True, exist_ok=True)
    ref_path.write_bytes(b"fake_png")
    account = Account(
        name="A",
        wechat_appid="wx",
        wechat_secret="s",
        category="职场",
        character_reference_path=str(ref_path),
    )
    db_session.add(account)
    await db_session.commit()
    await db_session.refresh(account)
    return account


async def test_create_image_post(auth_client, db_session, tmp_path):
    account = await _seed_account_with_ref(db_session, tmp_path)
    r = await auth_client.post(
        "/api/image-posts",
        json={
            "account_id": str(account.id),
            "template": "two_panel_contrast",
            "topic": "测试主题",
            "tone": "self_mockery",
        },
    )
    assert r.status_code == 202, r.text
    body = r.json()
    assert body["topic"] == "测试主题"
    assert body["status"] == "pending"


async def test_create_image_post_requires_character_reference(
    auth_client, db_session
):
    account = Account(
        name="NoRef",
        wechat_appid="wx",
        wechat_secret="s",
        category="x",
        # no character_reference_path
    )
    db_session.add(account)
    await db_session.commit()
    r = await auth_client.post(
        "/api/image-posts",
        json={
            "account_id": str(account.id),
            "template": "two_panel_contrast",
            "topic": "x",
        },
    )
    assert r.status_code == 400
    assert "角色参考图" in r.json()["detail"]


async def test_list_image_posts(auth_client, db_session, tmp_path):
    account = await _seed_account_with_ref(db_session, tmp_path)
    for i in range(3):
        await auth_client.post(
            "/api/image-posts",
            json={
                "account_id": str(account.id),
                "template": "single_panel_caption",
                "topic": f"t{i}",
            },
        )
    r = await auth_client.get("/api/image-posts")
    assert r.status_code == 200
    body = r.json()
    assert body["total"] == 3
    assert len(body["items"]) == 3


async def test_get_image_post_detail(auth_client, db_session, tmp_path):
    account = await _seed_account_with_ref(db_session, tmp_path)
    create = await auth_client.post(
        "/api/image-posts",
        json={
            "account_id": str(account.id),
            "template": "two_panel_contrast",
            "topic": "t",
        },
    )
    post_id = create.json()["id"]
    r = await auth_client.get(f"/api/image-posts/{post_id}")
    assert r.status_code == 200
    body = r.json()
    assert body["id"] == post_id
    assert "captions" in body  # detail-only field


async def test_patch_image_post_updates_captions(auth_client, db_session, tmp_path):
    account = await _seed_account_with_ref(db_session, tmp_path)
    create = await auth_client.post(
        "/api/image-posts",
        json={
            "account_id": str(account.id),
            "template": "two_panel_contrast",
            "topic": "t",
        },
    )
    post_id = create.json()["id"]
    r = await auth_client.patch(
        f"/api/image-posts/{post_id}",
        json={"captions": ["新上文案", "新下文案"]},
    )
    assert r.status_code == 200
    assert r.json()["captions"] == ["新上文案", "新下文案"]


async def test_delete_image_post(auth_client, db_session, tmp_path):
    account = await _seed_account_with_ref(db_session, tmp_path)
    create = await auth_client.post(
        "/api/image-posts",
        json={
            "account_id": str(account.id),
            "template": "two_panel_contrast",
            "topic": "t",
        },
    )
    post_id = create.json()["id"]
    r = await auth_client.delete(f"/api/image-posts/{post_id}")
    assert r.status_code == 204
    r2 = await auth_client.get(f"/api/image-posts/{post_id}")
    assert r2.status_code == 404
```

- [x] **Step 2: 跑确认 FAIL**

```bash
cd backend
uv run pytest tests/integration/test_image_posts_routes.py -v
```

预期：404（路由未注册）或 ImportError。

- [x] **Step 3: 实现路由**

`backend/app/image_posts/routes.py`：

```python
"""Image post API routes."""
import uuid
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.accounts import service as account_service
from app.api.deps import get_db
from app.auth.dependencies import get_current_username
from app.image_posts import service
from app.image_posts.models import (
    ImageAsset,
    ImagePost,
    ImagePostStatus,
    ImagePostTemplate,
)
from app.image_posts.schemas import (
    ImagePostCreate,
    ImagePostDetail,
    ImagePostListPage,
    ImagePostOut,
    ImagePostUpdate,
)
from app.image_posts.templates import TEMPLATES

router = APIRouter(prefix="/image-posts", tags=["image-posts"])


def _post_to_out(post: ImagePost) -> ImagePostOut:
    return ImagePostOut.model_validate(post)


def _post_to_detail(post: ImagePost) -> ImagePostDetail:
    return ImagePostDetail.model_validate(post)


@router.post("", response_model=ImagePostOut, status_code=202)
async def create(
    payload: ImagePostCreate,
    db: AsyncSession = Depends(get_db),
    _: str = Depends(get_current_username),
) -> ImagePostOut:
    account = await account_service.get_account(db, payload.account_id)
    if account is None:
        raise HTTPException(404, "Account not found")
    if not account.character_reference_path:
        raise HTTPException(400, "该公众号未上传角色参考图")

    if payload.panel_asset_ids is not None:
        expected = TEMPLATES[payload.template].panel_count
        if len(payload.panel_asset_ids) != expected:
            raise HTTPException(
                400,
                f"panel_asset_ids 长度需等于模板 panel_count ({expected})",
            )
        # 验证每张都属于该 account
        rows = (await db.execute(
            select(ImageAsset.id).where(
                ImageAsset.id.in_(payload.panel_asset_ids),
                ImageAsset.account_id == payload.account_id,
            )
        )).all()
        if len(rows) != len(payload.panel_asset_ids):
            raise HTTPException(400, "存在非法或非本账号的 asset_id")

    post = ImagePost(
        account_id=payload.account_id,
        template=payload.template,
        topic=payload.topic,
        tone=payload.tone,
        status=ImagePostStatus.pending,
        panel_asset_ids=(
            [str(a) for a in payload.panel_asset_ids]
            if payload.panel_asset_ids
            else None
        ),
    )
    db.add(post)
    await db.commit()
    await db.refresh(post)

    from app.tasks.image_pipeline import generate_image_post
    generate_image_post.delay(str(post.id))

    return _post_to_out(post)


@router.get("", response_model=ImagePostListPage)
async def list_all(
    account_id: uuid.UUID | None = None,
    status: ImagePostStatus | None = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    _: str = Depends(get_current_username),
) -> ImagePostListPage:
    items, total = await service.list_image_posts(
        db, account_id=account_id, status=status,
        page=page, page_size=page_size,
    )
    return ImagePostListPage(
        items=[_post_to_out(p) for p in items], total=total,
    )


@router.get("/{post_id}", response_model=ImagePostDetail)
async def get_one(
    post_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    _: str = Depends(get_current_username),
) -> ImagePostDetail:
    obj = await service.get_image_post(db, post_id)
    if obj is None:
        raise HTTPException(404, "ImagePost not found")
    return _post_to_detail(obj)


@router.patch("/{post_id}", response_model=ImagePostDetail)
async def update(
    post_id: uuid.UUID,
    payload: ImagePostUpdate,
    db: AsyncSession = Depends(get_db),
    _: str = Depends(get_current_username),
) -> ImagePostDetail:
    obj = await service.get_image_post(db, post_id)
    if obj is None:
        raise HTTPException(404, "ImagePost not found")
    if payload.captions is not None:
        obj.captions = payload.captions
    await db.commit()
    await db.refresh(obj)
    return _post_to_detail(obj)


@router.delete("/{post_id}", status_code=204)
async def delete(
    post_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    _: str = Depends(get_current_username),
) -> None:
    obj = await service.get_image_post(db, post_id)
    if obj is None:
        raise HTTPException(404, "ImagePost not found")
    if obj.status in (ImagePostStatus.generating, ImagePostStatus.composing, ImagePostStatus.pushing):
        raise HTTPException(409, "进行中的图片草稿不能删除")
    # 不删关联 asset
    from pathlib import Path
    if obj.composed_image_path:
        Path(obj.composed_image_path).unlink(missing_ok=True)
    await db.delete(obj)
    await db.commit()
```

- [x] **Step 4: 注册路由到 router.py**

`backend/app/api/router.py`，在现有 `include_router` 列表后追加：

```python
from app.image_posts.routes import router as image_posts_router
api_router.include_router(image_posts_router)
```

- [x] **Step 5: 跑测试确认 PASS**

```bash
uv run pytest tests/integration/test_image_posts_routes.py -v
```

预期：6 条 PASS。

- [x] **Step 6: lint / type**

```bash
uv run ruff check app/image_posts/routes.py app/api/router.py tests/integration/test_image_posts_routes.py
uv run mypy app/image_posts/routes.py
```

- [x] **Step 7: 提交**

```bash
git add backend/app/image_posts/routes.py backend/app/api/router.py \
  backend/tests/integration/test_image_posts_routes.py
git commit -m "feat(image-posts): CRUD routes + trigger generate task"
```

---

## Task 12: 文案重写 + 重新生成 + 推送路由（TDD）

**Files:**
- Modify: `backend/app/image_posts/routes.py`
- Modify: `backend/tests/integration/test_image_posts_routes.py`

- [x] **Step 1: 追加失败测试**

在 `tests/integration/test_image_posts_routes.py` 末尾追加：

```python
async def test_regenerate_captions_route(auth_client, db_session, tmp_path, monkeypatch):
    import json as _json
    from app.ai_providers.base import ChatResult, TokenUsage

    async def fake_chat(messages, *, model, temperature, json_mode=False, **k):
        return ChatResult(
            content=_json.dumps({
                "captions": ["新上", "新下"],
                "scene_prompts": ["s1", "s2"],
            }),
            model=model,
            usage=TokenUsage(prompt_tokens=10, completion_tokens=10),
        )

    from app.image_posts import routes as image_posts_routes
    class FakeProvider:
        name = "fake"
        async def chat(self, *a, **k): return await fake_chat(*a, **k)
    fake_registry = type("R", (), {
        "role": lambda self, r: (FakeProvider(), "m"),
    })()
    monkeypatch.setattr(image_posts_routes, "get_registry", lambda: fake_registry, raising=False)
    async def _noop(s): return None
    monkeypatch.setattr(image_posts_routes, "_ensure_registry", _noop, raising=False)

    account = await _seed_account_with_ref(db_session, tmp_path)
    create = await auth_client.post(
        "/api/image-posts",
        json={
            "account_id": str(account.id),
            "template": "two_panel_contrast",
            "topic": "t",
        },
    )
    post_id = create.json()["id"]
    r = await auth_client.post(f"/api/image-posts/{post_id}/regenerate-captions")
    assert r.status_code == 200
    body = r.json()
    assert body["captions"] == ["新上", "新下"]


async def test_regenerate_route_resets_status(auth_client, db_session, tmp_path):
    account = await _seed_account_with_ref(db_session, tmp_path)
    create = await auth_client.post(
        "/api/image-posts",
        json={
            "account_id": str(account.id),
            "template": "two_panel_contrast",
            "topic": "t",
        },
    )
    post_id = create.json()["id"]
    # Force into failed
    from app.image_posts.models import ImagePost, ImagePostStatus
    from sqlalchemy import select
    obj = (await db_session.execute(
        select(ImagePost).where(ImagePost.id == uuid.UUID(post_id))
    )).scalar_one()
    obj.status = ImagePostStatus.failed
    await db_session.commit()

    r = await auth_client.post(f"/api/image-posts/{post_id}/regenerate")
    assert r.status_code == 202
    await db_session.refresh(obj)
    assert obj.status == ImagePostStatus.pending


async def test_push_route_dispatches_task(auth_client, db_session, tmp_path):
    account = await _seed_account_with_ref(db_session, tmp_path)
    create = await auth_client.post(
        "/api/image-posts",
        json={
            "account_id": str(account.id),
            "template": "two_panel_contrast",
            "topic": "t",
        },
    )
    post_id = create.json()["id"]
    # Force status=generated
    from app.image_posts.models import ImagePost, ImagePostStatus
    from sqlalchemy import select
    obj = (await db_session.execute(
        select(ImagePost).where(ImagePost.id == uuid.UUID(post_id))
    )).scalar_one()
    obj.status = ImagePostStatus.generated
    obj.captions = ["上", "下"]
    obj.asset_ids = []
    await db_session.commit()

    r = await auth_client.post(f"/api/image-posts/{post_id}/push-to-wechat")
    assert r.status_code == 202


async def test_push_rejects_non_generated_status(auth_client, db_session, tmp_path):
    account = await _seed_account_with_ref(db_session, tmp_path)
    create = await auth_client.post(
        "/api/image-posts",
        json={
            "account_id": str(account.id),
            "template": "two_panel_contrast",
            "topic": "t",
        },
    )
    post_id = create.json()["id"]
    # status is "pending" by default
    r = await auth_client.post(f"/api/image-posts/{post_id}/push-to-wechat")
    assert r.status_code == 409
```

- [x] **Step 2: 跑确认 FAIL**

```bash
cd backend
uv run pytest tests/integration/test_image_posts_routes.py -k "regenerate or push" -v
```

预期：4 条 FAIL。

- [x] **Step 3: 实现 3 个新路由**

在 `app/image_posts/routes.py` 末尾追加（需要新 import）：

```python
from app.ai_providers.base import Message
from app.ai_providers.registry import RegistryError, get_registry, load_from_db


async def _ensure_registry(session: AsyncSession) -> None:
    await load_from_db(session)


def _parse_json_safe(content: str) -> dict[str, Any]:
    import json as _json
    s = content.strip()
    if s.startswith("```"):
        s = s.strip("`")
        if s.startswith("json"):
            s = s[4:]
        s = s.strip()
    return _json.loads(s)


@router.post("/{post_id}/regenerate-captions", response_model=ImagePostDetail)
async def regenerate_captions(
    post_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    _: str = Depends(get_current_username),
) -> ImagePostDetail:
    obj = await service.get_image_post(db, post_id)
    if obj is None:
        raise HTTPException(404, "ImagePost not found")

    template = TEMPLATES[ImagePostTemplate(obj.template)]
    await _ensure_registry(db)
    try:
        writer, model = get_registry().role("writer")
    except RegistryError as exc:
        raise HTTPException(500, f"AI role binding error: {exc}") from exc

    prompt = template.caption_prompt_template.format(
        topic=obj.topic, tone=obj.tone or "通用",
    )
    chat_result = await writer.chat(
        [Message(role="user", content=prompt)],
        model=model, temperature=0.8, json_mode=True,
    )
    parsed = _parse_json_safe(chat_result.content)
    obj.captions = parsed["captions"]
    obj.panel_prompts = parsed["scene_prompts"]
    await db.commit()
    await db.refresh(obj)
    return _post_to_detail(obj)


@router.post("/{post_id}/regenerate", response_model=ImagePostOut, status_code=202)
async def regenerate(
    post_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    _: str = Depends(get_current_username),
) -> ImagePostOut:
    obj = await service.get_image_post(db, post_id)
    if obj is None:
        raise HTTPException(404, "ImagePost not found")
    if obj.status in (ImagePostStatus.generating, ImagePostStatus.composing, ImagePostStatus.pushing):
        raise HTTPException(409, "进行中的图片草稿不能重新生成")
    obj.status = ImagePostStatus.pending
    obj.error_msg = None
    obj.composed_image_path = None
    await db.commit()
    await db.refresh(obj)
    from app.tasks.image_pipeline import generate_image_post
    generate_image_post.delay(str(obj.id))
    return _post_to_out(obj)


@router.post("/{post_id}/push-to-wechat", response_model=ImagePostOut, status_code=202)
async def push(
    post_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    _: str = Depends(get_current_username),
) -> ImagePostOut:
    obj = await service.get_image_post(db, post_id)
    if obj is None:
        raise HTTPException(404, "ImagePost not found")
    if obj.status not in (ImagePostStatus.generated, ImagePostStatus.failed):
        raise HTTPException(409, f"当前状态 {obj.status} 不支持推送")
    if not obj.captions:
        raise HTTPException(400, "缺少文案，无法推送")
    # Reset failed → composing path via Celery
    if obj.status == ImagePostStatus.failed:
        obj.error_msg = None
        await db.commit()
        await db.refresh(obj)
    from app.tasks.image_pipeline import compose_and_push_image_post
    compose_and_push_image_post.delay(str(obj.id))
    return _post_to_out(obj)
```

- [x] **Step 4: 跑测试确认 PASS**

```bash
uv run pytest tests/integration/test_image_posts_routes.py -v
```

预期：10 条都 PASS。

- [x] **Step 5: lint / type**

```bash
uv run ruff check app/image_posts/routes.py
uv run mypy app/image_posts/routes.py
```

- [x] **Step 6: 提交**

```bash
git add backend/app/image_posts/routes.py backend/tests/integration/test_image_posts_routes.py
git commit -m "feat(image-posts): regenerate-captions/regenerate/push-to-wechat routes"
```

---

## Task 13: ImageAsset GET 路由 + 缩略图文件路由

**Files:**
- Create: `backend/app/image_assets/__init__.py`
- Create: `backend/app/image_assets/routes.py`
- Modify: `backend/app/api/router.py`
- Create: `backend/tests/integration/test_image_assets_routes.py`

- [x] **Step 1: 创建包**

```bash
mkdir -p backend/app/image_assets
echo '"""Image asset library routes."""' > backend/app/image_assets/__init__.py
```

- [x] **Step 2: 写失败测试**

`backend/tests/integration/test_image_assets_routes.py`：

```python
import uuid
from pathlib import Path

import pytest
from httpx import ASGITransport, AsyncClient

from app.accounts.models import Account
from app.api.deps import get_db
from app.image_posts.models import ImageAsset, ImageAssetSource
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
        login = await client.post(
            "/api/auth/login",
            data={"username": "admin", "password": "hunter2"},
        )
        client.headers["Authorization"] = f"Bearer {login.json()['access_token']}"
        yield client


async def _seed_assets(db_session, tmp_path, n=3) -> tuple[Account, list[ImageAsset]]:
    account = Account(name="A", wechat_appid="wx", wechat_secret="s", category="x")
    db_session.add(account)
    await db_session.commit()
    await db_session.refresh(account)

    assets = []
    for i in range(n):
        p = tmp_path / f"a{i}.png"
        p.write_bytes(b"\x89PNG\r\n\x1a\nfake" + bytes([i]))
        a = ImageAsset(
            account_id=account.id,
            image_path=str(p),
            scene_prompt=f"scene {i}",
            tags=["test", f"tag{i}"],
            source=ImageAssetSource.ai_generated,
        )
        db_session.add(a)
        await db_session.commit()
        await db_session.refresh(a)
        assets.append(a)
    return account, assets


async def test_list_image_assets(auth_client, db_session, tmp_path):
    account, _ = await _seed_assets(db_session, tmp_path, n=3)
    r = await auth_client.get(f"/api/image-assets?account_id={account.id}")
    assert r.status_code == 200
    body = r.json()
    assert body["total"] == 3
    assert len(body["items"]) == 3


async def test_get_image_asset_detail(auth_client, db_session, tmp_path):
    _, assets = await _seed_assets(db_session, tmp_path, n=1)
    r = await auth_client.get(f"/api/image-assets/{assets[0].id}")
    assert r.status_code == 200
    body = r.json()
    assert body["scene_prompt"] == "scene 0"


async def test_get_image_asset_file(auth_client, db_session, tmp_path):
    _, assets = await _seed_assets(db_session, tmp_path, n=1)
    r = await auth_client.get(f"/api/image-assets/{assets[0].id}/file")
    assert r.status_code == 200
    assert r.headers["content-type"].startswith("image/")
    assert len(r.content) > 0
```

- [x] **Step 3: 跑确认 FAIL**

```bash
cd backend
uv run pytest tests/integration/test_image_assets_routes.py -v
```

预期：404（路由未注册）。

- [x] **Step 4: 实现路由**

`backend/app/image_assets/routes.py`：

```python
"""Image asset library routes."""
import uuid
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import FileResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db
from app.auth.dependencies import get_current_username
from app.image_posts import service
from app.image_posts.schemas import ImageAssetListPage, ImageAssetOut

router = APIRouter(prefix="/image-assets", tags=["image-assets"])


@router.get("", response_model=ImageAssetListPage)
async def list_all(
    account_id: uuid.UUID | None = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(24, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    _: str = Depends(get_current_username),
) -> ImageAssetListPage:
    items, total = await service.list_image_assets(
        db, account_id=account_id, page=page, page_size=page_size,
    )
    return ImageAssetListPage(
        items=[ImageAssetOut.model_validate(a) for a in items], total=total,
    )


@router.get("/{asset_id}", response_model=ImageAssetOut)
async def get_one(
    asset_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    _: str = Depends(get_current_username),
) -> ImageAssetOut:
    obj = await service.get_image_asset(db, asset_id)
    if obj is None:
        raise HTTPException(404, "ImageAsset not found")
    return ImageAssetOut.model_validate(obj)


@router.get("/{asset_id}/file")
async def get_file(
    asset_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    _: str = Depends(get_current_username),
) -> FileResponse:
    obj = await service.get_image_asset(db, asset_id)
    if obj is None:
        raise HTTPException(404, "ImageAsset not found")
    p = Path(obj.image_path)
    if not p.exists():
        raise HTTPException(404, "Image file missing")
    return FileResponse(p, media_type="image/png")
```

- [x] **Step 5: 注册路由**

`backend/app/api/router.py`：

```python
from app.image_assets.routes import router as image_assets_router
api_router.include_router(image_assets_router)
```

- [x] **Step 6: 跑测试确认 PASS**

```bash
uv run pytest tests/integration/test_image_assets_routes.py -v
```

预期：3 条 PASS。

- [x] **Step 7: lint / type**

```bash
uv run ruff check app/image_assets/ app/api/router.py
uv run mypy app/image_assets/routes.py
```

- [x] **Step 8: 提交**

```bash
git add backend/app/image_assets/ backend/app/api/router.py \
  backend/tests/integration/test_image_assets_routes.py
git commit -m "feat(image-assets): GET routes + file response for thumbnails"
```

---

## Task 14: 前端 — 类型 + API client + 顶部导航

**Files:**
- Modify: `frontend/src/App.tsx`
- Create: `frontend/src/api/image-posts.ts`

- [x] **Step 1: 写 API client**

`frontend/src/api/image-posts.ts`：

```typescript
import { api } from "./client";

export type ImagePostTemplate = "two_panel_contrast" | "single_panel_caption";
export type ImagePostStatus =
  | "pending" | "generating" | "generated"
  | "composing" | "pushing" | "pushed" | "failed";

export interface ImagePost {
  id: string;
  account_id: string;
  template: ImagePostTemplate;
  topic: string;
  tone: string | null;
  status: ImagePostStatus;
  error_msg: string | null;
  wechat_pushed_at: string | null;
  created_at: string;
}

export interface ImagePostDetail extends ImagePost {
  captions: string[] | null;
  panel_prompts: string[] | null;
  asset_ids: string[] | null;
  panel_asset_ids: string[] | null;
  composed_image_path: string | null;
  wechat_thumb_media_id: string | null;
  wechat_draft_media_id: string | null;
}

export interface ImagePostListPage {
  items: ImagePost[];
  total: number;
}

export interface ImageAsset {
  id: string;
  account_id: string;
  image_path: string;
  scene_prompt: string | null;
  tags: string[] | null;
  source: string;
  used_count: number;
  created_at: string;
}

export interface ImageAssetListPage {
  items: ImageAsset[];
  total: number;
}

export const imagePostsApi = {
  list: (params?: { account_id?: string; status?: string; page?: number }) =>
    api.get<ImagePostListPage>("/image-posts", { params }),
  get: (id: string) => api.get<ImagePostDetail>(`/image-posts/${id}`),
  create: (body: {
    account_id: string;
    template: ImagePostTemplate;
    topic: string;
    tone?: string | null;
    panel_asset_ids?: string[] | null;
  }) => api.post<ImagePost>("/image-posts", body),
  patch: (id: string, body: { captions: string[] }) =>
    api.patch<ImagePostDetail>(`/image-posts/${id}`, body),
  regenerateCaptions: (id: string) =>
    api.post<ImagePostDetail>(`/image-posts/${id}/regenerate-captions`),
  regenerate: (id: string) => api.post<ImagePost>(`/image-posts/${id}/regenerate`),
  push: (id: string) => api.post<ImagePost>(`/image-posts/${id}/push-to-wechat`),
  delete: (id: string) => api.delete(`/image-posts/${id}`),
};

export const imageAssetsApi = {
  list: (params: { account_id: string; page?: number }) =>
    api.get<ImageAssetListPage>("/image-assets", { params }),
  fileUrl: (id: string) => `/api/image-assets/${id}/file`,
};
```

- [x] **Step 2: 修改 App.tsx 加路由 + 顶部导航**

参考现有 App.tsx 结构（找到 NavLink 列表 + Routes 列表）。在 NavLink 列表（草稿 之后）追加：

```tsx
<NavLink to="/image-posts" className={navLinkClass}>图片</NavLink>
```

在 `<Routes>` 中追加（与 `/drafts` 路由并列）：

```tsx
<Route path="/image-posts" element={<ImagePosts />} />
<Route path="/image-posts/:id" element={<ImagePostDetail />} />
<Route path="/image-assets" element={<ImageAssets />} />
```

并在顶部 import：

```tsx
import ImagePosts from "./pages/ImagePosts";
import ImagePostDetail from "./pages/ImagePostDetail";
import ImageAssets from "./pages/ImageAssets";
```

页面文件下个 task 才创建——本步骤先在 App.tsx 写引用但不创建页面，**预期 build 会失败**。临时新建 3 个空 stub 文件：

```bash
cat > frontend/src/pages/ImagePosts.tsx <<'EOF'
export default function ImagePosts() {
  return <div>ImagePosts</div>;
}
EOF
cat > frontend/src/pages/ImagePostDetail.tsx <<'EOF'
export default function ImagePostDetail() {
  return <div>ImagePostDetail</div>;
}
EOF
cat > frontend/src/pages/ImageAssets.tsx <<'EOF'
export default function ImageAssets() {
  return <div>ImageAssets</div>;
}
EOF
```

- [x] **Step 3: build 验证**

```bash
cd frontend
pnpm build
```

预期：通过。

- [x] **Step 4: 提交**

```bash
git add frontend/src/api/image-posts.ts frontend/src/App.tsx \
  frontend/src/pages/ImagePosts.tsx \
  frontend/src/pages/ImagePostDetail.tsx \
  frontend/src/pages/ImageAssets.tsx
git commit -m "feat(image-posts/ui): API client + nav + page stubs"
```

---

## Task 15: 前端 — ImagePosts 列表页 + 创建表单 modal

**Files:**
- Modify: `frontend/src/pages/ImagePosts.tsx`
- Create: `frontend/src/components/image-posts/ImagePostFormModal.tsx`

- [x] **Step 1: 写 ImagePostFormModal**

`frontend/src/components/image-posts/ImagePostFormModal.tsx`：

```tsx
import { useMutation, useQuery } from "@tanstack/react-query";
import { useState } from "react";
import { api } from "../../api/client";
import {
  imagePostsApi,
  type ImagePostTemplate,
} from "../../api/image-posts";
import { Button, Input, Modal, Textarea } from "../ui";

interface AccountMin {
  id: string;
  name: string;
  character_reference_path: string | null;
}

interface Props {
  open: boolean;
  onClose: () => void;
  onCreated: (postId: string) => void;
}

const TONES = [
  { value: "humor", label: "幽默" },
  { value: "self_mockery", label: "自嘲" },
  { value: "poignant", label: "扎心" },
  { value: "warm", label: "温暖" },
];

export function ImagePostFormModal({ open, onClose, onCreated }: Props) {
  const accounts = useQuery({
    queryKey: ["accounts"],
    queryFn: async () => (await api.get<AccountMin[]>("/accounts")).data,
  });

  const [accountId, setAccountId] = useState("");
  const [template, setTemplate] = useState<ImagePostTemplate>("two_panel_contrast");
  const [topic, setTopic] = useState("");
  const [tone, setTone] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const create = useMutation({
    mutationFn: async () => {
      const resp = await imagePostsApi.create({
        account_id: accountId,
        template,
        topic,
        tone,
      });
      return resp.data;
    },
    onSuccess: (data) => {
      onCreated(data.id);
      onClose();
    },
    onError: (e: unknown) => {
      const d = (e as { response?: { data?: { detail?: string } } }).response?.data?.detail;
      setError(d ?? "创建失败");
    },
  });

  const account = accounts.data?.find((a) => a.id === accountId);
  const needsCharRef = account && !account.character_reference_path;

  return (
    <Modal
      open={open}
      onClose={onClose}
      title="新建 AI 场景图"
      size="md"
      footer={
        <>
          <Button variant="secondary" onClick={onClose} disabled={create.isPending}>
            取消
          </Button>
          <Button
            variant="primary"
            onClick={() => create.mutate()}
            disabled={!accountId || !topic.trim() || create.isPending || !!needsCharRef}
            loading={create.isPending}
          >
            生成
          </Button>
        </>
      }
    >
      <div style={{ display: "flex", flexDirection: "column", gap: "var(--space-4)" }}>
        <div>
          <label style={{ fontSize: "var(--text-xs)", color: "var(--color-ink-3)" }}>公众号</label>
          <select
            value={accountId}
            onChange={(e) => setAccountId(e.target.value)}
            style={{ width: "100%", padding: "var(--space-2)", marginTop: "var(--space-1)" }}
          >
            <option value="">— 选择公众号 —</option>
            {accounts.data?.map((a) => (
              <option key={a.id} value={a.id}>{a.name}</option>
            ))}
          </select>
          {needsCharRef && (
            <p style={{ fontSize: "var(--text-xs)", color: "var(--color-failed-fg)", marginTop: "var(--space-1)" }}>
              该公众号未上传角色参考图，请先在「公众号」页配置
            </p>
          )}
        </div>

        <div>
          <label style={{ fontSize: "var(--text-xs)", color: "var(--color-ink-3)" }}>模板</label>
          <div style={{ display: "flex", gap: "var(--space-2)", marginTop: "var(--space-1)" }}>
            {[
              { v: "two_panel_contrast", l: "双格反差" },
              { v: "single_panel_caption", l: "单格大字" },
            ].map((t) => (
              <button
                key={t.v}
                type="button"
                onClick={() => setTemplate(t.v as ImagePostTemplate)}
                style={{
                  flex: 1,
                  padding: "var(--space-2) var(--space-3)",
                  border: template === t.v ? "2px solid var(--color-ink)" : "1px solid var(--color-surface-3)",
                  background: template === t.v ? "var(--color-surface-2)" : "transparent",
                  borderRadius: "var(--radius-md)",
                  cursor: "pointer",
                  fontSize: "var(--text-sm)",
                }}
              >
                {t.l}
              </button>
            ))}
          </div>
        </div>

        <Textarea
          label="主题"
          value={topic}
          onChange={(e) => setTopic(e.target.value)}
          placeholder="例：打工人对周一开会的态度 vs 周五下午的态度"
          rows={4}
        />

        <div>
          <label style={{ fontSize: "var(--text-xs)", color: "var(--color-ink-3)" }}>语气（可选）</label>
          <div style={{ display: "flex", gap: "var(--space-1)", marginTop: "var(--space-1)", flexWrap: "wrap" }}>
            {TONES.map((t) => (
              <button
                key={t.value}
                type="button"
                onClick={() => setTone(tone === t.value ? null : t.value)}
                style={{
                  padding: "var(--space-1) var(--space-3)",
                  border: tone === t.value ? "2px solid var(--color-ink)" : "1px solid var(--color-surface-3)",
                  background: tone === t.value ? "var(--color-surface-2)" : "transparent",
                  borderRadius: "var(--radius-full)",
                  cursor: "pointer",
                  fontSize: "var(--text-xs)",
                }}
              >
                {t.l}
              </button>
            ))}
          </div>
        </div>

        {error && (
          <p style={{ color: "var(--color-failed-fg)", fontSize: "var(--text-sm)" }}>{error}</p>
        )}
      </div>
    </Modal>
  );
}
```

- [x] **Step 2: 实现 ImagePosts 列表页**

`frontend/src/pages/ImagePosts.tsx`（覆写 stub）：

```tsx
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { imagePostsApi, type ImagePost } from "../api/image-posts";
import { Badge, Button, EmptyState, PageSpinner } from "../components/ui";
import { ImagePostFormModal } from "../components/image-posts/ImagePostFormModal";

const STATUS_LABEL: Record<string, string> = {
  pending: "排队中",
  generating: "生成中",
  generated: "可推送",
  composing: "合成中",
  pushing: "推送中",
  pushed: "已推送",
  failed: "失败",
};

const STATUS_GROUP: Record<string, "active" | "ready" | "done" | "failed"> = {
  pending: "active",
  generating: "active",
  composing: "active",
  pushing: "active",
  generated: "ready",
  pushed: "done",
  failed: "failed",
};

const TEMPLATE_LABEL: Record<string, string> = {
  two_panel_contrast: "双格",
  single_panel_caption: "单格",
};

export default function ImagePosts() {
  const navigate = useNavigate();
  const qc = useQueryClient();
  const [modalOpen, setModalOpen] = useState(false);

  const { data, isLoading } = useQuery({
    queryKey: ["image-posts"],
    queryFn: async () => (await imagePostsApi.list({ page: 1 })).data,
    refetchInterval: 5000,
  });

  const del = useMutation({
    mutationFn: imagePostsApi.delete,
    onSuccess: () => qc.invalidateQueries({ queryKey: ["image-posts"] }),
  });

  return (
    <div className="page-shell">
      <div className="page-header">
        <div className="page-header-meta">
          <h1 className="text-page-title">AI 场景图</h1>
          <p className="text-page-subtitle">主题 → AI 生成 → 推送公众号草稿</p>
        </div>
        <Button onClick={() => setModalOpen(true)}>+ 新建</Button>
      </div>

      {isLoading ? (
        <PageSpinner />
      ) : !data || data.items.length === 0 ? (
        <EmptyState
          title="还没有图片草稿"
          description="点「+ 新建」开始"
          action={<Button onClick={() => setModalOpen(true)}>新建</Button>}
        />
      ) : (
        <div style={{ display: "flex", flexDirection: "column" }}>
          {data.items.map((post: ImagePost) => (
            <div
              key={post.id}
              role="button"
              tabIndex={0}
              onClick={() => navigate(`/image-posts/${post.id}`)}
              onKeyDown={(e) => {
                if (e.key === "Enter" || e.key === " ") navigate(`/image-posts/${post.id}`);
              }}
              style={{
                display: "grid",
                gridTemplateColumns: "60px 1fr 80px 90px 56px",
                gap: "var(--space-4)",
                alignItems: "center",
                padding: "var(--space-4) var(--space-2)",
                borderBottom: "1px solid var(--color-surface-3)",
                cursor: "pointer",
              }}
            >
              <Badge variant="outline">{TEMPLATE_LABEL[post.template]}</Badge>
              <div style={{ minWidth: 0 }}>
                <p style={{ margin: 0, fontSize: "var(--text-base)" }}>
                  {(post.topic || "").slice(0, 30)}
                </p>
                {post.error_msg && (
                  <p style={{ margin: 0, fontSize: "var(--text-xs)", color: "var(--color-failed-fg)" }}>
                    {post.error_msg}
                  </p>
                )}
              </div>
              <span className="mono" style={{ fontSize: "var(--text-xs)" }}>
                {new Date(post.created_at).toLocaleDateString()}
              </span>
              <div style={{ display: "flex", justifyContent: "flex-end" }}>
                <Badge>
                  {STATUS_LABEL[post.status] ?? post.status}
                </Badge>
              </div>
              <div onClick={(e) => e.stopPropagation()} style={{ display: "flex", justifyContent: "flex-end" }}>
                <Button variant="ghost" size="sm" onClick={() => del.mutate(post.id)}>
                  删除
                </Button>
              </div>
            </div>
          ))}
        </div>
      )}

      {modalOpen && (
        <ImagePostFormModal
          open={modalOpen}
          onClose={() => setModalOpen(false)}
          onCreated={(id) => navigate(`/image-posts/${id}`)}
        />
      )}
    </div>
  );
}
```

- [x] **Step 3: build**

```bash
cd frontend
pnpm build
```

预期：通过。

- [x] **Step 4: 提交**

```bash
git add frontend/src/pages/ImagePosts.tsx \
  frontend/src/components/image-posts/ImagePostFormModal.tsx
git commit -m "feat(image-posts/ui): list page + create form modal"
```

---

## Task 16: 前端 — CompositionCanvas 组件（Canvas 实时叠字）

**Files:**
- Create: `frontend/src/components/image-posts/CompositionCanvas.tsx`
- Modify: `frontend/public/index.html` 或入口 `main.tsx` 加 @font-face
- Create: `frontend/public/fonts/SourceHanSansSC-Bold.otf`（复制后端的）

- [x] **Step 1: 复制字体到前端 public/**

```bash
mkdir -p frontend/public/fonts
cp backend/app/image_composer/fonts/SourceHanSansSC-Bold.otf frontend/public/fonts/
```

- [x] **Step 2: 加 @font-face 到 index.css 或 main.tsx**

在 `frontend/src/index.css` 顶部追加：

```css
@font-face {
  font-family: "Source Han Sans SC";
  src: url("/fonts/SourceHanSansSC-Bold.otf") format("opentype");
  font-weight: 700;
  font-display: swap;
}
```

- [x] **Step 3: 实现 CompositionCanvas**

`frontend/src/components/image-posts/CompositionCanvas.tsx`：

```tsx
import { useEffect, useRef } from "react";
import type { ImagePostTemplate } from "../../api/image-posts";

interface Props {
  panelImageUrls: string[];          // 例：["/api/image-assets/{id}/file", ...]
  captions: string[];
  template: ImagePostTemplate;
  watermark: string;
  width?: number;                    // 默认 750 双格 / 1024 单格
}

const TEMPLATE_SIZE: Record<ImagePostTemplate, { w: number; h: number; fontRatio: number }> = {
  two_panel_contrast: { w: 750, h: 1600, fontRatio: 0.06 },
  single_panel_caption: { w: 1024, h: 1280, fontRatio: 0.10 },
};

export function CompositionCanvas({
  panelImageUrls,
  captions,
  template,
  watermark,
  width: displayWidth,
}: Props) {
  const canvasRef = useRef<HTMLCanvasElement>(null);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const { w, h, fontRatio } = TEMPLATE_SIZE[template];
    canvas.width = w;
    canvas.height = h;
    const ctx = canvas.getContext("2d");
    if (!ctx) return;

    // White background
    ctx.fillStyle = "white";
    ctx.fillRect(0, 0, w, h);

    // Load all panel images
    const loadPromises = panelImageUrls.map(
      (url) =>
        new Promise<HTMLImageElement>((resolve, reject) => {
          const img = new Image();
          img.crossOrigin = "anonymous";
          img.onload = () => resolve(img);
          img.onerror = reject;
          img.src = url;
        })
    );

    Promise.all(loadPromises).then((imgs) => {
      const baseFontSize = Math.floor(w * fontRatio);
      const margin = Math.floor(w * 0.03);
      const panelW = w - 2 * margin;
      const panelH = panelW;
      const captionBandH = Math.floor(baseFontSize * 2.2);
      const watermarkH = Math.floor(baseFontSize * 1.2);
      const panelCount = template === "two_panel_contrast" ? 2 : 1;

      const totalH =
        template === "two_panel_contrast"
          ? (captionBandH + panelH) * panelCount + watermarkH
          : Math.floor(baseFontSize * 2.5) + panelH + Math.floor(baseFontSize * 0.8);
      const startY = Math.max(0, Math.floor((h - totalH) / 2));
      let y = startY;

      ctx.textAlign = "center";
      ctx.textBaseline = "top";

      if (template === "two_panel_contrast") {
        for (let i = 0; i < panelCount; i++) {
          const cap = captions[i] ?? "";
          ctx.font = `bold ${baseFontSize}px "Source Han Sans SC", sans-serif`;
          ctx.fillStyle = "rgb(20,20,20)";
          ctx.fillText(cap, w / 2, y + (captionBandH - baseFontSize) / 2);
          y += captionBandH;

          if (imgs[i]) ctx.drawImage(imgs[i], margin, y, panelW, panelH);
          y += panelH;
        }
        const wmSize = Math.max(10, Math.floor(w * 0.018));
        ctx.font = `${wmSize}px "Source Han Sans SC", sans-serif`;
        ctx.fillStyle = "rgb(160,160,160)";
        ctx.fillText(watermark, w / 2, h - watermarkH + (watermarkH - wmSize) / 2);
      } else {
        const bigBand = Math.floor(baseFontSize * 2.5);
        ctx.font = `bold ${baseFontSize}px "Source Han Sans SC", sans-serif`;
        ctx.fillStyle = "rgb(20,20,20)";
        ctx.fillText(captions[0] ?? "", w / 2, y + (bigBand - baseFontSize) / 2);
        y += bigBand;
        if (imgs[0]) ctx.drawImage(imgs[0], margin, y, panelW, panelH);
        y += panelH;
        const wmSize = Math.max(10, Math.floor(w * 0.018));
        ctx.font = `${wmSize}px "Source Han Sans SC", sans-serif`;
        ctx.fillStyle = "rgb(160,160,160)";
        ctx.fillText(watermark, w / 2, y + (Math.floor(baseFontSize * 0.8) - wmSize) / 2);
      }
    }).catch((e) => {
      console.error("canvas image load failed", e);
    });
  }, [panelImageUrls, captions, template, watermark]);

  return (
    <canvas
      ref={canvasRef}
      style={{
        width: displayWidth ?? "100%",
        maxWidth: "100%",
        height: "auto",
        background: "var(--color-surface-2)",
        borderRadius: "var(--radius-md)",
      }}
    />
  );
}
```

- [x] **Step 4: build**

```bash
cd frontend
pnpm build
```

预期：通过。

- [x] **Step 5: 提交**

```bash
git add frontend/public/fonts/ frontend/src/index.css \
  frontend/src/components/image-posts/CompositionCanvas.tsx
git commit -m "feat(image-posts/ui): CompositionCanvas for live caption overlay preview"
```

---

## Task 17: 前端 — ImagePostDetail 详情页

**Files:**
- Modify: `frontend/src/pages/ImagePostDetail.tsx`

- [x] **Step 1: 实现详情页（覆写 stub）**

`frontend/src/pages/ImagePostDetail.tsx`：

```tsx
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { api } from "../api/client";
import { imageAssetsApi, imagePostsApi } from "../api/image-posts";

import { Badge, Button, EyebrowLabel, Input, PageSpinner } from "../components/ui";
import { CompositionCanvas } from "../components/image-posts/CompositionCanvas";

interface AccountMin {
  id: string;
  name: string;
}

const TEMPLATE_LABEL: Record<string, string> = {
  two_panel_contrast: "双格反差",
  single_panel_caption: "单格大字",
};

const STATUS_LABEL: Record<string, string> = {
  pending: "排队中",
  generating: "生成中",
  generated: "可推送",
  composing: "合成中",
  pushing: "推送中",
  pushed: "已推送",
  failed: "失败",
};

const TERMINAL = new Set(["pushed", "failed", "generated"]);

export default function ImagePostDetail() {
  const { id } = useParams<{ id: string }>();
  const qc = useQueryClient();
  const [captions, setCaptions] = useState<string[]>([]);

  const detail = useQuery({
    queryKey: ["image-post", id],
    queryFn: async () => (await imagePostsApi.get(id!)).data,
    refetchInterval: (q) =>
      q.state.data && TERMINAL.has(q.state.data.status) ? false : 2000,
  });

  const accounts = useQuery({
    queryKey: ["accounts"],
    queryFn: async () => (await api.get<AccountMin[]>("/accounts")).data,
  });

  useEffect(() => {
    if (detail.data?.captions) setCaptions(detail.data.captions);
  }, [detail.data?.captions]);

  const saveCaptions = useMutation({
    mutationFn: () => imagePostsApi.patch(id!, { captions }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["image-post", id] }),
  });

  const regenCaptions = useMutation({
    mutationFn: () => imagePostsApi.regenerateCaptions(id!),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["image-post", id] }),
  });

  const regenerate = useMutation({
    mutationFn: () => imagePostsApi.regenerate(id!),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["image-post", id] }),
  });

  const pushToWechat = useMutation({
    mutationFn: () => imagePostsApi.push(id!),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["image-post", id] }),
  });

  if (!detail.data) return <PageSpinner />;

  const post = detail.data;
  const account = accounts.data?.find((a) => a.id === post.account_id);
  const panelImageUrls = (post.asset_ids ?? []).map((aid) => imageAssetsApi.fileUrl(aid));
  const canPush = post.status === "generated" || post.status === "failed";

  return (
    <div className="page-shell">
      <div style={{ marginBottom: "var(--space-4)" }}>
        <Link to="/image-posts">← 返回列表</Link>
      </div>

      <div style={{ display: "grid", gridTemplateColumns: "1fr 360px", gap: "var(--space-6)", alignItems: "start" }}>
        {/* LEFT — Canvas */}
        <div style={{ display: "flex", flexDirection: "column", gap: "var(--space-4)" }}>
          <EyebrowLabel>预览</EyebrowLabel>
          {panelImageUrls.length > 0 && captions.length > 0 ? (
            <CompositionCanvas
              panelImageUrls={panelImageUrls}
              captions={captions}
              template={post.template}
              watermark={`公众号·${account?.name ?? ""}`}
            />
          ) : (
            <div style={{
              minHeight: "60vh", display: "flex", alignItems: "center",
              justifyContent: "center", background: "var(--color-surface-2)",
              borderRadius: "var(--radius-md)",
            }}>
              {post.status === "generating" ? "生成中…" : "暂无候选图"}
            </div>
          )}
          <div style={{ display: "flex", gap: "var(--space-2)" }}>
            <Button
              variant="secondary"
              onClick={() => regenerate.mutate()}
              loading={regenerate.isPending}
              disabled={!TERMINAL.has(post.status)}
            >
              🔄 重新生成图
            </Button>
          </div>
        </div>

        {/* RIGHT — editor */}
        <div style={{ display: "flex", flexDirection: "column", gap: "var(--space-4)", position: "sticky", top: 0 }}>
          <Badge>{STATUS_LABEL[post.status]}</Badge>
          {post.error_msg && (
            <div style={{ padding: "var(--space-3)", background: "var(--color-failed)", color: "var(--color-failed-fg)", borderRadius: "var(--radius-md)", fontSize: "var(--text-sm)" }}>
              {post.error_msg}
            </div>
          )}

          <div>
            <EyebrowLabel>文案</EyebrowLabel>
            <div style={{ display: "flex", flexDirection: "column", gap: "var(--space-2)", marginTop: "var(--space-2)" }}>
              {captions.map((cap, i) => (
                <Input
                  key={i}
                  value={cap}
                  onChange={(e) => {
                    const next = [...captions];
                    next[i] = e.target.value;
                    setCaptions(next);
                  }}
                  placeholder={`文案 ${i + 1}`}
                />
              ))}
            </div>
            <div style={{ display: "flex", gap: "var(--space-2)", marginTop: "var(--space-2)" }}>
              <Button
                variant="secondary"
                size="sm"
                onClick={() => saveCaptions.mutate()}
                loading={saveCaptions.isPending}
              >
                💾 保存文案
              </Button>
              <Button
                variant="secondary"
                size="sm"
                onClick={() => regenCaptions.mutate()}
                loading={regenCaptions.isPending}
              >
                ✨ 重写文案
              </Button>
            </div>
          </div>

          <div>
            <EyebrowLabel>元信息</EyebrowLabel>
            <div style={{ fontSize: "var(--text-sm)", color: "var(--color-ink-2)", marginTop: "var(--space-2)", lineHeight: 1.7 }}>
              <p>主题：{post.topic}</p>
              <p>语气：{post.tone ?? "—"}</p>
              <p>模板：{TEMPLATE_LABEL[post.template]}</p>
              <p>公众号：{account?.name ?? "—"}</p>
              <p>创建：{new Date(post.created_at).toLocaleString()}</p>
            </div>
          </div>

          <Button
            variant="primary"
            onClick={() => pushToWechat.mutate()}
            disabled={!canPush || pushToWechat.isPending || captions.length === 0}
            loading={pushToWechat.isPending}
          >
            {post.status === "pushed" ? "已推送" : "推送到微信草稿箱"}
          </Button>
        </div>
      </div>
    </div>
  );
}
```

- [x] **Step 2: build**

```bash
cd frontend
pnpm build
```

预期：通过。可能有 unused import 警告，按提示修。

- [x] **Step 3: 提交**

```bash
git add frontend/src/pages/ImagePostDetail.tsx
git commit -m "feat(image-posts/ui): detail page with Canvas preview + push"
```

---

## Task 18: 阶段 1 端到端回归 + 文档收尾

- [x] **Step 1: 后端全套**

```bash
cd backend
uv run ruff check
uv run mypy app/image_posts app/image_assets app/image_generator app/image_composer app/tasks/image_pipeline.py
uv run pytest
```

预期：ruff 干净，mypy 对相关模块干净（不要求全仓库 mypy 干净——project mypy reality），pytest 全绿。

- [x] **Step 2: 前端**

```bash
cd frontend
pnpm build
```

- [x] **Step 3: 推送**

```bash
cd ..
git push origin master
```

- [x] **Step 4: 标记 plan 阶段 1 完成**

到此为止，**阶段 1 MVP 全部跑通**——可以填表单、生成、预览、推送。下面进入阶段 2（图库复用）。

---

# 阶段 2：图库复用

## Task 19: 前端 — AssetPickerModal + 表单集成

**Files:**
- Create: `frontend/src/components/image-posts/AssetPickerModal.tsx`
- Modify: `frontend/src/components/image-posts/ImagePostFormModal.tsx`

- [x] **Step 1: 写 AssetPickerModal**

`frontend/src/components/image-posts/AssetPickerModal.tsx`：

```tsx
import { useQuery } from "@tanstack/react-query";
import { useState } from "react";
import { imageAssetsApi, type ImageAsset } from "../../api/image-posts";
import { Button, Modal, PageSpinner } from "../ui";

interface Props {
  open: boolean;
  onClose: () => void;
  accountId: string;
  needCount: number;
  onConfirm: (assetIds: string[]) => void;
}

export function AssetPickerModal({ open, onClose, accountId, needCount, onConfirm }: Props) {
  const [selected, setSelected] = useState<string[]>([]);

  const assets = useQuery({
    queryKey: ["image-assets", accountId],
    queryFn: async () => (await imageAssetsApi.list({ account_id: accountId })).data,
    enabled: Boolean(accountId) && open,
  });

  function toggle(id: string) {
    if (selected.includes(id)) {
      setSelected(selected.filter((s) => s !== id));
    } else if (selected.length < needCount) {
      setSelected([...selected, id]);
    }
  }

  return (
    <Modal
      open={open}
      onClose={onClose}
      title={`从图库选 ${needCount} 张`}
      description={`已选 ${selected.length}/${needCount}`}
      size="lg"
      footer={
        <>
          <Button variant="secondary" onClick={onClose}>取消</Button>
          <Button
            variant="primary"
            disabled={selected.length !== needCount}
            onClick={() => onConfirm(selected)}
          >
            确认
          </Button>
        </>
      }
    >
      {assets.isLoading ? (
        <PageSpinner />
      ) : !assets.data || assets.data.items.length === 0 ? (
        <p>该账号还没有可复用的图。</p>
      ) : (
        <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(140px, 1fr))", gap: "var(--space-3)" }}>
          {assets.data.items.map((a: ImageAsset) => {
            const isSelected = selected.includes(a.id);
            const order = selected.indexOf(a.id);
            return (
              <div
                key={a.id}
                onClick={() => toggle(a.id)}
                style={{
                  position: "relative",
                  cursor: "pointer",
                  border: isSelected ? "3px solid var(--color-ink)" : "1px solid var(--color-surface-3)",
                  borderRadius: "var(--radius-md)",
                  overflow: "hidden",
                  aspectRatio: "1 / 1",
                }}
              >
                <img
                  src={imageAssetsApi.fileUrl(a.id)}
                  alt={a.scene_prompt ?? ""}
                  style={{ width: "100%", height: "100%", objectFit: "cover" }}
                />
                {isSelected && (
                  <div style={{
                    position: "absolute", top: 4, left: 4,
                    width: 24, height: 24, borderRadius: "50%",
                    background: "var(--color-ink)", color: "white",
                    display: "flex", alignItems: "center", justifyContent: "center",
                    fontSize: 12, fontWeight: "bold",
                  }}>
                    {order + 1}
                  </div>
                )}
                <div style={{
                  position: "absolute", bottom: 0, left: 0, right: 0,
                  background: "rgba(0,0,0,0.6)", color: "white",
                  fontSize: 10, padding: "2px 6px",
                  whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis",
                }}>
                  {a.scene_prompt}
                </div>
              </div>
            );
          })}
        </div>
      )}
    </Modal>
  );
}
```

- [x] **Step 2: 集成到 ImagePostFormModal**

修改 `ImagePostFormModal.tsx`：

(1) 在 useState 列表加：
```tsx
const [imageSource, setImageSource] = useState<"new" | "reuse">("new");
const [pickerOpen, setPickerOpen] = useState(false);
const [pickedAssetIds, setPickedAssetIds] = useState<string[]>([]);
```

(2) 修改 `create.mutationFn`：
```tsx
const resp = await imagePostsApi.create({
  account_id: accountId,
  template,
  topic,
  tone,
  panel_asset_ids: imageSource === "reuse" ? pickedAssetIds : null,
});
```

(3) 在表单底部（语气 chip 之后、错误提示之前）加：

```tsx
<div>
  <label style={{ fontSize: "var(--text-xs)", color: "var(--color-ink-3)" }}>图源</label>
  <div style={{ display: "flex", gap: "var(--space-2)", marginTop: "var(--space-1)" }}>
    {[
      { v: "new", l: "AI 新生成" },
      { v: "reuse", l: "从图库选" },
    ].map((s) => (
      <button
        key={s.v}
        type="button"
        onClick={() => {
          setImageSource(s.v as "new" | "reuse");
          if (s.v === "new") setPickedAssetIds([]);
        }}
        style={{
          flex: 1,
          padding: "var(--space-2)",
          border: imageSource === s.v ? "2px solid var(--color-ink)" : "1px solid var(--color-surface-3)",
          background: imageSource === s.v ? "var(--color-surface-2)" : "transparent",
          borderRadius: "var(--radius-md)",
          cursor: "pointer",
          fontSize: "var(--text-sm)",
        }}
      >
        {s.l}
      </button>
    ))}
  </div>
  {imageSource === "reuse" && (
    <Button
      variant="secondary"
      size="sm"
      onClick={() => setPickerOpen(true)}
      style={{ marginTop: "var(--space-2)" }}
      disabled={!accountId}
    >
      📁 {pickedAssetIds.length > 0 ? `已选 ${pickedAssetIds.length} 张` : "选择图片"}
    </Button>
  )}
</div>
```

(4) 在 Modal 外（return JSX 末尾）追加：

```tsx
{pickerOpen && accountId && (
  <AssetPickerModal
    open={pickerOpen}
    onClose={() => setPickerOpen(false)}
    accountId={accountId}
    needCount={template === "two_panel_contrast" ? 2 : 1}
    onConfirm={(ids) => {
      setPickedAssetIds(ids);
      setPickerOpen(false);
    }}
  />
)}
```

(5) 文件顶部 import：

```tsx
import { AssetPickerModal } from "./AssetPickerModal";
```

(6) 修改「生成」按钮 disabled：

```tsx
disabled={
  !accountId ||
  !topic.trim() ||
  create.isPending ||
  !!needsCharRef ||
  (imageSource === "reuse" &&
    pickedAssetIds.length !== (template === "two_panel_contrast" ? 2 : 1))
}
```

- [x] **Step 3: build**

```bash
cd frontend
pnpm build
```

- [x] **Step 4: 提交**

```bash
git add frontend/src/components/image-posts/
git commit -m "feat(image-posts/ui): asset picker + reuse mode in create form"
```

---

## Task 20: 后端 — 验证复用路径集成测试

**Files:**
- Modify: `backend/tests/integration/test_image_pipeline.py`

- [ ] **Step 1: 追加复用路径测试**

在 `tests/integration/test_image_pipeline.py` 末尾追加：

```python
@pytest.mark.asyncio
async def test_generate_with_panel_asset_ids_skips_doubao(
    db_engine, db_session, monkeypatch, tmp_path
):
    """复用图库时不应调豆包，只调 LLM。"""
    import json as _json
    from app.image_posts.models import ImageAsset, ImageAssetSource
    from app.tasks import image_pipeline

    async def fake_chat(messages, *, model, temperature, json_mode=False, **k):
        from app.ai_providers.base import ChatResult, TokenUsage
        return ChatResult(
            content=_json.dumps({
                "captions": ["新A", "新B"],
                "scene_prompts": ["s1", "s2"],
            }),
            model=model,
            usage=TokenUsage(prompt_tokens=5, completion_tokens=5),
        )
    class FakeProvider:
        name = "fake"
        async def chat(self, *a, **k): return await fake_chat(*a, **k)
    fake_registry = type("R", (), {
        "role": lambda self, r: (FakeProvider(), "m"),
    })()
    monkeypatch.setattr(image_pipeline, "get_registry", lambda: fake_registry, raising=False)
    monkeypatch.setattr(image_pipeline, "_ensure_registry",
                        lambda s: _noop_async(), raising=False)

    account = await _seed_account_with_ref(
        db_session, tmp_path / "accounts" / "char.png"
    )
    # Pre-seed assets
    asset_ids = []
    for i in range(2):
        p = tmp_path / "image_assets" / f"a{i}.png"
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(b"fake")
        asset = ImageAsset(
            account_id=account.id,
            image_path=str(p),
            scene_prompt=f"s{i}",
            tags=[],
            source=ImageAssetSource.ai_generated,
        )
        db_session.add(asset)
        await db_session.commit()
        await db_session.refresh(asset)
        asset_ids.append(str(asset.id))

    post = ImagePost(
        account_id=account.id,
        template=ImagePostTemplate.two_panel_contrast,
        topic="t",
        status=ImagePostStatus.pending,
        panel_asset_ids=asset_ids,
    )
    db_session.add(post)
    await db_session.commit()

    # 不 mock 豆包 URL — 如果代码调它会抛 ConnectError
    await image_pipeline._generate_with_session(db_session, post.id)

    fresh_sm = async_sessionmaker(db_engine, expire_on_commit=False)
    async with fresh_sm() as fresh:
        refreshed = (
            await fresh.execute(select(ImagePost).where(ImagePost.id == post.id))
        ).scalar_one()
        assert refreshed.status == ImagePostStatus.generated
        assert refreshed.asset_ids == asset_ids
        # used_count 应该都加了 1
        from app.image_posts.models import ImageAsset
        used_assets = (await fresh.execute(
            select(ImageAsset).where(ImageAsset.id.in_(
                [uuid.UUID(a) for a in asset_ids]
            ))
        )).scalars().all()
        for a in used_assets:
            assert a.used_count == 1
```

- [ ] **Step 2: 跑测试确认 PASS**

```bash
cd backend
uv run pytest tests/integration/test_image_pipeline.py::test_generate_with_panel_asset_ids_skips_doubao -v
```

- [ ] **Step 3: lint**

```bash
uv run ruff check tests/integration/test_image_pipeline.py
```

- [ ] **Step 4: 提交**

```bash
git add backend/tests/integration/test_image_pipeline.py
git commit -m "test(image-posts): verify reuse path skips Doubao + increments used_count"
```

---

## Task 21: 前端 — ImageAssets 浏览页

**Files:**
- Modify: `frontend/src/pages/ImageAssets.tsx`

- [ ] **Step 1: 实现浏览页（覆写 stub）**

`frontend/src/pages/ImageAssets.tsx`：

```tsx
import { useQuery } from "@tanstack/react-query";
import { useState } from "react";
import { api } from "../api/client";
import { imageAssetsApi, type ImageAsset } from "../api/image-posts";
import { Badge, EmptyState, EyebrowLabel, PageSpinner } from "../components/ui";

interface AccountMin {
  id: string;
  name: string;
}

export default function ImageAssets() {
  const [accountId, setAccountId] = useState<string>("");

  const accounts = useQuery({
    queryKey: ["accounts"],
    queryFn: async () => (await api.get<AccountMin[]>("/accounts")).data,
  });

  const assets = useQuery({
    queryKey: ["image-assets-browse", accountId],
    queryFn: async () => (await imageAssetsApi.list({ account_id: accountId })).data,
    enabled: Boolean(accountId),
  });

  return (
    <div className="page-shell">
      <div className="page-header">
        <div className="page-header-meta">
          <h1 className="text-page-title">图库</h1>
          <p className="text-page-subtitle">已生成的角色场景图，可在创建新草稿时复用</p>
        </div>
      </div>

      <div style={{ marginBottom: "var(--space-4)" }}>
        <EyebrowLabel>选择公众号</EyebrowLabel>
        <select
          value={accountId}
          onChange={(e) => setAccountId(e.target.value)}
          style={{ marginTop: "var(--space-2)", padding: "var(--space-2)", minWidth: 200 }}
        >
          <option value="">— 选 —</option>
          {accounts.data?.map((a) => (
            <option key={a.id} value={a.id}>{a.name}</option>
          ))}
        </select>
      </div>

      {!accountId ? (
        <EmptyState title="请先选公众号" description="不同公众号有独立的图库" />
      ) : assets.isLoading ? (
        <PageSpinner />
      ) : !assets.data || assets.data.items.length === 0 ? (
        <EmptyState title="还没有图" description="先在「AI 场景图」生成几张" />
      ) : (
        <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(180px, 1fr))", gap: "var(--space-4)" }}>
          {assets.data.items.map((a: ImageAsset) => (
            <div key={a.id} style={{
              border: "1px solid var(--color-surface-3)",
              borderRadius: "var(--radius-md)", overflow: "hidden",
            }}>
              <img
                src={imageAssetsApi.fileUrl(a.id)}
                alt={a.scene_prompt ?? ""}
                style={{ width: "100%", aspectRatio: "1/1", objectFit: "cover", display: "block" }}
              />
              <div style={{ padding: "var(--space-3)", fontSize: "var(--text-xs)" }}>
                <p style={{ margin: 0, color: "var(--color-ink-2)" }}>
                  {(a.scene_prompt ?? "").slice(0, 60)}
                </p>
                <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginTop: "var(--space-2)" }}>
                  <Badge variant="outline">复用 {a.used_count} 次</Badge>
                  <span className="mono" style={{ color: "var(--color-ink-3)" }}>
                    {new Date(a.created_at).toLocaleDateString()}
                  </span>
                </div>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
```

- [ ] **Step 2: build**

```bash
cd frontend
pnpm build
```

- [ ] **Step 3: 提交**

```bash
git add frontend/src/pages/ImageAssets.tsx
git commit -m "feat(image-posts/ui): image-assets browse page (read-only)"
```

---

## Task 22: 阶段 2 回归 + 推送

- [ ] **Step 1: 全套**

```bash
cd backend
uv run ruff check
uv run pytest
cd ../frontend
pnpm build
```

- [ ] **Step 2: 推送**

```bash
cd ..
git push origin master
```

---

# 阶段 3：抛光

## Task 23: 用量记录扩展 + cost_cents 支持

**Files:**
- Modify: `backend/app/ai_providers/usage.py`
- Modify: `backend/app/tasks/image_pipeline.py`
- Modify: `backend/tests/integration/test_image_pipeline.py`

- [ ] **Step 1: 看现有 `record_usage` 签名**

```bash
grep -n "def record_usage" backend/app/ai_providers/usage.py
```

记录现有签名，下一步扩展兼容。

- [ ] **Step 2: 加 `cost_cents` 参数（向后兼容）**

修改 `record_usage` 函数签名，加 `cost_cents: int | None = None` 参数（按现有签名风格放在末尾）。如果实现里把 usage 拆到 `AIUsage` 表，加一列 `cost_cents` 或直接计算后写 `total_cost` 字段（视现有 schema 而定）。

如果 `AIUsage` 表没 `cost_cents` 字段，加一个 migration：

```bash
cd backend
uv run alembic revision -m "add cost_cents to ai_usage"
```

然后实现 migration：

```python
def upgrade() -> None:
    op.add_column("ai_usage", sa.Column("cost_cents", sa.Integer(), nullable=True))

def downgrade() -> None:
    op.drop_column("ai_usage", "cost_cents")
```

- [ ] **Step 3: 在 image_pipeline 里调 `record_usage`**

修改 `_generate_with_session` 的 caption stage，在 `parsed = ...` 后追加：

```python
        await record_usage(
            session,
            provider_name=writer.name,
            role="writer",
            model=writer_model,
            usage=chat_result.usage,
            purpose="image_caption_gen",
            ref_id=post.id,
        )
```

在 image stage（新生成分支）的 `await provider.generate(...)` 之后追加：

```python
            await record_usage(
                session,
                provider_name=provider.name,
                role="image_generator",
                model=get_settings().doubao_image_model,
                usage=None,  # 豆包按张计费无 token 概念
                purpose="image_generation",
                ref_id=post.id,
                cost_cents=30,  # ~¥0.3
            )
```

`record_usage` 的实现需要支持 `usage=None`。

- [ ] **Step 4: 加成本估算到 `pricing` 表（如有）**

`backend/app/ai_providers/usage.py` 末尾追加常量：

```python
DOUBAO_SEEDREAM_PRICE_PER_IMAGE_CENTS = 30  # ~¥0.3
```

- [ ] **Step 5: 跑测试 + lint**

```bash
uv run pytest tests/integration/test_image_pipeline.py -v
uv run ruff check app/ai_providers/usage.py app/tasks/image_pipeline.py
```

- [ ] **Step 6: 提交**

```bash
git add backend/app/ai_providers/usage.py backend/app/tasks/image_pipeline.py \
  backend/alembic/versions/
git commit -m "feat(image-posts): record AI usage for image-gen + caption-gen"
```

---

## Task 24: 最终回归 + push + 部署提示

- [ ] **Step 1: 后端完整**

```bash
cd backend
uv run ruff check
uv run mypy app/image_posts app/image_assets app/image_generator app/image_composer app/tasks/image_pipeline.py app/accounts
uv run pytest
```

预期：全套通过；总计应该 ~100 条测试（86 baseline + 14 新增）。

- [ ] **Step 2: 前端构建**

```bash
cd frontend
pnpm build
```

预期：tsc + vite 都干净，gzip 总大小 < 200 KB（新 Canvas 组件 + 字体只在浏览器需要时加载）。

- [ ] **Step 3: 检查 git 日志**

```bash
git log --oneline | head -25
```

应该看到 ~22-24 条本次 feature 的 commits。

- [ ] **Step 4: push**

```bash
git push origin master
```

- [ ] **Step 5: 部署提示（用户在服务器执行）**

```bash
git pull
docker compose up -d --build api worker web
# entrypoint 自动跑 alembic upgrade head
```

部署后冒烟：
1. 设置 `DOUBAO_API_KEY` 到服务器 `.env` 并重启 api/worker
2. 「公众号」页 → 编辑账号 → 上传角色参考图（jpg/png ≤10MB）
3. 「图片」页 → + 新建 → 选公众号 / 模板 / 写主题 / 选语气 → 生成
4. 等 30-60 秒 → 进详情页 → 看到候选图 + 文案
5. 改文案 → 实时 Canvas 预览
6. 「推送到微信草稿箱」→ 等 10-30 秒变 "已推送"
7. 公众号后台 → 草稿箱 → 看到草稿

---

## 边界情况备忘（来自 spec）

| 情形 | 行为 |
|---|---|
| 公众号没传角色参考图 | 创建 image-post 直接 400 |
| 豆包 timeout / 429 | Celery autoretry 2 次（已有模式） |
| 豆包返回 NSFW | status=failed，错误信息明确 |
| 用户改完文案没保存就刷新 | 丢失（v1 不做自动保存，提示「保存文案」按钮） |
| 推送时 token 过期 (40001) | 复用现有 force_refresh 重试逻辑 |
| 删 image_post | 关联 asset 保留（图库不丢） |

---

## 风险提示

- 豆包 Seedream API 字段名/模型 ID **以官方 SDK 文档为准**，本计划基于 2026-05 文档状态；如 API 改了，调整 `app/image_generator/doubao.py` 中的 payload 即可。
- Canvas 渲染和 Pillow 渲染可能有像素级差异，UI 上需提示「预览仅供参考」（已在 spec 第 6.6 节确认）。
- 字体文件 ~10MB，前端通过 CSS @font-face 加载首次会有 ~1-2s 延迟；可以考虑只对当前要渲染的字符子集化（v2 优化）。
