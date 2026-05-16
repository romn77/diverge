import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import path from "node:path";
import test from "node:test";
import vm from "node:vm";
import ts from "typescript";

const sanitizerPath = path.join(import.meta.dirname, "reportSanitizer.ts");
const markdownContentPath = path.join(
  import.meta.dirname,
  "..",
  "components",
  "MarkdownContent.tsx"
);
const highlightTerminalPath = path.join(import.meta.dirname, "highlightTerminal.ts");
const sanitizerSource = readFileSync(sanitizerPath, "utf8");

function loadSanitizerModule() {
  const compiledModule = { exports: {} };
  const output = ts.transpileModule(sanitizerSource, {
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

test("report sanitizer hides internal report-generation terms from user-facing copy", () => {
  const markdownContentSource = readFileSync(markdownContentPath, "utf8");
  const highlightTerminalSource = readFileSync(highlightTerminalPath, "utf8");

  assert.match(sanitizerSource, /Portfolio\\s\+Ledger\\s\+Context/);
  assert.match(sanitizerSource, /json-decision-card/);
  assert.match(sanitizerSource, /LLM\\s\+gateway/);
  assert.match(markdownContentSource, /sanitizeUserFacingReportText/);
  assert.match(highlightTerminalSource, /sanitizeUserFacingReportText/);
});

test("report sanitizer keeps only the latest debate turn for accumulated histories", () => {
  const { sanitizeUserFacingReportText } = loadSanitizerModule();
  const input = [
    "Neutral Analyst: 第一轮发言。",
    "```json-highlights",
    '{"category":"risk_neutral","signal":"HOLD","summary":"first","signal_confidence":"low","stance":"mixed","stance_label":"Neutral","core_argument":"first","risk_assessment":"moderate","key_recommendations":["one"]}',
    "```",
    "Neutral Analyst: 第二轮发言。",
  ].join("\n");

  const output = sanitizeUserFacingReportText(input);

  assert.doesNotMatch(output, /第一轮发言/);
  assert.match(output, /^Neutral Analyst: 第二轮发言/);
});

test("report sanitizer strips long planning prefaces before the visible report body", () => {
  const { sanitizeUserFacingReportText } = loadSanitizerModule();
  const input = [
    "好的，用户要求我继续这个任务。我需要先理解系统指令和工具约束。",
    "我需要调用工具并确认输出格式，然后才能写正式报告。",
    "```python",
    "get_stock_data(ticker='AMD', days=120)",
    "```",
    "",
    "### 我的裁决",
    "",
    "这是最终给用户看的正文。",
  ].join("\n");

  const output = sanitizeUserFacingReportText(input);

  assert.doesNotMatch(output, /用户要求我继续/);
  assert.match(output, /^### 我的裁决/);
  assert.match(output, /这是最终给用户看的正文/);
});

test("report sanitizer trims planning scaffolding after the latest debate label", () => {
  const { sanitizeUserFacingReportText } = loadSanitizerModule();
  const input = [
    "Aggressive Analyst: 我的核心任务是反驳对手，输出格式要包含正文和 structured highlights。",
    "我将采用以下结构：先反驳，再给框架。",
    "",
    "好的，各位同事。我是激进风险分析师。以下是最终正文。",
  ].join("\n");

  const output = sanitizeUserFacingReportText(input);

  assert.equal(
    output,
    "好的，各位同事。我是激进风险分析师。以下是最终正文。"
  );
});
