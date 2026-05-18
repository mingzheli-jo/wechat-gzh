# 微信公众号文章 & 账号统计设计

**Date:** 2026-05-18
**Status:** Design — pending implementation plan
**Author:** brainstormed via /brainstorming

## 目标

为系统接入的每个微信公众号拉取「截止昨天」的：

- 文章维度：阅读、点赞、分享、评论总数
- 账号维度：当前粉丝数、昨日新增、昨日取消
- 派生汇总：最近 30 天文章数、最近 30 天总阅读

数据每天凌晨自动刷新，前端有「立即刷新」按钮兜底。

## 范围共识（在 brainstorm 阶段已锁定）

| 决策 | 选择 |
|------|------|
| 流量主收益 | **不做**（无官方开放 API；以后再补，字段不预留） |
| 数据粒度 | 账号汇总 + 可点进去看每篇文章明细 |
| 历史/趋势 | 不做时间序列；只存最新数字，每日 upsert 覆盖 |
| 评论 | 只要总数，不拉评论内容 |
| 抓取方式 | 每天 03:00 Celery beat 自动拉 + 页面手动刷新按钮 |
| UI 入口 | 顶部导航新增「数据」页 |
| 与 Draft/LibraryItem 关联 | 不关联，独立展示 |

## 非目标

- 不存每日快照、不画趋势曲线
- 不拉评论正文 / 作者 / 点赞数
- 不与 `LibraryItem` 或 `Draft` 做内部关联（即使是同一篇文章也不显式 link）
- 不做流量主广告收益
- 不做前端单元测试（沿用项目现有规范）

## 架构 & 模块布局

| 路径 | 动作 | 责任 |
|------|------|------|
| `app/wechat/stats.py` | 新建 | 统计相关微信 API 客户端：`fetch_user_summary`、`fetch_user_cumulate`、`fetch_article_total`、`fetch_comment_count` |
| `app/stats/__init__.py` | 新建 | 包 |
| `app/stats/models.py` | 新建 | `WechatArticle` ORM 模型 |
| `app/stats/schemas.py` | 新建 | Pydantic schemas |
| `app/stats/service.py` | 新建 | DB upsert + 查询封装 |
| `app/stats/routes.py` | 新建 | FastAPI 路由 |
| `app/api/router.py` | 修改 | 注册 stats 路由 |
| `app/accounts/models.py` | 修改 | Account 表新增 4 列 |
| `app/accounts/schemas.py` | 修改 | 暴露上述字段（read-only） |
| `app/tasks/stats.py` | 新建 | 2 个 Celery task：`sync_all_accounts_stats`、`sync_one_account_stats` |
| `app/tasks/maintenance.py` | 修改 | beat schedule 加 `sync-stats-daily` |
| `app/config.py` | 修改 | 加 `stats_backfill_days: int = 30`、`stats_daily_cron_hour: int = 3` |
| `alembic/versions/<hash>_add_wechat_stats.py` | 新建 | 单 migration |
| `frontend/src/pages/Stats.tsx` | 新建 | 账号列表页 |
| `frontend/src/pages/StatsDetail.tsx` | 新建 | 单账号文章明细页 |
| `frontend/src/lib/api/stats.ts` | 新建 | API client |
| `frontend/src/App.tsx` + 顶部导航 | 修改 | 新增「数据」入口 |

## 数据模型

### `wechat_articles`（新表）

```python
class WechatArticle(Base):
    __tablename__ = "wechat_articles"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    account_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("accounts.id", ondelete="CASCADE"), nullable=False, index=True
    )
    msgid: Mapped[int] = mapped_column(BigInteger, nullable=False)
    article_idx: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    publish_time: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    read_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    like_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    share_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    comment_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    last_synced_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    __table_args__ = (
        UniqueConstraint("account_id", "msgid", "article_idx", name="uq_wechat_article"),
        Index("ix_wechat_article_publish", "account_id", "publish_time"),
    )
```

### `accounts` 表新增 4 列

```python
follower_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
new_follow_yesterday: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
cancel_follow_yesterday: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
stats_synced_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
```

### 字段到微信 API 映射

| 字段 | API |
|------|-----|
| `follower_count` | `/datacube/getusercumulate` 最近行的 `cumulate_user` |
| `new_follow_yesterday` | `/datacube/getusersummary` 昨日行的 `new_user` |
| `cancel_follow_yesterday` | `getusersummary` 昨日行的 `cancel_user` |
| `WechatArticle.read_count` | `/datacube/getarticletotal` 的 `int_page_read_count` |
| `WechatArticle.like_count` | 同上的 `like_count` |
| `WechatArticle.share_count` | 同上的 `share_count` |
| `WechatArticle.comment_count` | `/cgi-bin/comment/list` 的 `total`（按 `msg_data_id=msgid` 查） |

## 抓取流程

### 每日 Celery beat 任务

`app.tasks.stats.sync_all_accounts_stats` —— 默认 `cron 03:00 daily`

1. 读取所有 `Account`（**顺序遍历**，不并发）
2. 对每个 account 调用 `sync_one_account_stats.apply()`
3. 单账号失败：catch + log + 继续下一个，不阻断 batch

### 单账号同步逻辑

`sync_one_account_stats(account_id)`：

1. 取 access_token（复用 `app/wechat/token.py`）
2. **拉粉丝**：
   - `getusercumulate(begin=yesterday, end=yesterday)` → `follower_count`
   - `getusersummary(begin=yesterday, end=yesterday)` → `new_follow_yesterday` / `cancel_follow_yesterday`
3. **拉文章累积数据**：
   - `getarticletotal(begin, end)` 每次最多 7 天窗口
   - 循环切片直到覆盖 `stats_backfill_days`（默认 30 → 5 次调用）
   - 返回是「该文章自发布以来累积数」，daily 刷过去 30 天即可
4. **拉评论数**：每篇文章 `comment/list(msg_data_id=msgid, begin=0, count=0)` → `total`
   - N+1：30 天通常 N < 50，可接受
   - 单篇失败 → 该篇 `comment_count` 保留旧值，不阻断
5. **DB upsert（单事务）**：
   - Account 4 字段 + `stats_synced_at = now()`
   - `wechat_articles` 按 `(account_id, msgid, article_idx)` upsert
6. 返回 `{accounts_updated, articles_upserted, errors[]}`

### 手动刷新触发

- `POST /api/stats/refresh` → `sync_all_accounts_stats.delay()`，返回 202 + `{job_id, status: "queued"}`
- `POST /api/stats/refresh?account_id=<uuid>` → `sync_one_account_stats.delay(account_id)`
- 前端用 `stats_synced_at` 轮询确认完成（3 秒间隔，最长 30 秒）

### 初始 backfill

不需要单独代码路径。第一次跑 cron 或手动「全局刷新」即灌入过去 30 天数据，因为 daily 跑本身就是 30 天全量。

## 后端 API

| Method | Path | 用途 | 状态码 |
|--------|------|------|--------|
| `GET` | `/api/stats/accounts` | 数据页主表 | 200 |
| `GET` | `/api/stats/accounts/{account_id}/articles?days=30&sort=publish_time` | 单账号文章明细 | 200 / 404 |
| `POST` | `/api/stats/refresh` | 触发全量刷新 | 202 |
| `POST` | `/api/stats/refresh?account_id=<uuid>` | 触发单账号刷新 | 202 / 404 |

### Schemas

```python
class AccountStatsRow(BaseModel):
    account_id: uuid.UUID
    name: str
    follower_count: int
    new_follow_yesterday: int
    cancel_follow_yesterday: int
    articles_count_30d: int     # 派生：count(wechat_articles where publish_time > now - 30d)
    total_read_30d: int         # 派生：sum(read_count) 同上
    stats_synced_at: datetime | None


class ArticleStatsRow(BaseModel):
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

`AccountStatsRow.articles_count_30d` / `total_read_30d` 在 `service.list_account_stats()` 里走 group-by SQL 算出来，不入表。账号数 < 几十时性能无问题。

派生字段的 **30 天窗口固定写死在 service 层**，不跟 `stats_backfill_days` 联动。`stats_backfill_days` 只控制 daily sync 拉多深，便于以后想拉更长历史时不影响 UI 展示窗口；前端列表/明细页的"30 天"标签也是固定的。

### `articles` 端点查询参数

| 参数 | 默认 | 取值 |
|------|------|------|
| `days` | 30 | 7 / 30 / 90 |
| `sort` | `publish_time` | `publish_time` / `read_count` / `like_count` / `share_count` / `comment_count` |
| `order` | `desc` | `desc` / `asc` |

## 前端

### 导航

顶部菜单「图片」右边加「数据」入口。

### `/stats` 账号列表页

| 元素 | 内容 |
|------|------|
| 页面顶部 | 标题「数据」+ 右上角「全局刷新」按钮（disabled while pending） |
| 主表 | 一行一个账号 |
| 列 | 账号名 / 当前粉丝 / 昨日新增 / 昨日取消 / 30 天文章数 / 30 天总阅读 / 同步时间（相对时间）/ 操作（「查看明细」link + 「刷新本号」icon） |
| 空状态 | 「还没有同步过统计数据。」+ 「立即同步」按钮 |
| 加载 | skeleton 行 |
| 默认排序 | 30 天总阅读 desc，列头可点切换 |

### `/stats/:accountId` 单账号明细页

```
┌─────────────────────────────────────────────────────────┐
│ ← 返回                            [刷新本号]              │
│                                                          │
│ 账号名 · 当前粉丝 1234 · 昨日 +12 / -3 · 同步于 2 小时前  │
└─────────────────────────────────────────────────────────┘

时间范围: [7 天] [30 天] [90 天]      排序: 发布时间 ▼

┌─────────────────────────────────────────────────────────┐
│ 标题                  发布时间    阅读  点赞  分享  评论 │
├─────────────────────────────────────────────────────────┤
│ XXX 的文章           05-17       2.3k    45   12    8  │
│ ...                                                      │
└─────────────────────────────────────────────────────────┘
```

- summary card 走 `GET /api/stats/accounts/{id}`（service 内 reuse `list_account_stats` 单行查询）
- 文章表走 `GET /api/stats/accounts/{id}/articles?days=<n>&sort=<field>`
- 「刷新本号」按下变 spinner，3 秒后 refetch；如 `stats_synced_at` 比按按下时新就停 spinner，否则再轮一次（最长 30 秒）

### 视觉风格

复用 Editorial Swiss（参考 `2026-05-06-frontend-polish-editorial-swiss.md`）：等宽数字字体放数字、强对比线分隔列表、不堆装饰。尊重 `prefers-reduced-motion`。

## 错误处理

| 情形 | 行为 |
|------|------|
| Access token 过期 / 失效 | 复用 `app/wechat/token.py` 自动刷新 |
| 单 API timeout | httpx 10s + 1 次 backoff 重试，再失败 → log error，该字段保留旧值 |
| 微信 daily quota 命中（errcode 45009 等） | log + 整个 account 任务 abort，下次 cron 再来 |
| 账号已封 / appid 失效（errcode 40013 等） | log + abort 该 account，不影响其他账号 |
| 评论 API 失败 | 单篇 `comment_count` 保留旧值，其它字段照更新 |
| Celery task 整体异常 | 落 Celery `task_failure` log，下次 cron 自动恢复 |

幂等性：所有写入都是 upsert，重复跑同一天数据结果一致。

## 边界情况

| 场景 | 行为 |
|------|------|
| 账号 0 群发文章 | 仅刷粉丝字段，`wechat_articles` 无新行；summary 文章数 = 0 |
| 文章被微信删除 | API 不再返回该 msgid → 我们**不删除** `wechat_articles` 历史行；前端按 publish_time 30 天窗口过滤掉 |
| 文章多图文 | `article_idx` 区分（第一篇 0、第二篇 1...） |
| 新增 Account | 第一次同步把过去 30 天数据一次性灌入 |
| 跨天精度 | T-1 数据通常 02:00 后齐；cron 03:00 能稳拿「昨天」 |
| `stats_synced_at = null` | 前端显示「从未同步」+ 引导「立即同步」按钮 |
| 时区 | 微信 datacube API 用**北京时间** (`Asia/Shanghai`)。`begin_date=yesterday` 指北京时间的昨天 (`(now_in_shanghai - 1d).date()`)。DB 所有 datetime 列存 UTC（沿用项目现有惯例）。展示层 timezone 转换由前端做 |
| 评论数首次同步失败 | 该篇 `comment_count` 走 column default = 0；下次同步成功后被覆盖。所以"首次同步评论失败 → 显示 0"是预期行为 |

## 测试策略

TDD，严格按现有项目规范。

- **单元** `tests/unit/test_wechat_stats_client.py`：respx 模拟 4 个微信端点，验证响应解析
- **单元** `tests/unit/test_stats_service.py`：upsert 幂等性、派生字段 SQL 计算、`days` 过滤正确
- **集成** `tests/integration/test_stats_task.py`：mock 微信 client 跑 `sync_one_account_stats`，验证字段更新 + 错误时只跳过相关字段
- **集成** `tests/integration/test_stats_routes.py`：3 个端点 happy path + 404 + 鉴权
- **前端 build**：tsc + vite clean

## 配置

`.env.example` 新增：

```bash
STATS_BACKFILL_DAYS=30
STATS_DAILY_CRON_HOUR=3
```

`app/config.py`：

```python
stats_backfill_days: int = Field(default=30, ge=7, le=90)
stats_daily_cron_hour: int = Field(default=3, ge=0, le=23)
```

## 风险与未来

| 项 | 备注 |
|----|------|
| 微信 API quota | 个人账号每天默认 2000 次/接口，本设计单账号约 5 + 50 + 1 + 1 ≈ 60 次/天，远低于上限 |
| `getarticletotal` 数据延迟 | T-1，03:00 跑数据应已齐；如果偶发拉到 null，cron 第二天补 |
| 流量主收益 | 未来若做，独立加新表 `account_revenue_records` + Cookie 爬虫 module，跟本设计无 schema 冲突 |
| 趋势分析 | 未来若想加，可改 daily upsert 为「插入新快照行」+ 新增 `snapshot_date` 列 + 改前端图表组件；schema 演进可控 |

## 提交计划（高层任务划分，详见后续 plan）

1. config / migration / Account 4 字段
2. WechatArticle model + migration（与上面合并 1 个 alembic 文件）
3. `app/wechat/stats.py` 微信客户端（TDD）
4. `app/stats/service.py` upsert + 查询 helpers（TDD）
5. `app/tasks/stats.py` 两个 Celery task（TDD）
6. `app/stats/routes.py` 3 个端点（TDD）
7. 前端 API client + 类型 + 顶部导航
8. 前端 `/stats` 列表页
9. 前端 `/stats/:accountId` 明细页
10. 端到端回归（pytest 全绿 + pnpm build 干净）+ 文档收尾

具体每个任务的 step / TDD red-green 循环 / commit 边界在 plan 文档里展开。
