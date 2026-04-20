import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import path from "node:path";
import test from "node:test";

const pagePath = path.join(import.meta.dirname, "(workbench)", "page.tsx");
const layoutPath = path.join(import.meta.dirname, "(workbench)", "layout.tsx");

test("home page delegates chrome and data loading to the shared workbench shell", () => {
  const source = readFileSync(pagePath, "utf8");
  const layoutSource = readFileSync(layoutPath, "utf8");

  assert.match(layoutSource, /WorkbenchShell/);
  assert.match(layoutSource, /WorkbenchProvider/);
  assert.match(source, /HomeDashboard/);
  assert.match(source, /searchParams/);
  assert.match(source, /initialSearchQuery/);
  assert.doesNotMatch(source, /\[selectedReportId,\s*setSelectedReportId\]/);
  assert.doesNotMatch(source, /\[activeTaskId,\s*setActiveTaskId\]/);
  assert.doesNotMatch(source, /\[showNewAnalysis,\s*setShowNewAnalysis\]/);
  assert.doesNotMatch(source, /listReports/);
  assert.doesNotMatch(source, /listTasks/);
});
