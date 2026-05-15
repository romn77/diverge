#!/usr/bin/env bash
set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
ENV_FILE="${ENV_FILE:-$PROJECT_ROOT/configs/env/sh-dev.env}"
case "$ENV_FILE" in
  /*) ;;
  *) ENV_FILE="$PROJECT_ROOT/$ENV_FILE" ;;
esac

if [ -f "$ENV_FILE" ]; then
  set -a
  # shellcheck disable=SC1090
  source "$ENV_FILE"
  set +a
fi

SSH_TARGET="${1:-${DEV_TUNNEL_SSH_TARGET:-${SH_DEV_SSH_TARGET:-}}}"
if [ -z "$SSH_TARGET" ]; then
  echo "Error: set SH_DEV_SSH_TARGET in $ENV_FILE or pass user@host." >&2
  exit 1
fi

BIND_ADDRESS="${DEV_TUNNEL_BIND_ADDRESS:-127.0.0.1}"
LOCAL_POSTGRES_PORT="${DEV_TUNNEL_POSTGRES_LOCAL_PORT:-15432}"
REMOTE_POSTGRES_HOST="${DEV_TUNNEL_POSTGRES_REMOTE_HOST:-127.0.0.1}"
REMOTE_POSTGRES_PORT="${DEV_TUNNEL_POSTGRES_REMOTE_PORT:-5432}"
LOCAL_REDIS_PORT="${DEV_TUNNEL_REDIS_LOCAL_PORT:-16379}"
REMOTE_REDIS_HOST="${DEV_TUNNEL_REDIS_REMOTE_HOST:-127.0.0.1}"
REMOTE_REDIS_PORT="${DEV_TUNNEL_REDIS_REMOTE_PORT:-6379}"

ssh_args=(
  -N
  -o ExitOnForwardFailure=yes
  -o ServerAliveInterval="${DEV_TUNNEL_SERVER_ALIVE_INTERVAL:-30}"
  -o ServerAliveCountMax="${DEV_TUNNEL_SERVER_ALIVE_COUNT_MAX:-3}"
  -L "${BIND_ADDRESS}:${LOCAL_POSTGRES_PORT}:${REMOTE_POSTGRES_HOST}:${REMOTE_POSTGRES_PORT}"
  -L "${BIND_ADDRESS}:${LOCAL_REDIS_PORT}:${REMOTE_REDIS_HOST}:${REMOTE_REDIS_PORT}"
)

if [ -n "${DEV_TUNNEL_SSH_PORT:-}" ]; then
  ssh_args+=(-p "$DEV_TUNNEL_SSH_PORT")
fi

if [ -n "${DEV_TUNNEL_IDENTITY_FILE:-}" ]; then
  ssh_args+=(-i "$DEV_TUNNEL_IDENTITY_FILE")
fi

if [ -n "${DEV_TUNNEL_JUMP_HOST:-}" ]; then
  ssh_args+=(-J "$DEV_TUNNEL_JUMP_HOST")
fi

echo "Opening SH dev support-service tunnel:"
echo "  Postgres: ${BIND_ADDRESS}:${LOCAL_POSTGRES_PORT} -> ${REMOTE_POSTGRES_HOST}:${REMOTE_POSTGRES_PORT}"
echo "  Redis:    ${BIND_ADDRESS}:${LOCAL_REDIS_PORT} -> ${REMOTE_REDIS_HOST}:${REMOTE_REDIS_PORT}"
echo "  SSH:      ${SSH_TARGET}"
echo
echo "Keep this process running while using the local workbench."

exec ssh "${ssh_args[@]}" "$SSH_TARGET"
