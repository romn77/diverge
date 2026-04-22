import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import path from "node:path";
import test from "node:test";

const componentPath = path.join(import.meta.dirname, "TickerPricePanel.tsx");

test("TickerPricePanel renders a trading-focused chart surface with range and extreme metrics", () => {
  const source = readFileSync(componentPath, "utf8");

  assert.match(source, /getTickerHistory/);
  assert.match(source, /TickerSparkline/);
  assert.match(source, /PriceLineChart/);
  assert.match(source, /Window High/);
  assert.match(source, /Window Low/);
  assert.match(source, /Window Change/);
  assert.match(source, /buildLinePath/);
  assert.match(source, /buildYAxisTicks/);
  assert.match(source, /buildMonthTicks/);
  assert.match(source, /ChartShell/);
  assert.match(source, /TradingMetricStrip/);
  assert.match(source, /text-\[12px\]/);
  assert.match(source, /fontSize="16"/);
  assert.match(source, /h-\[20rem\] w-full md:h-\[22rem\]/);
  assert.match(source, /text-\[9px\]/);
  assert.match(source, /h-7 w-7/);
  assert.match(source, /text-\[0\.95rem\]/);
  assert.match(source, /md:text-\[1\.05rem\]/);
  assert.match(source, /formatMetricDateCompact/);
  assert.match(source, /whitespace-nowrap/);
});

test("TickerPricePanel no longer exposes compact-only visibility toggles", () => {
  const source = readFileSync(componentPath, "utf8");

  assert.match(source, /embedded\?: boolean/);
  assert.doesNotMatch(source, /showSymbolHeading/);
  assert.doesNotMatch(source, /visibleMetrics/);
});
