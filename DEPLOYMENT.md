# 部署文档

完整的部署、配置、运维指南。从 0 到 1 把这个工具跑起来。

## 1. 系统要求

| 组件 | 最低版本 | 说明 |
|---|---|---|
| Docker | 24.0+ | 含 Compose v2（`docker compose` 命令） |
| 磁盘 | 5 GB | 镜像 ~3 GB + Postgres 数据 + 抓取的图片 |
| 内存 | 2 GB | postgres 256M + redis 64M + api 256M + worker 512M + beat 64M + web 32M |
| 公网 IP | 可选 | 仅推送到微信草稿箱时需要（公众号后台 IP 白名单） |

支持的宿主机：Linux、macOS、Windows（WSL2 推荐）。

## 2. 快速开始（5 分钟）

```bash
git clone <repo-url> wechat-batch-rewriter
cd wechat-batch-rewriter

# 1. 复制环境变量模板
cp .env.example .env

# 2. 生成加密 key（用于加密 AI key 和公众号 AppSecret）
python -c "from cryptography.fernet import Fernet; print('ENCRYPTION_KEY=' + Fernet.generate_key().decode())" >> .env

# 3. 生成 admin 密码 hash
docker compose run --rm api python -m app.scripts.init_admin --password 你的密码
# 把打印出来的 hash 写入 .env 的 ADMIN_PASSWORD_HASH=

# 4. 改 JWT_SECRET 为长随机字符串
# 编辑 .env，把 JWT_SECRET=change-me-to-a-long-random-string 替换为你的随机值
# 比如: openssl rand -hex 32

# 5. 起全栈
docker compose up -d --build

# 6. 验证
curl http://localhost/api/health   # 应返回 {"status":"ok"}
```

打开浏览器：http://localhost → 用 admin + 你的密码登录。

## 3. .env 必填项

| 变量 | 用途 | 示例 |
|---|---|---|
| `DATABASE_URL` | Postgres 连接 | `postgresql+asyncpg://postgres:postgres@postgres:5432/wechat_rewriter` |
| `POSTGRES_DB/USER/PASSWORD` | Postgres 容器初始化 | 默认即可，生产改强密码 |
| `REDIS_URL` | Redis 连接 | `redis://redis:6379/0` |
| `ADMIN_USERNAME` | 登录用户名 | `admin` |
| `ADMIN_PASSWORD_HASH` | bcrypt 哈希 | 见步骤 3 |
| `JWT_SECRET` | JWT 签名 key（改长随机串！） | `openssl rand -hex 32` |
| `ENCRYPTION_KEY` | Fernet 加密 key（**丢了所有 AppSecret 不可恢复**） | 见步骤 2 |
| `IMAGE_STORAGE_DIR` | 抓取图片存储目录（容器内） | `/data/images`（默认对应 `image_data` volume） |
| `REWRITE_BATCH_MAX` | 单次提交最多多少篇 | `20` |

**安全提示**：
- `ENCRYPTION_KEY` 一旦设定不要再改，否则历史加密的 AppSecret/AI key 全部解不出来。
- `.env` 不提交 git（已在 .gitignore）。建议另存一份到 1Password/keepass。

## 4. 服务架构

```
┌─────────────────────────────────────────────────────────────┐
│                    Internet (HTTP/HTTPS)                    │
│                            │                                │
│                            ▼                                │
│  ┌─────────┐   nginx       ┌───────┐   FastAPI / uvicorn   │
│  │   web   │──────────────▶│  api  │                        │
│  │  :80    │  /api/* proxy │ :8000 │                        │
│  └─────────┘  / SPA        └───┬───┘                        │
│                                │                            │
│                  ┌─────────────┼─────────────┐              │
│                  ▼             ▼             ▼              │
│            ┌─────────┐   ┌───────┐    ┌─────────┐          │
│            │postgres │   │ redis │    │ worker  │          │
│            │  :5432  │   │ :6379 │    │ celery  │          │
│            └─────────┘   └───────┘    └─────────┘          │
│                              ▲              ▲              │
│                              │  broker      │              │
│                              └──────────────┘              │
│                                              ┌──────┐      │
│                                              │ beat │      │
│                                              └──────┘      │
│                                          (cron schedule)   │
└─────────────────────────────────────────────────────────────┘

Volumes:
  pg_data      ← Postgres 数据
  redis_data   ← Redis 持久化
  image_data   ← 抓取的图片（worker 生成、api 不读）
```

| 服务 | 镜像 | 暴露端口 | 重启策略 |
|---|---|---|---|
| postgres | postgres:16-alpine | 内部 5432 | unless-stopped 推荐 |
| redis | redis:7-alpine | 内部 6379 | unless-stopped 推荐 |
| api | 本地 build | 8000 (host) | unless-stopped 推荐 |
| worker | 本地 build | 内部 only | unless-stopped 推荐 |
| beat | 本地 build | 内部 only | unless-stopped 推荐 |
| web | 本地 build | 80 (host) | unless-stopped 推荐 |

`docker-compose.yml` 默认没设 `restart: unless-stopped`，**生产环境建议加上**：

```yaml
api:
  restart: unless-stopped
  ...
```

或在 `docker compose up -d` 后手动：

```bash
docker update --restart=unless-stopped $(docker compose ps -q)
```

## 5. 首次配置（管理员后台）

登录后浏览器：

### 5.1 配 AI Provider（必需）

去 **设置** → 添加 Provider：

| 字段 | DeepSeek | Kimi (Moonshot) |
|---|---|---|
| name | `deepseek` | `kimi` |
| base_url | `https://api.deepseek.com/v1` | `https://api.moonshot.cn/v1` |
| api_key | DeepSeek 控制台拿到的 `sk-...` | platform.moonshot.cn 拿到的 `sk-...`（不是 `sk-kimi-` 开头的 K2 key） |
| models | `deepseek-chat` | `moonshot-v1-8k,moonshot-v1-32k,moonshot-v1-128k` |

**重要**：Kimi for Coding（K2，`sk-kimi-` 前缀）只对认可的 coding agent（Claude Code/Cursor 等）开放，**不能用作本工具的 Provider**。要用 Moonshot 通用 API。

### 5.2 绑定角色

在 **设置 → 角色绑定** 给三个角色各指定 provider 和 model：

| 角色 | 推荐配置 | 说明 |
|---|---|---|
| writer | DeepSeek + `deepseek-chat` | 改写标题和正文，token 大 |
| reviewer | Kimi + `moonshot-v1-8k` 或 DeepSeek | 4 维评审，需要 JSON 模式 |
| lite | DeepSeek + `deepseek-chat` | 后续可选轻量任务（暂未使用） |

绑定后，registry 会在下一个 task 触发时自动 reload（不再需要重启 worker）。

### 5.3 添加公众号

去 **公众号** → 添加：

| 字段 | 来源 |
|---|---|
| name | 自取 |
| wechat_appid | 公众号后台 → 设置 → 公众号设置 |
| wechat_secret | 公众号后台 → 基本配置 → 重置 AppSecret |
| category | 自取（如 `职场`、`母婴`） |
| title_prompt | 写给 LLM 的标题改写指令 |
| content_prompt | 写给 LLM 的正文改写指令 |
| style_desc | 公众号风格描述（专业克制 / 活泼 / 学术） |

**只有认证的服务号或订阅号**才有 draft API 权限。**未认证的个人订阅号无法推送草稿**。

### 5.4（仅推送时）配 IP 白名单

如果你打算用"推送到微信草稿箱"功能，公众号后台 → 基本配置 → IP 白名单 → 加上你 docker host 的公网出口 IP。

## 6. 日常使用

```
1. 素材库 → 粘贴文章 URL（一行一个）→ 标签 → 添加抓取
   ↓ Worker 自动抓取（pending → processing → done/failed）

2. 素材库 → 勾选 done 的文章 → 选公众号 → 改写
   ↓ Worker 改写（draft → reviewing → reviewed）

3. 草稿 → 点开 → 修改 标题/正文 → 设封面 → 推送到微信草稿箱
   ↓ Worker 处理图片 + 调微信 API（→ published_to_wechat）

4. 在微信公众平台后台 → 草稿箱 → 看到草稿 → 手动发布
```

## 7. 运维操作

### 7.1 查看日志

```bash
# 所有服务
docker compose logs -f

# 单个服务
docker compose logs -f worker
docker compose logs -f api --tail 100

# beat 调度器
docker compose logs -f beat
```

### 7.2 重启某个服务

```bash
docker compose restart worker
docker compose restart api
```

### 7.3 升级代码

```bash
git pull
docker compose up -d --build
# Alembic 迁移会在 api 启动时自动跑（entrypoint-api.sh 里）
```

### 7.4 备份

```bash
# Postgres dump（含所有 drafts/accounts/AI 配置）
docker compose exec postgres pg_dump -U postgres wechat_rewriter | gzip > backup-$(date +%F).sql.gz

# 还原
gunzip -c backup-2026-05-01.sql.gz | docker compose exec -T postgres psql -U postgres wechat_rewriter
```

**重要**：Postgres 备份不含 `ENCRYPTION_KEY`。**还原后必须用同一个 key**（在 `.env`），否则所有 AppSecret/AI key 解不出来。把 `.env` 也备份。

### 7.5 清理（自动）

`beat` 服务每天跑 `cleanup` 任务：
- 删 30 天前已 published_to_wechat 或 failed 的 draft 关联的图片文件 + Image 行
- 删 90 天前的 `ai_usage` 行

每小时跑 `reset_stuck`：
- 把 `library_items` 里 status=processing 卡了 >1 小时的重置为 pending（worker 重新抓）

不需要手动操作。如要立即触发：

```bash
docker compose exec worker celery -A app.tasks.celery_app call app.tasks.maintenance.cleanup
```

## 8. 故障排查

### 8.1 容器起不来

```bash
docker compose ps           # 看 status
docker compose logs <service>  # 看错误
```

| 现象 | 可能原因 | 修复 |
|---|---|---|
| api 报 `connection refused` | postgres/redis 还没 ready | 等 30s；healthcheck 应等到 healthy 再启 api |
| worker 报 `Authentication failed for postgres` | `.env` 的 `POSTGRES_PASSWORD` 与 volume 里历史值不一致 | `docker compose down -v` 删卷重来，或者改 .env 匹配历史 |
| web 报 502 | api 还没好；或 nginx 被 cache | `docker compose restart web` |

### 8.2 改写一直 pending

```bash
# 看 worker 是否在跑
docker compose logs worker --tail 30
# 看 redis 队列长度
docker compose exec redis redis-cli llen celery
```

可能原因：
- AI provider key 过期/欠费 → Settings 看 ProviderOut 状态
- AI 调用超时（Kimi 偶发 30s+）→ 加大 worker 数（`CELERY_WORKER_CONCURRENCY`）
- `_ensure_registry` reload 失败 → 看 worker error log

### 8.3 抓取一直 failed

```bash
# 看具体错误
docker compose exec postgres psql -U postgres -d wechat_rewriter \
  -c "SELECT source_url, error_msg FROM library_items WHERE status='failed' ORDER BY updated_at DESC LIMIT 5;"
```

| error_msg | 含义 | 处理 |
|---|---|---|
| `WeChat anti-bot captcha triggered` | 微信反爬触发 | 等 30 分钟换 IP 再试 |
| `HTTP 404` | 文章不存在/被删 | 跳过 |
| `HTTP 503` | 微信暂时性故障 | 自动重试 3 次后仍 fail，可点重试按钮 |

### 8.4 推送到微信失败

| errcode | 含义 | 处理 |
|---|---|---|
| 40001 | access_token 失效 | 已自动 refresh + 重试，仍失败说明 AppSecret 错 |
| 40164 | IP 不在白名单 | 公众号后台加 IP 白名单 |
| 45009 | 调用次数超限 | 等 24h 或升级账号 |
| 53503 | 内容含敏感词 | 改文案，重新触发 |

## 9. HTTPS（生产推荐）

bundled web 容器只跑 HTTP。生产建议在前面加 Caddy：

```yaml
# docker-compose.override.yml
services:
  caddy:
    image: caddy:2-alpine
    ports:
      - "80:80"
      - "443:443"
    volumes:
      - ./Caddyfile:/etc/caddy/Caddyfile
      - caddy_data:/data
    depends_on: [web]

  web:
    ports: []   # 不再直接暴露 80

volumes:
  caddy_data:
```

`Caddyfile`:

```
your-domain.com {
  reverse_proxy web:80
}
```

启动：`docker compose up -d`，Caddy 自动申请 Let's Encrypt 证书。

## 10. 监控（可选）

### 10.1 系统资源

```bash
docker stats   # 各容器实时 CPU/内存
```

### 10.2 业务指标

进 Settings 页面底部看 **AI 用量** 卡片：
- 30 天总成本（USD 估算）
- 每天柱状图
- 按角色/模型分布的表格

数据从 `ai_usage` 表 SELECT，beat 每 90 天清一次老数据。

### 10.3 数据库慢查询

```bash
docker compose exec postgres psql -U postgres -d wechat_rewriter \
  -c "SELECT * FROM pg_stat_statements ORDER BY total_exec_time DESC LIMIT 10;"
```

需要先在 postgres 里 `CREATE EXTENSION pg_stat_statements;`。

## 11. 关停

```bash
# 停服务保留数据
docker compose down

# 停服务并删卷（所有数据消失！谨慎）
docker compose down -v
```

## 12. 已知限制

- **单用户**：JWT 体系只支持 1 个 admin，无团队/RBAC。
- **微信反爬**：v1 没有 cookie 池或代理池，触发 captcha 后只能等。
- **手动发布**：推送到微信"草稿箱"，最终发布需要在公众号后台手动点。
- **Kimi for Coding (K2) 不能用**：本工具不在白名单，必须用 Moonshot 通用 API（`api.moonshot.cn`）。
- **图片来源限制**：仅支持微信 mmbiz.qpic.cn 域的图片自动上传到公众号素材库。

## 13. 升级路径

未来可能加的：
- HTTPS 自动化（Caddy 集成到 compose 默认）
- 多用户 + 团队权限
- WeChat 反反爬（cookie pool）
- 更多文章源（知乎、小红书）
- 自动发布（cron 定时推草稿后再 publish）
- 手机端管理 UI

---

最后更新：2026-05-01
当前 commit：`bc6b5c7` (60 commits in)

---

## 14. 生产部署（Caddy + HTTPS）

适用：已有一台 Linux 服务器，装了 Docker + Compose，域名 A 记录已指向服务器 IP。

### 14.1 一次性 bootstrap

```bash
# 在服务器上，假设域名 wechat.azhefuye.online 已解析到这台机
ssh you@your-server
git clone git@github.com:你/wechat-batch-rewriter.git /opt/wechat-batch-rewriter
cd /opt/wechat-batch-rewriter

# 1. 复制并填充 .env
cp .env.example .env
# 编辑 .env，设置 POSTGRES_PASSWORD 为强密码、DOMAIN 为你的域名

# 2. 生成加密 key 和 JWT secret
echo "ENCRYPTION_KEY=$(python3 -c 'from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())')" >> .env
echo "JWT_SECRET=$(openssl rand -hex 32)" >> .env

# 3. 初始化 admin 密码 hash（临时启 api 服务跑一次性脚本）
docker compose run --rm api python -m app.scripts.init_admin --password 你的密码
# 把打印的 ADMIN_PASSWORD_HASH=... 行粘到 .env

# 4. 给脚本加执行权限
chmod +x deploy.sh backup.sh

# 5. 一键起栈（Caddy 会自动申请 Let's Encrypt 证书）
./deploy.sh
```

第一次 Caddy 申请证书大概要 30 秒 — 1 分钟。等 `https://wechat.azhefuye.online` 返回登录页就成功了。

**注意**：在 Windows 上克隆后直接推到服务器时，`deploy.sh` 和 `backup.sh` 的执行权限位不会自动保留。在服务器上 clone 后务必手动 `chmod +x deploy.sh backup.sh`。

### 14.2 后续更新

```bash
ssh you@your-server
cd /opt/wechat-batch-rewriter
./deploy.sh    # = git pull + rebuild + up -d + 健康检查
```

Alembic 迁移在 api 启动时自动跑（`entrypoint-api.sh`）。无需手动操作。

### 14.3 compose 文件说明

生产栈通过两个 compose 文件叠加启动：

```bash
docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d
```

`docker-compose.prod.yml` 在基础文件之上做以下覆盖：
- 为所有服务加 `restart: unless-stopped`
- 移除 `api` 和 `web` 的 host 端口暴露（Caddy 在内部 docker 网络直连）
- 新增 `caddy` 服务（80/443）+ `caddy_data`/`caddy_config` 卷

`Caddyfile` 配置：
- 自动申请 Let's Encrypt 证书（需要 80/443 对外可达）
- 反代到 `web:80`（web 容器内 nginx 再反代 `/api/*` 到 api）
- 开启 gzip/zstd 压缩
- 注入标准安全响应头
- 访问日志写入 `caddy_data` 卷（容器内 `/data/access.log`）

### 14.4 备份

```bash
# 手动跑一次
./backup.sh

# 加 cron 每天凌晨 3 点自动备
crontab -e
# 加这一行：
0 3 * * * cd /opt/wechat-batch-rewriter && ./backup.sh >> /var/log/wechat-backup.log 2>&1
```

备份保留 30 天，自动清理旧目录。`backups/YYYY-MM-DD/` 包含 `db.sql.gz` + `env.bak`。

**重要**：`env.bak` 里的 `ENCRYPTION_KEY` 是恢复 AppSecret/AI key 的唯一凭证。建议把 `backups/` 目录每周再 rsync 到 OSS/S3 异地。

如果要备份图片（默认不备，体积大）：

```bash
BACKUP_IMAGES=yes ./backup.sh
```

### 14.5 迁移到新服务器

```bash
# 在新机上
ssh new@new-server
git clone git@github.com:你/wechat-batch-rewriter.git /opt/wechat-batch-rewriter
cd /opt/wechat-batch-rewriter

# 拷贝旧机最新备份
scp -r old@old-server:/opt/wechat-batch-rewriter/backups/2026-05-06 ./backups/

# 用旧的 .env（关键：ENCRYPTION_KEY 不能变）
cp ./backups/2026-05-06/env.bak .env

# 启栈（空数据库）
chmod +x deploy.sh backup.sh
./deploy.sh

# 还原数据库
gunzip -c ./backups/2026-05-06/db.sql.gz | \
    docker compose -f docker-compose.yml -f docker-compose.prod.yml exec -T postgres \
    psql -U postgres wechat_rewriter

# 改 DNS 指向新机 IP，等 TTL 生效即可
```
