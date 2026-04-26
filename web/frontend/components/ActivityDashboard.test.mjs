import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import path from "node:path";
import test from "node:test";

const componentPath = path.join(import.meta.dirname, "ActivityDashboard.tsx");

test("ActivityDashboard centralizes in-flight analysis and screener monitoring", () => {
  const source = readFileSync(componentPath, "utf8");

  assert.match(source, /from "@\/components\/ui\/badge"/);
  assert.match(source, /from "@\/components\/ui\/button"/);
  assert.match(source, /from "@\/components\/ui\/card"/);
  assert.match(source, /usePreferences/);
  assert.match(source, /<Card/);
  assert.match(source, /<Badge/);
  assert.match(source, /buildTaskHref/);
  assert.match(source, /buildScreenerTaskHref/);
  assert.match(source, /t\("activity\.title", "Background work"\)/);
  assert.match(source, /t\("activity\.analysisTasks", "Analysis tasks"\)/);
  assert.match(source, /t\("activity\.screenerTasks", "Screener tasks"\)/);
  assert.match(source, /t\("activity\.metric\.totalMeta", "Combined background jobs"\)/);
});

test("ActivityDashboard lets failed task records be deleted from the task rows", () => {
  const source = readFileSync(componentPath, "utf8");

  assert.match(source, /Trash2/);
  assert.match(source, /deleteTask/);
  assert.match(source, /deleteScreenerTask/);
  assert.match(source, /failedTasks/);
  assert.match(source, /failedScreenerTasks/);
  assert.match(source, /onDelete/);
  assert.match(source, /stopPropagation/);
  assert.match(source, /activity\.deleteFailedTask/);
});

test("ActivityDashboard shows queued quota-aware work and exposes cancel actions", () => {
  const source = readFileSync(componentPath, "utf8");

  assert.match(source, /XCircle/);
  assert.match(source, /cancelTask/);
  assert.match(source, /cancelScreenerTask/);
  assert.match(source, /waiting_for_quota/);
  assert.match(source, /queue_position/);
  assert.match(source, /activity\.waitingForQuota/);
  assert.match(source, /activity\.cancelTask/);
  assert.match(source, /onCancel/);
});
