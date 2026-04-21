import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import path from "node:path";
import test from "node:test";

const reportRoutePath = path.join(
  import.meta.dirname,
  "(workbench)",
  "reports",
  "[reportId]",
  "page.tsx"
);

test("report route renders the report viewer from the shared workbench data", () => {
  const source = readFileSync(reportRoutePath, "utf8");

  assert.match(source, /ReportViewer/);
  assert.match(source, /useWorkbench/);
  assert.match(source, /reports\.find\(\(report\) => report\.id === params\.reportId\)/);
  assert.match(source, /reportMeta=\{reportMeta\}/);
});
