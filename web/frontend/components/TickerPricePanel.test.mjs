import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import path from "node:path";
import test from "node:test";

const componentPath = path.join(import.meta.dirname, "TickerPricePanel.tsx");

test("TickerPricePanel renders a trading-focused chart surface with range and extreme metrics", () => {
  const source = readFileSync(componentPath, "utf8");

  assert.match(source, /getTickerHistory/);
  assert.match(source, /TickerSparkline/);
  assert.match(source, /TickerFinancialChart/);
  assert.match(source, /PRICE_PANEL_LOOKBACK_DAYS = 1000/);
  assert.match(source, /SPARKLINE_LOOKBACK_POINTS = 30/);
  assert.match(source, /days: PRICE_PANEL_LOOKBACK_DAYS/);
  assert.match(source, /slice\(-SPARKLINE_LOOKBACK_POINTS\)/);
  assert.match(source, /buildSparklineDomain/);
  assert.match(source, /buildSparklineMarkers/);
  assert.match(source, /findCloseExtremeIndex/);
  assert.match(source, /toSparklineMarker/);
  assert.match(source, /r="2\.8"/);
  assert.match(source, /kind: "high" \| "low"/);
  assert.match(source, /tickerHistory\.windowHigh", "High"/);
  assert.match(source, /tickerHistory\.windowLow", "Low"/);
  assert.doesNotMatch(source, /Window Change/);
  assert.match(source, /buildLinePath/);
  assert.match(source, /ChartShell/);
  assert.match(source, /TickerRangeSummaryBar/);
  assert.match(source, /TickerRangeSummaryItem/);
  assert.match(source, /filterPointsForRange/);
  assert.match(source, /CHART_RANGE_DAYS/);
  assert.match(source, /\[chartRange,\s*setChartRange\]/);
  assert.match(source, /range=\{chartRange\}/);
  assert.match(source, /onRangeChange=\{setChartRange\}/);
  assert.match(source, /text-\[12px\]/);
  assert.match(source, /text-\[10px\]/);
  assert.match(source, /flex-\[1_1_14rem\]/);
  assert.match(source, /formatMetricDateCompact/);
  assert.doesNotMatch(source, /TradingMetricTile/);
  assert.doesNotMatch(source, /TradingMetricStrip/);
});

test("TickerPricePanel no longer exposes compact-only visibility toggles", () => {
  const source = readFileSync(componentPath, "utf8");

  assert.match(source, /embedded\?: boolean/);
  assert.doesNotMatch(source, /showSymbolHeading/);
  assert.doesNotMatch(source, /visibleMetrics/);
});
