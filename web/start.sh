#!/bin/bash
set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
REPORTS_DIR="$SCRIPT_DIR/../reports"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}Starting TradingAgents Report Viewer...${NC}"
echo

# Check if reports directory exists
if [ ! -d "$REPORTS_DIR" ]; then
    echo -e "${RED}Error: reports directory not found at $REPORTS_DIR${NC}"
    exit 1
fi

# Kill any lingering processes on ports 8000, 3000
cleanup() {
    echo
    echo -e "${BLUE}Shutting down...${NC}"
    if [ -n "$BACKEND_PID" ] && kill -0 $BACKEND_PID 2>/dev/null; then
        kill $BACKEND_PID 2>/dev/null || true
        wait $BACKEND_PID 2>/dev/null || true
    fi
    if [ -n "$FRONTEND_PID" ] && kill -0 $FRONTEND_PID 2>/dev/null; then
        kill $FRONTEND_PID 2>/dev/null || true
        wait $FRONTEND_PID 2>/dev/null || true
    fi
    echo -e "${GREEN}Stopped.${NC}"
}

trap cleanup EXIT INT TERM

# Kill any existing processes on these ports
lsof -ti :8000 2>/dev/null | xargs kill -9 2>/dev/null || true
lsof -ti :3000 2>/dev/null | xargs kill -9 2>/dev/null || true
sleep 1

# Start backend
echo -e "${BLUE}Starting backend...${NC}"
cd "$SCRIPT_DIR/backend"
pip install -r requirements.txt -q 2>/dev/null || pip install -r requirements.txt > /dev/null 2>&1
export REPORTS_DIR="$REPORTS_DIR"
uvicorn main:app --port 8000 --log-level critical > /tmp/backend.log 2>&1 &
BACKEND_PID=$!
sleep 2

# Check backend health
if ! curl -s http://localhost:8000/api/reports > /dev/null 2>&1; then
    echo -e "${RED}Backend failed to start. Log:${NC}"
    cat /tmp/backend.log
    exit 1
fi
echo -e "${GREEN}✓ Backend started (PID $BACKEND_PID)${NC}"

# Start frontend
echo -e "${BLUE}Starting frontend...${NC}"
cd "$SCRIPT_DIR/frontend"
if [ ! -d "node_modules" ]; then
    npm install --silent > /dev/null 2>&1
fi
npm run dev > /tmp/frontend.log 2>&1 &
FRONTEND_PID=$!
sleep 4

# Check frontend health
if ! curl -s http://localhost:3000 > /dev/null 2>&1; then
    echo -e "${RED}Frontend failed to start. Log:${NC}"
    cat /tmp/frontend.log
    exit 1
fi
echo -e "${GREEN}✓ Frontend started (PID $FRONTEND_PID)${NC}"

# Print access info
echo
echo -e "${GREEN}=== TradingAgents Report Viewer ===${NC}"
echo -e "Backend:  ${BLUE}http://localhost:8000${NC}"
echo -e "Frontend: ${BLUE}http://localhost:3000${NC}"
echo
echo "Reports found: $(find "$REPORTS_DIR" -mindepth 1 -maxdepth 1 -type d | wc -l)"
echo
echo -e "${BLUE}Press Ctrl+C to stop${NC}"
echo

# Wait for all child processes
wait
