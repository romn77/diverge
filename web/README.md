# TradingAgents Web Workbench

A web UI for browsing trading analysis reports, launching background analysis tasks, launching screener tasks, and reviewing screener candidate lists.

## Architecture

- **Backend**: FastAPI for report browsing, analysis task orchestration, screener task orchestration, and screener run discovery
- **Frontend**: Next.js with TypeScript, Tailwind CSS, and markdown/table rendering
- **Data**:
  - reports live in `../reports/`
  - screener artifacts live in `../results/screener/`

## Quick Start

### Option 1: Automated Start Script

```bash
./start.sh
```

This will:
1. Install backend dependencies
2. Start FastAPI backend on `http://localhost:${BACKEND_PORT:-8000}`
3. Install frontend dependencies
4. Start Next.js frontend on `http://localhost:${FRONTEND_PORT:-3000}`

Press Ctrl+C to stop both servers.

You can override ports before launch:

```bash
BACKEND_PORT=8010 FRONTEND_PORT=3010 ./start.sh
```

### Option 2: Manual Start

**Backend**:
```bash
cd backend
pip install -r requirements.txt
uvicorn main:app --port 8000
```

**Frontend** (in another terminal):
```bash
cd frontend
npm install
npm run dev
```

Then open http://localhost:3000 in your browser.

## API Endpoints

- `GET /api/reports` — List all available reports
- `GET /api/reports/{report_id}/structure` — List files in a report directory
- `GET /api/reports/{report_id}/content?path=...` — Fetch file content as markdown
- `POST /api/tasks` — Launch an analysis task
- `GET /api/tasks` — List analysis tasks
- `GET /api/tasks/{task_id}` — Fetch an analysis task
- `GET /api/tasks/{task_id}/stream` — Stream analysis task progress
- `GET /api/screener/config/options` — Get screener launch options
- `POST /api/screener/tasks` — Launch a screener task
- `GET /api/screener/tasks` — List screener tasks
- `GET /api/screener/tasks/{task_id}` — Fetch a screener task
- `GET /api/screener/tasks/{task_id}/stream` — Stream screener task progress
- `GET /api/screener/runs` — List completed screener runs
- `GET /api/screener/runs/{run_id}` — Fetch screener run metadata
- `GET /api/screener/runs/{run_id}/candidates` — Fetch screener candidate rows

## Screener Notes

- CN screening requires `TUSHARE_TOKEN`
- CLI US screening requires `--us-manifest /absolute/path/to/us_manifest.csv`
- Web US screening requires backend env `SCREEN_US_MANIFEST_PATH`
- LLM analysis happens after screener output, not during screener execution
- Shared screener cache and recovery checkpoints live under `../results/screener/.cache/`

## Development

### Frontend

```bash
cd frontend
npm run dev       # Start dev server
npm run build     # Build for production
npm run lint      # Run ESLint
```

### Backend

```bash
cd backend
uvicorn main:app --reload --port 8000
```

## Build & Deployment

```bash
cd frontend && npm run build
```

Both servers are ready for production deployment once built.

## Single-Host Docker Compose

From the repository root:

```bash
cp .env.example .env
# update FRONTEND_PORT, FRONTEND_ORIGIN, NEXT_PUBLIC_API_BASE_URL and any provider keys you need

./scripts/deploy-single-host.sh
```

Notes:

- frontend host port is controlled by `FRONTEND_PORT`
- backend remains on `8000`
- backend CORS uses `FRONTEND_ORIGIN`
- frontend API target is compiled from `NEXT_PUBLIC_API_BASE_URL`
