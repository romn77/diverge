import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import path from "node:path";
import test from "node:test";

const componentPath = path.join(import.meta.dirname, "TradePlanExecuteForm.tsx");

test("TradePlanExecuteForm turns a single plan into one trade record execution", () => {
  const source = readFileSync(componentPath, "utf8");

  assert.match(source, /executeTradePlan/);
  assert.match(source, /type TradePlan/);
  assert.match(source, /type TradePlanMutationResponse/);
  assert.match(source, /entry_timestamp/);
  assert.match(source, /entry_price/);
  assert.match(source, /size/);
  assert.match(source, /execution_note/);
  assert.match(source, /plan\.plan_id/);
  assert.match(source, /onSaved\(result\)/);
  assert.doesNotMatch(source, /linkTradeToPlan/);
});

test("TradePlanExecuteForm preserves offset-aware timestamps through datetime-local", () => {
  const source = readFileSync(componentPath, "utf8");

  assert.match(source, /normalizeRequiredTimestamp/);
  assert.match(source, /toOffsetDateTimeString/);
  assert.match(source, /getTimezoneOffset/);
  assert.equal(source.includes('return value.replace("Z", "").slice(0, 16);'), false);
});

test("TradePlanExecuteForm uses Workbench primitives instead of raw controls", () => {
  const source = readFileSync(componentPath, "utf8");

  assert.match(source, /<Button/);
  assert.match(source, /<Input/);
  assert.match(source, /<Textarea/);
  assert.doesNotMatch(source, /<button/);
  assert.doesNotMatch(source, /<input/);
  assert.doesNotMatch(source, /<textarea/);
});
