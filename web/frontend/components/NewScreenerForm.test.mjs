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
  assert.match(source, /AccessibleDialog/);
  assert.match(source, /Markets/i);
  assert.match(source, /CN Data Source/i);
  assert.match(source, /Top K/i);
  assert.doesNotMatch(source, /Limit Per Market/i);
  assert.doesNotMatch(source, /limit_per_market/);
  assert.match(source, /ariaLabel=\{t\("screener\.dialog", "New screener"\)\}/);
});

test("NewScreenerForm disables backend-unavailable markets with an explanation", () => {
  const source = readFileSync(formPath, "utf8");

  assert.match(source, /market\.enabled/);
  assert.match(source, /disabled=\{!market\.enabled\}/);
  assert.match(source, /screener\.marketHelp/);
  assert.match(source, /SCREEN_US_MANIFEST_PATH/i);
});

test("NewScreenerForm includes a CN data-source selector wired to form state", () => {
  const source = readFileSync(formPath, "utf8");

  assert.match(source, /cn_data_source/);
  assert.match(source, /configOptions\.cn_data_sources/);
  assert.match(source, /sourceOption\.label/);
  assert.match(source, /sourceOption\.value/);
});

test("NewScreenerForm exposes breakout selection without describing it as a hard filter", () => {
  const source = readFileSync(formPath, "utf8");

  assert.match(source, /breakout_types/);
  assert.match(source, /configOptions\.breakout_types/);
  assert.match(source, /Platform Breakout/i);
  assert.match(source, /Box Breakout/i);
  assert.match(source, /Wedge Breakout/i);
  assert.match(source, /do not hard-filter the pool/i);
});

test("NewScreenerForm performs submit-time validation before posting", () => {
  const source = readFileSync(formPath, "utf8");

  assert.match(source, /Select at least one market/i);
  assert.match(source, /Top K must be positive/i);
  assert.match(source, /as_of_date must use YYYY-MM-DD format/i);
});
