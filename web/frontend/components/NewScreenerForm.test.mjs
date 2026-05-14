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
  assert.match(source, /from "@\/components\/ui\/button"/);
  assert.match(source, /from "@\/components\/ui\/dialog"/);
  assert.match(source, /from "@\/components\/ui\/input"/);
  assert.match(source, /<Button/);
  assert.match(source, /DialogContent/);
  assert.match(source, /Markets/i);
  assert.match(source, /Top K/i);
  assert.doesNotMatch(source, /Limit Per Market/i);
  assert.doesNotMatch(source, /limit_per_market/);
  assert.match(source, /aria-label=\{t\("screener\.dialog", "New screener"\)\}/);
  assert.doesNotMatch(source, /AccessibleDialog/);
  assert.doesNotMatch(source, /<button/);
});

test("NewScreenerForm disables backend-unavailable markets with an explanation", () => {
  const source = readFileSync(formPath, "utf8");

  assert.match(source, /market\.enabled/);
  assert.match(source, /disabled=\{!market\.enabled\}/);
  assert.match(source, /screener\.marketHelp/);
  assert.match(source, /DATA_DIR\/manifest\/us\.csv/i);
});

test("NewScreenerForm hides data-source selectors from regular screener runs", () => {
  const source = readFileSync(formPath, "utf8");

  assert.match(source, /cn_data_source:\s*nextOptions\.defaults\.cn_data_source/);
  assert.match(source, /us_data_source:\s*nextOptions\.defaults\.us_data_source/);
  assert.doesNotMatch(source, /configOptions\.cn_data_sources\.map/);
  assert.doesNotMatch(source, /configOptions\.us_data_sources\.map/);
  assert.doesNotMatch(source, /screener\.cnDataSource/);
  assert.doesNotMatch(source, /screener\.usDataSource/);
});

test("NewScreenerForm keeps Top K editable without forcing blank input to zero", () => {
  const source = readFileSync(formPath, "utf8");

  assert.match(source, /type ScreenerFormState = Omit<ScreenTaskCreateRequest, "top_k">/);
  assert.match(source, /top_k:\s*String\(nextOptions\.defaults\.top_k\)/);
  assert.match(source, /top_k:\s*event\.target\.value/);
  assert.match(source, /top_k:\s*Number\(formState\.top_k\)/);
  assert.doesNotMatch(source, /top_k:\s*Number\(event\.target\.value\)/);
});

test("NewScreenerForm describes breakout selection as a final candidate constraint", () => {
  const source = readFileSync(formPath, "utf8");

  assert.match(source, /breakout_types/);
  assert.match(source, /configOptions\.breakout_types/);
  assert.match(source, /Platform Breakout/i);
  assert.match(source, /Box Breakout/i);
  assert.match(source, /Wedge Breakout/i);
  assert.match(source, /restrict final candidates to matching breakout setups/i);
  assert.doesNotMatch(source, /do not hard-filter the pool/i);
});

test("NewScreenerForm performs submit-time validation before posting", () => {
  const source = readFileSync(formPath, "utf8");

  assert.match(source, /Select at least one market/i);
  assert.match(source, /Top K must be positive/i);
  assert.match(source, /Top K must be 100 or less/i);
  assert.match(source, /max=\{100\}/);
  assert.doesNotMatch(source, /as_of_date must use YYYY-MM-DD format/i);
  assert.doesNotMatch(source, /screener\.asOfDate/);
  assert.doesNotMatch(source, /getLocalDateInputValue/);
});
