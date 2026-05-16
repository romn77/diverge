# AGENTS.md

Guidance for AI coding agents working in this repository. Keep this file current
when project structure, commands, or operational rules change.

## Project Overview

Diverge is a modified fork of an Apache-2.0 multi-agent financial trading
research framework. The repository combines:

- Python package code under `diverge/` for agents, data-source routing,
  screeners, valuation, research, and runtime helpers.
- A FastAPI backend under `web/backend/` for reports, tasks, auth/admin,
  screeners, assets, trades, storage, and workers.
- A Next.js frontend under `web/frontend/` for the Web Workbench.
- Runtime data and generated artifacts under `data/`.

This is research and internal decision-support software, not financial,
investment, legal, tax, or trading advice.

## Repository Layout

- `diverge/agents/`: analyst, researcher, trader, risk, and manager agents.
- `diverge/dataflows/`: data-source routing, vendor registry, shared errors,
  market utilities, and vendor adapters.
- `diverge/screener/`: CN/US screener pipeline, filters, indicators, cache, and
  replay support.
- `diverge/valuation/`: DCF, FCFF, multiples, assumptions, and schemas.
- `diverge/research/`: earnings, thesis tracker, and search workflow code.
- `web/backend/`: FastAPI app, routers, services, auth, Alembic migrations,
  task runtime, storage, and worker.
- `web/frontend/`: Next.js app, React components, frontend tests, API client,
  and styling.
- `tests/`: Python regression tests, grouped by backend/runtime area.
- `docs/`: plans, deployment notes, security/deep-research reports, and design
  references.
- `scripts/`: deployment, database, backup, and restore helpers.
- `data/`, `output/`: local runtime artifacts. Treat these as generated unless a
  task explicitly asks to update fixtures or checked-in sample data.
- `copy/skillshare/`: copied/reference material; avoid changing it unless the
  task is specifically about that subtree.

## Common Commands

Python environment:

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e ".[web]"
```

If using uv:

```bash
uv sync
```

Run the Web Workbench from `web/`:

```bash
./start.sh
```

Useful focused Python checks:

```bash
python -m pytest -q tests/dataflows tests/test_akshare.py tests/test_yfinance.py tests/screener/test_market_data.py tests/screener/test_universe.py
python -m pytest -q tests/web/test_backend_main.py tests/web/test_runner.py
```

Frontend checks from `web/frontend/`:

```bash
npm test
npm run build
npm run lint
```

Database/auth checks:

```bash
scripts/check-database.sh
scripts/check-database.sh --upgrade --bootstrap-admin
```

## Development Notes

- Python requires 3.11 or newer.
- Keep edits scoped to the area requested. There may be unrelated local changes
  in this working tree; do not revert or reformat them.
- Prefer existing patterns and helper APIs over new abstractions. Look at nearby
  routers/services/components/tests before adding new shapes.
- New data-source code should use the vendor package layout under
  `diverge/dataflows/vendors/`; legacy import aliases exist for compatibility
  but are not the preferred path for new code.
- Backend route logic should stay in routers, shared behavior in services, and
  long-running task behavior in `web/backend/runtime/`.
- Frontend code uses Next.js, React, TypeScript, Tailwind CSS, Radix primitives,
  and `lucide-react` icons. Keep operational Workbench screens dense, scannable,
  and consistent with existing components.
- For any frontend page, component, layout, styling, or theme work, use
  `.agents/skills/workbench-ui-theme-audit/SKILL.md` before editing and before
  calling the change done.
- Frontend changes should extend the existing Workbench visual system rather
  than redesign it by default. Do not change page information architecture,
  visual direction, typography, radius language, shadow language, or motion
  style unless the task explicitly asks for a redesign.
- Unless the task explicitly asks for a design change, style-element edits such
  as color, type scale, spacing, radius, border treatment, shadow treatment,
  and motion should follow the site-wide design language.
- Treat new hard-coded Tailwind color utilities, raw `rgb(...)`/`rgba(...)`, and
  literal hex colors inside `web/frontend` TSX files as design debt. Prefer
  shared primitives and semantic tokens, and do not expand the existing debt
  baseline unless the task explicitly requires it.
- For automated testing of Workbench business flows, use
  `.agents/skills/workbench-automation-testing/SKILL.md`. Business-flow E2E
  should be browser-first: drive the same UI journey a user would take, and use
  API/pytest checks only for fixture setup, cleanup, hidden permission/state
  assertions, or edge cases the browser cannot observe well.
- Frontend tests are Node built-in test files (`*.test.mjs` / `*.test.ts`) run
  by `npm test`; they often assert source contracts and UI copy.
- Use focused tests for the touched area first, then broaden when changing shared
  contracts such as auth, task state, screener behavior, storage, or API schemas.

## Automated Business Testing

- When a change affects a user-facing Workbench workflow, prefer a browser-driven
  Playwright or agent-browser E2E path over an API-only test. A test that never
  opens the browser is an API integration test, not business E2E.
- Start from the business actor and outcome: report discovery/review, launching
  analysis to completed report, building screener candidates, login/permissions,
  assets, journal, activity/queue observability, or deployment smoke.
- Keep E2E deterministic with temp `DATA_DIR` fixtures, test adapters, or
  deterministic runner modes. Do not depend on live LLM calls, live market-data
  vendors, real secrets, or local runtime data in default automation.
- API and pytest coverage should support business E2E by protecting hidden
  contracts such as auth/tenant scoping, audit metadata, task-store state,
  path traversal, malformed payloads, and migration behavior.
- Browser tests should use accessible roles/labels first. Add narrow
  `data-testid` selectors only for dense controls, translated/high-churn copy,
  icon-only actions, or repeated labels.
- Record the browser journey exercised, fixture mode, commands run, skipped
  checks, and residual risk whenever adding or reviewing automation.

## Subagent Development

- Subagents may be used for repository exploration, bounded implementation,
  review, and verification when the task benefits from parallel work or focused
  specialist attention.
- Keep delegated work concrete and scoped. For implementation, split work by
  clearly separated files or modules so subagents do not edit the same area at
  the same time.
- The coordinating agent remains responsible for reading relevant local context,
  integrating subagent changes, resolving conflicts, preserving user changes,
  and running or reporting the appropriate focused checks.
- Prefer subagents for sidecar work that can run in parallel, such as mapping
  call paths, drafting tests, reviewing risk areas, or implementing isolated
  slices. Keep tightly-coupled or blocking decisions with the coordinating
  agent.
- Subagents must follow this `AGENTS.md`, keep edits scoped to the user request,
  and avoid generated artifacts or destructive git commands unless explicitly
  requested.

## Data, Auth, And Deployment

- Do not commit secrets, API keys, session tokens, `.env` contents, local
  database URLs, or provider credentials.
- Important environment variables include `DATABASE_URL`, `AUTH_ENABLED`,
  `AUTH_MODE`, `FRONTEND_ORIGIN`, `NEXT_PUBLIC_API_BASE_URL`, `TASK_BACKEND`,
  `REDIS_URL`, `STORAGE_BACKEND`, `SCREEN_US_MANIFEST_PATH`, and
  `SCREEN_CN_MANIFEST_PATH`.
- US web screening requires backend `SCREEN_US_MANIFEST_PATH`. CN screening can
  use `SCREEN_CN_MANIFEST_PATH` or fall back to the configured CN source chain.
- Production-style worker mode uses `TASK_BACKEND=redis` and a Redis URL.
- Report markdown and artifacts stay on disk; PostgreSQL stores ownership,
  visibility, and file index metadata when auth/database mode is enabled.
- Audit metadata must stay small and must not include secrets, auth tokens,
  report content, raw prompts, portfolio details, or full exception text.

## Migrations

- Alembic migrations live in `web/backend/alembic/versions/`.
- Treat applied migrations as append-only. Add a new migration for schema
  changes instead of editing historical migration files.
- Auth/database startup expects required tables to exist. Use
  `scripts/check-database.sh --upgrade --bootstrap-admin` for local upgrade and
  bootstrap flows.
- Keep migration ordering and rollback notes aligned with `web/README.md` and
  `docs/deployment/tencent-cloud-production.md`.

## Safety Rules

- Before making edits, check the current file state and work with existing user
  changes.
- Do not run destructive commands such as `git reset --hard`, broad deletes, or
  checkout/restore over user changes unless explicitly requested.
- Avoid modifying generated caches such as `__pycache__/`, `.pytest_cache/`,
  `.ruff_cache/`, `web/frontend/.next/`, and runtime files in `data/` unless the
  task requires it.
- When changing financial calculations, data routing, auth, permissions,
  visibility, or deployment behavior, add or update regression coverage and call
  out any checks that could not be run.
