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

echo "Starting local Diverge Workbench with SH dev support services."
echo "Environment file: $ENV_FILE"
echo

exec env ENV_FILE="$ENV_FILE" "$PROJECT_ROOT/web/start.sh"
