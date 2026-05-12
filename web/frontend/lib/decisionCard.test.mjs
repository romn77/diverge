import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";

const source = readFileSync(new URL("./decisionCard.ts", import.meta.url), "utf8");

test("decisionCard.ts exposes v1.1 intelligence field contracts", () => {
  assert.match(source, /export type PortfolioRating/);
  assert.match(source, /export type PortfolioAction/);
  assert.match(source, /export type TradeReadiness/);
  assert.match(source, /READY/);
  assert.match(source, /WAITING_FOR_TRIGGER/);
  assert.match(source, /DATA_INSUFFICIENT/);
  assert.match(source, /export type DataQualityLevel/);
  assert.match(source, /complete/);
  assert.match(source, /partial/);
  assert.match(source, /weak/);
  assert.match(source, /insufficient/);
});

test("DecisionCard keeps v1.1 fields optional for old artifacts", () => {
  assert.match(source, /trade_readiness\?: TradeReadiness \| null/);
  assert.match(source, /data_quality_level\?: DataQualityLevel \| null/);
  assert.match(source, /why_not\?: WhyNot \| null/);
  assert.match(source, /action_playbook\?: ActionPlaybook \| null/);
  assert.match(source, /position_guidance\?: PositionGuidance \| null/);
});

test("DecisionDelta mirrors the lightweight backend artifact", () => {
  assert.match(source, /export interface FieldDelta/);
  assert.match(source, /previous: string \| number \| null/);
  assert.match(source, /current: string \| number \| null/);
  assert.match(source, /export interface DecisionDelta/);
  assert.match(source, /previous_report_id: string \| null/);
  assert.match(source, /trade_readiness: FieldDelta \| null/);
});
