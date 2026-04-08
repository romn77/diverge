import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import path from "node:path";
import test from "node:test";

const formPath = path.join(import.meta.dirname, "NewAnalysisForm.tsx");

test("NewAnalysisForm is driven by backend config options and task creation callbacks", () => {
  const source = readFileSync(formPath, "utf8");

  assert.match(source, /getConfigOptions/);
  assert.match(source, /createTask/);
  assert.match(source, /onTaskCreated:\s*\(taskId:\s*string\)/);
  assert.match(source, /Ticker/);
  assert.match(source, /Research Depth/i);
  assert.match(source, /LLM Provider/i);
  assert.match(source, /Output Language/i);
  assert.match(source, /role="dialog"/);
});

test("NewAnalysisForm disables providers without configured credentials", () => {
  const source = readFileSync(formPath, "utf8");

  assert.match(source, /provider\.enabled/);
  assert.match(source, /disabled=\{!provider\.enabled\}/);
  assert.match(source, /disabled_reason/);
  assert.match(source, /API key/i);
});

test("NewAnalysisForm defaults to the full analyst set instead of truncating to two", () => {
  const source = readFileSync(formPath, "utf8");

  assert.doesNotMatch(source, /analysts:\s*configOptions\.analysts\.slice\(0,\s*2\)/);
  assert.match(source, /analysts:\s*configOptions\.analysts\.map\(\(option\)\s*=>\s*option\.value\)/);
});
