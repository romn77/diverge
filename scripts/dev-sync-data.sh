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

ACTION="${1:-pull}"
SSH_TARGET="${DEV_SYNC_SSH_TARGET:-${SH_DEV_SSH_TARGET:-}}"
REMOTE_DATA_DIR="${DEV_SYNC_REMOTE_DATA_DIR:-/opt/diverge/data-dev}"
LOCAL_DATA_DIR="${DATA_DIR:-$PROJECT_ROOT/data}"
case "$LOCAL_DATA_DIR" in
  /*) ;;
  *) LOCAL_DATA_DIR="$PROJECT_ROOT/$LOCAL_DATA_DIR" ;;
esac

if [ -z "$SSH_TARGET" ]; then
  echo "Error: set DEV_SYNC_SSH_TARGET or SH_DEV_SSH_TARGET in $ENV_FILE." >&2
  exit 1
fi

if ! command -v rsync >/dev/null 2>&1; then
  echo "Error: rsync is not installed or not on PATH." >&2
  exit 1
fi

rsync_args=(-az --exclude "reports/.tmp/" --exclude ".tmp/" --exclude "__pycache__/")
if [ "${DEV_SYNC_DRY_RUN:-false}" = "true" ]; then
  rsync_args+=(-n)
fi
if [ "${DEV_SYNC_DELETE:-false}" = "true" ]; then
  rsync_args+=(--delete)
fi

case "$ACTION" in
  pull)
    mkdir -p "$LOCAL_DATA_DIR"
    echo "Pulling SH dev data:"
    echo "  ${SSH_TARGET}:${REMOTE_DATA_DIR}/ -> ${LOCAL_DATA_DIR}/"
    rsync "${rsync_args[@]}" "${SSH_TARGET}:${REMOTE_DATA_DIR}/" "$LOCAL_DATA_DIR/"
    ;;
  push)
    echo "Pushing local data to SH dev:"
    echo "  ${LOCAL_DATA_DIR}/ -> ${SSH_TARGET}:${REMOTE_DATA_DIR}/"
    ssh "$SSH_TARGET" "mkdir -p '$REMOTE_DATA_DIR'"
    rsync "${rsync_args[@]}" "$LOCAL_DATA_DIR/" "${SSH_TARGET}:${REMOTE_DATA_DIR}/"
    ;;
  *)
    echo "Usage: $0 [pull|push]" >&2
    echo "Set DEV_SYNC_DRY_RUN=true to preview changes." >&2
    echo "Set DEV_SYNC_DELETE=true to mirror deletions." >&2
    exit 2
    ;;
esac
