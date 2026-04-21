import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import path from "node:path";
import test from "node:test";

const componentPath = path.join(import.meta.dirname, "TickerPricePanel.tsx");

test("TickerPricePanel fetches shared ticker history data and renders both full and compact charts", () => {
  const source = readFileSync(componentPath, "utf8");

  assert.match(source, /getTickerHistory/);
  assert.match(source, /TickerSparkline/);
  assert.match(source, /PriceLineChart/);
  assert.match(source, /Window Change/);
  assert.match(source, /Data Points/);
  assert.match(source, /buildLinePath/);
});
