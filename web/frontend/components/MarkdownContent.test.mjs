import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import path from "node:path";
import test from "node:test";

const markdownContentPath = path.join(import.meta.dirname, "MarkdownContent.tsx");

test("MarkdownContent renders highlights outside the article and enables reading-mode affordances", () => {
  const source = readFileSync(markdownContentPath, "utf8");
  const articleStart = source.indexOf("<article");
  const articleEnd = source.indexOf("</article>");
  const articleBlock = source.slice(articleStart, articleEnd);

  assert.ok(articleStart >= 0);
  assert.ok(articleEnd > articleStart);
  assert.equal(articleBlock.includes("<HighlightCards"), false);
  assert.match(source, /w-full max-w-none/);
  assert.equal(source.includes("max-w-[88ch] mx-auto"), false);
  assert.match(source, /overflow-x-auto/);
  assert.match(source, /tabIndex=\{0\}/);
  assert.match(source, /role="region"/);
  assert.match(source, /aria-label=\{t\("markdown\.scrollableTable", "Scrollable table"\)\}/);
  assert.match(source, /progress-slide/);
});
