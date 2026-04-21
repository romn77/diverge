import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import path from "node:path";
import test from "node:test";

const componentPath = path.join(import.meta.dirname, "ScreenerResultsViewer.tsx");

test("ScreenerResultsViewer loads candidate rows and renders sortable score columns", () => {
  const source = readFileSync(componentPath, "utf8");

  assert.match(source, /getScreenerRun/);
  assert.match(source, /listScreenerRunCandidates/);
  assert.match(source, /global_rank/);
  assert.match(source, /total_score/);
  assert.match(source, /trend_score/);
  assert.match(source, /momentum_score/);
  assert.match(source, /risk_score/);
  assert.match(source, /liquidity_score/);
  assert.match(source, /breakout_type/);
  assert.match(source, /breakout_with_volume/);
  assert.match(source, /breakout_bonus/);
  assert.match(source, /strategy_tags/);
  assert.match(source, /risk_flags/);
  assert.match(source, /aria-pressed=\{sortKey === column\.key\}/);
  assert.match(source, /sortKey === column\.key\s*\?/);
  assert.match(source, /bg-\[var\(--primary\)\]/);
});

test("ScreenerResultsViewer includes breakout filter controls for results exploration", () => {
  const source = readFileSync(componentPath, "utf8");

  assert.match(source, /breakoutFilter/);
  assert.match(source, /Volume Confirmed/i);
  assert.match(source, /Platform Breakout/i);
  assert.match(source, /Box Breakout/i);
  assert.match(source, /Wedge Breakout/i);
});
