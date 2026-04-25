#!/usr/bin/env bash
set -euo pipefail

BACKUP_DIR="${BACKUP_DIR:-/app/backups}"
INTERVAL="${BACKUP_INTERVAL_SECONDS:-86400}"

mkdir -p "$BACKUP_DIR"

run_backup() {
  timestamp="$(date -u +%Y%m%dT%H%M%SZ)"
  output="$BACKUP_DIR/postgres-$timestamp.sql.gz"
  export PGPASSWORD="${POSTGRES_PASSWORD:?Set POSTGRES_PASSWORD}"
  pg_dump \
    --host "${POSTGRES_HOST:-postgres}" \
    --port "${POSTGRES_PORT:-5432}" \
    --username "${POSTGRES_USER:-postgres}" \
    --dbname "${POSTGRES_DB:-tradingagents}" \
    --no-owner \
    --no-privileges \
    | gzip > "$output"
  python -m web.backend.backup_to_storage "$output"
}

if [[ "${BACKUP_ONCE:-false}" == "true" ]]; then
  run_backup
  exit 0
fi

while true; do
  run_backup
  sleep "$INTERVAL"
done
