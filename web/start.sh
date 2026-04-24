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
BACKEND_PORT="${BACKEND_PORT:-8000}"
FRONTEND_PORT="${FRONTEND_PORT:-3000}"
FRONTEND_ORIGIN="${FRONTEND_ORIGIN:-http://localhost:${FRONTEND_PORT}}"
NEXT_PUBLIC_API_BASE_URL="${NEXT_PUBLIC_API_BASE_URL:-http://localhost:${BACKEND_PORT}}"
BACKEND_LOG="${BACKEND_LOG:-/tmp/tradingagents-backend.log}"
FRONTEND_LOG="${FRONTEND_LOG:-/tmp/tradingagents-frontend.log}"
AUTH_ENABLED="${AUTH_ENABLED:-false}"
AUTH_MODE="${AUTH_MODE:-required}"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color
BACKEND_PID=""
FRONTEND_PID=""

kill_port() {
    local port="$1"
    lsof -ti :"$port" 2>/dev/null | xargs kill -9 2>/dev/null || true
}

wait_for_http() {
    local url="$1"
    local attempts="${2:-20}"
    local delay="${3:-1}"

    for _ in $(seq 1 "$attempts"); do
        if curl -s "$url" > /dev/null 2>&1; then
            return 0
        fi
        sleep "$delay"
    done

    return 1
}

echo -e "${BLUE}Starting TradingAgents Report Viewer...${NC}"
echo

# Ensure runtime data directories exist
mkdir -p "$REPORTS_DIR" "$SCREENER_RUNS_DIR" "$SCREENER_TASKS_DIR" "$SCREENER_CACHE_DIR" "$STOCK_HISTORY_DIR"

# Kill any lingering processes on ports 8000, 3000
cleanup() {
    local backend_pid="${BACKEND_PID:-}"
    local frontend_pid="${FRONTEND_PID:-}"
    echo
    echo -e "${BLUE}Shutting down...${NC}"
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
export FRONTEND_ORIGIN="$FRONTEND_ORIGIN"
export AUTH_ENABLED="$AUTH_ENABLED"
export AUTH_MODE="$AUTH_MODE"
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
        python -m web.backend.bootstrap_admin > /dev/null
        if [ "$AUTH_MODE" = "optional" ]; then
            python -m web.backend.backfill_metadata > /dev/null
        fi
    )
fi
(
    cd "$ROOT_DIR"
    uvicorn web.backend.main:app --port "$BACKEND_PORT" --log-level critical
) > "$BACKEND_LOG" 2>&1 &
BACKEND_PID=$!

# Check backend health
if ! wait_for_http "http://localhost:${BACKEND_PORT}/api/healthz"; then
    echo -e "${RED}Backend failed to start. Log:${NC}"
    cat "$BACKEND_LOG"
    exit 1
fi
echo -e "${GREEN}✓ Backend started (PID $BACKEND_PID)${NC}"

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
echo -e "${GREEN}=== TradingAgents Report Viewer ===${NC}"
echo -e "Backend:  ${BLUE}http://localhost:${BACKEND_PORT}${NC}"
echo -e "Frontend: ${BLUE}http://localhost:${FRONTEND_PORT}${NC}"
echo
echo "Reports found: $(find "$REPORTS_DIR" -mindepth 1 -maxdepth 1 -type d | wc -l)"
echo "Frontend origin: $FRONTEND_ORIGIN"
echo "Frontend API target: $NEXT_PUBLIC_API_BASE_URL"
echo
echo -e "${BLUE}Press Ctrl+C to stop${NC}"
echo

# Wait for all child processes
wait
