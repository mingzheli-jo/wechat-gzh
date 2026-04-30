# 微信公众号批量改写系统 — 设计文档

**日期**：2026-04-30
**作者**：Stella
**状态**：草案 v1
**项目**：wechat-batch-rewriter

---

## 1. 项目概述

### 1.1 目标

构建一个**网页端工具**，帮助单用户批量将微信公众号爆款文章改写为可发布的新文章，并同步到指定公众号的草稿箱。

### 1.2 核心价值

- 把"找文章 → 改写 → 审核 → 发草稿"的人工流程自动化为可批量调度的流水线
- 通过角色化的多 AI 模型接入，平衡成本与质量
- 多公众号矩阵集中管理

### 1.3 范围（一期）

**包含**：
- 用户手动提交 URL → 抓取入素材库
- 素材库管理（标签、状态、分类）
- 批量触发 AI 改写（标题 + 正文）
- AI 审核（4 维度打分）
- 图片自动搬运 + 用户逐图复核
- 同步到微信公众号草稿箱
- 多 AI Provider 接入（OpenAI 兼容协议统一）
- 多公众号管理
- 单用户登录
- 本地敏感词黑名单（合规审核兜底）
- Docker Compose 一键部署

**不包含**（后续迭代）：
- AI 自动定时发布（需要排程系统）
- AI 生成封面图（图像模型）
- 图片水印识别 / 二维码识别
- 多用户 / 团队 / SaaS 多租户
- 关键词监控与自动选题
- 第三方爆款数据平台对接（如新榜）

---

## 2. 关键决策记录（ADR）

| # | 决策 | 选择 | 理由 |
|---|---|---|---|
| 1 | 文章来源 | 用户手动粘贴 URL | 微信反爬严格，第三方 API 收费高；先解决基本面 |
| 2 | 工作流形态 | 素材库（先入库后改写） | 抓取/改写解耦，便于打标签和分批操作 |
| 3 | 公众号—类型—模板关系 | 一对一（模板挂在公众号下） | 大多数运营是"一号一定位"，操作最顺 |
| 4 | 改写后输出 | 同步到微信草稿箱 | 比单纯导出价值更大，但不做自动发布 |
| 5 | 用户体系 | 单用户 + 固定账号密码 | 个人使用，无需多租户复杂度 |
| 6 | AI 审核维度 | 合规 + 原创度 + 质量 + 标题党 | 全维度覆盖；结果用打分模式不硬卡 |
| 7 | AI 模型路由 | 角色制（writer / reviewer / lite） | 业务对应"写作型/审核型/轻量型"，配置一次到处用 |
| 8 | 图片处理 | 默认搬运原图 + 用户逐图复核 | 自动化与可控的折衷 |
| 9 | 后端语言 | Python + FastAPI | 异步原生，AI 生态最完整 |
| 10 | 数据库 | PostgreSQL + Redis | PG 业务数据，Redis 队列+缓存+token |
| 11 | 架构形态 | 单体代码 + 独立 Worker 容器 | 复杂度可控，可平滑演进到流水线拆分 |

---

## 3. 系统架构

### 3.1 整体形态

5 个 Docker 容器，一份 `docker-compose.yml` 编排：

```
┌─────────────────────────────────────────┐
│  Frontend (React + Vite + Tailwind)     │ ← 浏览器
└────────────────┬────────────────────────┘
                 │ HTTPS
┌────────────────▼────────────────────────┐
│  API Container (FastAPI)                │
│  - 路由 / 认证 / CRUD                    │
│  - 把任务丢进队列                         │
└────────┬──────────────────────┬─────────┘
         │                      │
   ┌─────▼──────┐         ┌─────▼──────┐
   │  Postgres  │         │   Redis    │
   │  业务数据   │         │  队列+缓存  │
   └─────▲──────┘         └─────▲──────┘
         │                      │
┌────────┴──────────────────────┴─────────┐
│  Worker Container (Celery)               │
│  - 抓取 / 改写 / 审核 / 推送微信          │
│  - 长任务都在这里跑                       │
└──────────────────────────────────────────┘
```

### 3.2 模块划分（后端）

```
backend/
├── app/
│   ├── main.py                    # FastAPI 入口
│   ├── config.py                  # Settings (pydantic-settings)
│   ├── auth/                      # 单用户登录 (JWT)
│   ├── accounts/                  # 公众号管理 (CRUD + access_token)
│   ├── ai_providers/              # AI 抽象层
│   │   ├── base.py                # 统一接口
│   │   ├── openai_compat.py       # 兼容 OpenAI 协议的统一适配器
│   │   └── registry.py            # 角色 → provider 映射
│   ├── crawler/                   # 微信文章抓取
│   │   ├── fetcher.py             # HTTP 抓取 + 反爬处理
│   │   └── parser.py              # 解析正文/图片/标题
│   ├── library/                   # 素材库
│   ├── rewriter/                  # 改写流水线
│   │   ├── title.py
│   │   ├── content.py
│   │   └── prompt_builder.py      # 拼接 prompt
│   ├── reviewer/                  # AI 审核
│   │   ├── compliance.py
│   │   ├── originality.py
│   │   ├── quality.py
│   │   └── clickbait.py
│   ├── drafts/                    # 草稿管理
│   ├── images/                    # 图片下载/上传/复核
│   ├── wechat/                    # 微信公众号 API
│   │   ├── token.py               # access_token 自动刷新
│   │   ├── material.py            # 永久素材库
│   │   └── draft.py               # 草稿箱推送
│   ├── tasks/                     # Celery task 定义
│   │   ├── crawl.py
│   │   ├── rewrite.py
│   │   ├── review.py
│   │   └── publish.py
│   ├── db/                        # SQLAlchemy + Alembic
│   └── api/                       # 路由层（薄）
├── frontend/                      # React + Vite + shadcn/ui
├── docker/
│   ├── Dockerfile.api
│   ├── Dockerfile.worker
│   └── Dockerfile.web
├── docker-compose.yml
├── docker-compose.dev.yml
└── docker-compose.test.yml
```

设计原则：
- **API 层薄**：只做参数校验和分发，业务逻辑在领域模块
- **AI Provider 抽象统一**：业务代码只调"角色"，不关心底层是哪家
- **Celery task 是流水线的"步骤"**：每步独立可重试

---

## 4. 数据模型

PostgreSQL 主要表结构。

### 4.1 `accounts` — 公众号

| 字段 | 类型 | 说明 |
|---|---|---|
| id | UUID PK | |
| name | str | 公众号显示名 |
| wechat_appid | str | 微信开放平台 AppID |
| wechat_secret | str (加密) | AppSecret，AES/Fernet 加密存储 |
| category | str | 类型：职场/母婴/养生/育儿/... |
| title_prompt | text | 标题改写提示词 |
| content_prompt | text | 正文改写提示词 |
| style_desc | text | 公众号语气/风格描述 |
| is_active | bool | |
| created_at / updated_at | timestamp | |

### 4.2 `library_items` — 素材库

| 字段 | 类型 | 说明 |
|---|---|---|
| id | UUID PK | |
| source_url | str unique | 微信原文 URL |
| original_title | str | |
| original_author | str | |
| original_content_html | text | |
| original_content_text | text | 用于 token 计数和原创度对比 |
| images | jsonb | `[{url, alt, position}, ...]` |
| status | enum | `pending` / `processing` / `done` / `failed` |
| tags | jsonb | 用户打的标签 |
| crawled_at | timestamp | |
| error_msg | text | |

### 4.3 `drafts` — 草稿

| 字段 | 类型 | 说明 |
|---|---|---|
| id | UUID PK | |
| library_item_id | UUID FK | |
| account_id | UUID FK | |
| title | str | 改写后标题 |
| content_html | text | 改写后正文 |
| cover_image_id | UUID FK | |
| status | enum | `draft` / `reviewing` / `reviewed` / `published_to_wechat` / `failed` |
| review_report_id | UUID FK | |
| wechat_media_id | str | 推送后微信 media_id |
| wechat_pushed_at | timestamp | |
| created_at / updated_at | timestamp | |

### 4.4 `review_reports` — 审核报告

| 字段 | 类型 | 说明 |
|---|---|---|
| id | UUID PK | |
| draft_id | UUID FK | |
| compliance | jsonb | `{score, issues[], model}` |
| originality | jsonb | `{score, similarity, issues[]}` |
| quality | jsonb | `{score, issues[]}` |
| clickbait | jsonb | `{score, issues[]}` |
| overall_score | int | 综合分 |
| created_at | timestamp | |

### 4.5 `images` — 图片资产

| 字段 | 类型 | 说明 |
|---|---|---|
| id | UUID PK | |
| draft_id | UUID FK | |
| original_url | str | 原文图 URL |
| local_path | str | 本地存储路径 |
| wechat_media_id | str | |
| wechat_url | str | 微信内部 URL |
| status | enum | `pending` / `downloaded` / `uploaded` / `replaced` / `removed` |
| position | int | 在文章中的位置 |
| is_cover | bool | |

### 4.6 `tasks` — 任务追踪

| 字段 | 类型 | 说明 |
|---|---|---|
| id | UUID PK | task_id |
| kind | enum | `crawl` / `rewrite` / `review` / `publish` |
| ref_id | UUID | 关联到 library_item / draft |
| status | enum | `queued` / `running` / `success` / `failed` |
| progress | int | 0-100 |
| started_at / finished_at | timestamp | |
| error | text | |

### 4.7 配置类

- **`ai_providers`**：`{id, name, api_key (加密), base_url, model_list (jsonb), enabled}`
- **`role_bindings`**：`{role: 'writer'|'reviewer'|'lite', provider_id, model}`
- **`sensitive_words`**：本地敏感词黑名单（一期，作为合规审核兜底）
- **`ai_usage`**：每次 AI 调用的 token / cost 记录（按天聚合 + 按 provider 聚合）
- **`settings`**：全局配置（账号密码哈希、JWT secret 等）

---

## 5. 核心数据流

### 5.1 流程 1：素材入库

```
浏览器 ──POST /library {urls:[...]}──► API
                                        │ 创建 N 条 library_items (pending)
                                        │ 投递 N 个 crawl task
                                        ▼
                                      Worker (crawler)
                                        │ httpx 抓取 + lxml 解析
                                        │ 提取标题/作者/正文/图片
                                        ▼
                                      更新 status=done
浏览器 ──轮询 /tasks ──► API ──► 返回进度
```

抓取失败标 `failed` + `error_msg`，前端可重试。抓取使用 `httpx` + 随机 UA + 重试 3 次。

### 5.2 流程 2：批量改写（核心 Pipeline）

每篇文章一条 Celery chain：

```
rewrite_title → rewrite_content → process_images → review_all (group: 4 维度并行) → aggregate_report
```

API 接收 `{library_item_ids, account_id, override_prompts?}`，为每个 item 创建 draft + 投递 chain，立即返回 task_ids。

每一步更新 `tasks.progress`（25 / 50 / 75 / 100）。任何一步失败：链终止，draft 标 `failed`，`error_msg` 记录卡在哪一步。

**Token 成本控制**：rewrite_content 输入做截断，超过模型上下文就分段处理。

### 5.3 流程 3：图片处理（嵌在改写流程中）

```
process_images:
  for img in draft.images:
    1. 下载到 /data/images/{draft_id}/{idx}.{ext}
    2. 调微信 add_material API 上传到该公众号永久素材库
    3. 拿回 media_id 和 wechat_url
    4. 替换 content_html 里的 <img src>
    5. 更新 images 表 status=uploaded
  默认选第一张图作为封面
```

前端复核：草稿详情页右侧图片列表（缩略图），可标记封面 / 删除（同步移除 HTML 中 `<img>`）/ 上传替换。

### 5.4 流程 4：推送微信草稿箱

```
浏览器 ──POST /drafts/:id/publish-to-wechat──► API
                                                │ 投 publish task
                                                ▼
                                              Worker
                                                │ 1. 取 access_token (Redis 缓存)
                                                │ 2. 校验所有图片 status=uploaded
                                                │ 3. 调 add_draft API
                                                │ 4. 拿 media_id
                                                │ 5. 更新 draft.status=published_to_wechat
```

access_token 在 Redis 按 `account_id` 缓存，过期前主动刷新。推送前严格校验图片状态。

---

## 6. AI Provider 抽象层

### 6.1 统一接口

```python
class BaseProvider(ABC):
    name: str
    @abstractmethod
    async def chat(
        self,
        messages: list[Message],
        model: str,
        temperature: float = 0.7,
        max_tokens: int | None = None,
        json_mode: bool = False,
    ) -> ChatResult: ...
```

### 6.2 OpenAI 兼容适配器（一个适配器搞定主流模型）

Kimi、DeepSeek、智谱、Qwen、豆包、OpenRouter 等均兼容 OpenAI Chat Completions 协议，使用同一个 `OpenAICompatProvider`，配置不同 `base_url + api_key` 即可：

```python
class OpenAICompatProvider(BaseProvider):
    def __init__(self, name, api_key, base_url, default_models):
        self.client = AsyncOpenAI(api_key=api_key, base_url=base_url)

    async def chat(self, messages, model, **kwargs):
        resp = await self.client.chat.completions.create(...)
        return ChatResult(content=..., usage=..., model=...)
```

新增模型：前端配置页填 `name / base_url / api_key / 模型列表` → 写入 `ai_providers` 表 → 重新加载 registry。

### 6.3 角色绑定

启动时和热更新时从 `role_bindings` 表加载：

```python
registry.bind_role("writer",   provider="deepseek", model="deepseek-chat")
registry.bind_role("reviewer", provider="kimi",     model="moonshot-v1-32k")
registry.bind_role("lite",     provider="deepseek", model="deepseek-chat")

# 业务调用
result = await registry.role("writer").chat(messages, ...)
```

业务代码不依赖具体 provider；切换模型只改 `role_bindings` 表。

---

## 7. 错误处理矩阵

| 场景 | 处理 |
|---|---|
| AI API 超时 (60s+) | Celery 重试 3 次，指数退避 (10s/30s/90s)；3 次都失败 → task failed |
| AI API 限流 (429) | 解析 `Retry-After`，等够再重试；超 5 次放弃 |
| AI 返回非法 JSON（审核） | 重试 1 次 + 强化 prompt；再失败 → 该维度记 0 分 + 原始输出供排查 |
| AI 返回空 / 拒答（合规触发） | draft `failed`，error_msg 提示"模型拒绝生成，请换模型" |
| 抓取被反爬 | 重试 1 次（新 UA），失败 → library_item `failed`，前端可重试 |
| 图片下载 404 / 超时 | 该图标 `failed`，不阻塞整篇文章；前端复核时提示 |
| 微信 access_token 失效 | 强刷 token 后重试一次 |
| 微信其他 errcode | 直接失败，把原始错误码和说明写到 `error` 字段 |
| Worker 进程被杀 / 重启 | Celery `acks_late=True`；幂等性靠 task_id 检查 draft 当前 status |

### 7.1 成本和限流

- 每次 AI 调用记录 `prompt_tokens / completion_tokens / cost` 到 `ai_usage`
- 批量改写一次最多投递 N 篇（默认 20），可配置
- 本地敏感词黑名单作为合规审核兜底（启动时加载，零成本）

---

## 8. 部署

### 8.1 docker-compose.yml 关键服务

```yaml
services:
  postgres:
    image: postgres:16-alpine
    volumes: [pg_data:/var/lib/postgresql/data]
  redis:
    image: redis:7-alpine
    volumes: [redis_data:/data]
  api:
    build: { context: ., dockerfile: docker/Dockerfile.api }
    depends_on: [postgres, redis]
    env_file: .env
    ports: ["8000:8000"]
    command: uvicorn app.main:app --host 0.0.0.0 --port 8000
  worker:
    build: { context: ., dockerfile: docker/Dockerfile.worker }
    depends_on: [postgres, redis]
    env_file: .env
    volumes: [image_data:/data/images]
    command: celery -A app.tasks worker --concurrency=4 -Q default,crawl,rewrite,review,publish
  web:
    build: { context: ., dockerfile: docker/Dockerfile.web }
    ports: ["80:80"]
    depends_on: [api]
volumes:
  pg_data: {}
  redis_data: {}
  image_data: {}
```

`web` 容器为多阶段构建：node 编译 → nginx 提供静态资源 + 反代 `/api → api:8000`，浏览器只跟 80 端口打交道，无 CORS 问题。

### 8.2 环境变量（`.env.example`）

```env
DATABASE_URL=postgresql+asyncpg://postgres:postgres@postgres:5432/wechat_rewriter
REDIS_URL=redis://redis:6379/0

ADMIN_USERNAME=admin
ADMIN_PASSWORD_HASH=$2b$12$...
JWT_SECRET=<long random>

ENCRYPTION_KEY=<32 byte base64>

DEFAULT_WRITER_PROVIDER=deepseek
DEFAULT_REVIEWER_PROVIDER=kimi
DEFAULT_LITE_PROVIDER=deepseek

CRAWLER_TIMEOUT=30
CRAWLER_MAX_RETRY=3
CELERY_WORKER_CONCURRENCY=4
```

`.env` 不进 git，仓库只放 `.env.example`。

### 8.3 数据库迁移

Alembic。`api` 容器 entrypoint 启动时自动跑 `alembic upgrade head`。

### 8.4 部署命令

```bash
# 第一次
cp .env.example .env
# 编辑 .env
docker compose up -d --build
docker compose exec api python -m app.scripts.init_admin

# 更新
git pull && docker compose up -d --build api worker web

# 备份
docker compose exec postgres pg_dump -U postgres wechat_rewriter > backup.sql
```

### 8.5 安全

- 公众号 secret、AI api_key 用 Fernet 加密（密钥放 `.env`）
- 单用户登录 bcrypt + JWT，token 24h 过期
- 推荐前端套 Caddy/Nginx + Let's Encrypt 走 HTTPS（部署文档单独提供）
- Postgres / Redis 不暴露到宿主机端口

---

## 9. 测试策略

### 9.1 测试金字塔

- **Unit（多）**：纯函数、解析器、prompt 拼接、provider registry
- **Integration（中）**：testcontainers 起真 Postgres/Redis，跑 API 路由全链路（mock AI 调用）
- **E2E（少）**：Playwright，3 条主路径，用 mock provider 不打真 AI

工具：pytest + pytest-asyncio + httpx.AsyncClient + testcontainers-python + respx + fakeredis；前端 vitest + Playwright。

### 9.2 覆盖率目标

后端单元测试 **80%+**。

### 9.3 不测什么

- AI 输出质量本身（人工抽检）
- 微信 API 真实联调（手动验收清单）
- 第三方 LLM 真实调用（季度跑兼容性测试）

### 9.4 CI 流程

```yaml
1. ruff check + ruff format --check
2. mypy app/
3. pytest tests/unit -v --cov=app --cov-fail-under=80
4. pytest tests/integration -v
5. cd frontend && pnpm typecheck && pnpm test
6. docker compose -f docker-compose.test.yml up -d
7. playwright test
```

---

## 10. 实施阶段建议（仅供后续 plan 参考）

按依赖关系分四阶段，每阶段可独立验证：

1. **阶段 1**：基础设施 — 项目骨架、Docker、Postgres、Redis、Alembic、登录、公众号 CRUD
2. **阶段 2**：素材库 — 抓取 + 解析 + Celery 投递 + 进度查询 + 列表/标签管理
3. **阶段 3**：改写流水线 — AI Provider 抽象 + 角色绑定 + 改写 chain + 审核 group + 报告聚合
4. **阶段 4**：微信集成 — access_token 管理 + 素材库上传 + 草稿箱推送 + 图片复核界面

每阶段 E2E 跑通才进下一阶段。

---

## 11. 待办与开放问题

- 当前未对接「定时发布」，二期再评估是否上排程系统
- 未决定是否引入 AI 生成封面图（图像模型成本较高）
- 二期再加入第三方爆款数据平台对接（可作为素材库的另一个入口）
- 部分公众号文章为图片型内容（图文比例失衡），改写效果可能受限，需要 prompt 工程持续优化

---

**End of Design Document**
