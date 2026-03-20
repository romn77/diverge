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
});
