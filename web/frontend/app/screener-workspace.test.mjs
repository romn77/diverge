import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import path from "node:path";
import test from "node:test";

const screenerRoutePath = path.join(
  import.meta.dirname,
  "(workbench)",
  "screeners",
  "page.tsx"
);
const legacyRunRoutePath = path.join(
  import.meta.dirname,
  "(workbench)",
  "screeners",
  "[runId]",
  "page.tsx"
);

test("screener workspace route renders the shared screener dashboard", () => {
  const source = readFileSync(screenerRoutePath, "utf8");

  assert.match(source, /ScreenerDashboard/);
});

test("legacy screener run route redirects back into the workspace", () => {
  const source = readFileSync(legacyRunRoutePath, "utf8");

  assert.match(source, /buildScreenerRunHref/);
  assert.match(source, /router\.replace\(buildScreenerRunHref\(params\.runId\)\)/);
  assert.doesNotMatch(source, /ScreenerResultsViewer/);
});
