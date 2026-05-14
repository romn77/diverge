import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import path from "node:path";
import test from "node:test";

const highlightTerminalPath = path.join(
  import.meta.dirname,
  "highlightTerminal.ts"
);

test("highlightTerminal builds a valuation-focused fundamentals console", () => {
  const source = readFileSync(highlightTerminalPath, "utf8");

  assert.match(source, /Valuation Console/);
  assert.match(source, /valuation-table/);
  assert.match(source, /Fair Value/);
  assert.match(source, /DCF Status/);
  assert.match(source, /dcf-applicability/);
  assert.match(source, /PEG/);
  assert.match(source, /Bull Case/);
  assert.match(source, /Base Case/);
  assert.match(source, /Bear Case/);
});

test("highlightTerminal promotes base case fair value and PEG (1Y) into fundamentals hero chips", () => {
  const source = readFileSync(highlightTerminalPath, "utf8");
  const fundamentalsStart = source.indexOf("function buildFundamentalsDeck");
  const fundamentalsEnd = source.indexOf("function buildSentimentDeck");
  const fundamentalsSection =
    fundamentalsStart >= 0 && fundamentalsEnd > fundamentalsStart
      ? source.slice(fundamentalsStart, fundamentalsEnd)
      : "";
  assert.match(fundamentalsSection, /highlights\.fundamentals\.hero/);
  assert.match(fundamentalsSection, /"Balance Sheet Console"/);
  assert.match(fundamentalsSection, /highlights\.chip\.health/);
  assert.match(fundamentalsSection, /"Health"/);
  assert.match(fundamentalsSection, /highlights\.chip\.baseCaseFairValue/);
  assert.match(fundamentalsSection, /"Base Case Fair Value"/);
  assert.match(fundamentalsSection, /highlights\.chip\.peg1y/);
  assert.match(fundamentalsSection, /"PEG \(1Y\)"/);
  assert.doesNotMatch(fundamentalsSection, /label:\s*"Bias"/);
});
