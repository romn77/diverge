import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import path from "node:path";
import test from "node:test";

const componentPath = path.join(import.meta.dirname, "TickerFinancialChart.tsx");
const globalsCssPath = path.join(import.meta.dirname, "..", "app", "globals.css");

test("TickerFinancialChart range buttons use the shared selected-control highlight", () => {
  const componentSource = readFileSync(componentPath, "utf8");
  const globalsSource = readFileSync(globalsCssPath, "utf8");

  assert.match(componentSource, /aria-pressed=\{option === range\}/);
  assert.match(componentSource, /data-active=\{option === range\}/);
  assert.match(componentSource, /className="ticker-financial-chart__range-button"/);
  assert.doesNotMatch(componentSource, /is-active/);
  assert.match(
    globalsSource,
    /\.ticker-financial-chart__ranges button\[data-active="true"\]\s*\{[\s\S]*?background:\s*var\(--surface\);/
  );
  assert.match(globalsSource, /\.ticker-financial-chart__ranges button\[data-active="true"\]::after/);
  assert.doesNotMatch(
    globalsSource,
    /\.ticker-financial-chart__ranges button\.is-active\s*\{[\s\S]*?background:\s*var\(--primary\)/
  );
});
