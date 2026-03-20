import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import path from "node:path";
import test from "node:test";

const highlightCardsPath = path.join(import.meta.dirname, "HighlightCards.tsx");

test("HighlightCards flattens the deck into a linear summary rail", () => {
  const source = readFileSync(highlightCardsPath, "utf8");

  assert.match(source, /Structured report highlights/);
  assert.equal(source.includes("terminal-console"), false);
  assert.equal(source.includes("terminal-console-body"), false);
  assert.equal(source.includes("terminal-panel-header"), false);
});

test("HighlightCards supports panel span modifiers for richer fundamentals layouts", () => {
  const source = readFileSync(highlightCardsPath, "utf8");

  assert.match(source, /summary-panel--\$\{panel\.span\}/);
  assert.match(source, /aria-label=\{panel\.title\}/);
});
