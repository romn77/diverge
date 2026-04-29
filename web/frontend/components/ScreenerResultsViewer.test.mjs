import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import path from "node:path";
import test from "node:test";

const componentPath = path.join(import.meta.dirname, "ScreenerResultsViewer.tsx");

test("ScreenerResultsViewer loads candidate rows and renders observable indicator columns", () => {
  const source = readFileSync(componentPath, "utf8");

  assert.match(source, /from "@\/components\/ui\/badge"/);
  assert.doesNotMatch(source, /from "@\/components\/ui\/button"/);
  assert.match(source, /from "@\/components\/ui\/card"/);
  assert.match(source, /from "@\/components\/ui\/table"/);
  assert.match(source, /<Card/);
  assert.match(source, /<Table/);
  assert.match(source, /<Badge/);
  assert.match(source, /getScreenerRun/);
  assert.match(source, /listScreenerRunCandidates/);
  assert.match(source, /getTickerHistoryBatch/);
  assert.match(source, /TickerSparkline/);
  assert.match(source, /embedded = false/);
  assert.match(source, /const RootTag = embedded \? "section" : "main"/);
  assert.match(source, /viewer-frame fade-in/);
  assert.doesNotMatch(source, /#[0-9A-Fa-f]{3,8}/);
  assert.match(source, /overflow-x-auto/);
  assert.match(source, /global_rank/);
  assert.match(source, /close/);
  assert.match(source, /ma20/);
  assert.match(source, /ma60/);
  assert.match(source, /ret_20/);
  assert.match(source, /ret_60/);
  assert.match(source, /rsi/);
  assert.match(source, /atr_pct/);
  assert.match(source, /avg_amount_20d/);
  assert.match(source, /breakout_volume_ratio/);
  assert.match(source, /breakout_type/);
  assert.match(source, /breakout_with_volume/);
  assert.match(source, /trendSparkline/);
  assert.match(source, /strategy_tags/);
  assert.match(source, /risk_flags/);
  assert.match(source, /pressed=\{sortKey === column\.key\}/);
  assert.match(source, /aria-pressed=\{pressed\}/);
});

test("ScreenerResultsViewer keeps ranking scores out of the candidate table", () => {
  const source = readFileSync(componentPath, "utf8");

  assert.doesNotMatch(source, /screenerResults\.header\.total_score/);
  assert.doesNotMatch(source, /screenerResults\.header\.technical_score/);
  assert.doesNotMatch(source, /screenerResults\.header\.pattern_score/);
  assert.doesNotMatch(source, /screenerResults\.header\.trend_score/);
  assert.doesNotMatch(source, /screenerResults\.header\.momentum_score/);
  assert.doesNotMatch(source, /screenerResults\.header\.risk_score/);
  assert.doesNotMatch(source, /screenerResults\.header\.liquidity_score/);
  assert.doesNotMatch(source, /screenerResults\.header\.breakout_bonus/);
});

test("ScreenerResultsViewer skips low-signal intro copy and summary cards", () => {
  const source = readFileSync(componentPath, "utf8");

  assert.doesNotMatch(source, /Compare the ranked pool/);
  assert.doesNotMatch(source, /screenerResults\.summary\.topPick/);
  assert.doesNotMatch(source, /screenerResults\.summary\.coverage/);
  assert.doesNotMatch(source, /screenerResults\.summary\.filtered/);
  assert.doesNotMatch(source, /screenerResults\.summary\.profile/);
  assert.doesNotMatch(source, /function SummaryCard/);
});

test("ScreenerResultsViewer includes breakout filter controls for results exploration", () => {
  const source = readFileSync(componentPath, "utf8");

  assert.match(source, /breakoutFilter/);
  assert.match(source, /function SelectionChip/);
  assert.match(source, /h-7/);
  assert.match(source, /px-3/);
  assert.doesNotMatch(source, /size="sm"/);
  assert.match(source, /Volume Confirmed/i);
  assert.match(source, /Platform Breakout/i);
  assert.match(source, /Box Breakout/i);
  assert.match(source, /Wedge Breakout/i);
});

test("ScreenerResultsViewer does not expose internal artifact paths in the report summary", () => {
  const source = readFileSync(componentPath, "utf8");

  assert.doesNotMatch(source, /screenerResults\.summary\.artifacts/);
  assert.doesNotMatch(source, /artifact_paths/);
});
