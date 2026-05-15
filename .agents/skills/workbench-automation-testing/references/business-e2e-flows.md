# Browser-First Business E2E Flows

Use this reference when the user wants automated tests based on business
processes rather than API endpoints. The browser journey is the primary test.
API calls may prepare fixtures, reset data, or assert backend state after the
browser completes the flow.

## Principles

- Start from the user's business goal, not from an endpoint.
- Drive the route, form, navigation, task page, and result page through the UI.
- Assert business outcomes visible to the user: report available, candidates
  ranked, trade saved, asset summarized, admin setting reflected, queue status
  understandable.
- Keep external services deterministic with fixture data, test doubles, or
  explicit test runner modes.
- Add lower-level API/pytest coverage only for hidden contracts that the browser
  cannot observe well.

## Agent Browser Execution Pattern

When Codex or another agent is allowed to use a browser:

1. Start the app in an isolated test mode.
2. Open the Workbench route in the browser.
3. Use visible labels, roles, headings, and stable test IDs to perform actions.
4. Take screenshots or traces on failures.
5. Inspect logs/API state only to diagnose or verify hidden details.
6. Leave the test runnable by command, not only manually replayed by the agent.

The final artifact should be a Playwright spec or equivalent automated browser
test, not just a manual browser report.

## Journey 1: Report Discovery To Decision Review

Actor: operator or analyst.

Goal: find an existing research report and review the final decision.

Browser path:

1. Open `/`.
2. Search or filter the report library by ticker/report id.
3. Open a report from the visible report list.
4. Confirm report markdown renders.
5. Confirm structured decision card or equivalent final decision surface renders
   when the artifact exists.
6. Navigate back to the workbench without losing the report list.

Business assertions:

- the expected ticker/report appears in the library
- the report viewer shows the expected report identity
- final decision/rating/readiness content is visible when present
- missing optional artifacts degrade gracefully

Supporting setup:

- seed a minimal report directory in temp `DATA_DIR`
- optionally seed decision card JSON artifacts

## Journey 2: Launch Analysis To Completed Report

Actor: operator.

Goal: launch a new analysis and reach the generated report.

Browser path:

1. Open the analysis workspace.
2. Open the new analysis dialog.
3. Fill ticker, market/exchange if needed, analyst selection, model profile,
   output language, and visibility.
4. Submit the task.
5. Follow navigation to `/tasks/{taskId}`.
6. Observe queued/running/progress stages.
7. Wait for completion.
8. Click "View Report".
9. Confirm the generated report opens.

Business assertions:

- task can be created from the UI
- progress stages are understandable
- cancellation controls appear only for cancelable states
- completion links to a report the user can read

Supporting setup:

- use a deterministic test runner mode or fake LLM/vendor adapter
- keep the browser path identical to production
- avoid replacing the UI submission with `POST /api/tasks`

## Journey 3: Build Screener Candidates To Review Run

Actor: operator.

Goal: configure a screener, build candidates, and inspect ranked results.

Browser path:

1. Open `/screeners`.
2. Choose market, data source, ranking profile, filters, and top-k.
3. Launch the screener from the UI.
4. Follow navigation to `/screener-tasks/{taskId}`.
5. Observe progress stages.
6. Land on or open `/screeners?runId={runId}`.
7. Inspect candidate rows, ranking fields, and filter metadata.

Business assertions:

- selected filters are represented in the run/request summary
- candidate table renders expected symbols and scores
- empty/error states explain missing data
- completed task routes to the result view

Supporting setup:

- seed manifest/history/fundamental fixtures or use deterministic screener
  runner mode
- do not create the run only by writing `run_meta.json` unless the test is
  explicitly viewer-only

## Journey 4: Portfolio Asset Change To Summary

Actor: operator.

Goal: maintain holdings and see portfolio summary update.

Browser path:

1. Open `/assets`.
2. Create a position.
3. Confirm it appears in the holdings list.
4. Edit quantity, average cost, or currency.
5. Confirm summary metrics update.
6. Delete or close the test position.

Business assertions:

- form validation prevents invalid numeric data
- saved position appears with normalized values
- summary reflects the changed position
- owner/tenant scoping is respected when auth is enabled

Supporting setup:

- seed price/history fixtures or mock refresh behavior
- isolate `DATA_DIR`

## Journey 5: Trade Journal Record To Review Surface

Actor: operator.

Goal: capture a trade and review the journal record.

Browser path:

1. Open `/journal`.
2. Create a trade record.
3. Confirm it appears in trade history.
4. Edit or close the trade if the feature path is affected.
5. Open review/lessons surfaces when relevant.

Business assertions:

- trade record persists through UI
- ticker, side, dates, price, quantity, and notes display correctly
- validation prevents incomplete records
- generated review controls do not call live LLMs in default automation

Supporting setup:

- mock configured trade-review generation or use manual review fixtures

## Journey 6: Authenticated Admin Guardrail

Actor: admin, operator, or viewer.

Goal: prove permissions shape visible Workbench capabilities.

Browser path:

1. Open `/login`.
2. Sign in with a seeded account.
3. Navigate to the workbench and relevant admin page.
4. Confirm allowed actions are visible.
5. Confirm disallowed actions are hidden or blocked.
6. Log out and confirm protected pages redirect or show login state.

Business assertions:

- login works through browser
- role-specific navigation matches permissions
- admin-only mutations are unavailable to non-admin users
- session loss returns the user to a safe auth boundary

Supporting setup:

- use Postgres-backed auth for production-like tests
- keep credentials test-only and local to the fixture environment

## Journey 7: Data Sync And Queue Observability

Actor: admin/operator.

Goal: start background work and understand queue/progress state.

Browser path:

1. Open the relevant admin/data-source/activity page.
2. Launch sync or observe existing queued work.
3. Confirm queue status, running status, retry/waiting state, cancellation, and
   completion/failed state render correctly.

Business assertions:

- queued/running/waiting/canceled/failed states are visible and actionable
- cancel controls appear only when safe
- error text is concise and does not leak secrets
- activity page matches task detail state

Supporting setup:

- use fake vendor readiness clocks and deterministic task state for PR tests
- use real Redis only in nightly/release smoke

## Browser vs API Boundary

Use browser for:

- navigation
- forms
- submit actions
- task progress observation
- result review
- permission-visible UI
- CRUD flows

Use API/pytest for:

- fixture seeding and cleanup
- hidden permission matrix assertions
- tenant/owner leakage checks
- file/path traversal checks
- audit metadata privacy
- task-store and Redis state not visible in UI

If a test claims to cover a business workflow but never opens the browser, it is
an API integration test, not business E2E.
