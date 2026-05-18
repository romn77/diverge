import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import path from "node:path";
import test from "node:test";

const source = readFileSync(
  path.join(import.meta.dirname, "MarketBriefDashboard.tsx"),
  "utf8"
);

test("MarketBriefDashboard lists external multica markdown briefs without generation controls", () => {
  assert.match(source, /listMarketBriefs/);
  assert.match(source, /multica markdown/);
  assert.match(source, /No market brief markdown files found/);
  assert.doesNotMatch(source, /createMarketBriefTask/);
  assert.doesNotMatch(source, /listMarketBriefTasks/);
  assert.doesNotMatch(source, /DropdownMenuTrigger/);
  assert.doesNotMatch(source, /DropdownMenuContent/);
  assert.doesNotMatch(source, /handleRun/);
  assert.doesNotMatch(source, /selectedMarkets/);
  assert.doesNotMatch(source, /toggleMarket/);
  assert.doesNotMatch(source, /aria-pressed/);
  assert.doesNotMatch(source, /language === "zh" \? "zh-CN" : "en-US"/);
  assert.doesNotMatch(source, /output_language:/);
  assert.match(source, /marketBrief\.error\.load/);
  assert.match(source, /formatMarketBriefMarket/);
  assert.match(source, /buildReportHref/);
});

test("MarketBriefDashboard keeps task status activity out of the brief page", () => {
  assert.match(source, /className="workbench-content-frame space-y-5"/);
  assert.match(source, /workbench-page-shell/);
  assert.doesNotMatch(source, /isActiveTask/);
  assert.doesNotMatch(source, /marketBrief\.tasks/);
  assert.doesNotMatch(source, /marketBrief\.noTasks/);
  assert.doesNotMatch(source, /task\.status\.\$\{task\.status\}/);
});

test("MarketBriefDashboard uses tokenized workbench surfaces", () => {
  assert.match(source, /card-surface/);
  assert.match(source, /text-\[var\(--text\)\]/);
  assert.doesNotMatch(source, /bg-white|text-slate-|border-slate-|bg-amber/);
});
