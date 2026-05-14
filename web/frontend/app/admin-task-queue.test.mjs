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

test("admin task queue page renders an operations dashboard", () => {
  assert.equal(existsSync(adminTaskQueuePagePath), true);
  const source = readFileSync(adminTaskQueuePagePath, "utf8");

  assert.match(source, /listAdminTaskQueue/);
  assert.match(source, /getDataSyncJob/);
  assert.match(source, /createOhlcvSyncTask/);
  assert.match(source, /deleteAdminTaskQueueItem/);
  assert.match(source, /from "@\/components\/ui\/confirm-dialog"/);
  assert.match(source, /handleCreateOhlcvSync/);
  assert.match(source, /handleRemoveStaleQueueItem/);
  assert.match(source, /handleConfirmQueueAction/);
  assert.match(source, /refreshSelectedDataSyncJob/);
  assert.match(source, /handleRefreshAll/);
  assert.match(source, /setInterval/);
  assert.match(source, /clearInterval/);
  assert.match(source, /Task Queue/);
  assert.match(source, /Data Sync Details/);
  assert.match(source, /Start OHLCV sync/);
  assert.match(source, /Manual data sync/);
  assert.match(source, /Running/);
  assert.match(source, /Queued/);
  assert.match(source, /Waiting for quota/);
  assert.match(source, /latest_progress/);
  assert.match(source, /progress_events/);
  assert.match(source, /result/);
  assert.match(source, /error/);
  assert.match(source, /blocked_vendor/);
  assert.match(source, /queue_position/);
  assert.match(source, /task\.stale/);
  assert.match(source, /Remove this stale queue record/);
  assert.match(source, /<ConfirmDialog/);
  assert.match(source, /AdminConsolePage/);
  assert.match(source, /activeTab="task-queue"/);
  assert.match(source, /router\.replace\("\/login\?next=\/admin\/task-queue"\)/);
  assert.doesNotMatch(source, /cancelTask/);
  assert.doesNotMatch(source, /window\.confirm/);
  assert.doesNotMatch(source, /\bconfirm\(/);
});
