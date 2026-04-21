import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import path from "node:path";
import test from "node:test";

const componentPath = path.join(import.meta.dirname, "ActivityDashboard.tsx");

test("ActivityDashboard centralizes in-flight analysis and screener monitoring", () => {
  const source = readFileSync(componentPath, "utf8");

  assert.match(source, /buildTaskHref/);
  assert.match(source, /buildScreenerTaskHref/);
  assert.match(source, /Background work/);
  assert.match(source, /Analysis tasks/);
  assert.match(source, /Screener tasks/);
  assert.match(source, /Combined background jobs/);
});
