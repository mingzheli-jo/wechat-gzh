#!/usr/bin/env bash
set -euo pipefail
cd /app/backend
echo "[worker] waiting for postgres + redis..."
exec "$@"
