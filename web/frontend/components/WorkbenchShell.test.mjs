import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import path from "node:path";
import test from "node:test";

const shellPath = path.join(import.meta.dirname, "WorkbenchShell.tsx");

test("WorkbenchShell renders a global top utility bar before the sidebar/content split", () => {
  const source = readFileSync(shellPath, "utf8");

  assert.match(source, /<WorkspaceAccountMenu/);
  assert.match(source, /className="flex min-h-screen md:items-stretch"/);
  assert.match(source, /<Sidebar/);
  assert.match(source, /<div className="flex min-w-0 flex-1 flex-col">/);
  assert.match(source, /onOpenSidebar=\{\(\) => setIsSidebarOpen\(true\)\}/);

  const headerIndex = source.indexOf("<WorkspaceAccountMenu");
  const sidebarIndex = source.indexOf("<Sidebar");
  assert.notEqual(headerIndex, -1);
  assert.notEqual(sidebarIndex, -1);
  assert.ok(headerIndex < sidebarIndex, "top utility bar should render before sidebar");
});
