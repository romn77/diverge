import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import path from "node:path";
import test from "node:test";

const highlightCardsPath = path.join(import.meta.dirname, "HighlightCards.tsx");

test("HighlightCards hides console titles while keeping console aria labels", () => {
  const source = readFileSync(highlightCardsPath, "utf8");

  assert.match(source, /aria-label=\{consolePanel\.title\}/);
  assert.equal(source.includes("terminal-console-header"), false);
  assert.equal(source.includes("<h4>{consolePanel.title}</h4>"), false);
});
