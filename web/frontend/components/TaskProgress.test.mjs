import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import path from "node:path";
import test from "node:test";

const taskProgressPath = path.join(import.meta.dirname, "TaskProgress.tsx");

test("TaskProgress subscribes to backend task snapshots and renders the five-stage pipeline", () => {
  const source = readFileSync(taskProgressPath, "utf8");

  assert.match(source, /subscribeToTask/);
  assert.match(source, /getTask/);
  assert.match(source, /not_started/);
  assert.match(source, /processing/);
  assert.match(source, /completed/);
  assert.match(source, /Analysts/);
  assert.match(source, /Research/);
  assert.match(source, /Trading/);
  assert.match(source, /Risk/);
  assert.match(source, /Portfolio/);
  assert.match(source, /View Report/);
  assert.match(source, /Request details for/);
  assert.match(source, /Task Request Snapshot/);
  assert.match(source, /analysis_date/);
  assert.match(source, /quick_think_llm/);
  assert.match(source, /deep_think_llm/);
  assert.match(source, /readOnly/);
  assert.match(source, /scale-y-\[-1\]/);
  assert.equal(source.includes("max-w-5xl"), false);
  assert.match(source, /w-full space-y-6/);
});
