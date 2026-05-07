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

test("parseHighlights accepts portfolio five-level rating signals", () => {
  const { parseHighlights } = loadHighlightsModule();
  const markdown = [
    "Portfolio decision.",
    "```json-highlights",
    JSON.stringify({
      category: "portfolio_decision",
      signal: "OVERWEIGHT",
      signal_confidence: "medium",
      summary: "Add only when the setup confirms.",
      final_decision: "UNDERWEIGHT",
      decision_basis: "Risk/reward is not yet attractive.",
      strategic_actions: [{ action: "Trim into strength.", priority: "conditional" }],
      risk_warnings: ["Valuation reset"],
    }),
    "```",
  ].join("\n");

  const result = parseHighlights(markdown);

  assert.equal(result.highlights?.signal, "OVERWEIGHT");
  assert.equal(result.highlights?.category, "portfolio_decision");
  assert.equal(result.highlights?.final_decision, "UNDERWEIGHT");
});

test("parseHighlights strips json-decision-card blocks from markdown output", () => {
  const { parseHighlights } = loadHighlightsModule();
  const markdown = [
    "Portfolio decision.",
    "```json-decision-card",
    JSON.stringify({
      rating: "SELL",
      action: "AVOID",
      conviction_score: 62,
    }),
    "```",
    "Readable conclusion.",
  ].join("\n");

  const result = parseHighlights(markdown);

  assert.equal(result.highlights, null);
  assert.equal(result.cleanMarkdown.includes("json-decision-card"), false);
  assert.match(result.cleanMarkdown, /Portfolio decision/);
  assert.match(result.cleanMarkdown, /Readable conclusion/);
});
