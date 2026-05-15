# Diverge Automated Testing Strategy

## Background

Current development has many feature changes and refactors happening across the
Python runtime, FastAPI backend, Next.js Workbench, auth/database behavior,
screeners, assets, journal, and deployment scripts. Unit tests are necessary but
not enough for this shape of product. The recurring pain is that important
regressions happen at boundaries:

- frontend API client vs backend response shape
- route navigation vs task/report/screener state
- auth/session/permission checks vs user-visible pages
- local task mode vs Redis worker mode
- generated report/screener artifacts vs viewers
- deployment/startup scripts vs actual service boot

The repository already has broad Python regression coverage and many frontend
`node --test` source-contract tests. The missing layer is a small, reliable
business-flow suite where an agent or Playwright browser performs the same
Workbench actions a user performs, while test fixtures or adapters keep external
LLM/vendor dependencies deterministic.

## Current State

- Python tests are configured through `pyproject.toml` and pytest.
- Backend tests already use isolated temp data and include an ASGI HTTP harness
  in `tests/web/http_harness.py`.
- Frontend tests run with `node --test` from `web/frontend/package.json`.
- No Playwright/Cypress browser automation config was found.
- No GitHub Actions workflow was found under `.github/`.
- `web/start.sh` can start backend, optional Redis worker, and frontend, but
  existing tests mostly assert script contents instead of exercising a full
  browser flow.
- `web/frontend/next.config.ts` supports `API_PROXY_TARGET`, which is useful for
  browser tests that serve Next.js and proxy `/api/*` to a fixture-backed backend.

## Testing Model

Use four layers. Each layer should answer a different question.

### 1. Unit And Contract Tests

Question: did a local function, schema, parser, service, or component contract
change unexpectedly?

Keep the existing pytest and `node --test` pattern. Expand it when touching pure
logic, schemas, parsing, permission gates, report artifact readers, or frontend
source contracts.

Expected commands:

```bash
python -m pytest -q tests/web/test_backend_main.py tests/web/test_task_route_support.py
cd web/frontend && npm test
```

### 2. API Integration Tests

Question: do backend routes and services preserve hidden contracts that the
browser cannot observe well?

Use the existing ASGI harness for deterministic backend flows. This layer should
cover auth/database permissions, report visibility, task lifecycle, screener
task/runs, assets, journal, data-sync queue behavior, and audit metadata.

This layer supports business E2E. It should not replace a browser test when the
regression is in a real Workbench workflow.

### 3. Browser Business E2E Tests

Question: can a user complete the critical Workbench business workflows in a
real browser?

Add Playwright under `web/frontend/`. Start with Chromium only in PR checks.
Keep the suite intentionally small and deterministic:

- no live LLM calls
- no live market-data vendor calls
- fixture-backed `DATA_DIR`
- local backend on an ephemeral port
- Next.js dev server with `API_PROXY_TARGET`
- traces/screenshots retained only on failure

Recommended first tests:

1. Workbench navigation smoke: open the app and navigate through business areas.
2. Report discovery to review: find a report from the dashboard and inspect the
   decision/review surface.
3. Launch analysis to completed report: submit the analysis form in the browser,
   observe progress, and open the generated report using deterministic test
   adapters.
4. Build screener to candidates: configure a screener in the browser, launch it,
   observe progress, and inspect ranked candidate results.
5. Login and permission navigation: sign in through `/login` and confirm
   role-appropriate UI.
6. Assets workflow: create/edit/delete a position and confirm summary changes.
7. Journal workflow: create a trade record and confirm it appears in history.
8. Activity/queue observability: verify visible queued/running/terminal states.

The first implementation slice should do the first four as true browser
journeys. API calls can seed preconditions and inspect hidden state, but the
tested business action must happen through the UI. Add auth and CRUD flows after
the browser fixture story is stable.

### 4. Production-Like Smoke Tests

Question: does the deployable stack boot and expose the expected health surfaces?

Run this less frequently, such as nightly or pre-release. Use Docker Compose with
Postgres and Redis, but still avoid LLM/vendor calls. Cover:

- migrations and bootstrap admin
- `/api/healthz`
- frontend reachable
- backend/worker Redis connectivity
- one queued fixture task can be created, listed, canceled, and observed

This layer is valuable but slower and more operationally brittle, so it should
not be the first PR gate.

## Fixture Strategy

Create deterministic e2e fixtures rather than using checked-in runtime data.

Recommended structure:

```text
web/frontend/e2e/
  fixtures/
    data/
      reports/
      screener/runs/
      screener/tasks/
      history/
      manifest/
  pages/
  specs/
  global-setup.ts
```

Use `DATA_DIR` to point the backend at a copied temp fixture directory for each
test run. This keeps tests isolated and prevents writes to real local data.

For task and screener scenarios, prefer a test-only backend runner mode or fake
external adapters that preserve the same UI submission, progress, and result
navigation path. Fixture task records are acceptable for viewer/progress-page
regressions, but they are not enough for business-flow coverage of launching
work from the UI.

## Browser Agent Policy

Codex or another agent may directly use a browser to exercise existing business
flows. The browser run is useful for exploration, debugging, screenshots, and
forward-testing the flow. The durable outcome should still be an automated
Playwright spec or equivalent command that can be rerun later.

Use the browser for:

- navigation
- filling forms
- launching analysis/screener/background work
- observing task progress
- opening generated reports and results
- verifying role-visible UI
- CRUD workflows for assets and journal

Use API or pytest only for:

- fixture setup/cleanup
- hidden authorization, tenant, audit, or task-store assertions
- path traversal and malformed payload checks
- diagnosing browser failures

## Selector Strategy

Prefer accessible selectors first: roles, labels, headings, and ARIA names.
However, this Workbench has multilingual copy and frequent UI polish, so critical
controls should receive stable `data-testid` attributes in a narrow way.

Good candidates:

- new analysis open/submit controls
- task status badge and view-report action
- report list item and report viewer root
- screener run list and candidate table
- login account/password/submit controls
- asset/journal create/edit/delete controls

Do not blanket every element with test IDs. Add them where text selectors would
be fragile or where the UI is dense.

## CI Recommendation

Add GitHub Actions in stages.

PR fast lane:

```bash
python -m pytest -q tests/web tests/runtime tests/decision_card
cd web/frontend && npm test
cd web/frontend && npm run build
cd web/frontend && npm run test:e2e -- --project=chromium
```

Nightly or manual release lane:

```bash
python -m pytest -q
cd web/frontend && npm run lint
docker compose -f compose.prod.yml up -d postgres redis
scripts/check-database.sh --upgrade --bootstrap-admin
cd web/frontend && npm run test:e2e:smoke
```

The exact full pytest scope can be tuned after runtime is measured. The key is to
make PR checks fast enough that developers actually trust and run them.

## Implementation Roadmap

### Phase 1: Browser Business Smoke Foundation

- Add `@playwright/test` to `web/frontend`.
- Add `web/frontend/playwright.config.ts`.
- Add `test:e2e` and `test:e2e:headed` npm scripts.
- Add fixture data and a global setup that copies fixtures into a temp `DATA_DIR`.
- Start backend with `AUTH_ENABLED=false`, `TASK_BACKEND=local`, and fixture
  `DATA_DIR`.
- Start frontend with `API_PROXY_TARGET` pointing to that backend.
- Add four business specs: workbench navigation, report discovery to review,
  launch analysis to report, build screener to candidates.

### Phase 2: Auth And CRUD Scenarios

- Add an auth-enabled fixture mode using SQLite only if the backend can support
  it cleanly; otherwise use Postgres in a slower lane.
- Cover login/logout, permission-based navigation, assets CRUD, journal CRUD,
  and admin read-only visibility.

### Phase 3: CI And Quarantine Policy

- Add PR workflow for unit/contract/build/e2e smoke.
- Add nightly workflow for broader pytest and production-like Compose smoke.
- Add a quarantine convention for flaky specs with issue links and owners.
- Store Playwright traces and screenshots as CI artifacts on failure.

### Phase 4: Testable Task Runner Mode

- Add a test-only deterministic task runner mode that creates a minimal report
  and progress stream without LLM/vendor dependencies.
- Use it for one real create-task-to-report browser scenario.
- Keep live provider validation manual or scheduled only with explicit secrets.

## Definition Of Done For Future Features

For backend-only changes:

- focused pytest for touched services/routes
- API integration test if route contracts or auth/permissions change

For frontend-only changes:

- existing `node --test` source contract updates
- Playwright update if a critical workflow, route, or navigation behavior changes

For cross-stack features:

- pytest route/service coverage
- frontend API contract test
- one browser scenario or explicit note why the existing scenario covers it

For auth, storage, task runtime, screener, report artifact, or deployment
changes:

- regression test in the relevant layer
- PR validation notes listing what was not automated

## Main Recommendation

Do not try to build a huge E2E suite first. Start with four deterministic
Workbench smoke tests and make them easy to run locally and in PRs. Once that
baseline is trusted, expand into auth, CRUD, and production-like Compose smoke.

The highest leverage first milestone is:

```text
Playwright + fixture DATA_DIR + API_PROXY_TARGET + four browser-driven Workbench business specs
```

That directly targets the current pain: broad refactors breaking user-visible
flows that unit tests and source-contract tests cannot see.

## Skill Packaging

The automation strategy should also live as a repo-local skill so future Codex
or agent sessions can apply it consistently by module workflow.

Recommended skill:

```text
.agents/skills/workbench-automation-testing/
```

The skill should encode:

- how to choose between pytest, API integration tests, Playwright, and
  production-like smoke tests
- module workflow maps for reports, tasks, screeners, auth/admin, assets,
  journal, runtime, and deployment
- fixture and selector rules for browser automation
- PR, nightly, and release gate recommendations

This makes the strategy executable by future agents instead of leaving it as a
one-time planning document.
