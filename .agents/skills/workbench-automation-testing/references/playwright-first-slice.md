# Playwright First Slice

Use this reference when implementing the first browser automation layer for the
Diverge Web Workbench.

## Goal

Add a small deterministic browser suite that drives real Workbench business
flows end to end. The browser must perform the user actions. Backend fixtures,
test doubles, or APIs may prepare state, but they must not replace the workflow
being tested.

## Recommended Files

```text
web/frontend/
  playwright.config.ts
  e2e/
    fixtures/
      data/
        reports/
        screener/runs/
        screener/tasks/
        manifest/
    pages/
      WorkbenchPage.ts
      ReportPage.ts
      ScreenerPage.ts
    specs/
      report-discovery-to-review.spec.ts
      launch-analysis-to-report.spec.ts
      build-screener-to-candidates.spec.ts
      workbench-navigation-smoke.spec.ts
    global-setup.ts
```

## NPM Scripts

Add scripts similar to:

```json
{
  "test:e2e": "playwright test",
  "test:e2e:headed": "playwright test --headed",
  "test:e2e:debug": "playwright test --debug"
}
```

## Runtime Shape

Use two local services:

- backend: `AUTH_ENABLED=false`, `TASK_BACKEND=local`, temp `DATA_DIR`
- frontend: Next.js dev server with `API_PROXY_TARGET=http://127.0.0.1:<backend>`

Prefer `API_PROXY_TARGET` so Playwright stays on the frontend origin while the
app reaches backend APIs through rewrites. The spec should still click and type
through the UI.

## First Business Specs

1. **Workbench navigation smoke**
   - visit `/`
   - expect the analysis workspace shell
   - navigate to screeners, activity, assets, and journal through visible nav
   - expect each page's business shell to render

2. **Report discovery to review**
   - fixture includes one report directory
   - open the report from the dashboard list, not by direct URL unless this is a
     detail-page-only regression
   - expect report title/markdown and decision/review surface

3. **Launch analysis to report**
   - open the new analysis dialog
   - fill the form in the browser
   - submit and follow the task page
   - wait for deterministic completion
   - click "View Report"
   - expect the generated report

4. **Build screener to candidates**
   - configure a screener in the browser
   - launch it from `/screeners`
   - follow the screener task page
   - open the completed run
   - expect candidate rows and run metadata

## Selectors

Prefer accessible selectors:

- `getByRole("heading", { name: /.../ })`
- `getByLabel(...)`
- `getByRole("button", { name: /.../ })`

Add narrow `data-testid` when:

- the control is icon-only or dense
- copy is translated or likely to change
- multiple controls share the same visible name
- the test otherwise needs brittle CSS selectors

Good stable IDs:

- `workbench-root`
- `report-list-item`
- `report-viewer`
- `task-status`
- `task-view-report`
- `screener-run-viewer`
- `screener-candidate-row`
- `login-account`
- `login-password`
- `login-submit`

## Fixture Rules

- Copy fixture data into a temp directory during setup.
- Set `DATA_DIR` to the temp copy.
- Do not mutate checked-in fixture files during tests.
- Keep fixture reports and CSVs tiny.
- Avoid timestamps that make assertions timezone-sensitive.
- For business-flow specs, seed only preconditions. The tested action itself
  should happen through the browser.
- If the real workflow needs LLM/vendor calls, add a deterministic test adapter
  or runner mode that preserves the same UI path.

## Playwright Config Guidance

Recommended defaults:

- Chromium only for PR smoke.
- `trace: "on-first-retry"`.
- `screenshot: "only-on-failure"`.
- `video: "retain-on-failure"` only if CI artifact size is acceptable.
- retries in CI, no retries locally.
- one worker in CI until fixture isolation is proven.

## Anti-Flake Rules

- Do not use arbitrary `waitForTimeout`.
- Wait for headings, status text, route changes, or specific API responses.
- Avoid assertions on animation timing.
- Keep all tests independent.
- Prefer direct route setup only for detail-page regressions. For business
  journeys, enter through the same route a user would use.
