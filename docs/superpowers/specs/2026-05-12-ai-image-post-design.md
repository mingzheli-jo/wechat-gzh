# AI 场景图自动化生成 — 设计文档

**日期：** 2026-05-12
**作者：** Claude + 用户协作头脑风暴产出
**目标：** 给现有微信公众号工具增加「主题 → AI 生成场景图 → 推送到微信草稿箱」的子系统。

---

## 1. 背景与目标

### 1.1 用户场景

公众号有一种高传播率的内容玩法：固定卡通形象（如水豚 IP）+ 上下两格 + 文案制造「反差/对比」效果。例如：

> 我不去就是家庭聚餐
> [水豚趴桌上的图]
>
> 我去了就是团建聚餐
> [水豚在烤架前的图]

这类内容创作门槛低、复用性高，但人工每天画很累。希望自动化：

1. 用户填一个主题（文字描述）+ 语气
2. 系统自动生成文案（2 条对比 或 1 句金句）
3. 系统自动出对应场景图（同一只角色 IP，保持一致性）
4. 程序合成最终图（叠中文字 + 水印 + 拼图）
5. UI 预览 → 用户确认 → 推送到微信草稿箱

### 1.2 关键决策

| 维度 | v1 决策 | 理由 |
|---|---|---|
| 模板 | 多模板：**双格反差** + **单格大字** | 用户验证过的格式，工作量可控 |
| 角色一致性 | 每个公众号挂 **1 张参考图** | 跟「默认封面」交互对偶；账号间互不干扰 |
| 图像生成 | **豆包 Seedream**（抽 ImageProvider 接口） | 国内直连、原生中文 IP 风格、参考图能力强 |
| 中文文字 | **Pillow 程序叠字** | 100% 准确、改文案零出图成本 |
| 工作流 | **生成 → UI 预览 → 推送** | 翻车成本低；改文案实时叠字预览 |
| 表单字段 | 公众号 · 模板 · 主题 · 语气 tag | 语气 tag 让 LLM 文案风格更稳定 |
| 每次生成 | **1 套 + 可重生成** | 迭代式省钱；重写文案不重出图 |
| 历史图片复用 | **支持账号级图库** | 节省豆包 API 成本 |
| 推送格式 | **图文消息**（draft/add） | 复用现有 pipeline；有标题/封面/数据 |

### 1.3 v2 不做

- 主题库 + cron 定时批量生成
- 三格 / 四格漫画模板
- 多角色切换（DB 升级 1:1 → 1:N）
- 跨账号风格统一
- 多图轮播
- 图库人工上传 / 删除 / 编辑（v1 只读浏览）

---

## 2. 架构总览

子系统独立于现有「文章改写」pipeline，复用 Account / WeChat 推送 / Celery / DB 基础设施。

```
[用户填表单] → POST /api/image-posts
   ↓
[Celery: generate_image_post]
   ├─ LLM (DeepSeek) 出 captions + scene_prompts
   ├─ if panel_asset_ids 提供 → 跳过出图，直接用复用资源
   │  else → ImageProvider (豆包) 按 scene_prompts 出 N 张图（无字）
   │         → 自动入 image_assets 表
   └─ 状态：generated
        ↓
[UI 预览页]：候选图 + 文案输入
   ├─ 改文案 → 前端 Canvas 实时叠字（无后端调用）
   ├─ 「重新生成图」→ 重跑 generate_image_post（¥0.3-0.6）
   ├─ 「重写文案」→ 调 LLM 重出 captions（同步路由，¥0.01）
   └─ 点「推送」
        ↓
[Celery: compose_and_push]
   ├─ Pillow 合成（拼图 + 叠字 + 水印）→ composed_image
   ├─ upload_image() → 微信永久素材 → thumb_media_id
   └─ push_draft()（图文消息，封面+正文都用合成图）
        ↓
   status = pushed → 微信公众号后台草稿箱可见
```

### 2.1 新增模块

| 模块 | 责任 |
|---|---|
| `app/image_posts/` | models / schemas / routes / service |
| `app/image_assets/` | 图库 models / routes / service |
| `app/image_generator/` | ImageProvider 抽象 + Doubao 实现 |
| `app/image_composer/` | Pillow 叠字 + 拼图 + 水印 |
| `app/tasks/image_pipeline.py` | 2 个 Celery task |

### 2.2 复用模块

| 模块 | 用途 |
|---|---|
| `app/wechat/material.py` | `upload_image()` 上传合成图到微信永久素材 |
| `app/wechat/draft.py` | `push_draft()` 推送图文消息 |
| `app/wechat/token.py` | `get_access_token()` |
| `app/tasks/celery_app.py` | Celery 实例 |
| `app/ai_providers/usage.py` | 用量记录 |
| `app/auth/dependencies.py` | API 鉴权 |

### 2.3 前端新增

- 顶部导航新增 `/image-posts`（与「Library」「公众号」「草稿」「设置」并列）
- 列表页：所有图片草稿，按状态分组
- 详情页：候选预览 + 编辑文案 + 实时叠字 + 推送
- 图库页 `/image-assets`：账号图库（只读）

---

## 3. 数据模型

### 3.1 `accounts` 表（已有，新增 2 列）

| 列 | 类型 | 说明 |
|---|---|---|
| `character_reference_path` | text NULL | 角色参考图本地路径，e.g. `accounts/{id}/character.png` |
| `character_reference_updated_at` | timestamptz NULL | 调试用 |

注：参考图存本地，运行时读 bytes → base64 → 喂给豆包。**不上传到微信永久素材**（与 `default_thumb_media_id` 用途不同）。

### 3.2 `image_posts` 表（新）

| 列 | 类型 | 说明 |
|---|---|---|
| `id` | uuid PK | |
| `account_id` | uuid FK → accounts | |
| `template` | enum | `two_panel_contrast` / `single_panel_caption` |
| `topic` | text | 用户填的主题描述 |
| `tone` | text NULL | `humor` / `self_mockery` / `poignant` / `warm` / null |
| `status` | enum | `pending` / `generating` / `generated` / `composing` / `pushing` / `pushed` / `failed` |
| `captions` | jsonb | `["上文案", "下文案"]` 或 `["金句"]`，长度由 template 决定 |
| `panel_prompts` | jsonb | LLM 生成的每格英文 scene 描述 |
| `asset_ids` | jsonb | 关联的 `image_assets.id` 列表（按格序） |
| `panel_asset_ids` | jsonb NULL | 创建时用户指定的复用 asset_ids（与 `asset_ids` 区分：用户意图 vs 实际使用） |
| `composed_image_path` | text NULL | Pillow 合成后的本地路径 |
| `wechat_thumb_media_id` | str(200) NULL | 合成图上传微信后的 media_id |
| `wechat_draft_media_id` | str(200) NULL | `draft/add` 返回的草稿 media_id |
| `wechat_pushed_at` | timestamptz NULL | 推送成功时间 |
| `error_msg` | text NULL | 失败时填 |
| `created_at` | timestamptz | |
| `updated_at` | timestamptz | |

### 3.3 `image_assets` 表（新，账号级图库）

| 列 | 类型 | 说明 |
|---|---|---|
| `id` | uuid PK | |
| `account_id` | uuid FK → accounts | 账号专属，不跨账号共享 |
| `image_path` | text NOT NULL | 本地路径 `IMAGE_STORAGE_DIR/image_assets/{id}.png` |
| `scene_prompt` | text | 生成时使用的英文场景描述 |
| `tags` | jsonb | 关键词数组，e.g. `["desk", "writing", "sitting"]` |
| `source` | enum | v1: `ai_generated`；预留 `manual_upload` |
| `used_count` | int NOT NULL default 0 | 复用次数（运营数据 + 排序） |
| `created_at` | timestamptz | |

**索引：** `account_id`（GIN on `tags` 留 v2）

**删除策略：** 删 `image_post` 不删关联 asset。Asset 删除入口在图库页（v2）。

### 3.4 Template 配置（不入库，纯代码）

```python
# app/image_posts/templates.py
@dataclass(frozen=True)
class TemplateConfig:
    key: str
    panel_count: int
    caption_count: int
    caption_max_chars: int           # 单条文案上限
    caption_prompt_template: str     # LLM 系统 prompt
    composition: Literal["vertical_stack", "single"]
    caption_position: Literal["top_of_each_panel", "top_of_image"]
    output_size: tuple[int, int]     # (width, height)
    font_size_ratio: float           # font_size = width * ratio

TEMPLATES: dict[str, TemplateConfig] = {
    "two_panel_contrast": TemplateConfig(
        key="two_panel_contrast",
        panel_count=2,
        caption_count=2,
        caption_max_chars=14,
        caption_prompt_template="""你是一名公众号表情包文案作者。基于主题，生成两条对比/反差文案。

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
""",
        composition="vertical_stack",
        caption_position="top_of_each_panel",
        output_size=(750, 1600),
        font_size_ratio=0.06,
    ),
    "single_panel_caption": TemplateConfig(
        key="single_panel_caption",
        panel_count=1,
        caption_count=1,
        caption_max_chars=20,
        caption_prompt_template="""你是一名公众号金句作者。基于主题，生成一句扎心/共鸣/自嘲的金句。

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
""",
        composition="single",
        caption_position="top_of_image",
        output_size=(1024, 1280),
        font_size_ratio=0.10,
    ),
}
```

### 3.5 Alembic 迁移

单一 migration 文件 `<hash>_add_image_post_tables.py`：
- alter `accounts` add 2 columns
- create `image_posts`
- create `image_assets`
- create enum types

---

## 4. 核心 Pipeline

### 4.1 Task A: `generate_image_post(image_post_id)`

```python
async def _generate_with_session(session, post_id):
    post = (await session.execute(
        select(ImagePost).where(ImagePost.id == post_id)
    )).scalar_one()
    account = (await session.execute(
        select(Account).where(Account.id == post.account_id)
    )).scalar_one()

    if not account.character_reference_path:
        post.status = ImagePostStatus.failed
        post.error_msg = "该公众号未上传角色参考图"
        await session.commit()
        return

    post.status = ImagePostStatus.generating
    await session.commit()

    try:
        template = TEMPLATES[post.template]

        # ── 文案 Stage ─────────────────────────
        await _ensure_registry(session)
        writer, model = get_registry().role("writer")
        prompt = template.caption_prompt_template.format(
            topic=post.topic, tone=post.tone or "通用",
        )
        chat_result = await writer.chat(
            [Message(role="user", content=prompt)],
            model=model, temperature=0.8, json_mode=True,
        )
        parsed = _parse_json_safe(chat_result.content)
        post.captions = parsed["captions"]
        post.panel_prompts = parsed["scene_prompts"]
        await session.commit()
        await record_usage(...)

        # ── 图片 Stage（条件跑） ───────────────
        if post.panel_asset_ids:
            # 复用：用现有 asset
            post.asset_ids = post.panel_asset_ids
            for aid in post.panel_asset_ids:
                await session.execute(
                    update(ImageAsset)
                    .where(ImageAsset.id == aid)
                    .values(used_count=ImageAsset.used_count + 1)
                )
        else:
            # 新生成
            provider = get_image_provider()
            ref_b64 = base64.b64encode(
                Path(account.character_reference_path).read_bytes()
            ).decode()
            asset_ids = []
            for i, scene in enumerate(post.panel_prompts):
                neg_prompt = "text, chinese characters, captions, letters"
                result = await provider.generate(ImageGenRequest(
                    prompt=scene + " (style: flat cartoon, no text)",
                    reference_image_b64=ref_b64,
                    size="1024x1024",
                    negative_prompt=neg_prompt,
                ))
                local_path = await _download_to_local(
                    result.url, IMAGE_STORAGE_DIR / "image_assets"
                )
                tags = await _extract_tags(scene)  # 简易：用 LLM 出 3-5 个词
                asset = ImageAsset(
                    account_id=post.account_id,
                    image_path=str(local_path),
                    scene_prompt=scene,
                    tags=tags,
                    source=ImageAssetSource.ai_generated,
                )
                session.add(asset)
                await session.flush()
                asset_ids.append(asset.id)
                await record_usage(
                    role="image_generator",
                    purpose="image_generation",
                    cost_cents=30,  # 豆包 ~¥0.3
                    ...
                )
            post.asset_ids = asset_ids

        post.status = ImagePostStatus.generated
        post.error_msg = None
        await session.commit()

    except Exception as exc:
        logger.exception("image post generation failed: %s", post.id)
        post.status = ImagePostStatus.failed
        post.error_msg = f"{type(exc).__name__}: {exc}"
        await session.commit()
```

### 4.2 Task B: `compose_and_push_image_post(image_post_id)`

```python
async def _compose_and_push_with_session(session, post_id):
    post = ...
    account = ...
    assets = (await session.execute(
        select(ImageAsset).where(ImageAsset.id.in_(post.asset_ids))
    )).scalars().all()

    if post.status not in (ImagePostStatus.generated, ImagePostStatus.failed):
        raise InvalidStateError(f"cannot push from {post.status}")

    template = TEMPLATES[post.template]
    post.status = ImagePostStatus.composing
    await session.commit()

    try:
        # ── Pillow 合成 ──────────────────────
        output_path = IMAGE_STORAGE_DIR / "image_posts" / f"{post.id}.png"
        panel_paths = [Path(a.image_path) for a in _order_by(assets, post.asset_ids)]
        composer.compose(
            template=template,
            panel_paths=panel_paths,
            captions=post.captions,
            watermark=f"公众号·{account.name}",
            font_path=FONT_PATH,
            output_path=output_path,
        )
        post.composed_image_path = str(output_path)
        post.status = ImagePostStatus.pushing
        await session.commit()

        # ── 上传 + 推送 ──────────────────────
        token = await get_access_token(account_id=str(account.id), ...)
        upload_result = await upload_image(
            access_token=token, file_path=str(output_path),
        )
        post.wechat_thumb_media_id = upload_result["media_id"]

        title = post.captions[0][:30]
        # 正文：单张大图占满
        wechat_img_url = upload_result.get("url", "")
        content_html = (
            f'<p style="text-align:center;">'
            f'<img src="{wechat_img_url}" style="max-width:100%;"/>'
            f'</p>'
        )
        draft_media_id = await push_draft(
            access_token=token,
            title=title,
            content_html=content_html,
            thumb_media_id=post.wechat_thumb_media_id,
            author=account.name,
        )
        post.wechat_draft_media_id = draft_media_id
        post.wechat_pushed_at = datetime.now(UTC)
        post.status = ImagePostStatus.pushed
        post.error_msg = None
        await session.commit()

    except Exception as exc:
        logger.exception("image post push failed: %s", post.id)
        post.status = ImagePostStatus.failed
        post.error_msg = f"{type(exc).__name__}: {exc}"
        await session.commit()
```

### 4.3 文案重写（同步路由）

`POST /api/image-posts/{id}/regenerate-captions` — 不走 Celery：

```python
@router.post("/{post_id}/regenerate-captions", response_model=ImagePostDetail)
async def regenerate_captions(post_id, db):
    post = ...
    template = TEMPLATES[post.template]
    writer, model = get_registry().role("writer")
    prompt = template.caption_prompt_template.format(...)
    result = await writer.chat([Message(role="user", content=prompt)], ...)
    parsed = _parse_json_safe(result.content)
    post.captions = parsed["captions"]
    post.panel_prompts = parsed["scene_prompts"]  # 也更新，下次出图换场景
    await db.commit()
    return ImagePostDetail.from(post)
```

LLM 一次调用，~¥0.01，~2 秒。前端拿到新文案后 Canvas 实时叠字预览。

---

## 5. 技术细节

### 5.1 ImageProvider 抽象

```python
# app/image_generator/base.py
@dataclass
class ImageGenRequest:
    prompt: str
    reference_image_b64: str | None
    size: str = "1024x1024"
    negative_prompt: str | None = None

@dataclass
class ImageGenResult:
    url: str           # provider 返回的临时 CDN URL
    raw: dict          # 原始响应，调试/审计

class BaseImageProvider(ABC):
    name: str
    @abstractmethod
    async def generate(self, req: ImageGenRequest) -> ImageGenResult: ...

# app/image_generator/doubao.py
class DoubaoImageProvider(BaseImageProvider):
    name = "doubao"
    def __init__(self, api_key: str, base_url: str): ...
    async def generate(self, req): ...
        # POST https://ark.cn-beijing.volces.com/api/v3/images/generations
        # body: { model: "doubao-seedream-3-0-t2i-250415",
        #         prompt, image (base64 reference), size, ... }
```

**v1 工厂：** `get_image_provider()` → `DoubaoImageProvider` 读 env vars。**不入 ai_providers 表**——那张表是 OpenAI-compatible chat 模板，硬塞图像 API 会污染抽象。

### 5.2 环境变量

新增到 `.env.example`：

```bash
DOUBAO_API_KEY=
DOUBAO_BASE_URL=https://ark.cn-beijing.volces.com/api/v3
DOUBAO_IMAGE_MODEL=doubao-seedream-3-0-t2i-250415
IMAGE_POSTS_FONT_PATH=app/image_composer/fonts/SourceHanSans-Bold.otf
```

`Settings` 类（`app/config.py`）加同名字段，`DoubaoImageProvider` 从 `get_settings()` 拿。

### 5.3 Composer (Pillow)

```python
# app/image_composer/compose.py
from PIL import Image, ImageDraw, ImageFont

def compose(
    template: TemplateConfig,
    panel_paths: list[Path],
    captions: list[str],
    watermark: str,
    font_path: Path,
    output_path: Path,
) -> None:
    if template.composition == "vertical_stack":
        _compose_vertical_stack(template, panel_paths, captions, watermark, font_path, output_path)
    elif template.composition == "single":
        _compose_single(template, panel_paths[0], captions[0], watermark, font_path, output_path)

def _compose_vertical_stack(...):
    """双格反差：[caption1][panel1][caption2][panel2][watermark]"""
    w, h = template.output_size
    canvas = Image.new("RGB", (w, h), "white")
    font_size = int(w * template.font_size_ratio)
    font = ImageFont.truetype(str(font_path), font_size)
    # 计算每格高度，叠图，叠字，叠水印
    ...

def _compose_single(...):
    """单格大字：[big_caption][panel][watermark]"""
    ...
```

**字号自适应折行**：
- 测量文字像素宽度
- 超过 `w * 0.9` → 减字号
- 仍超 → 换行（最多 2 行）
- 仍超 → 截断 + ellipsis

**字体文件**：`backend/app/image_composer/fonts/SourceHanSans-Bold.otf`（思源黑体 Bold，免费商用，~5MB，**提交进 git 仓库**）。

### 5.4 用量记录

复用 `app/ai_providers/usage.py`，新增 purpose 值：

| purpose | 触发 | 计费 |
|---|---|---|
| `image_caption_gen` | LLM 出文案 | prompt + completion tokens |
| `image_caption_regen` | 文案重写 | 同上 |
| `image_generation` | 豆包出图 | 自定义 `cost_cents`（豆包按张计费，无 token 概念） |

`record_usage()` 签名需支持 `cost_cents` 参数，扩展之。

**成本估算表**（`app/ai_providers/usage.py`）追加：

```python
DOUBAO_SEEDREAM_PRICE_PER_IMAGE_CENTS = 30  # ¥0.3
```

### 5.5 守门 + 错误处理

**前置守门** (`POST /api/image-posts`)：
- ❌ Account 没传 `character_reference_path` → 400 「该公众号未上传角色参考图」
- ❌ `panel_asset_ids` 长度 ≠ `template.panel_count` → 400
- ❌ Account 不属于当前用户 / 不存在 → 404
- ⚠️ Account 没传 `default_thumb_media_id` → **不强制**（推送时合成图自己当封面）

**Pipeline 失败**：
- 豆包 timeout / 429 → Celery autoretry 2 次（已有模式，`autoretry_for=(httpx.HTTPError,)`）
- 豆包返回 NSFW / refusal → `status=failed, error_msg=具体原因`
- Composer 失败（字体加载 / IO） → 同上
- 微信推送失败（封面失效 / token 过期）→ 复用现有 `publish_draft` 重试 + token 刷新逻辑

**前端展示失败**：详情页顶部红 banner + error_msg + 「重试」按钮。

---

## 6. UI 设计

### 6.1 顶部导航

```
[Logo] | Library | 公众号 | 草稿 | 图片 ★新 | 设置 | 退出
```

### 6.2 列表页 `/image-posts`

跟「草稿」列表同款风格。按 `status` 分组：
- **生成中** (`pending` / `generating` / `composing` / `pushing`)
- **可推送** (`generated`)
- **已推送** (`pushed`)
- **失败** (`failed`)

每行：缩略图（48×48） · 模板标签 chip · 主题摘要（前 20 字） · 公众号名 · 创建时间 · 状态 chip · 操作按钮。

右上角 `+ 新建` 按钮 → 打开生成 modal。

### 6.3 生成表单 modal

```
公众号 [下拉]
模板  [双格反差] [单格大字]    (chip 二选一)
主题  [textarea, 6-8 行]
语气  [幽默] [自嘲] [扎心] [温暖]  (chip 可选)
图源  [● AI 新生成] [○ 从图库选]

(图源=图库时显示)
  [📁 选择图片] → 弹二级 modal 显示 image_assets 列表，选 N 张

[ 取消 ]  [ 生成 ]
```

### 6.4 详情页 `/image-posts/{id}`

**左右分栏**：

**左侧（图片预览区，~60% 宽）：**
- 顶部：Canvas 实时叠字预览（前端绘制）
- 底部 toolbar：
  - `🔄 重新生成图` （调豆包，¥0.3-0.6）
  - `⬇ 下载 PNG`（导出 Canvas 当前帧）

**右侧（编辑区，~40% 宽，sticky）：**
- 文案输入框（双格 = 2 个 input，单格 = 1 个 input）
  - 改字 → 左侧 Canvas 立即更新
- `💾 保存文案`（PATCH，存 db）
- `✨ 重写文案`（调 LLM，~¥0.01）
- 元信息卡片：主题 / 语气 / 模板 / 公众号 / 创建时间
- 状态 chip + 进度 banner（轮询）
- 底部大按钮：`推送到微信草稿箱`（disabled until status=generated & captions 完整）

### 6.5 状态轮询

跟现有 `DraftDetail` 同款：`status` 不在 terminal 状态时 `refetchInterval: 2000` 拉详情，前端 banner 展示进度。

### 6.6 实时叠字预览（核心 UX）

**纯前端 Canvas，无后端调用：**

```typescript
function renderPreview(canvas, rawImageUrls, captions, template) {
  // 1. 加载 raw images
  // 2. 按 template.composition 拼图
  // 3. 用 canvas.fillText 叠中文字（CSS @font-face 加载思源黑体）
  // 4. 加水印
}
```

文案 input change → useEffect 重渲染。Debounce ~50ms 流畅。

**风险**：Canvas 渲染和 Pillow 渲染可能有细微差异。**对策**：保证最终推送用的图来自 Pillow（服务端），UI 只是高保真预览。提交前可以加一行小字提醒「预览仅供参考，最终图以推送结果为准」。

### 6.7 图库浏览页 `/image-assets`（次要）

- 按账号筛选（默认显示当前活跃账号）
- 网格布局，缩略图 + scene_prompt 截断 + tags 显示 + used_count 标签
- v1 只读，删/上传按钮 v2

---

## 7. API 路由

### 7.1 ImagePost 路由 (`/api/image-posts`)

| 方法 | 路径 | 说明 |
|---|---|---|
| `POST` | `/api/image-posts` | 创建 image post 并触发生成 |
| `GET` | `/api/image-posts` | 分页列表（按 status 分组） |
| `GET` | `/api/image-posts/{id}` | 详情 |
| `PATCH` | `/api/image-posts/{id}` | 仅修改 captions（前端"保存文案"） |
| `DELETE` | `/api/image-posts/{id}` | 删除（关联 asset 不删） |
| `POST` | `/api/image-posts/{id}/regenerate` | 重新出图（重跑 generate task） |
| `POST` | `/api/image-posts/{id}/regenerate-captions` | 仅重写文案（同步） |
| `POST` | `/api/image-posts/{id}/push-to-wechat` | 推送（触发 compose_and_push task） |

### 7.2 ImageAsset 路由 (`/api/image-assets`)

| 方法 | 路径 | 说明 |
|---|---|---|
| `GET` | `/api/image-assets?account_id=X` | 分页列表 |
| `GET` | `/api/image-assets/{id}` | 详情 |
| `GET` | `/api/image-assets/{id}/file` | 图片二进制（用于 UI 缩略图） |

### 7.3 Account 路由扩展

| 方法 | 路径 | 说明 |
|---|---|---|
| `POST` | `/api/accounts/{id}/character-reference` | 上传角色参考图（multipart） |
| `DELETE` | `/api/accounts/{id}/character-reference` | 清除角色参考图 |

实现跟现有 `default-cover` 上传端点高度相似（已有的 multipart + 校验 + 存盘 + DB 更新）。

---

## 8. 测试策略

| 层 | 测试内容 |
|---|---|
| 单元 | Composer 渲染（黄金图字节对比） |
| 单元 | Template caption_prompt_template 格式化 |
| 单元 | DoubaoImageProvider 请求体序列化 + 响应解析 |
| 单元 | 字号自适应 / 文字折行 |
| 单元 | Tag 提取（基于 scene_prompt） |
| 集成 | 全 pipeline 成功路径：respx mock 豆包 + 微信 |
| 集成 | 复用路径：传 panel_asset_ids → 跳过豆包调用 |
| 集成 | 失败路径：豆包 NSFW / 微信 token 过期 |
| 集成 | 前置守门：未上传角色参考图 → 400 |
| 集成 | 文案重写路由：只调 LLM 不调豆包 |
| 集成 | image_asset.used_count 复用时正确自增 |
| 集成 | 字符删除策略：删 image_post 后 asset 仍在 |
| 前端 | Canvas 渲染快照测试（playwright） |
| 前端 | 表单提交 + 详情页轮询 |

预计 **12-15 条新测试**，跟现有 `test_drafts_routes.py` 风格保持一致。

---

## 9. 风险与缓解

| 风险 | 影响 | 缓解 |
|---|---|---|
| 豆包 Seedream 角色一致性不稳定 | 同一角色出图风格漂 | v1 用 reference_image + 强 prompt；v2 可上 LoRA / IP-Adapter |
| 豆包 NSFW 拒绝率高 | 失败率高 | 文案模板限制（不引导敏感话题）；失败展示明确 error_msg 让用户重试 |
| Canvas vs Pillow 渲染差异 | 用户看到的预览跟推送结果不符 | 字体一致；UI 文案提示「预览仅供参考」；v2 可让后端预生成缩略图 |
| 图库膨胀 | 磁盘占用 | 每张 ~200KB，1000 张 = 200MB，可接受；v2 加自动归档 / 清理 |
| 豆包 API 单价上涨 | 成本失控 | 用量记录 + 设置月度上限 alert |

---

## 10. 实施分阶段建议

**阶段 1：MVP（无图库复用）**
- 表 / Provider / Composer / 2 个 Celery task / 基础 UI
- 不做图库复用（每次都新生成）

**阶段 2：图库复用**
- `image_assets` 表 + `panel_asset_ids` 字段
- 表单加 toggle / 图库浏览页
- 测试复用路径

**阶段 3：抛光**
- 实时 Canvas 预览
- 用量记录
- 错误 banner

建议在 `writing-plans` 阶段拆分成具体 task list。

---

## 11. 附录：豆包 Seedream API 草样

请求示例：

```bash
curl -X POST https://ark.cn-beijing.volces.com/api/v3/images/generations \
  -H "Authorization: Bearer $DOUBAO_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "model": "doubao-seedream-3-0-t2i-250415",
    "prompt": "a cute capybara sitting at desk writing, flat cartoon style, no text",
    "image": "data:image/png;base64,...",
    "size": "1024x1024",
    "response_format": "url"
  }'
```

响应：
```json
{
  "data": [{ "url": "https://ark-content-cdn..." }],
  "usage": { "generated_images": 1 }
}
```

字段名 / 模型 ID 实施时以官方 SDK 文档为准。
