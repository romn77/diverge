import assert from "node:assert/strict";
import { existsSync, readFileSync } from "node:fs";
import path from "node:path";
import test from "node:test";

const adminTaskQueuePagePath = path.join(
  import.meta.dirname,
  "admin",
  "task-queue",
  "page.tsx"
);

test("admin task queue page renders a read-only operations dashboard", () => {
  assert.equal(existsSync(adminTaskQueuePagePath), true);
  const source = readFileSync(adminTaskQueuePagePath, "utf8");

  assert.match(source, /listAdminTaskQueue/);
  assert.match(source, /getDataSyncJob/);
  assert.match(source, /refreshSelectedDataSyncJob/);
  assert.match(source, /handleRefreshAll/);
  assert.match(source, /setInterval/);
  assert.match(source, /clearInterval/);
  assert.match(source, /Task Queue/);
  assert.match(source, /Data Sync Details/);
  assert.match(source, /Read-only/);
  assert.match(source, /Running/);
  assert.match(source, /Queued/);
  assert.match(source, /Waiting for quota/);
  assert.match(source, /latest_progress/);
  assert.match(source, /progress_events/);
  assert.match(source, /result/);
  assert.match(source, /error/);
  assert.match(source, /blocked_vendor/);
  assert.match(source, /queue_position/);
  assert.match(source, /href="\/admin\/users"/);
  assert.match(source, /href="\/admin\/data-sources"/);
  assert.match(source, /router\.replace\("\/login\?next=\/admin\/task-queue"\)/);
  assert.doesNotMatch(source, /cancelTask/);
  assert.doesNotMatch(source, /deleteTask/);
});
