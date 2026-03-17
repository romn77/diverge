import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import path from "node:path";
import test from "node:test";

const reportViewerPath = path.join(import.meta.dirname, "ReportViewer.tsx");

test("ReportViewer uses sticky headers with pressed-state navigation buttons", () => {
  const source = readFileSync(reportViewerPath, "utf8");

  assert.match(source, /sticky top-0/);
  assert.match(source, /overflow-x-auto/);
  assert.match(source, /aria-pressed=\{selectedTab === "complete"\}/);
  assert.equal(source.includes("top-[5.75rem]"), false);
  assert.equal(source.includes("top-[6.5rem]"), false);
  assert.equal(source.includes('role="tablist"'), false);
  assert.equal(source.includes('role="tab"'), false);
});

test("ReportViewer lets the reading surface use the full content column", () => {
  const source = readFileSync(reportViewerPath, "utf8");

  assert.equal(source.includes("max-w-[1080px]"), false);
  assert.equal(source.includes("max-w-[76rem]"), false);
  assert.equal(source.includes("max-w-[1260px]"), false);
  assert.equal(source.includes("reader-frame"), false);
  assert.equal(source.includes("p-3 md:h-screen md:overflow-hidden md:p-4 lg:p-5"), false);
});
