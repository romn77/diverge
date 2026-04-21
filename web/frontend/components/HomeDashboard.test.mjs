import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import path from "node:path";
import test from "node:test";

const componentPath = path.join(import.meta.dirname, "HomeDashboard.tsx");

test("HomeDashboard is analysis-focused and keeps browse modules in page content", () => {
  const source = readFileSync(componentPath, "utf8");

  assert.match(source, /buildActivityHref/);
  assert.match(source, /Search reports/);
  assert.match(source, /Tracked Tickers/);
  assert.match(source, /Coverage Snapshot/);
  assert.match(source, /New Analysis/);
  assert.doesNotMatch(source, /Launch Screener/);
  assert.doesNotMatch(source, /Open Trade Journal/);
  assert.doesNotMatch(source, /buildScreenerRunHref/);
  assert.doesNotMatch(source, /QueueCard/);
});
