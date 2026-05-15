import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import path from "node:path";
import test from "node:test";

const source = readFileSync(
  path.join(import.meta.dirname, "MarketBriefDashboard.tsx"),
  "utf8"
);

test("MarketBriefDashboard exposes manual A/US brief generation without changing home", () => {
  assert.match(source, /createMarketBriefTask/);
  assert.match(source, /listMarketBriefs/);
  assert.match(source, /listMarketBriefTasks/);
  assert.match(source, /"cn"/);
  assert.match(source, /"us"/);
  assert.match(source, /aria-pressed/);
  assert.match(source, /buildReportHref/);
});

test("MarketBriefDashboard uses tokenized workbench surfaces", () => {
  assert.match(source, /card-surface/);
  assert.match(source, /text-\[var\(--text\)\]/);
  assert.doesNotMatch(source, /bg-white|text-slate-|border-slate-|bg-amber/);
});
