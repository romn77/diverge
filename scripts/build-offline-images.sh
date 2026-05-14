#!/bin/bash
set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ENV_FILE="${ENV_FILE:-$PROJECT_ROOT/.env}"
EXPLICIT_NEXT_PUBLIC_API_BASE_URL_SET=false
if [ "${NEXT_PUBLIC_API_BASE_URL+x}" = "x" ]; then
  EXPLICIT_NEXT_PUBLIC_API_BASE_URL="$NEXT_PUBLIC_API_BASE_URL"
  EXPLICIT_NEXT_PUBLIC_API_BASE_URL_SET=true
fi

OUTPUT_DIR="${OUTPUT_DIR:-$PROJECT_ROOT/dist}"
PLATFORM="${PLATFORM:-linux/amd64}"
TAG="${TAG:-$(date +%Y%m%d%H%M%S)}"
BACKEND_IMAGE="${BACKEND_IMAGE:-diverge-backend}"
FRONTEND_IMAGE="${FRONTEND_IMAGE:-diverge-frontend}"
INCLUDE_RUNTIME_IMAGES="${INCLUDE_RUNTIME_IMAGES:-false}"

IMAGE_ARCHIVE="$OUTPUT_DIR/diverge-images-${TAG}.tar.gz"
COMPOSE_OVERRIDE="$OUTPUT_DIR/compose.images-${TAG}.yml"

usage() {
  cat <<'USAGE'
Build production Docker images locally, export them as a tarball, and generate
a compose override file for servers that should run images without building.

Usage:
  scripts/build-offline-images.sh

Common environment variables:
  TAG=20260426
  PLATFORM=linux/amd64
  NEXT_PUBLIC_API_BASE_URL=https://your-domain.example
  NPM_CONFIG_REGISTRY=https://registry.npmmirror.com
  INCLUDE_RUNTIME_IMAGES=true
  OUTPUT_DIR=/tmp/diverge-release

Server usage after copying the generated files:
  gunzip -c diverge-images-<TAG>.tar.gz | docker load
  docker compose -f compose.prod.yml -f compose.images-<TAG>.yml up -d

No-nginx public IP usage:
  docker compose -f compose.no-nginx.yml -f compose.images-<TAG>.yml up -d
USAGE
}

is_truthy() {
  case "${1:-}" in
    1|true|TRUE|yes|YES|y|Y) return 0 ;;
    *) return 1 ;;
  esac
}

require_command() {
  if ! command -v "$1" >/dev/null 2>&1; then
    echo "Error: $1 is not installed or not on PATH." >&2
    exit 1
  fi
}

if [ "${1:-}" = "-h" ] || [ "${1:-}" = "--help" ]; then
  usage
  exit 0
fi

cd "$PROJECT_ROOT"

require_command docker
require_command gzip

if ! docker buildx version >/dev/null 2>&1; then
  echo "Error: docker buildx is not available." >&2
  exit 1
fi

if [ -f "$ENV_FILE" ]; then
  set -a
  # shellcheck disable=SC1090
  source "$ENV_FILE"
  set +a
fi

if [ "$EXPLICIT_NEXT_PUBLIC_API_BASE_URL_SET" = "true" ]; then
  NEXT_PUBLIC_API_BASE_URL="$EXPLICIT_NEXT_PUBLIC_API_BASE_URL"
fi

NEXT_PUBLIC_API_BASE_URL="${NEXT_PUBLIC_API_BASE_URL:-}"
PUBLIC_HOSTNAME="${PUBLIC_HOSTNAME:-}"

if [ -z "$NEXT_PUBLIC_API_BASE_URL" ] && [ -n "$PUBLIC_HOSTNAME" ]; then
  NEXT_PUBLIC_API_BASE_URL="https://${PUBLIC_HOSTNAME}"
fi

if [ -z "$NEXT_PUBLIC_API_BASE_URL" ]; then
  echo "Error: set NEXT_PUBLIC_API_BASE_URL or PUBLIC_HOSTNAME before building the frontend image." >&2
  echo "Example: NEXT_PUBLIC_API_BASE_URL=https://your-domain.example scripts/build-offline-images.sh" >&2
  exit 1
fi

mkdir -p "$OUTPUT_DIR"

echo "Building backend image: ${BACKEND_IMAGE}:${TAG}"
docker buildx build \
  --platform "$PLATFORM" \
  -f web/backend/Dockerfile \
  -t "${BACKEND_IMAGE}:${TAG}" \
  --load \
  .

echo "Building frontend image: ${FRONTEND_IMAGE}:${TAG}"
docker buildx build \
  --platform "$PLATFORM" \
  -f web/frontend/Dockerfile \
  --build-arg "NEXT_PUBLIC_API_BASE_URL=${NEXT_PUBLIC_API_BASE_URL}" \
  --build-arg "NPM_CONFIG_REGISTRY=${NPM_CONFIG_REGISTRY:-https://registry.npmmirror.com}" \
  -t "${FRONTEND_IMAGE}:${TAG}" \
  --load \
  web/frontend

save_images=(
  "${BACKEND_IMAGE}:${TAG}"
  "${FRONTEND_IMAGE}:${TAG}"
)

if is_truthy "$INCLUDE_RUNTIME_IMAGES"; then
  runtime_images=(
    "postgres:16-alpine"
    "redis:7-alpine"
    "nginx:1.27-alpine"
  )

  for image in "${runtime_images[@]}"; do
    echo "Pulling runtime image for ${PLATFORM}: ${image}"
    docker pull --platform "$PLATFORM" "$image"
    save_images+=("$image")
  done
fi

echo "Writing compose image override: $COMPOSE_OVERRIDE"
cat > "$COMPOSE_OVERRIDE" <<EOF
services:
  backend:
    image: ${BACKEND_IMAGE}:${TAG}
    build: null
    pull_policy: never
  worker:
    image: ${BACKEND_IMAGE}:${TAG}
    build: null
    pull_policy: never
  prewarm-scheduler:
    image: ${BACKEND_IMAGE}:${TAG}
    build: null
    pull_policy: never
  prewarm-worker:
    image: ${BACKEND_IMAGE}:${TAG}
    build: null
    pull_policy: never
  backup:
    image: ${BACKEND_IMAGE}:${TAG}
    build: null
    pull_policy: never
  frontend:
    image: ${FRONTEND_IMAGE}:${TAG}
    build: null
    pull_policy: never
EOF

echo "Saving images: ${save_images[*]}"
docker save "${save_images[@]}" | gzip > "$IMAGE_ARCHIVE"

echo
echo "Offline image package is ready:"
echo "  $IMAGE_ARCHIVE"
echo "  $COMPOSE_OVERRIDE"
echo
echo "Copy both files to the server, then run:"
echo "  gunzip -c $(basename "$IMAGE_ARCHIVE") | docker load"
echo "  docker compose -f compose.prod.yml -f $(basename "$COMPOSE_OVERRIDE") up -d"
echo
echo "Without a domain/nginx, use:"
echo "  docker compose -f compose.no-nginx.yml -f $(basename "$COMPOSE_OVERRIDE") up -d"
