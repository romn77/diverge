# Online Integration Fixes Plan

**Goal:** Close the production integration gaps found during online testing:
administrator task observability, cooperative task termination, automatic latest
ready trading dates, workspace-default reports with visibility management,
simplified data paths and manifests, and a Vercel-hosted SG frontend demo.

**Architecture:** Keep existing backend API contracts wherever possible. Prefer
small backend/runtime changes, explicit task metadata, durable audit trails, and
plain operational runbooks. Frontend changes should be limited to user-facing
workflow simplification and visibility controls, not new landing pages.

**Tech Stack:** FastAPI backend, Redis task queue, SQLAlchemy/Alembic metadata,
Next.js Workbench, Docker Compose production stack, Vercel frontend deployment.

---

## Confirmed Decisions

- Admin task observability first stage is log/runbook based and does not change
  frontend or API contracts.
- Existing cancel endpoints are reused for queued and running task termination.
  Do not add new cancel APIs.
- Running task termination is cooperative, not a hard thread/process kill.
- Do not add a `canceling` status. Keep status `running` after a terminate
  request and add the minimal `cancel_requested_at` marker.
- Store who requested cancel in audit/logs rather than adding user fields to task
  payloads.
- Task termination behavior must be consistent across analysis, screener, and
  data_sync.
- Canceled tasks should not publish final business results. Reusable cache data
  already written by screener/data_sync is not rolled back.
- Product-level `public` means existing `workspace` visibility. Do not add
  anonymous public report access in this plan.
- New analysis defaults to workspace visibility, with user override to private.
- Report visibility can be changed by the owner or by admins in the same tenant.
- Admin changes to another user's report must leave a minimal override marker and
  be shown modestly in the UI.
- Minimal report override fields: `visibility_updated_by_user_id`,
  `visibility_updated_at`, and `visibility_admin_override`.
- Stock analysis should not let normal users choose an old analysis date.
- Analysis date is resolved automatically from ticker market, market timezone,
  and data-ready cutoff.
- Report ids/directories include the analysis date and generated time:
  `TICKER_YYYYMMDD_HHMMSS`.
- Screener main entry always uses latest ready data. Admin data-sync keeps date
  controls for operational backfill.
- `DATA_DIR` is the primary path configuration. Derived directories and
  manifests should live under it by default.
- Manifests are fixed at `DATA_DIR/manifest/us.csv` and
  `DATA_DIR/manifest/cn.csv`, with env overrides only for advanced cases.
- Vercel hosts only the SG frontend demo. Backend, worker, Redis, Postgres, and
  object storage remain in the current backend environment.
- Vercel demo may use `*.vercel.app`; demo backend should allow that origin and
  use `SESSION_COOKIE_SAMESITE=none` with secure cookies.

---

## Phase 1: Admin Task Observability

**Status:** Initial patch exists in the working tree. Keep it as the first
standalone implementation slice.

**Files:**
- Create: `web/backend/runtime/task_logging.py`
- Modify: `web/backend/worker.py`
- Modify: `web/backend/runtime/task_scheduler.py`
- Modify: `web/backend/runtime/analysis_tasks.py`
- Modify: `web/backend/runtime/screener_tasks.py`
- Modify: `web/backend/runtime/data_sync_tasks.py`
- Create: `scripts/ops-task-logs.sh`
- Create: `docs/operations/task-troubleshooting.md`
- Modify: `.env.example`
- Modify: `web/README.md`

**Implementation Notes:**
1. Emit stable `task_event` log lines for queued, claimed, started, progress,
   quota wait, completed, failed, canceled, and acknowledged events.
2. Include operational metadata only: `kind`, `task_id`, `status`, `worker_id`,
   owner/tenant ids, queue wait, elapsed time, stage, current agent, and compact
   error summary.
3. Do not log report content, prompts, portfolio context, full request payloads,
   secrets, or full exception text in task event logs.
4. Keep `job_records.worker_id` populated for running task records.
5. Provide a simple log filter script for task id based debugging.

**Tests:**
- `python -m py_compile` for touched backend runtime files.
- `bash -n scripts/ops-task-logs.sh`.
- `tests/web/test_redis_task_queue.py`
- `tests/web/test_job_records.py`
- `tests/web/test_data_sync_backend.py`
- `tests/web/test_screener_breakout_contracts.py`
- `tests/web/test_backend_main.py`

---

## Phase 2: Cooperative Task Termination

**Files:**
- Modify: `web/backend/runtime/analysis_tasks.py`
- Modify: `web/backend/runtime/screener_tasks.py`
- Modify: `web/backend/runtime/data_sync_tasks.py`
- Modify: `web/backend/runtime/task_store.py` if shared helpers are useful
- Modify: `web/backend/routers/tasks.py`
- Modify: `web/backend/routers/screeners.py`
- Modify: `web/backend/routers/data_sync.py` only if data_sync cancel endpoint is
  not already present and operationally required
- Modify: `web/frontend/lib/api.ts`
- Modify: `web/frontend/components/TaskProgress.tsx`
- Modify: `web/frontend/components/ScreenerTaskProgress.tsx`
- Modify: `web/frontend/components/ActivityDashboard.tsx`
- Modify: `web/frontend/lib/uiPreferences.ts`
- Test: `tests/web/test_redis_task_queue.py`
- Test: `tests/web/test_backend_main.py`
- Test: focused frontend source tests for cancel visibility/copy

**Implementation Steps:**
1. Add `cancel_requested_at` to analysis, screener, and data_sync task payloads.
2. Persist `cancel_requested_at` into Redis/local task state and job records when
   available.
3. For queued, pending, and waiting-for-quota tasks, existing cancel endpoints
   immediately mark `canceled` and remove queue/delayed references.
4. For running tasks, existing cancel endpoints set `cancel_requested_at`, append
   a progress event, audit/log the request, and keep status `running`.
5. Add shared cancel-check helpers that raise a local `TaskCanceled` style
   exception at safe boundaries.
6. Analysis checks after each `graph.stream(...)` chunk before producing final
   report artifacts.
7. Screener checks in progress callbacks, between stages, before export/result
   publication, and before persisting final screener run.
8. Data-sync checks in progress callbacks, between symbol/batch work, before
   screener prewarm, and before writing completed result.
9. On cooperative cancellation:
   - status becomes `canceled`
   - `canceled_at` and `finished_at` are set
   - latest progress says task was canceled by request
   - `error` remains empty/null
   - analysis temp report directory is removed
   - screener final run is not published
   - data_sync completed result and prewarm are not written
10. Frontend exposes cancel/terminate for running tasks. Copy should say that
    running work stops at the next safe step.

**Open Risk:**
- A single long-running vendor/model call cannot be interrupted safely by this
  phase. Stale worker detection/timeout remains a later operational hardening
  item.

---

## Phase 3: Automatic Latest Ready Trading Date

**Files:**
- Modify: `web/backend/schemas/tasks.py`
- Modify: `web/backend/routers/tasks.py`
- Modify: `diverge/runner.py`
- Modify: `web/backend/runtime/data_sync_tasks.py` or a shared date resolver
- Modify: `web/backend/routers/screeners.py`
- Modify: `web/frontend/components/NewAnalysisForm.tsx`
- Modify: `web/frontend/components/ScreenerDashboard.tsx`
- Modify: `web/frontend/components/NewScreenerForm.tsx`
- Modify: `web/frontend/lib/uiPreferences.ts`
- Test: backend date resolver tests
- Test: frontend source tests for hidden date controls

**Implementation Steps:**
1. Add a shared resolver for latest ready trading day:
   - detect market from ticker for analysis
   - use market-local timezone
   - use CN cutoff default `DATA_SYNC_TUSHARE_READY_TIME=18:10`
   - use US cutoff default `DATA_SYNC_MASSIVE_READY_TIME=21:10`
   - before cutoff use the previous trading day
   - on holidays/weekends use the previous trading day
2. Make `TaskCreatePayload.analysis_date` optional. If absent, resolve it on the
   backend before constructing `AnalysisRequest`.
3. Hide analysis date input in the normal new-analysis form.
4. Keep analysis date in task payload, report metadata, decision card, and report
   list/detail displays.
5. Change analysis report id format to `TICKER_YYYYMMDD_HHMMSS`, where
   `YYYYMMDD` is the analysis date and `HHMMSS` is generated time.
6. Remove ordinary screener date selection. The backend resolves latest ready
   `as_of_date` for screener tasks.
7. Keep admin data-sync date inputs for operational backfill.

**Tests:**
- CN/US cutoff behavior.
- Weekend/holiday fallback.
- Analysis payload without date resolves correctly.
- Screener payload without date resolves latest ready date.
- Report id includes analysis date and generated time.

---

## Phase 4: Workspace Default And Report Visibility Management

**Files:**
- Create Alembic migration for report visibility override fields.
- Modify: `web/backend/report_metadata.py`
- Modify: `web/backend/services/reports.py`
- Modify: `web/backend/routers/reports.py`
- Modify: `web/backend/schemas/tasks.py`
- Modify: `web/backend/routers/tasks.py`
- Modify: `web/frontend/lib/api.ts`
- Modify: `web/frontend/components/NewAnalysisForm.tsx`
- Modify: `web/frontend/components/HomeDashboard.tsx`
- Modify: `web/frontend/components/ReportViewer.tsx`
- Modify: `web/frontend/lib/uiPreferences.ts`
- Test: `tests/web/test_metadata_backfill.py`
- Test: `tests/web/test_auth_backend.py`
- Test: focused frontend source tests

**Implementation Steps:**
1. Change new task default visibility from private to workspace in frontend and
   backend schema.
2. Add report fields:
   - `visibility_updated_by_user_id`
   - `visibility_updated_at`
   - `visibility_admin_override`
3. Add backend service function to update report visibility.
4. Allow owner to change own report visibility.
5. Allow admin to change same-tenant reports.
6. Deny non-owner non-admin visibility changes.
7. When admin changes another user's report, set `visibility_admin_override`.
8. Record audit event with actor, report id, old visibility, new visibility, and
   owner id.
9. Add report list/detail UI affordance to switch visibility for authorized
   users.
10. Show a modest admin override marker:
    - regular users: `管理员已调整`
    - admin/detail contexts may include timestamp
11. Do not add anonymous public sharing.

---

## Phase 5: DATA_DIR And Manifest Path Simplification

**Files:**
- Modify: `diverge/data_layout.py`
- Modify: `web/backend/app_config.py`
- Modify: `web/backend/routers/screeners.py`
- Modify: `web/backend/runtime/data_sync_tasks.py`
- Modify manifest generation/import scripts after locating current script names
- Modify: `.env.example`
- Modify: `web/README.md`
- Modify: deployment docs
- Test: data layout tests and screener route tests

**Implementation Steps:**
1. Treat `DATA_DIR` as the primary path users configure.
2. Keep existing path env vars as advanced overrides only.
3. Add default manifest paths:
   - `DATA_DIR/manifest/us.csv`
   - `DATA_DIR/manifest/cn.csv`
4. Add resolver helpers for manifest path lookup:
   - env override first
   - default `DATA_DIR/manifest/<market>.csv` second
   - CN source-chain fallback remains
   - US missing manifest raises a clear setup error
5. Update scripts that generate or consume manifest files so default output is
   `DATA_DIR/manifest/`.
6. Add script options only where useful:
   - `--market us|cn|all`
   - `--output-dir <DATA_DIR>/manifest`
7. Update `.env.example` to document the standard layout rather than encouraging
   `SCREEN_*_MANIFEST_PATH`.
8. Update deployment checks to verify US manifest and warn for missing CN
   manifest.

**Standard Layout:**

```text
data/
  manifest/
    us.csv
    cn.csv
  reports/
  screener/
  cache/
  history/
  fundamentals/
```

---

## Phase 6: Vercel SG Frontend Demo

**Files:**
- Modify: `web/README.md`
- Modify: deployment docs, likely `docs/deployment/tencent-cloud-production.md`
- Create: optional Vercel deployment notes under `docs/deployment/`
- No backend migration required unless cookie config docs reveal gaps

**Implementation Steps:**
1. Deploy only `web/frontend` to Vercel for demo.
2. Set Vercel build root to `web/frontend`.
3. Configure `NEXT_PUBLIC_API_BASE_URL` to the HTTPS backend API domain.
4. Configure backend demo env:
   - `FRONTEND_ORIGIN=https://<demo>.vercel.app`
   - `SESSION_COOKIE_SECURE=true`
   - `SESSION_COOKIE_SAMESITE=none`
5. Verify CORS credential behavior from Vercel frontend to backend.
6. Keep backend, worker, Redis, Postgres, and COS in existing backend
   environment.
7. Later production custom-domain recommendation:
   - frontend `sg.<domain>`
   - api `api.<domain>`
   - consider returning to `SameSite=lax` when same-site subdomains are used.

**Demo Acceptance Checks:**
- Login works from Vercel domain.
- Authenticated API calls include cookies.
- Report list/detail loads.
- New analysis form submits to backend.
- Activity/task progress routes can read backend task state.

---

## Sequencing

1. Finish and review Phase 1 patch.
2. Implement Phase 2 task termination end to end.
3. Implement Phase 3 date simplification and report id format.
4. Implement Phase 4 visibility defaults and controls.
5. Implement Phase 5 path/manifest cleanup plus script migration.
6. Document and validate Phase 6 Vercel demo.

Each phase should be testable independently and should avoid unrelated
refactors.

---

## Explicit Non-Goals

- No anonymous public report sharing.
- No hard-kill of Python threads or worker processes for running tasks.
- No rollback of already-written reusable market data cache.
- No migration of backend/worker/Redis/Postgres/COS to Vercel.
- No broad redesign of Workbench navigation.
