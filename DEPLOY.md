# 微信公众号批量改写 · 云端部署手册

后端通过 Docker 部署，**一个脚本 `./deploy.sh` 全自动**完成：配镜像加速器 →
生成密钥 → 构建 → 启动 → 自动迁移数据库 → 首次引导管理员密码 → 接入全机共享
edge 反代（自动 HTTPS）→ 验活。对外只暴露 `https://wechat.azhefuye.online`。

> 详尽的逐项配置说明见 `DEPLOYMENT.md`；本文件是与「米粒手账」同款的一键流程。

---

## 0. 前置条件（只需确认一次）

1. **DNS**：`wechat.azhefuye.online` 的 A 记录指向服务器公网 IP（`dig +short wechat.azhefuye.online` 能返回 IP）。
2. **防火墙 / 安全组**：放行入站 **80** 和 **443**。
3. **装 Docker**（若未装）：`curl -fsSL https://get.docker.com | sh`。
4. **共享入口 edge-caddy 已运行**（全机唯一占用 80/443，路由各站点）：
   ```bash
   cd <米粒手账仓库>/infra/edge && docker compose up -d
   ```
   它的 `Caddyfile` 已含 `wechat.azhefuye.online → wechat-batch-rewriter-web-1:80`。

---

## 1. 一键部署

```bash
git clone git@github.com:mingzheli-jo/wechat-gzh.git
cd wechat-gzh
chmod +x deploy.sh
./deploy.sh
```

脚本会自动：
1. `git pull` 最新代码；
2. 配腾讯云 Docker 镜像加速器（幂等）；
3. 首次生成 `.env`（随机 `POSTGRES_PASSWORD` / `JWT_SECRET` / Fernet `ENCRYPTION_KEY`）；
4. 构建镜像；
5. **首次引导设置管理员密码**（admin 账号，写入 `ADMIN_PASSWORD_HASH`）；
   - 非交互可用：`ADMIN_PASSWORD=你的密码 ./deploy.sh`
6. 启动 postgres / redis / api / worker / beat / web；api 启动时自动 `alembic upgrade head`；
7. 把 web 接入 `edge` 网络并重载 edge-caddy 路由；
8. 公网验活 `https://wechat.azhefuye.online/`。

结尾打印 `✓ 部署成功！` 即完成。证书首签需十几秒，未过时等 30 秒重试
`curl -i https://wechat.azhefuye.online/`。

> ⚠️ `ENCRYPTION_KEY` 一旦丢失，已加密的 AI Key / 公众号 AppSecret 不可恢复。
> 首次部署后请妥善备份 `.env`。

---

## 2. 日常运维

> 下表 `C` = `docker compose -f docker-compose.yml -f docker-compose.prod.yml --env-file .env`

**更新部署**（拉新代码 + 重建，等同重跑脚本）
```bash
./deploy.sh
```

**查看日志**
```bash
C logs -f api      # 或 worker / beat / web
```

**备份 / 恢复数据库**
```bash
C exec -T postgres pg_dump -U "$(grep ^POSTGRES_USER= .env | cut -d= -f2)" \
  "$(grep ^POSTGRES_DB= .env | cut -d= -f2)" > backup_$(date +%Y%m%d).sql

cat backup_YYYYMMDD.sql | C exec -T postgres \
  psql -U "$(grep ^POSTGRES_USER= .env | cut -d= -f2)" \
  "$(grep ^POSTGRES_DB= .env | cut -d= -f2)"
```

**停止 / 重启**
```bash
C down       # 停（数据卷保留）
C up -d      # 起
```

**回滚到上一个版本**
```bash
git log --oneline -5
git checkout <commit>
SKIP_PULL=1 ./deploy.sh
```

---

## 排错速查

| 现象 | 排查 |
|---|---|
| 验活 TLS 失败 | DNS 未指向本机 / 80 443 未放行 / edge-caddy 未起；`docker logs edge-caddy` |
| api 一直起不来 | `C logs api` 看 alembic 迁移或启动校验报错（弱 JWT/缺密钥会拒绝启动）|
| 502 Bad Gateway | api/web 没起来；`C ps` 确认状态；web 是否接入 edge 网络 |
| 页面能开但接口 401 | 管理员密码错；可 `ADMIN_PASSWORD=新密码`，删掉 .env 里 `ADMIN_PASSWORD_HASH` 后重跑 |
| 域名转发错站点 | edge `Caddyfile` 必须用唯一容器名 `wechat-batch-rewriter-web-1:80` |
