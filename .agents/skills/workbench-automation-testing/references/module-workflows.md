# Diverge Module Workflow Test Map

Use this reference to choose test coverage by module. For business workflows,
prefer browser-driven E2E through the existing Workbench UI. Use lower-level
API/pytest tests for setup, hidden contracts, and edge cases the browser cannot
observe well.

## Analysis Reports

Business workflow:

1. User opens the analysis workspace.
2. User searches/filters the report library.
3. User opens a report from the visible list.
4. User reviews markdown sections and structured decision surfaces.
5. User returns to the workbench or opens another report.

Primary risks:

- report id/path handling
- markdown/artifact parsing
- visibility/owner scope
- frontend route and viewer regressions

Preferred tests:

- Playwright report discovery-to-review journey
- pytest service/API tests for metadata, visibility, path rejection
- `node --test` for parser/source contracts

Fixture hints:

- include a minimal report directory with `complete_report.md`
- include optional `decision_card` and `decision_delta` JSON artifacts when the
  viewer behavior is changed

## Analysis Tasks

Business workflow:

1. User opens the analysis workspace.
2. User opens `NewAnalysisForm`.
3. User fills ticker, model/profile, analysts, language, and visibility.
4. User submits the task from the browser.
5. User follows task progress.
6. User opens the completed report.

Primary risks:

- model/profile payload drift
- task queue statuses and cancellation
- SSE replay/disconnect behavior
- generated report id handoff

Preferred tests:

- Playwright launch-analysis-to-report journey
- pytest route/service tests for payload normalization and task lifecycle
- API integration tests for create/list/cancel/status

Fixture hints:

- use a test-only runner mode that preserves UI submission and task navigation
- avoid live LLM and vendor calls

## Screeners

Business workflow:

1. User opens `/screeners`.
2. User selects market/source/ranking/filter options.
3. User launches a screener from the browser.
4. User follows screener task progress.
5. User opens completed candidate results.

Primary risks:

- market/source/as-of-date preparation
- cache-only vs live-source behavior
- candidate CSV/read-model drift
- progress cursor replay
- route handoff from task to run

Preferred tests:

- Playwright build-screener-to-candidates journey
- pytest service tests for preparation, read model, stale data, sync readiness
- API tests for task/runs/candidates

Fixture hints:

- seed manifest/history/fundamental inputs when testing the full build journey
- include `run_meta.json` and `candidates.csv` only for viewer-specific tests
- include `data/manifest/us.csv` when US screening setup is involved

## Auth, Permissions, And Admin

Business workflow:

1. User opens `/login`.
2. User signs in with a seeded account.
3. User navigates Workbench/admin pages.
4. User sees only allowed actions.
5. User logs out or loses session and returns to a safe auth boundary.

Primary risks:

- session cookie and bearer behavior
- tenant/owner scoping
- role permission drift
- admin-only mutations
- audit metadata privacy

Preferred tests:

- Playwright login and permission navigation journey
- pytest database/auth tests for permission boundaries
- API integration tests for role matrix and tenant isolation

Fixture hints:

- use Postgres-backed auth for production-like smoke
- avoid inventing SQLite support unless the backend already supports it cleanly

## Assets And Journal

Business workflow:

1. User opens assets or journal.
2. User creates/edits/deletes a position or trade record through forms.
3. User confirms the list and summary update.
4. When relevant, user launches an analysis that consumes portfolio/trade
   context.

Primary risks:

- owner/tenant scoping
- numeric parsing and currency/market normalization
- refresh side effects
- generated review payload shape
- portfolio/trade context leakage into tasks

Preferred tests:

- Playwright CRUD business journey
- pytest service/API tests for scoping and context builders

Fixture hints:

- isolate `DATA_DIR`
- mock price/history refresh calls or use fixed history fixtures

## Data Sync, Runtime, And Worker

Business workflow:

1. Admin/operator starts or observes background work from the Workbench.
2. User reads queued/running/waiting/canceled/failed states.
3. User cancels when safe.
4. User confirms final activity state.

Primary risks:

- Redis/local divergence
- stale running recovery
- quota delays
- cancellation transitions
- vendor readiness dates

Preferred tests:

- Playwright activity/queue observability journey for visible states
- pytest lifecycle/task-store tests
- focused Redis integration tests where already present
- Docker/Redis smoke in nightly/release lanes

Fixture hints:

- use fake task stores and fake vendor readiness clocks for PR checks
- use real Redis only for production-like smoke

## Deployment And Startup

Business workflow:

1. Agent starts the deployable/local app.
2. Agent opens the frontend in a browser.
3. Agent signs in when auth is enabled.
4. Agent completes a short critical Workbench journey.

Primary risks:

- env var drift
- port/origin/API URL mismatch
- migrations before backend startup
- worker/backend split
- health checks that do not cover real readiness

Preferred tests:

- source-contract tests for scripts/env expectations
- production-like smoke for Compose on nightly/release
- browser business smoke through frontend after backend health is ready

Fixture hints:

- never require secrets for smoke
- use health endpoints and fixture task lifecycle rather than live provider calls
