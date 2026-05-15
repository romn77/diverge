---
name: workbench-automation-testing
description: Browser-first business workflow automation for Diverge Web Workbench, FastAPI backend, task runtime, reports, screeners, assets, journal, auth, deployment smoke tests, and Playwright E2E coverage. Use when asked to plan, add, review, refactor, or run automated tests beyond unit tests; when a feature needs module-level or business-flow coverage; when Codex/agents should use a browser to execute real Workbench journeys end to end; when broad refactors risk frontend/backend regressions; or when creating CI gates, fixtures, selectors, or reusable test plans.
---

# Workbench Automation Testing

## Purpose

Use this skill to turn Diverge testing needs into repeatable business-flow
automation that future Codex or agent runs can execute through a browser. The
goal is not to add large brittle E2E suites. The goal is to protect the changed
business journey with the smallest reliable browser path, using API checks only
as setup, teardown, or supporting assertions.

## First Decision

Classify the request before editing. If the request mentions a user workflow,
business flow, Workbench behavior, regression risk across modules, or end-to-end
automation, default to browser-driven E2E.

- **Business workflow**: use Playwright or an agent browser to drive the UI from
  the user's entry point to the business outcome. Use APIs only to seed/reset
  state or inspect supporting records.
- **Pure logic or schema**: add or update focused pytest or `node --test`
  coverage.
- **Backend route/service contract**: add API integration coverage with isolated
  temp data when there is no meaningful UI path or when validating hidden
  permission/data contracts.
- **Auth, task runtime, storage, screener, report artifact, deployment, or
  cross-stack behavior**: add browser coverage for the user-facing journey plus
  lower-level regression tests for hidden boundaries.
- **CI or release confidence**: update fast PR checks first; keep slower
  Docker/Postgres/Redis checks for nightly or release lanes.

If the user asks for analysis only, write findings under `docs/plans/`. If the
user asks for implementation, edit tests/config directly and run focused checks.

## Core Workflow

1. Read the touched module and nearby tests before deciding the coverage shape.
2. Map the business actor, goal, entry route, UI steps, generated artifacts,
   state transitions, and final user-visible outcome.
3. Execute the main acceptance path through the browser. Do not replace a
   business journey with direct API calls when the UI path exists.
4. Choose fixtures/test doubles that avoid live LLM calls and live market-data
   vendors while preserving the same browser journey.
5. Prefer deterministic temp `DATA_DIR` fixtures over checked-in runtime data.
6. Prefer accessible selectors first; add narrow `data-testid` selectors only
   for dense or multilingual/high-churn controls.
7. Implement the smallest browser journey that fails on the regression being
   protected.
8. Run focused tests for the touched layer, then broaden only for shared
   contracts.
9. Record commands, skipped checks, and residual risks in the final response or
   plan file.

## References

Load only the reference needed for the task:

- `references/module-workflows.md`: module-by-module workflow map, risk areas,
  preferred test layers, and fixture hints.
- `references/business-e2e-flows.md`: browser-first business journeys and
  acceptance criteria for agents.
- `references/playwright-first-slice.md`: concrete Playwright setup for the
  first Workbench business smoke suite.
- `references/ci-quality-gates.md`: PR, nightly, and release gate guidance.

## Guardrails

- Do not rely on real API keys, live LLM calls, or vendor market-data calls in
  default automated tests.
- Do not call backend APIs to complete a business workflow when the user can
  complete that workflow in the browser. APIs are allowed for seeding, cleanup,
  and deeper assertions.
- Do not write tests against local `data/` unless the task explicitly asks to
  update checked-in fixtures.
- Do not turn source-text assertions into the only proof for a real user
  workflow when browser/API behavior is what matters.
- Do not add broad sleeps in browser tests; wait on visible state, route changes,
  API responses, or deterministic fixture state.
- Do not make Redis/Postgres/Docker checks mandatory for every small PR unless
  the changed surface needs that confidence.

## Recommended Output

For planning tasks, produce:

- affected workflow
- business actor and expected outcome
- risk boundaries
- browser journey and supporting lower-level tests
- fixture strategy
- first test cases
- commands to run

For implementation tasks, produce:

- changed test/config files
- fixtures or selectors added
- browser path exercised
- commands run and results
- remaining gaps
