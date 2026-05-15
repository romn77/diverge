#!/bin/bash
set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
ENV_FILE="${ENV_FILE:-$PROJECT_ROOT/.env}"
COMPOSE_FILE="${COMPOSE_FILE:-compose.prod.yml}"

cd "$PROJECT_ROOT"

if ! command -v docker >/dev/null 2>&1; then
  echo "Error: docker is not installed or not on PATH." >&2
  exit 1
fi

if ! docker compose version >/dev/null 2>&1; then
  echo "Error: docker compose is not available." >&2
  exit 1
fi

if [ ! -f "$ENV_FILE" ]; then
  echo "Error: $ENV_FILE not found." >&2
  echo "Copy .env.example to .env and update the deployment variables first." >&2
  exit 1
fi

set -a
# shellcheck disable=SC1090
source "$ENV_FILE"
set +a

DATA_DIR="${DATA_DIR:-$PROJECT_ROOT/data}"

mkdir -p "$DATA_DIR/reports" "$DATA_DIR/manifest"

echo "Building Docker images..."
docker compose -f "$COMPOSE_FILE" build

echo "Starting services..."
docker compose -f "$COMPOSE_FILE" up -d

echo
echo "Deployment complete."
echo "Compose file: $COMPOSE_FILE"
if [ -n "${PUBLIC_HOSTNAME:-}" ]; then
  echo "Frontend/API: https://${PUBLIC_HOSTNAME}"
else
  echo "Frontend/API: http://localhost"
fi
echo
echo "Logs:"
echo "  docker compose -f $COMPOSE_FILE logs -f backend"
echo "  docker compose -f $COMPOSE_FILE logs -f frontend"
