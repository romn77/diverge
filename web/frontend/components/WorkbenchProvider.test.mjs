import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import path from "node:path";
import test from "node:test";

const componentPath = path.join(import.meta.dirname, "WorkbenchProvider.tsx");

test("WorkbenchProvider deduplicates screener runs before storing workspace state", () => {
  const source = readFileSync(componentPath, "utf8");

  assert.match(source, /function dedupeScreenerRuns/);
  assert.match(source, /setScreenerRuns\(dedupeScreenerRuns\(await listScreenerRuns\(\)\)\)/);
});

test("WorkbenchProvider only polls task queues while active tasks exist", () => {
  const source = readFileSync(componentPath, "utf8");

  assert.match(source, /function hasActiveTaskStatus/);
  assert.match(source, /const hasActiveTasks = useMemo\(\(\) => tasks\.some\(hasActiveTaskStatus\), \[tasks\]\)/);
  assert.match(source, /const hasActiveScreenerTasks = useMemo/);
  assert.match(source, /const hasActiveOpportunityTasks = useMemo/);
  assert.match(source, /const hasActiveJournalReviewTasks = useMemo/);
  assert.match(source, /if \(!hasActiveTasks\) \{\s*return;\s*\}\s*const intervalId = window\.setInterval\(\(\) => \{\s*void refreshTasks\(\);/s);
  assert.match(source, /if \(!hasActiveScreenerTasks\) \{\s*return;\s*\}\s*const intervalId = window\.setInterval\(\(\) => \{\s*void refreshScreenerTasks\(\);/s);
  assert.match(source, /if \(!hasActiveOpportunityTasks\) \{\s*return;\s*\}\s*const intervalId = window\.setInterval\(\(\) => \{\s*void refreshOpportunityTasks\(\);/s);
  assert.match(source, /if \(!hasActiveJournalReviewTasks\) \{\s*return;\s*\}\s*const intervalId = window\.setInterval\(\(\) => \{\s*void refreshJournalReviewTasks\(\);/s);
});

test("WorkbenchProvider gates the standalone assets workspace behind a product flag", () => {
  const source = readFileSync(componentPath, "utf8");

  assert.match(source, /ASSETS_WORKSPACE_ENABLED/);
  assert.match(source, /const canReadAssets = hasPermission\(authState, "assets:read"\)/);
  assert.match(source, /canAccessAssetsWorkspace =\s*ASSETS_WORKSPACE_ENABLED && canAccessWorkbench && canReadAssets/s);
});
