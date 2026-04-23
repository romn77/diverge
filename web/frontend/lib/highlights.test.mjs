import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";
import vm from "node:vm";
import ts from "typescript";

const highlightsSource = readFileSync(
  new URL("./highlights.ts", import.meta.url),
  "utf8"
);

function loadHighlightsModule() {
  const compiledModule = { exports: {} };
  const output = ts.transpileModule(highlightsSource, {
    compilerOptions: {
      module: ts.ModuleKind.CommonJS,
      target: ts.ScriptTarget.ES2022,
    },
  });

  vm.runInNewContext(output.outputText, {
    exports: compiledModule.exports,
    module: compiledModule,
  });

  return compiledModule.exports;
}

test("parseHighlights removes every json-highlights block after parsing the first valid block", () => {
  const { parseHighlights } = loadHighlightsModule();
  const markdown = [
    "Opening thesis.",
    "```json-highlights",
    JSON.stringify({
      category: "bear_case",
      signal: "HOLD",
      signal_confidence: "high",
      summary: "First structured summary.",
      stance: "bearish",
      key_arguments: [
        {
          point: "Valuation is stretched.",
          evidence: "The stock trades above the valuation range.",
        },
      ],
    }),
    "```",
    "Follow-up debate.",
    "```json-highlights",
    JSON.stringify({
      category: "bear_case",
      signal: "HOLD",
      signal_confidence: "medium",
      summary: "Second structured summary.",
      stance: "bearish",
      key_arguments: [
        {
          point: "Momentum is mixed.",
          evidence: "The long-term trend has not repaired yet.",
        },
      ],
    }),
    "```",
    "Closing paragraph.",
  ].join("\n");

  const result = parseHighlights(markdown);

  assert.equal(result.highlights?.summary, "First structured summary.");
  assert.equal(result.cleanMarkdown.includes("json-highlights"), false);
  assert.match(result.cleanMarkdown, /Opening thesis/);
  assert.match(result.cleanMarkdown, /Follow-up debate/);
  assert.match(result.cleanMarkdown, /Closing paragraph/);
});
