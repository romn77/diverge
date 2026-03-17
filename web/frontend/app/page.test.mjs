import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import path from "node:path";
import test from "node:test";

const pagePath = path.join(import.meta.dirname, "page.tsx");

test("page lifts report state and renders a content-first start panel", () => {
  const source = readFileSync(pagePath, "utf8");

  assert.match(source, /listReports/);
  assert.match(source, /\[reports,\s*setReports\]/);
  assert.match(source, /\[searchQuery,\s*setSearchQuery\]/);
  assert.match(source, /\[isSidebarOpen,\s*setIsSidebarOpen\]/);
  assert.match(source, /Recent reports/i);
  assert.match(source, /reports=\{reports\}/);
  assert.match(source, /isOpen=\{isSidebarOpen\}/);
  assert.match(source, /onClose=\{\(\) => setIsSidebarOpen\(false\)\}/);
});

test("page uses a desktop row layout so sidebar and content stay aligned", () => {
  const source = readFileSync(pagePath, "utf8");

  assert.match(source, /app-shell relative min-h-screen bg-\[var\(--bg\)\] md:flex md:items-stretch/);
});
