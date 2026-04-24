import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import path from "node:path";
import test from "node:test";

const globalsCssPath = path.join(import.meta.dirname, "globals.css");

test("summary panel grid keeps dense highlight panels balanced", () => {
  const source = readFileSync(globalsCssPath, "utf8");
  const panelGridBlock = source.match(/\.summary-panels\s*\{([\s\S]*?)\}/)?.[1] ?? "";
  const panelBlock = source.match(/\.summary-panel\s*\{([\s\S]*?)\}/)?.[1] ?? "";
  const mobileBlock = source.match(/@media \(max-width: 860px\)\s*\{([\s\S]*?)\n\}/)?.[1] ?? "";

  assert.match(panelGridBlock, /display:\s*grid;/);
  assert.match(panelGridBlock, /grid-template-columns:\s*repeat\(2,\s*minmax\(0,\s*1fr\)\);/);
  assert.match(panelBlock, /border-radius:\s*22px;/);
  assert.match(panelBlock, /box-shadow:\s*0 18px 34px/);
  assert.match(mobileBlock, /\.summary-panels\s*\{[\s\S]*?grid-template-columns:\s*1fr;/);
});
