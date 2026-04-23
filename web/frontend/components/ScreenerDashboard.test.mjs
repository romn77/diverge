import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import path from "node:path";
import test from "node:test";

const componentPath = path.join(import.meta.dirname, "ScreenerDashboard.tsx");

test("ScreenerDashboard provides a stable screener workspace destination", () => {
  const source = readFileSync(componentPath, "utf8");

  assert.match(source, /from "@\/components\/ui\/badge"/);
  assert.match(source, /from "@\/components\/ui\/button"/);
  assert.match(source, /from "@\/components\/ui\/card"/);
  assert.match(source, /<Card/);
  assert.match(source, /<Button/);
  assert.match(source, /<Badge/);
  assert.match(source, /openScreenerDialog/);
  assert.match(source, /buildActivityHref/);
  assert.match(source, /buildScreenerRunHref/);
  assert.match(source, /snapshot_available/);
  assert.match(source, /Recent Runs/);
  assert.match(source, /Metadata only/);
  assert.match(source, /Market Coverage/);
  assert.match(source, /Queue Snapshot/);
});
