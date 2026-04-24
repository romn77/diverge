import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import path from "node:path";
import test from "node:test";

const highlightCardsPath = path.join(import.meta.dirname, "HighlightCards.tsx");

test("HighlightCards keeps the flattened summary deck accessible", () => {
  const source = readFileSync(highlightCardsPath, "utf8");

  assert.match(source, /const panels = deck\.consoles\.flatMap/);
  assert.match(source, /className="highlights-container summary-deck"/);
  assert.match(source, /aria-label=\{panel\.title\}/);
  assert.match(source, /summary-panel--\$\{panel\.span\}/);
  assert.equal(source.includes("terminal-console-header"), false);
  assert.equal(source.includes("terminal-console"), false);
  assert.equal(source.includes("<h4>{consolePanel.title}</h4>"), false);
});
