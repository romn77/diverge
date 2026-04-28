import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import path from "node:path";
import test from "node:test";

const routesPath = path.join(import.meta.dirname, "workbenchRoutes.ts");

test("workbench route helpers cover the route-driven destinations", () => {
  const source = readFileSync(routesPath, "utf8");

  assert.match(source, /export function buildHomeHref/);
  assert.match(source, /new URLSearchParams\(\{ q: normalizedQuery \}\)/);
  assert.match(source, /export function buildJournalHref/);
  assert.match(source, /return "\/journal";/);
  assert.match(source, /export function buildAssetsHref/);
  assert.match(source, /return "\/assets";/);
  assert.match(source, /export function buildActivityHref/);
  assert.match(source, /return "\/activity";/);
  assert.match(source, /export function buildLoginHref/);
  assert.match(source, /resolveNextPath/);
  assert.match(source, /next: resolveNextPath\(nextPath\)/);
  assert.match(source, /return `\/reports\/\$\{encodeURIComponent\(reportId\)\}`;/);
  assert.match(source, /return `\/tasks\/\$\{encodeURIComponent\(taskId\)\}`;/);
  assert.match(source, /export function buildScreenerHref/);
  assert.match(source, /return "\/screeners";/);
  assert.match(source, /new URLSearchParams\(\{ runId \}\)/);
  assert.match(source, /return `\/screeners\?\$\{searchParams\.toString\(\)\}`;/);
  assert.match(source, /return buildScreenerHref\(runId\);/);
  assert.match(source, /return `\/screener-tasks\/\$\{encodeURIComponent\(taskId\)\}`;/);
});
