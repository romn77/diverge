#!/usr/bin/env bash
set -euo pipefail

COMPOSE_FILE="${COMPOSE_FILE:-compose.prod.yml}"
TAIL_LINES="${TAIL_LINES:-300}"
FOLLOW="${FOLLOW:-false}"
TASK_ID="${1:-}"

services=(backend worker)
follow_args=()
if [[ "$FOLLOW" == "1" || "$FOLLOW" == "true" || "$FOLLOW" == "yes" ]]; then
  follow_args=(-f)
fi

pattern='task_event|worker_started|analysis task failed|screener task failed|data sync'
if [[ -n "$TASK_ID" ]]; then
  pattern="task_id=\"${TASK_ID}\"|task_id=${TASK_ID}"
fi

docker compose -f "$COMPOSE_FILE" logs "${follow_args[@]}" --tail "$TAIL_LINES" "${services[@]}" \
  | grep --line-buffered -E "$pattern" || true
