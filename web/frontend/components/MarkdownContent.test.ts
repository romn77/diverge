import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import path from "node:path";
import test from "node:test";

const markdownContentPath = path.join(import.meta.dirname, "MarkdownContent.tsx");

test("MarkdownContent renders highlight cards outside the markdown article", () => {
  const source = readFileSync(markdownContentPath, "utf8");
  const articleStart = source.indexOf("<article");
  const articleEnd = source.indexOf("</article>");
  const articleBlock = source.slice(articleStart, articleEnd);

  assert.ok(articleStart >= 0);
  assert.ok(articleEnd > articleStart);
  assert.equal(articleBlock.includes("<HighlightCards"), false);
});
