#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")"

# --- Sanity checks -----------------------------------------------------------

if [ ! -f .env ]; then
    echo "ERROR: .env not found. Copy .env.example → .env and fill in secrets first."
    echo "  See DEPLOYMENT.md section 14 for details."
    exit 1
fi

REQUIRED=(POSTGRES_PASSWORD JWT_SECRET ENCRYPTION_KEY ADMIN_PASSWORD_HASH DOMAIN)
for var in "${REQUIRED[@]}"; do
    if ! grep -qE "^${var}=.+" .env; then
        echo "ERROR: .env is missing or empty: ${var}"
        exit 1
    fi
done

# --- Pull latest code (skip if no git repo) ----------------------------------

if [ -d .git ]; then
    echo "==> git pull"
    git pull --ff-only
fi

# --- Build and start ---------------------------------------------------------

echo "==> docker compose build"
docker compose -f docker-compose.yml -f docker-compose.prod.yml build

echo "==> docker compose up -d"
docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d --remove-orphans

# --- Wait for api to be healthy ----------------------------------------------

echo "==> waiting for api to be ready..."
for i in {1..30}; do
    if docker compose -f docker-compose.yml -f docker-compose.prod.yml exec -T api \
            curl -fsS http://localhost:8000/health > /dev/null 2>&1; then
        echo "    api is healthy"
        break
    fi
    if [ "$i" -eq 30 ]; then
        echo "WARNING: api did not become healthy after 60 s — check logs:"
        echo "  docker compose -f docker-compose.yml -f docker-compose.prod.yml logs api"
    fi
    sleep 2
done

# --- Done --------------------------------------------------------------------

DOMAIN_VALUE=$(grep -E "^DOMAIN=.+" .env | cut -d= -f2- | tr -d '[:space:]')
echo "==> Done. Visit https://${DOMAIN_VALUE:-wechat.azhefuye.online}"
docker compose -f docker-compose.yml -f docker-compose.prod.yml ps
