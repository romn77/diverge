#!/bin/bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
ROOT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
ENV_FILE="$ROOT_DIR/.env"
if [ -f "$ENV_FILE" ]; then
    set -a
    . "$ENV_FILE"
    set +a
fi
DATA_DIR="${DATA_DIR:-$ROOT_DIR/data}"
REPORTS_DIR="${REPORTS_DIR:-$DATA_DIR/reports}"
SCREENER_RUNS_DIR="${SCREENER_RUNS_DIR:-$DATA_DIR/screener/runs}"
SCREENER_TASKS_DIR="${SCREENER_TASKS_DIR:-$DATA_DIR/screener/tasks}"
SCREENER_CACHE_DIR="${SCREENER_CACHE_DIR:-$DATA_DIR/cache/screener}"
STOCK_HISTORY_DIR="${STOCK_HISTORY_DIR:-$DATA_DIR/history}"
FUNDAMENTALS_DIR="${FUNDAMENTALS_DIR:-$DATA_DIR/fundamentals}"
BACKEND_PORT="${BACKEND_PORT:-8000}"
FRONTEND_PORT="${FRONTEND_PORT:-3000}"
FRONTEND_ORIGIN="${FRONTEND_ORIGIN:-http://localhost:${FRONTEND_PORT},http://127.0.0.1:${FRONTEND_PORT}}"
NEXT_PUBLIC_API_BASE_URL="${NEXT_PUBLIC_API_BASE_URL:-http://localhost:${BACKEND_PORT}}"
BACKEND_LOG="${BACKEND_LOG:-/tmp/diverge-backend.log}"
FRONTEND_LOG="${FRONTEND_LOG:-/tmp/diverge-frontend.log}"
WORKER_LOG="${WORKER_LOG:-/tmp/diverge-worker.log}"
BACKEND_LOG_LEVEL="${BACKEND_LOG_LEVEL:-${LOG_LEVEL:-info}}"
TAIL_LOGS="${TAIL_LOGS:-true}"
TAIL_LOG_LINES="${TAIL_LOG_LINES:-80}"
AUTH_ENABLED="${AUTH_ENABLED:-false}"
AUTH_MODE="${AUTH_MODE:-required}"
TASK_BACKEND="${TASK_BACKEND:-local}"
TASK_QUEUE_LIMIT="${TASK_QUEUE_LIMIT:-2}"
TASK_GLOBAL_RUNNING_LIMIT="${TASK_GLOBAL_RUNNING_LIMIT:-$TASK_QUEUE_LIMIT}"
TASK_USER_RUNNING_LIMIT="${TASK_USER_RUNNING_LIMIT:-1}"
TASK_GLOBAL_PENDING_LIMIT="${TASK_GLOBAL_PENDING_LIMIT:-100}"
TASK_USER_PENDING_LIMIT_ADMIN="${TASK_USER_PENDING_LIMIT_ADMIN:-10}"
TASK_USER_PENDING_LIMIT_OPERATOR="${TASK_USER_PENDING_LIMIT_OPERATOR:-5}"
TASK_USER_PENDING_LIMIT_VIEWER="${TASK_USER_PENDING_LIMIT_VIEWER:-2}"
REDIS_URL="${REDIS_URL:-redis://127.0.0.1:6379/0}"
START_REDIS_DOCKER="${START_REDIS_DOCKER:-false}"
REDIS_CONTAINER_NAME="${REDIS_CONTAINER_NAME:-diverge-redis}"
REDIS_PORT="${REDIS_PORT:-6379}"
STORAGE_BACKEND="${STORAGE_BACKEND:-local}"
STORAGE_LOCAL_ROOT="${STORAGE_LOCAL_ROOT:-$DATA_DIR}"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color
BACKEND_PID=""
FRONTEND_PID=""
WORKER_PID=""
TAIL_PID=""

kill_port() {
    local port="$1"
    if command -v lsof > /dev/null 2>&1; then
        lsof -ti :"$port" 2>/dev/null | xargs kill -9 2>/dev/null || true
    fi
    if command -v fuser > /dev/null 2>&1; then
        fuser -k "${port}/tcp" > /dev/null 2>&1 || true
    fi
}

wait_for_http() {
    local url="$1"
    local attempts="${2:-20}"
    local delay="${3:-1}"

    for _ in $(seq 1 "$attempts"); do
        if curl --noproxy "*" -fsS "$url" > /dev/null 2>&1; then
            return 0
        fi
        sleep "$delay"
    done

    return 1
}

redis_ping() {
    python -c "import os, redis; redis.Redis.from_url(os.environ['REDIS_URL'], socket_connect_timeout=2, socket_timeout=2).ping()" > /dev/null 2>&1
}

ensure_redis_available() {
    if [ "$TASK_BACKEND" != "redis" ]; then
        return 0
    fi

    if redis_ping; then
        return 0
    fi

    if [ "$START_REDIS_DOCKER" = "true" ]; then
        if ! command -v docker > /dev/null 2>&1; then
            echo -e "${RED}TASK_BACKEND=redis requires Redis, but Docker is not available.${NC}" >&2
            exit 1
        fi
        echo -e "${BLUE}Starting local Redis container...${NC}"
        docker start "$REDIS_CONTAINER_NAME" > /dev/null 2>&1 || \
            docker run -d --name "$REDIS_CONTAINER_NAME" -p "${REDIS_PORT}:6379" redis:7-alpine > /dev/null
        sleep 2
        if redis_ping; then
            return 0
        fi
    fi

    echo -e "${RED}Redis is not reachable at $REDIS_URL.${NC}" >&2
    echo "Start Redis first, for example:" >&2
    echo "  docker run --rm -p ${REDIS_PORT}:6379 redis:7-alpine" >&2
    echo "Or set START_REDIS_DOCKER=true to let this script start a named local container." >&2
    exit 1
}

tail_logs_enabled() {
    case "$TAIL_LOGS" in
        true|TRUE|1|yes|YES|on|ON)
            return 0
            ;;
        *)
            return 1
            ;;
    esac
}

start_log_tail() {
    if ! tail_logs_enabled; then
        echo "Log streaming disabled. To follow logs manually:"
        echo "  tail -f \"$BACKEND_LOG\" \"$FRONTEND_LOG\""
        if [ "$TASK_BACKEND" = "redis" ]; then
            echo "  tail -f \"$WORKER_LOG\""
        fi
        return 0
    fi

    LOG_FILES=("$BACKEND_LOG" "$FRONTEND_LOG")
    if [ "$TASK_BACKEND" = "redis" ]; then
        LOG_FILES+=("$WORKER_LOG")
    fi

    echo -e "${BLUE}Streaming logs from ${#LOG_FILES[@]} file(s). Set TAIL_LOGS=false ./start.sh to only print paths.${NC}"
    echo -e "${BLUE}Showing the last $TAIL_LOG_LINES lines; press Ctrl+C to stop all services.${NC}"
    echo
    tail -n "$TAIL_LOG_LINES" -F "${LOG_FILES[@]}" &
    TAIL_PID=$!
}

echo -e "${BLUE}Starting Diverge Report Viewer...${NC}"
echo

# Ensure runtime data directories exist
mkdir -p "$REPORTS_DIR" "$SCREENER_RUNS_DIR" "$SCREENER_TASKS_DIR" "$SCREENER_CACHE_DIR" "$STOCK_HISTORY_DIR" "$FUNDAMENTALS_DIR"
mkdir -p "$(dirname "$BACKEND_LOG")" "$(dirname "$FRONTEND_LOG")" "$(dirname "$WORKER_LOG")"

# Kill any lingering processes on ports 8000, 3000
cleanup() {
    local backend_pid="${BACKEND_PID:-}"
    local frontend_pid="${FRONTEND_PID:-}"
    local worker_pid="${WORKER_PID:-}"
    local tail_pid="${TAIL_PID:-}"
    echo
    echo -e "${BLUE}Shutting down...${NC}"
    if [ -n "$tail_pid" ] && kill -0 "$tail_pid" 2>/dev/null; then
        kill "$tail_pid" 2>/dev/null || true
        wait "$tail_pid" 2>/dev/null || true
    fi
    if [ -n "$worker_pid" ] && kill -0 "$worker_pid" 2>/dev/null; then
        kill "$worker_pid" 2>/dev/null || true
        wait "$worker_pid" 2>/dev/null || true
    fi
    if [ -n "$backend_pid" ] && kill -0 "$backend_pid" 2>/dev/null; then
        kill "$backend_pid" 2>/dev/null || true
        wait "$backend_pid" 2>/dev/null || true
    fi
    if [ -n "$frontend_pid" ] && kill -0 "$frontend_pid" 2>/dev/null; then
        kill "$frontend_pid" 2>/dev/null || true
        wait "$frontend_pid" 2>/dev/null || true
    fi
    echo -e "${GREEN}Stopped.${NC}"
}

trap cleanup EXIT INT TERM

# Kill any existing processes on these ports
kill_port "$BACKEND_PORT"
kill_port "$FRONTEND_PORT"
sleep 1

# Start backend
echo -e "${BLUE}Starting backend...${NC}"
cd "$SCRIPT_DIR/backend"
pip install -r requirements.txt -q 2>/dev/null || pip install -r requirements.txt > /dev/null 2>&1
export REPORTS_DIR="$REPORTS_DIR"
export SCREENER_RUNS_DIR="$SCREENER_RUNS_DIR"
export SCREENER_TASKS_DIR="$SCREENER_TASKS_DIR"
export SCREENER_CACHE_DIR="$SCREENER_CACHE_DIR"
export STOCK_HISTORY_DIR="$STOCK_HISTORY_DIR"
export FUNDAMENTALS_DIR="$FUNDAMENTALS_DIR"
export FRONTEND_ORIGIN="$FRONTEND_ORIGIN"
export AUTH_ENABLED="$AUTH_ENABLED"
export AUTH_MODE="$AUTH_MODE"
export TASK_BACKEND="$TASK_BACKEND"
export TASK_QUEUE_LIMIT="$TASK_QUEUE_LIMIT"
export TASK_GLOBAL_RUNNING_LIMIT="$TASK_GLOBAL_RUNNING_LIMIT"
export TASK_USER_RUNNING_LIMIT="$TASK_USER_RUNNING_LIMIT"
export TASK_GLOBAL_PENDING_LIMIT="$TASK_GLOBAL_PENDING_LIMIT"
export TASK_USER_PENDING_LIMIT_ADMIN="$TASK_USER_PENDING_LIMIT_ADMIN"
export TASK_USER_PENDING_LIMIT_OPERATOR="$TASK_USER_PENDING_LIMIT_OPERATOR"
export TASK_USER_PENDING_LIMIT_VIEWER="$TASK_USER_PENDING_LIMIT_VIEWER"
export REDIS_URL="$REDIS_URL"
export STORAGE_BACKEND="$STORAGE_BACKEND"
export STORAGE_LOCAL_ROOT="$STORAGE_LOCAL_ROOT"
export LOG_LEVEL="$BACKEND_LOG_LEVEL"
ensure_redis_available
if [ "$AUTH_ENABLED" = "true" ]; then
    if ! migration_output=$(alembic -c alembic.ini upgrade head 2>&1); then
        if [ -n "$migration_output" ]; then
            printf '%s\n' "$migration_output" >&2
        fi
        echo -e "${RED}Auth database migration failed before backend startup.${NC}" >&2
        echo "When AUTH_ENABLED=true, start the configured database first." >&2
        echo "For the default local stack: docker compose up -d postgres" >&2
        echo "Or set AUTH_ENABLED=false in .env to use the filesystem-only workbench." >&2
        exit 1
    fi
    (
        cd "$ROOT_DIR"
        python -m web.backend.devops.bootstrap_admin > /dev/null
        if [ "$AUTH_MODE" = "optional" ]; then
            python -m web.backend.devops.backfill_metadata > /dev/null
        fi
    )
fi
(
    cd "$ROOT_DIR"
    uvicorn web.backend.main:app --port "$BACKEND_PORT" --log-level "$BACKEND_LOG_LEVEL"
) > "$BACKEND_LOG" 2>&1 &
BACKEND_PID=$!

# Check backend health
if ! wait_for_http "http://localhost:${BACKEND_PORT}/api/healthz"; then
    echo -e "${RED}Backend failed to start. Log:${NC}"
    cat "$BACKEND_LOG"
    exit 1
fi
echo -e "${GREEN}✓ Backend started (PID $BACKEND_PID)${NC}"

if [ "$TASK_BACKEND" = "redis" ]; then
    echo -e "${BLUE}Starting worker...${NC}"
    (
        cd "$ROOT_DIR"
        python -m web.backend.worker
    ) > "$WORKER_LOG" 2>&1 &
    WORKER_PID=$!
    sleep 1
    if ! kill -0 "$WORKER_PID" 2>/dev/null; then
        echo -e "${RED}Worker failed to start. Log:${NC}"
        cat "$WORKER_LOG"
        exit 1
    fi
    echo -e "${GREEN}✓ Worker started (PID $WORKER_PID)${NC}"
fi

# Start frontend
echo -e "${BLUE}Starting frontend...${NC}"
cd "$SCRIPT_DIR/frontend"
if [ ! -d "node_modules" ]; then
    npm install --silent > /dev/null 2>&1
fi
export NEXT_PUBLIC_API_BASE_URL="$NEXT_PUBLIC_API_BASE_URL"
npm run dev -- --port "$FRONTEND_PORT" > "$FRONTEND_LOG" 2>&1 &
FRONTEND_PID=$!

# Check frontend health
if ! wait_for_http "http://localhost:${FRONTEND_PORT}" 30 1; then
    echo -e "${RED}Frontend failed to start. Log:${NC}"
    cat "$FRONTEND_LOG"
    exit 1
fi
echo -e "${GREEN}✓ Frontend started (PID $FRONTEND_PID)${NC}"

# Print access info
echo
echo -e "${GREEN}=== Diverge Report Viewer ===${NC}"
echo -e "Backend:  ${BLUE}http://localhost:${BACKEND_PORT}${NC}"
echo -e "Frontend: ${BLUE}http://localhost:${FRONTEND_PORT}${NC}"
echo
echo "Reports found: $(find "$REPORTS_DIR" -mindepth 1 -maxdepth 1 -type d | wc -l)"
echo "Frontend origin: $FRONTEND_ORIGIN"
echo "Frontend API target: $NEXT_PUBLIC_API_BASE_URL"
echo "Task backend: $TASK_BACKEND"
echo "Backend log level: $BACKEND_LOG_LEVEL"
echo "Backend log: $BACKEND_LOG"
echo "Frontend log: $FRONTEND_LOG"
if [ "$TASK_BACKEND" = "redis" ]; then
    echo "Redis URL: $REDIS_URL"
    echo "Running limits: global=$TASK_GLOBAL_RUNNING_LIMIT user=$TASK_USER_RUNNING_LIMIT"
    echo "Queue limits: global=$TASK_GLOBAL_PENDING_LIMIT admin=$TASK_USER_PENDING_LIMIT_ADMIN operator=$TASK_USER_PENDING_LIMIT_OPERATOR viewer=$TASK_USER_PENDING_LIMIT_VIEWER"
    echo "Worker log: $WORKER_LOG"
fi
echo
echo -e "${BLUE}Press Ctrl+C to stop${NC}"
echo
start_log_tail

# Wait for all child processes
wait
