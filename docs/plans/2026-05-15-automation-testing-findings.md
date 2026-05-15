# Automation Testing Strategy Findings

## Initial Context

- The repository already has many Python regression tests under `tests/`.
- The frontend has many Node built-in source-contract tests under
  `web/frontend/**/*.test.*`.
- At the start of analysis, no Playwright config or browser E2E test files were
  found in the quick file inventory.

## Findings

- Python test configuration lives in `pyproject.toml` and uses pytest with
  `--import-mode=importlib`.
- Frontend tests run through `node --test` via `web/frontend/package.json`.
  Existing tests are source-contract and copy/structure tests rather than
  browser-driven user flows.
- `.github/` only contains `pull_request_template.md`; no GitHub Actions
  workflow was found in the repository.
- `web/start.sh` can start backend, optional Redis worker, and Next.js frontend
  together. It also handles local data directories, health checks, log files,
  auth migrations/bootstrap, and configurable ports.
- Backend tests already include a reusable ASGI HTTP harness at
  `tests/web/http_harness.py`, which can support API-level integration tests
  without opening real sockets.
- Start script behavior is currently covered mostly as source assertions in
  `tests/test_web_start_script.py`; full-stack startup is not automatically
  exercised end to end.
- The workbench has route-driven product areas for reports, analysis tasks,
  screener tasks/runs, activity, assets, journal, login, and admin pages.
- Frontend API calls are centralized in `web/frontend/lib/api.ts`; protected
  requests use `credentials: "include"` and 401 responses emit an
  `AUTH_REQUIRED_EVENT`.
- Task progress uses SSE/EventSource on `/api/tasks/{task_id}/stream` and
  `/api/screener/tasks/{task_id}/stream`. The backend has deterministic support
  for replaying progress events from a cursor.
- Next.js supports `API_PROXY_TARGET` rewrites, which can simplify browser tests
  by letting Playwright hit the frontend origin while proxying `/api/*` to a
  test backend.
- The repository has local, Docker Compose, and production-style Redis worker
  modes. These should not all be tested at the same frequency.
- There are useful ARIA labels and semantic roles in some components, but no
  `data-testid` selectors were found. Browser tests should prefer accessible
  roles where stable and add targeted stable selectors for high-churn controls.
- The PR template already asks for tests/manual checks/screenshots and Codex
  preflight review, but there is no automated workflow enforcing those checks.

## Early Interpretation

- The main automated-testing gap is not lack of unit coverage. It is lack of a
  reliable browser-driven business-flow layer that proves users can complete
  Workbench journeys after broad refactors.
- API integration tests remain useful for hidden contracts, setup, and deep
  assertions, but they should not be counted as business E2E when they skip the
  UI path a user would actually take.
- The first practical browser layer should drive high-value paths directly in
  the app: Workbench navigation, report discovery to review, launching analysis
  to a completed report through deterministic adapters, building a screener to
  candidate results, login/permissions, assets CRUD, journal CRUD, and activity
  queue observability.
