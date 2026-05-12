# 默认封面（Account-level fallback cover）实现计划

**Goal:** 每个公众号可配置一张默认封面图（永久素材 media_id）。推送草稿时若无可用 cover，自动回退到账号默认封面。优先级：草稿自身 cover > 账号默认 cover > 失败。

**Tech Stack:** Python 3.12 / FastAPI / SQLAlchemy 2.x async / Alembic / pydantic v2 / React 18 / Vite。复用现有 `app.wechat.material.upload_image()`（已是永久素材接口）。

**Repo conventions:**
- 直接提交到 `master`
- TDD strict：失败测试 → 实现 → 通过测试 → commit
- 后端 `uv run pytest`, `uv run ruff check`, `uv run mypy` 改动文件 clean
- 前端 `pnpm build` clean
- commit 风格 `feat:` / `fix:` / `test:` / `docs:`

---

## 文件结构

| 文件 | 动作 | 责任 |
|------|------|------|
| `backend/app/accounts/models.py` | 修改 | 新增列 `default_thumb_media_id: str | None` |
| `backend/app/accounts/schemas.py` | 修改 | `AccountOut.default_thumb_media_id: str | None` |
| `backend/app/accounts/routes.py` | 修改 | 新增 `POST/DELETE /accounts/{id}/default-cover` |
| `backend/alembic/versions/<新>.py` | 新建 | 加 `default_thumb_media_id` 列 |
| `backend/app/tasks/publish.py` | 修改 | 无 draft cover 时 fallback 到 account 默认 |
| `backend/tests/integration/test_accounts_routes.py` | 修改 | 加上传/清除/读取测试 |
| `backend/tests/integration/test_publish_task.py` | 新建 | 测 fallback 路径 |
| `frontend/src/pages/Settings.tsx`（或 Accounts 组件） | 修改 | 文件选择 + 上传按钮 + 已上传/未上传状态 |

---

## Task 1: Account 加 `default_thumb_media_id` 列 + migration

- [ ] **Step 1: 修改 `backend/app/accounts/models.py`**

在 `style_desc` 字段之后新增一列：

```python
    style_desc: Mapped[str] = mapped_column(Text, nullable=False, default="")
    default_thumb_media_id: Mapped[str | None] = mapped_column(
        String(200), nullable=True
    )
```

- [ ] **Step 2: 生成 alembic migration**

```bash
cd backend
uv run alembic revision -m "add default_thumb_media_id to accounts"
```

编辑生成文件的 `upgrade()` / `downgrade()`：

```python
def upgrade() -> None:
    op.add_column(
        "accounts",
        sa.Column("default_thumb_media_id", sa.String(length=200), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("accounts", "default_thumb_media_id")
```

`down_revision` 应为 `aa119e18bb5f`。

- [ ] **Step 3: 跑现有测试不破坏既有套件 + lint**

```bash
uv run pytest
uv run ruff check app/accounts alembic/versions/
uv run mypy app/accounts/models.py
```

- [ ] **Step 4: 提交**

```bash
git add backend/app/accounts/models.py backend/alembic/versions/
git commit -m "feat(accounts): add default_thumb_media_id column + migration"
```

---

## Task 2: Schemas 暴露 `default_thumb_media_id`（TDD）

- [ ] **Step 1: 在 `backend/tests/integration/test_accounts_routes.py` 末尾追加测试**

```python
async def test_account_response_exposes_default_thumb_media_id(
    auth_client, db_session
):
    # 创建一个账号
    payload = {
        "name": "test-acc",
        "wechat_appid": "wx_test",
        "wechat_secret": "secret",
        "category": "职场",
        "title_prompt": "t",
        "content_prompt": "c",
    }
    r = await auth_client.post("/api/accounts", json=payload)
    assert r.status_code == 201
    body = r.json()
    assert "default_thumb_media_id" in body
    assert body["default_thumb_media_id"] is None
```

- [ ] **Step 2: 跑确认 FAIL**

- [ ] **Step 3: 修改 `backend/app/accounts/schemas.py`**

```python
class AccountOut(BaseModel):
    ...
    default_thumb_media_id: str | None
```

- [ ] **Step 4: 跑确认 PASS + lint**

- [ ] **Step 5: 提交**

```bash
git commit -m "feat(accounts): expose default_thumb_media_id in API"
```

---

## Task 3: 上传默认封面端点（TDD）

**Files:**
- Modify: `backend/app/accounts/routes.py`
- Test: `backend/tests/integration/test_accounts_routes.py`

- [ ] **Step 1: 追加失败测试**

测试要点：
- mock `app.wechat.token.get_access_token` 返回 "fake_token"
- mock `app.wechat.material.upload_image` 返回 `{"media_id": "test_media_xyz", "url": "..."}`
- 上传 1 字节 fake image，期望 200 + `default_thumb_media_id == "test_media_xyz"`

```python
async def test_upload_default_cover(auth_client, db_session, monkeypatch):
    from app.wechat import material as material_module
    from app.wechat import token as token_module

    async def fake_token(*args, **kwargs):
        return "fake_token"

    async def fake_upload(**kwargs):
        return {"media_id": "test_media_xyz", "url": "https://x/y.jpg"}

    monkeypatch.setattr(token_module, "get_access_token", fake_token)
    monkeypatch.setattr(material_module, "upload_image", fake_upload)

    # 创建账号
    r = await auth_client.post("/api/accounts", json={...})
    account_id = r.json()["id"]

    # 上传封面
    files = {"file": ("cover.jpg", b"\xff\xd8\xff\xe0fake", "image/jpeg")}
    r = await auth_client.post(
        f"/api/accounts/{account_id}/default-cover", files=files
    )
    assert r.status_code == 200
    assert r.json()["default_thumb_media_id"] == "test_media_xyz"


async def test_upload_default_cover_rejects_oversize(auth_client, db_session):
    # ...创建账号
    files = {"file": ("big.jpg", b"x" * (11 * 1024 * 1024), "image/jpeg")}
    r = await auth_client.post(
        f"/api/accounts/{account_id}/default-cover", files=files
    )
    assert r.status_code == 413
```

- [ ] **Step 2: 跑确认 FAIL**

- [ ] **Step 3: 实现端点 `backend/app/accounts/routes.py`**

```python
from fastapi import File, UploadFile
import tempfile
from pathlib import Path

from app.wechat.material import WeChatMaterialError, upload_image
from app.wechat.token import get_access_token

MAX_COVER_SIZE = 10 * 1024 * 1024  # WeChat 限制 10MB
ALLOWED_MIME = {"image/jpeg", "image/jpg", "image/png", "image/gif", "image/bmp"}


@router.post("/{account_id}/default-cover", response_model=AccountOut)
async def upload_default_cover(
    account_id: uuid.UUID,
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
    _: str = Depends(get_current_username),
) -> AccountOut:
    obj = await service.get_account(db, account_id)
    if obj is None:
        raise HTTPException(404, "Account not found")
    if file.content_type not in ALLOWED_MIME:
        raise HTTPException(415, f"不支持的图片格式: {file.content_type}")

    content = await file.read()
    if len(content) > MAX_COVER_SIZE:
        raise HTTPException(413, f"图片超过 {MAX_COVER_SIZE // 1024 // 1024}MB 限制")
    if len(content) == 0:
        raise HTTPException(400, "上传文件为空")

    with tempfile.NamedTemporaryFile(
        suffix=Path(file.filename or "cover.jpg").suffix or ".jpg",
        delete=False,
    ) as tmp:
        tmp.write(content)
        tmp_path = tmp.name
    try:
        token = await get_access_token(
            account_id=str(obj.id),
            appid=obj.wechat_appid,
            secret=obj.wechat_secret,
        )
        try:
            result = await upload_image(access_token=token, file_path=tmp_path)
        except WeChatMaterialError as exc:
            raise HTTPException(502, f"微信素材上传失败: {exc}") from exc
        obj.default_thumb_media_id = result["media_id"]
        await db.commit()
        await db.refresh(obj)
    finally:
        Path(tmp_path).unlink(missing_ok=True)
    return AccountOut.model_validate(obj)
```

- [ ] **Step 4: 跑测试确认 PASS**

- [ ] **Step 5: lint / 回归 + 提交**

```bash
git commit -m "feat(accounts): endpoint to upload default cover to WeChat"
```

---

## Task 4: 清除默认封面端点（TDD）

- [ ] **Step 1: 追加测试**

```python
async def test_delete_default_cover_clears_field(auth_client, db_session):
    # ...设置好 default_thumb_media_id="abc"
    r = await auth_client.delete(f"/api/accounts/{account_id}/default-cover")
    assert r.status_code == 200
    assert r.json()["default_thumb_media_id"] is None
```

- [ ] **Step 2: 跑确认 FAIL**

- [ ] **Step 3: 实现**

```python
@router.delete("/{account_id}/default-cover", response_model=AccountOut)
async def clear_default_cover(
    account_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    _: str = Depends(get_current_username),
) -> AccountOut:
    obj = await service.get_account(db, account_id)
    if obj is None:
        raise HTTPException(404, "Account not found")
    obj.default_thumb_media_id = None
    await db.commit()
    await db.refresh(obj)
    return AccountOut.model_validate(obj)
```

- [ ] **Step 4: 跑测试 PASS + lint + 提交**

```bash
git commit -m "feat(accounts): endpoint to clear default cover"
```

---

## Task 5: publish 任务 fallback 到账号默认封面（TDD）

**Files:**
- Modify: `backend/app/tasks/publish.py:39-48`
- Test: `backend/tests/integration/test_publish_task.py`（新建）

- [ ] **Step 1: 新建测试文件**

测试三种场景：
1. 无 cover image + 账号有默认 → 用账号默认推送成功
2. 无 cover image + 账号无默认 → 失败 with 清晰 error_msg
3. 有 cover image（uploaded）→ 用 draft 自身 cover（不走 fallback）

mock `app.wechat.draft.push_draft` 和 `app.wechat.token.get_access_token`。

- [ ] **Step 2: 修改 `app/tasks/publish.py`**

把 cover 检查改为：

```python
draft_cover = next((i for i in images if i.is_cover), None)
draft_cover_ready = (
    draft_cover is not None
    and draft_cover.status == ImageStatus.uploaded
    and draft_cover.wechat_media_id
)
if draft_cover_ready:
    thumb_media_id = draft_cover.wechat_media_id
elif account.default_thumb_media_id:
    thumb_media_id = account.default_thumb_media_id
else:
    draft.status = DraftStatus.failed
    draft.error_msg = "本草稿无封面图片，且账号未配置默认封面"
    await session.commit()
    return
```

然后把后面所有 `cover.wechat_media_id` 引用替换为局部变量 `thumb_media_id`。

- [ ] **Step 3: 跑测试 PASS + lint + 提交**

```bash
git commit -m "feat(publish): fall back to account default cover when draft has none"
```

---

## Task 6: 前端 Settings 加默认封面上传 UI

**Files:**
- 找到现有 Accounts 编辑界面（很可能在 `Settings.tsx` 里）
- 加文件选择 + 上传按钮 + 状态显示

- [ ] **Step 1: 定位现有 Accounts 编辑组件**

```bash
grep -rn "accounts\|/accounts" frontend/src --include="*.tsx" | head
```

- [ ] **Step 2: 在 Account 编辑表单加 UI**

UI 元素：
- 一个 file `<input type="file" accept="image/*">`
- 文案：当前状态显示 `已上传 (media_id 前 8 位)` 或 `未上传`
- 「上传」按钮调 `POST /accounts/{id}/default-cover` (multipart)
- 「清除」按钮调 `DELETE /accounts/{id}/default-cover`
- 上传成功后 invalidate accounts query

- [ ] **Step 3: `pnpm build` 干净通过**

- [ ] **Step 4: 提交**

```bash
git commit -m "feat(accounts): UI for uploading default cover image"
```

---

## Task 7: 最终回归 + push

- [ ] **Step 1: 全套**

```bash
cd backend
uv run ruff check
uv run mypy app/accounts app/tasks/publish.py
uv run pytest

cd ../frontend
pnpm build
```

- [ ] **Step 2: git push**

```bash
git push origin master
```

- [ ] **Step 3: 部署提示**

```bash
git pull && docker compose up -d --build api worker web
```

部署后冒烟：
1. Settings → 选个账号 → 上传一张 jpg 默认封面 → 看到「已上传」
2. 找一篇无图原文 → 跑改写 → 草稿到达 reviewed → 点推送 → 成功
3. 反复推送原文有图的草稿 → 仍优先用草稿自身的图

---

## 边界情况备忘

| 情形 | 行为 |
|------|------|
| 草稿 cover 上传到微信成功 | 用草稿 cover（不变） |
| 草稿 cover 上传到微信失败 | 走账号默认 fallback |
| 原文无图 (零 Image 行) | 走账号默认 fallback |
| 账号未配置默认封面 + 草稿 cover 不可用 | 失败：「本草稿无封面图片，且账号未配置默认封面」 |
| 默认封面 media_id 失效（微信端被删） | 微信 API 返回 errcode=40007；草稿置 failed，用户需重传默认 |
| 上传文件超 10MB | 413 |
| 上传非图片 MIME | 415 |
