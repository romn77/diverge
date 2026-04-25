#!/usr/bin/env bash
set -euo pipefail

if [[ $# -ne 1 ]]; then
  echo "Usage: scripts/restore-postgres.sh /path/to/postgres-backup.sql.gz" >&2
  exit 2
fi

backup_file="$1"
export PGPASSWORD="${POSTGRES_PASSWORD:?Set POSTGRES_PASSWORD}"

gunzip -c "$backup_file" | psql \
  --host "${POSTGRES_HOST:-postgres}" \
  --port "${POSTGRES_PORT:-5432}" \
  --username "${POSTGRES_USER:-postgres}" \
  --dbname "${POSTGRES_DB:-tradingagents}"
