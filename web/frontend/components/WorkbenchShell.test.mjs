import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import path from "node:path";
import test from "node:test";

const shellPath = path.join(import.meta.dirname, "WorkbenchShell.tsx");

test("WorkbenchShell renders the utility bar inside the main content column next to the sidebar layout", () => {
  const source = readFileSync(shellPath, "utf8");

  assert.match(source, /<WorkspaceAccountMenu/);
  assert.match(source, /usePreferences/);
  assert.match(source, /t\("workbench\.preparingTitle", "Preparing the workbench"\)/);
  assert.match(source, /t\("workbench\.loginRequiredTitle", "Redirecting to sign in"\)/);
  assert.match(source, /app-shell relative min-h-screen overflow-x-hidden/);
  assert.match(source, /className="min-h-screen min-w-0 flex-1 overflow-x-hidden"/);
  assert.match(source, /className="flex min-h-screen min-w-0 max-w-full md:items-stretch"/);
  assert.match(source, /<Sidebar/);
  assert.match(source, /<div className="flex min-w-0 max-w-full flex-1 flex-col overflow-x-hidden">/);
  assert.match(source, /onOpenSidebar=\{\(\) => setIsSidebarOpen\(true\)\}/);

  const headerIndex = source.indexOf("<WorkspaceAccountMenu");
  const sidebarIndex = source.indexOf("<Sidebar");
  const contentColumnIndex = source.indexOf(
    '<div className="flex min-w-0 max-w-full flex-1 flex-col overflow-x-hidden">'
  );
  assert.notEqual(headerIndex, -1);
  assert.notEqual(sidebarIndex, -1);
  assert.notEqual(contentColumnIndex, -1);
  assert.ok(sidebarIndex < contentColumnIndex, "sidebar should render before the main content column");
  assert.ok(contentColumnIndex < headerIndex, "utility bar should render inside the main content column");
});
