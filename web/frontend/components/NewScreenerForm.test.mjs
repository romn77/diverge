import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import path from "node:path";
import test from "node:test";

const formPath = path.join(import.meta.dirname, "NewScreenerForm.tsx");

test("NewScreenerForm is driven by backend screener config options and task creation callbacks", () => {
  const source = readFileSync(formPath, "utf8");

  assert.match(source, /getScreenerConfigOptions/);
  assert.match(source, /createScreenerTask/);
  assert.match(source, /onTaskCreated:\s*\(taskId:\s*string\)/);
  assert.match(source, /Markets/i);
  assert.match(source, /Top K/i);
  assert.match(source, /Limit Per Market/i);
  assert.match(source, /role="dialog"/);
});

test("NewScreenerForm disables backend-unavailable markets with an explanation", () => {
  const source = readFileSync(formPath, "utf8");

  assert.match(source, /market\.enabled/);
  assert.match(source, /disabled=\{!market\.enabled\}/);
  assert.match(source, /disabled_reason/);
  assert.match(source, /SCREEN_US_MANIFEST_PATH/i);
});
