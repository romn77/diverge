import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import path from "node:path";
import test from "node:test";

const sanitizerPath = path.join(import.meta.dirname, "reportSanitizer.ts");
const markdownContentPath = path.join(
  import.meta.dirname,
  "..",
  "components",
  "MarkdownContent.tsx"
);
const highlightTerminalPath = path.join(import.meta.dirname, "highlightTerminal.ts");

test("report sanitizer hides internal report-generation terms from user-facing copy", () => {
  const sanitizerSource = readFileSync(sanitizerPath, "utf8");
  const markdownContentSource = readFileSync(markdownContentPath, "utf8");
  const highlightTerminalSource = readFileSync(highlightTerminalPath, "utf8");

  assert.match(sanitizerSource, /Portfolio\\s\+Ledger\\s\+Context/);
  assert.match(sanitizerSource, /json-decision-card/);
  assert.match(sanitizerSource, /LLM\\s\+gateway/);
  assert.match(markdownContentSource, /sanitizeUserFacingReportText/);
  assert.match(highlightTerminalSource, /sanitizeUserFacingReportText/);
});
