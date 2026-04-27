# TradingAgents Web Workbench

A web UI for browsing trading analysis reports, launching background analysis tasks, launching screener tasks, and reviewing screener candidate lists.

## Architecture

- **Backend**: FastAPI for report browsing, analysis task orchestration, screener task orchestration, and screener run discovery
- **Frontend**: Next.js with TypeScript, Tailwind CSS, and markdown/table rendering
- **Data**:
  - reports live in `../data/reports/`
  - screener runs live in `../data/screener/runs/`
  - screener runtime state lives in `../data/screener/tasks/`
  - screener cache and checkpoints live in `../data/cache/screener/`
  - stock history CSVs live in `../data/history/`

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

To exercise the production-style Redis worker path locally, run:

```bash
TASK_BACKEND=redis \
REDIS_URL=redis://127.0.0.1:6379/0 \
START_REDIS_DOCKER=true \
./start.sh
```

With `TASK_BACKEND=redis`, the script verifies Redis before startup and launches `python -m web.backend.worker` alongside the API. Without `START_REDIS_DOCKER=true`, start Redis yourself first, for example `docker run --rm -p 6379:6379 redis:7-alpine`.

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
- `GET /api/admin/audit-events` — List tenant-scoped audit events for users with `admin:audit`

## Screener Notes

- CLI CN screening can optionally use `--cn-manifest /absolute/path/to/cn_manifest.csv`; otherwise it falls back to live CN universe loading
- Web CN screening can optionally use backend env `SCREEN_CN_MANIFEST_PATH`; otherwise it falls back to live CN universe loading
- CLI US screening requires `--us-manifest /absolute/path/to/us_manifest.csv`
- Web US screening requires backend env `SCREEN_US_MANIFEST_PATH`
- LLM analysis happens after screener output, not during screener execution
- Shared screener cache and recovery checkpoints live under `../data/cache/screener/`

## Auth Rollout

The auth/session layer is controlled by `AUTH_ENABLED` and `AUTH_MODE`:

- `AUTH_ENABLED=false`: disable auth entirely and fall back to the legacy filesystem-only workbench
- `AUTH_ENABLED=true` with `AUTH_MODE=optional`: enable PostgreSQL-backed auth and metadata while leaving only low-sensitivity compatibility routes public during rollout; report listing and report content still require login
- `AUTH_ENABLED=true` with `AUTH_MODE=required`: require login for protected routes

Recommended rollout sequence:

```bash
cp .env.example .env
# set DATABASE_URL, AUTH_BOOTSTRAP_ADMIN_EMAIL, AUTH_BOOTSTRAP_ADMIN_PASSWORD, and FRONTEND_ORIGIN

# check database connectivity, migration status, and required tables
scripts/check-database.sh

# apply migrations and verify the schema
scripts/check-database.sh --upgrade --bootstrap-admin
```

Equivalent manual commands:

```bash
cd web/backend
alembic -c alembic.ini upgrade head

# bootstrap the first admin if the user table is empty
python -m web.backend.devops.bootstrap_admin
```

One-time metadata backfill before switching auth to required:

```bash
AUTH_ENABLED=true AUTH_MODE=required python -m web.backend.devops.backfill_metadata
```

Backfill defaults:

- historical reports are indexed into PostgreSQL as `workspace` visibility and assigned to the bootstrap admin as owner
- historical trades are assigned to the bootstrap admin through `trade_entries`
- historical screener runs are assigned to the bootstrap admin through `screener_runs`
- existing users and historical metadata are assigned to the default tenant during migrations and backfill

Permissions and tenant scope:

- roles are presets over module permissions; admin receives all permissions, operator/viewer keep the current workbench access preset
- per-user permission overrides support explicit `grant` and `deny`, with deny winning over the role preset
- `/api/auth/me` returns `permissions` and `tenant`; frontend create/admin actions use those fields, while backend checks remain the source of truth
- workspace reports are visible only inside the same tenant; private reports, tasks, screeners, assets, trades, and usage counters stay owner-scoped within that tenant
- there is no cross-tenant super-admin role yet; admin override is tenant-admin override

Operational notes:

- `audit_events` now include login success/failure, logout, password changes, admin user mutations, data-source changes, task creation, asset writes, and journal writes; startup logs still include metadata backfill counts
- report markdown and artifacts stay on disk; PostgreSQL stores ownership, visibility, and file index metadata
- new reports created by authenticated tasks default to `private`
- audit metadata must stay small and must not include secrets, API keys, auth tokens, report content, raw prompts, portfolio details, or full exception text; retain audit rows according to your deployment policy and export/delete old rows during regular maintenance

Rollback:

- soft rollback: keep `AUTH_ENABLED=true` and change `AUTH_MODE=required` back to `AUTH_MODE=optional`; reports still require login in optional mode
- full rollback: set `AUTH_ENABLED=false`
- schema rollback order is the reverse migration order: audit events, workbench `tenant_id` columns, tenants/users membership, then user permissions

The backfilled PostgreSQL metadata can remain in place for either rollback path.

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

## Production MVP On Tencent Cloud

Use `compose.prod.yml` for the domestic production MVP stack. It adds Nginx, Redis, a dedicated worker, and a backup service around the existing frontend/backend/Postgres services:

```bash
docker compose -f compose.prod.yml build
docker compose -f compose.prod.yml up -d
```

Production defaults:

- only Nginx exposes `80/443`
- backend and worker use `TASK_BACKEND=redis`
- object storage uses `STORAGE_BACKEND=tencent_cos`
- Postgres remains same-host but is dumped to COS by the `backup` service
- the frontend remains self-hosted, but `NEXT_PUBLIC_API_BASE_URL` keeps a future Vercel deployment possible

See `docs/deployment/tencent-cloud-production.md` for the Tencent Cloud checklist, COS migration, backup, and future overseas storage notes.
