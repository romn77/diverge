import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import path from "node:path";
import test from "node:test";

const shellPath = path.join(import.meta.dirname, "WorkbenchShell.tsx");

test("WorkbenchShell renders the page title and utility bar together in the top toolbar", () => {
  const source = readFileSync(shellPath, "utf8");

  assert.match(source, /<WorkspaceAccountMenu/);
  assert.match(source, /usePreferences/);
  assert.match(source, /t\("workbench\.preparingTitle", "Preparing the workbench"\)/);
  assert.match(source, /t\("workbench\.loginRequiredTitle", "Redirecting to sign in"\)/);
  assert.match(source, /app-shell relative min-h-dvh overflow-x-hidden bg-transparent/);
  assert.doesNotMatch(source, /app-shell relative min-h-screen overflow-x-hidden bg-\[var\(--bg\)\]/);
  assert.match(source, /className="min-h-dvh min-w-0 flex-1 overflow-x-hidden"/);
  assert.match(source, /className="flex min-h-dvh min-w-0 max-w-full md:items-stretch"/);
  assert.match(source, /<Sidebar/);
  assert.match(source, /<div className="flex min-w-0 max-w-full flex-1 flex-col overflow-x-hidden">/);
  assert.match(source, /<header className="workbench-topbar">/);
  assert.match(source, /workbench-topbar-title/);
  assert.match(source, /workbench-topbar-menu md:hidden/);
  assert.doesNotMatch(source, /workbench-topbar-search/);
  assert.match(source, /workbench-topbar-actions/);
  assert.match(source, /setTopbarActions/);
  assert.doesNotMatch(source, /buildHomeHref\(nextQuery\)/);
  assert.match(source, /t\("home\.launchAnalysis", "New Analysis"\)/);
  assert.doesNotMatch(source, /workbench-topbar-eyebrow/);

  const headerIndex = source.indexOf("<WorkspaceAccountMenu");
  const topbarIndex = source.indexOf('<header className="workbench-topbar">');
  const sidebarIndex = source.indexOf("<Sidebar");
  const contentColumnIndex = source.indexOf(
    '<div className="flex min-w-0 max-w-full flex-1 flex-col overflow-x-hidden">'
  );
  assert.notEqual(headerIndex, -1);
  assert.notEqual(topbarIndex, -1);
  assert.notEqual(sidebarIndex, -1);
  assert.notEqual(contentColumnIndex, -1);
  assert.ok(sidebarIndex < contentColumnIndex, "sidebar should render before the main content column");
  assert.ok(contentColumnIndex < topbarIndex, "toolbar should render inside the main content column");
  assert.ok(topbarIndex < headerIndex, "utility bar should render inside the toolbar");
});

test("WorkbenchShell navigates screener dialog submissions before refreshing lists", () => {
  const source = readFileSync(shellPath, "utf8");
  const screenerDialogSource = source.slice(
    source.indexOf("<NewScreenerForm"),
    source.indexOf("</WorkbenchChromeContext.Provider>")
  );
  const pushIndex = screenerDialogSource.indexOf("router.push(buildScreenerTaskHref(taskId))");
  const refreshTasksIndex = screenerDialogSource.indexOf("void refreshScreenerTasks()");
  const refreshRunsIndex = screenerDialogSource.indexOf("void refreshScreenerRuns()");

  assert.ok(pushIndex > -1, "expected screener dialog to push the task route");
  assert.ok(refreshTasksIndex > -1, "expected screener dialog to refresh tasks");
  assert.ok(refreshRunsIndex > -1, "expected screener dialog to refresh runs");
  assert.ok(pushIndex < refreshTasksIndex, "task route push should happen before task refresh");
  assert.ok(pushIndex < refreshRunsIndex, "task route push should happen before run refresh");
});
