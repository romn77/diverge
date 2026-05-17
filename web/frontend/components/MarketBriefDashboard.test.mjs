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
  assert.match(source, /DropdownMenuTrigger/);
  assert.match(source, /DropdownMenuContent/);
  assert.match(source, /DropdownMenuItem/);
  assert.match(source, /handleRun\(\[market\.value\]\)/);
  assert.match(source, /MARKET_OPTIONS\.map\(\(market\) => market\.value\)/);
  assert.doesNotMatch(source, /selectedMarkets/);
  assert.doesNotMatch(source, /toggleMarket/);
  assert.doesNotMatch(source, /aria-pressed/);
  assert.match(source, /language === "zh" \? "zh-CN" : "en-US"/);
  assert.match(source, /marketBrief\.chooseMarket/);
  assert.match(source, /marketBrief\.market\.cn/);
  assert.match(source, /marketBrief\.market\.us/);
  assert.match(source, /marketBrief\.market\.all/);
  assert.match(source, /marketBrief\.error\.load/);
  assert.match(source, /marketBrief\.error\.run/);
  assert.match(source, /formatMarketBriefMarket/);
  assert.match(source, /buildReportHref/);
});

test("MarketBriefDashboard keeps task status activity out of the brief page", () => {
  assert.match(source, /className="workbench-content-frame space-y-5"/);
  assert.match(source, /workbench-page-shell/);
  assert.match(source, /isActiveTask/);
  assert.doesNotMatch(source, /marketBrief\.tasks/);
  assert.doesNotMatch(source, /marketBrief\.noTasks/);
  assert.doesNotMatch(source, /task\.status\.\$\{task\.status\}/);
});

test("MarketBriefDashboard uses tokenized workbench surfaces", () => {
  assert.match(source, /card-surface/);
  assert.match(source, /text-\[var\(--text\)\]/);
  assert.doesNotMatch(source, /bg-white|text-slate-|border-slate-|bg-amber/);
});
