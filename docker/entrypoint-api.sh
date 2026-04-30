#!/usr/bin/env bash
set -euo pipefail
cd /app/backend
echo "[entrypoint] running alembic migrations..."
alembic upgrade head
echo "[entrypoint] starting: $*"
exec "$@"
