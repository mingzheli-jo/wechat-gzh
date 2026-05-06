#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")"

DATE=$(date +%F)
DIR="./backups/${DATE}"
mkdir -p "$DIR"

# --- Postgres dump -----------------------------------------------------------

echo "==> Backing up postgres → ${DIR}/db.sql.gz"
docker compose exec -T postgres pg_dump -U postgres wechat_rewriter \
    | gzip > "${DIR}/db.sql.gz"

# --- .env (ENCRYPTION_KEY is required to decrypt the db dump) ---------------

echo "==> Backing up .env → ${DIR}/env.bak"
cp .env "${DIR}/env.bak"
chmod 600 "${DIR}/env.bak"

# --- Image volume (opt-in; off by default — can be large) -------------------

if [ "${BACKUP_IMAGES:-no}" = "yes" ]; then
    echo "==> Backing up image volume → ${DIR}/images.tar.gz"
    docker run --rm \
        -v wechat-batch-rewriter_image_data:/data:ro \
        -v "$(pwd)/${DIR}":/backup \
        alpine tar czf /backup/images.tar.gz -C /data .
fi

# --- Prune backups older than 30 days ----------------------------------------

find ./backups -mindepth 1 -maxdepth 1 -type d -mtime +30 -exec rm -rf {} +

echo "==> Backup complete: ${DIR}"
ls -lh "${DIR}"
