#!/bin/bash
set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
ENV_FILE="${ENV_FILE:-$PROJECT_ROOT/.env}"

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
FRONTEND_PORT="${FRONTEND_PORT:-3000}"

mkdir -p "$DATA_DIR/reports" "$DATA_DIR/manifest"

echo "Building Docker images..."
docker compose build

echo "Starting services..."
docker compose up -d

echo
echo "Deployment complete."
echo "Frontend: http://localhost:${FRONTEND_PORT}"
echo "Backend API: http://localhost:8000"
echo
echo "Logs:"
echo "  docker compose logs -f backend"
echo "  docker compose logs -f frontend"
