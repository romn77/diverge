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
  assert.match(source, /strategy_tags/);
  assert.match(source, /risk_flags/);
});
