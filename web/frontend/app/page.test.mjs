import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import path from "node:path";
import test from "node:test";

const pagePath = path.join(import.meta.dirname, "page.tsx");

test("page lifts report state and renders a content-first start panel", () => {
  const source = readFileSync(pagePath, "utf8");

  assert.match(source, /listReports/);
  assert.match(source, /listTasks/);
  assert.match(source, /\[reports,\s*setReports\]/);
  assert.match(source, /\[tasks,\s*setTasks\]/);
  assert.match(source, /\[queueLocked,\s*setQueueLocked\]/);
  assert.match(source, /\[searchQuery,\s*setSearchQuery\]/);
  assert.match(source, /\[isSidebarOpen,\s*setIsSidebarOpen\]/);
  assert.match(source, /\[activeTaskId,\s*setActiveTaskId\]/);
  assert.match(source, /\[showNewAnalysis,\s*setShowNewAnalysis\]/);
  assert.match(source, /Recent reports/i);
  assert.match(source, /reports=\{reports\}/);
  assert.match(source, /isOpen=\{isSidebarOpen\}/);
  assert.match(source, /onClose=\{\(\) => setIsSidebarOpen\(false\)\}/);
  assert.match(source, /taskQueue=\{visibleTaskQueue\}/);
  assert.match(source, /newAnalysisDisabled=\{newAnalysisDisabled\}/);
  assert.doesNotMatch(source, /canReturnToQueue=\{/);
  assert.doesNotMatch(source, /onReturnToQueue=\{\(\) => \{/);
  assert.match(source, /<NewAnalysisForm/);
  assert.match(source, /<TaskProgress/);
});

test("page uses a desktop row layout so sidebar and content stay aligned", () => {
  const source = readFileSync(pagePath, "utf8");

  assert.match(source, /app-shell relative min-h-screen bg-\[var\(--bg\)\] md:flex md:items-stretch/);
});
