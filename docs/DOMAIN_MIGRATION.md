# 公众号 · jo-personal.online 域名迁移

## 当前结果

2026-10-01 新入口 `https://wechat.jo-personal.online` 已上线，指向 `101.42.185.88`。
主操作完成共享 Caddy 新旧双 Host 切换，并在生产更新指定环境变量。
本次文档准备另做只读 HTTPS 验活（证书验证开启）：首页 `/` 和 `/api/health` 返回 200，
未携带登录凭据访问 `/api/accounts` 返回 401。域名与 HTTPS 当前可用；
主操作者另完成真实登录 200，并用登录 token 读取 `/api/accounts` 返回 200。
09:01已完成发布后15分钟持续观测，DNS/HTTPS/入口及认证边界持续正常；业务容器未重启，原调度保持。

| 项目 | 现行值与边界 |
|---|---|
| 新入口 | `https://wechat.jo-personal.online` |
| 旧入口 | 保留wechat.azhefuye.online旧Host配置；旧域名公网已失效，正常访问使用新域名 |
| 应用目录 | `/opt/wechat-batch-rewriter` |
| 共享反代 | `/opt/mili-shouzhang/infra/edge/Caddyfile`，容器 `edge-caddy` |
| 双 Host upstream | 新旧域名同指 `wechat-batch-rewriter-web-1:80` |
| 应用配置 | `/opt/wechat-batch-rewriter/.env`：`DOMAIN=wechat.jo-personal.online` |
| 自动化配置 | `/home/ubuntu/gzh-digest/.env`：`API_BASE=https://wechat.jo-personal.online/api` |

## 认证与数据边界

共享 Caddy 保留其他站点、根域名、www 和现有认证配置；本项目仍由后端 JWT 登录保护 API。
首页和健康接口可公开访问，不代表 `/api/accounts` 等业务接口无需登录。
`backend/app/accounts/routes.py` 的列表路由依赖 `get_current_username`；
未登录 401 是预期结果，不应通过删除密码哈希或关闭认证处理。

迁移仅改上述 `DOMAIN`、`API_BASE` 两个生产配置键；不改数据库密码、
`JWT_SECRET`、`ENCRYPTION_KEY`、`ADMIN_PASSWORD_HASH`、AI Key 或公众号 AppSecret。
不替换整份 `.env`，不执行初始化、数据库恢复或卷删除。尤其 Fernet 密钥保持原值，
避免既有加密凭据无法解密。

## 调度与执行边界

不重启 api、worker、beat、web 或数据库，不运行 `deploy.sh` 来完成本次域名切换。
保留 ubuntu 的原 cron（08:30 调用 `/home/ubuntu/gzh-digest/run-auto.sh`）、运行锁和选题状态。
文档准备仅用无凭据 GET；主操作者用现有账号登录验证后只读取账号列表。
本次不调用创作、改写、统计刷新、草稿推送等业务写入接口；
不手动触发 cron、Celery 任务或真实微信消息。

仓库 `.env.example` 只同步 `DOMAIN` 默认值。自动化的生产 `API_BASE` 来自独立 `.env`，
不得把该目录的真实凭据复制入库。`ops/gzh-digest/auto_pipeline.py` 的 `API_BASE`
缺省地址同步为 `https://wechat.jo-personal.online/api`，只改 URL 常量，不改出稿逻辑。
该目录没有入库的 `.env.example` 或运行 README，不新建重复配置。

## 风险与缓解

| 失败模式 | 缓解 |
|---|---|
| 双 Host 路由误指其他项目或绕过认证 | 保持唯一 upstream；验证首页/健康 200 和未登录业务 API 401，保留共享站点与认证配置 |
| 重生成加密密钥或整份覆盖 .env，历史凭据不可用 | 只更新指定两键，其他 secret 原值保留，配置备份不入库 |
| 验收过程中触发真实出稿、推送或重复定时任务 | 只做登录与 GET 读取验证；不重启调度、不运行 cron、不发生成/推送等业务 POST |

## 验收与回滚

| 验收项 | 当前结果 |
|---|---|
| 新域名 HTTPS、首页 `/` | 通过，200 |
| `/api/health` | 通过，200 |
| 未登录 `/api/accounts` | 通过，401，认证边界保留 |
| 真实登录与带 token 读取 `/api/accounts` | 主操作者验证通过，均为 200 |
| 生产 DOMAIN / 自动化 API_BASE | 主操作者已更新为上述新值 |
| 自动化脚本缺省 API_BASE | Python AST 解析及唯一缺省 URL 验证通过；未执行 run_daily |
| 15 分钟最终观测 | 通过；09:01入口持续正常、业务重启0/无OOM，原08:00/08:30 cron保持，未人工触发 |
| 文档、默认值及提交检查 | 已通过：DOMAIN 默认值唯一、现行部署文档旧域名检索、迁移文档链接目标检查、git diff --check |

如新入口异常，保留旧入口并由操作者按备份恢复对应入口或指定配置键；
不恢复数据库、不更换密钥、不触发业务任务。恢复共享配置须继续保护其他项目的站点与认证。

## 文档同步

同步 `DEPLOY.md`、`DEPLOYMENT.md`、主设计部署节、每日出稿恢复文档及本迁移记录，
并将 `.env.example` 默认域名改为新域名。本轮不改页面、tokens、业务逻辑或测试契约。
自动化脚本只同步一个默认 URL 字符串；AST 与缺省地址验证后回写本台账，不触发 `run_daily`。
