#!/usr/bin/env bash
set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
ENV_FILE="${ENV_FILE:-$PROJECT_ROOT/configs/env/sh-dev.env}"
case "$ENV_FILE" in
  /*) ;;
  *) ENV_FILE="$PROJECT_ROOT/$ENV_FILE" ;;
esac

if [ ! -f "$ENV_FILE" ]; then
  echo "Error: $ENV_FILE not found." >&2
  echo "Copy configs/env/sh-dev.example.env to configs/env/sh-dev.env first." >&2
  exit 1
fi

set -a
# shellcheck disable=SC1090
source "$ENV_FILE"
set +a

if [ -z "${PYTHON_BIN:-}" ]; then
  if [ -x "$PROJECT_ROOT/.venv/bin/python" ]; then
    PYTHON_BIN="$PROJECT_ROOT/.venv/bin/python"
  else
    PYTHON_BIN="${PYTHON:-python}"
  fi
fi

echo "Checking SH dev database with $ENV_FILE..."
"$PYTHON_BIN" -m web.backend.devops.check_database \
  --env-file "$ENV_FILE" \
  --override-env \
  "$@"

echo
echo "Checking SH dev Redis..."
"$PYTHON_BIN" - <<'PY'
import os
import sys

try:
    import redis
except ImportError:
    print("Redis check failed: install backend requirements first.", file=sys.stderr)
    raise SystemExit(1)

redis_url = os.environ.get("REDIS_URL", "").strip()
if not redis_url:
    print("Redis check failed: REDIS_URL is not set.", file=sys.stderr)
    raise SystemExit(1)

client = redis.Redis.from_url(redis_url, socket_connect_timeout=2, socket_timeout=2)
client.ping()
prefix = os.environ.get("TASK_STORE_PREFIX", "diverge")
print(f"Redis: ok url={redis_url} task_store_prefix={prefix}")
PY

echo
echo "SH dev support services are reachable."
