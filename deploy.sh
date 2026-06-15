#!/usr/bin/env bash
#
# 微信公众号批量改写 · 一键部署脚本（腾讯云 CVM）
#
# 与「米粒手账(Qianji)」同款体验：一条命令完成
#   拉代码 → 配镜像加速器 → 生成 .env(随机密钥) → 构建 → 启动 →
#   等 api 健康(自动跑 alembic 迁移) → 接入全机共享 edge 反代 → 公网验活。
#
# 用法：
#   ./deploy.sh                    # 标准部署（首次会引导设置管理员密码）
#   SKIP_PULL=1 ./deploy.sh        # 不自动 git pull（用当前代码部署，回滚时用）
#   ADMIN_PASSWORD=xxx ./deploy.sh # 首次非交互提供管理员密码（CI/无人值守）
#
# 入口反代：本机唯一占用 80/443 的是独立 edge-caddy（见 infra/edge，位于
# 米粒手账仓库）。本项目不自带 caddy；web 容器接入外部 `edge` 网络，由
# edge-caddy 按唯一容器名 wechat-batch-rewriter-web-1:80 反代。
#
# 幂等：可重复运行；已有 .env / 加速器 / edge 网络都会自动跳过。
set -euo pipefail
cd "$(dirname "$0")"

PROJ="$(basename "$PWD")"          # wechat-batch-rewriter
API_CTN="${PROJ}-api-1"
WEB_CTN="${PROJ}-web-1"
EDGE_NET="edge"
EDGE_CADDY="edge-caddy"

# ---- 权限：非 root 自动加 sudo；docker 需 root 时整体加 sudo ----
SUDO=""
[ "$(id -u)" -ne 0 ] && SUDO="sudo"
DOCKER="docker"
if ! docker info >/dev/null 2>&1; then
  DOCKER="$SUDO docker"
fi
COMPOSE="$DOCKER compose -f docker-compose.yml -f docker-compose.prod.yml --env-file .env"

log()  { echo -e "\033[1;36m==>\033[0m $*"; }
warn() { echo -e "\033[1;33m[!]\033[0m $*"; }
ok()   { echo -e "\033[1;32m    ✓ $*\033[0m"; }

# ---- 0. 自动拉取最新代码 ----
if [ -z "${SKIP_PULL:-}" ] && [ -d .git ]; then
  log "git pull 最新代码"
  git pull --ff-only || warn "git pull 失败（本地有改动？），用当前代码继续"
fi

# ---- 1. 腾讯云 Docker 镜像加速器（基础镜像提速，幂等）----
configure_docker_mirror() {
  local daemon=/etc/docker/daemon.json
  local mirror="https://mirror.ccs.tencentyun.com"
  if [ -f "$daemon" ] && grep -q "mirror.ccs.tencentyun.com" "$daemon"; then
    log "Docker 镜像加速器已配置，跳过"; return
  fi
  log "配置腾讯云 Docker 镜像加速器"
  $SUDO mkdir -p /etc/docker
  if [ -f "$daemon" ] && command -v jq >/dev/null 2>&1; then
    $SUDO cp "$daemon" "${daemon}.bak.$(date +%s)"
    jq --arg m "$mirror" '.["registry-mirrors"]=((.["registry-mirrors"]//[])+[$m]|unique)' \
      "$daemon" | $SUDO tee "$daemon.tmp" >/dev/null && $SUDO mv "$daemon.tmp" "$daemon"
  else
    [ -f "$daemon" ] && { $SUDO cp "$daemon" "${daemon}.bak.$(date +%s)"; warn "已备份原 daemon.json"; }
    echo "{\"registry-mirrors\": [\"$mirror\"]}" | $SUDO tee "$daemon" >/dev/null
  fi
  log "重启 docker 使加速器生效"
  $SUDO systemctl restart docker || warn "重启 docker 失败，请手动确认 docker 正常"
  for _ in $(seq 1 15); do $DOCKER info >/dev/null 2>&1 && break; sleep 1; done
}
configure_docker_mirror

# ---- 2. 生成 .env（首次；已存在则沿用，不覆盖密钥）----
gen_fernet_key() {
  # Fernet 要求 urlsafe base64 编码的 32 字节密钥（44 字符）
  openssl rand 32 | openssl base64 -A | tr '+/' '-_'
}

if [ -f .env ]; then
  log ".env 已存在，沿用现有配置"
else
  log "生成 .env（随机数据库密码 / JWT / Fernet 加密密钥）"
  cp .env.example .env
  sed -i "s|^POSTGRES_PASSWORD=.*|POSTGRES_PASSWORD=$(openssl rand -hex 16)|" .env
  sed -i "s|^JWT_SECRET=.*|JWT_SECRET=$(openssl rand -hex 32)|" .env
  sed -i "s|^ENCRYPTION_KEY=.*|ENCRYPTION_KEY=$(gen_fernet_key)|" .env
fi

DOMAIN=$(grep -E '^DOMAIN=' .env | cut -d= -f2- | tr -d '[:space:]')
[ -z "$DOMAIN" ] && { warn ".env 缺少 DOMAIN，请手动补上后重跑"; exit 1; }
log "部署域名：$DOMAIN"

# ---- 3. 确保共享 edge 网络存在（edge-caddy 由 infra/edge 启动并占用 80/443）----
if ! $DOCKER network inspect "$EDGE_NET" >/dev/null 2>&1; then
  log "创建共享 edge 网络"
  $DOCKER network create "$EDGE_NET" >/dev/null
fi
if ! $DOCKER ps --format '{{.Names}}' | grep -qx "$EDGE_CADDY"; then
  warn "未发现运行中的 $EDGE_CADDY —— 公网入口(80/443)需要它。"
  warn "请先在 infra/edge 启动：cd infra/edge && docker compose up -d"
fi

# ---- 4. 构建镜像 ----
log "构建镜像（首次约 2~3 分钟）"
$COMPOSE build

# ---- 5. 首次引导管理员密码 → 写入 ADMIN_PASSWORD_HASH ----
if ! grep -qE '^ADMIN_PASSWORD_HASH=.+' .env; then
  log "首次部署：设置管理员登录密码"
  PW="${ADMIN_PASSWORD:-}"
  if [ -z "$PW" ]; then
    read -r -s -p "    请输入管理员密码(admin 账号): " PW; echo
  fi
  [ -z "$PW" ] && { warn "未提供管理员密码，已中止"; exit 1; }
  # 用 api 镜像离线计算 bcrypt 哈希（覆盖 entrypoint，跳过 alembic，无需数据库）
  HASH=$($COMPOSE run --rm --no-deps --entrypoint python api \
    -m app.scripts.init_admin --password "$PW" | tr -d '\r\n')
  [ -z "$HASH" ] && { warn "生成密码哈希失败"; exit 1; }
  # 用 | 作分隔符，避免 bcrypt 哈希里的 / 干扰 sed
  sed -i "s|^ADMIN_PASSWORD_HASH=.*|ADMIN_PASSWORD_HASH=${HASH}|" .env
  ok "管理员密码已设置（哈希写入 .env）"
fi

# ---- 6. 启动全部服务（postgres/redis/api/worker/beat/web）----
log "启动服务（api 启动时自动跑 alembic upgrade head）"
$COMPOSE up -d --remove-orphans

wait_api_healthy() {
  log "等待 api 就绪（含数据库迁移）..."
  for _ in $(seq 1 30); do
    if $COMPOSE exec -T api curl -fsS http://localhost:8000/health >/dev/null 2>&1; then
      ok "api 已就绪"; return 0
    fi
    sleep 2
  done
  warn "api 60s 内未就绪，查日志：$COMPOSE logs api"
}
wait_api_healthy

# ---- 7. 确保 web 接入 edge 网络，并刷新 edge-caddy 路由 ----
if $DOCKER ps --format '{{.Names}}' | grep -qx "$WEB_CTN"; then
  $DOCKER network connect "$EDGE_NET" "$WEB_CTN" 2>/dev/null \
    && log "已将 $WEB_CTN 接入 $EDGE_NET" || true
fi
if $DOCKER ps --format '{{.Names}}' | grep -qx "$EDGE_CADDY"; then
  $DOCKER exec "$EDGE_CADDY" caddy reload --config /etc/caddy/Caddyfile 2>/dev/null \
    && log "已重载 edge-caddy" || warn "edge-caddy reload 失败（路由可能已生效，忽略）"
fi

# ---- 8. 公网验活 ----
log "验证 https://${DOMAIN}/"
if curl -fsS -m 15 "https://${DOMAIN}/" >/dev/null 2>&1; then
  ok "部署成功！打开 https://${DOMAIN} 用 admin 登录"
else
  warn "公网验活未通过——证书首签需十几秒、或 DNS/80/443/edge-caddy 未就绪，30s 后重试："
  warn "  curl -i https://${DOMAIN}/"
fi

echo
$COMPOSE ps
