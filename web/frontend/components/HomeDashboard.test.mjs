import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import path from "node:path";
import test from "node:test";

const componentPath = path.join(import.meta.dirname, "HomeDashboard.tsx");

test("HomeDashboard is analysis-focused and keeps browse modules in page content", () => {
  const source = readFileSync(componentPath, "utf8");

  assert.match(source, /from "@\/components\/ui\/badge"/);
  assert.match(source, /from "@\/components\/ui\/button"/);
  assert.match(source, /from "@\/components\/ui\/card"/);
  assert.match(source, /from "@\/components\/ui\/input"/);
  assert.match(source, /<Card/);
  assert.match(source, /<Input/);
  assert.match(source, /<Badge/);
  assert.match(source, /buildActivityHref/);
  assert.match(source, /Search reports/);
  assert.match(source, /Tracked Tickers/);
  assert.match(source, /Coverage Snapshot/);
  assert.match(source, /New Analysis/);
  assert.doesNotMatch(source, /Launch Screener/);
  assert.doesNotMatch(source, /Open Trade Journal/);
  assert.doesNotMatch(source, /buildScreenerRunHref/);
  assert.doesNotMatch(source, /QueueCard/);
});

test("HomeDashboard hero actions share a unified CTA base style across button and link elements", () => {
  const source = readFileSync(componentPath, "utf8");

  assert.match(source, /<Button/);
  assert.match(source, /asChild/);
  assert.match(source, /variant="secondary"/);
  assert.match(source, /Search reports/);
});
