import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import path from "node:path";
import test from "node:test";

const componentPath = path.join(import.meta.dirname, "TradePlanForm.tsx");

test("TradePlanForm captures the required first-version trade plan fields", () => {
  const source = readFileSync(componentPath, "utf8");

  assert.match(source, /from "@\/components\/ui\/button"/);
  assert.match(source, /from "@\/components\/ui\/dialog"/);
  assert.match(source, /from "@\/components\/ui\/input"/);
  assert.match(source, /from "@\/components\/ui\/select"/);
  assert.match(source, /from "@\/components\/ui\/textarea"/);
  assert.match(source, /createTradePlan/);
  assert.match(source, /updateTradePlan/);
  assert.match(source, /resolveMarketSymbol/);
  assert.match(source, /entry_condition:\s*string/);
  assert.match(source, /thesis:\s*string/);
  assert.match(source, /invalidation_condition:\s*string/);
  assert.match(source, /risk_rule:\s*string/);
  assert.match(source, /reward_target:\s*string/);
  assert.match(source, /position_plan:\s*string/);
  assert.match(source, /expires_at:\s*string/);
  assert.match(source, /source:\s*plan\?\.source \?\? "manual"/);
});

test("TradePlanForm requires expiry and a quantifiable position plan without batch entries", () => {
  const source = readFileSync(componentPath, "utf8");

  assert.match(source, /normalizeRequiredTimestamp/);
  assert.match(source, /requireQuantifiablePositionPlan/);
  assert.match(source, /Position plan must include a quantifiable size/);
  assert.match(source, /\/\\d\/\.test\(normalized\)/);
  assert.doesNotMatch(source, /scale_in|tranches|batches|legs/);
});

test("TradePlanForm keeps executed plan baselines immutable in the editor", () => {
  const source = readFileSync(componentPath, "utf8");

  assert.match(source, /const baselineLocked = initialPlan\?\.status === "executed"/);
  assert.match(source, /return \{ notes: state\.notes\.trim\(\) \};/);
  assert.match(source, /Baseline fields are locked/);
});

test("TradePlanForm uses Workbench primitives instead of raw form controls", () => {
  const source = readFileSync(componentPath, "utf8");

  assert.match(source, /<Button/);
  assert.match(source, /<Input/);
  assert.match(source, /<Select/);
  assert.match(source, /<Textarea/);
  assert.doesNotMatch(source, /<button/);
  assert.doesNotMatch(source, /<input/);
  assert.doesNotMatch(source, /<select/);
  assert.doesNotMatch(source, /<textarea/);
});
