import assert from "node:assert/strict";
import { existsSync, readFileSync } from "node:fs";
import path from "node:path";
import test from "node:test";

const libDir = import.meta.dirname;
const decisionCardPath = path.join(libDir, "decisionCard.ts");
const fetchDecisionCardPath = path.join(libDir, "fetchDecisionCard.ts");

test("decision card frontend modules exist for ReportViewer imports", () => {
  assert.equal(existsSync(decisionCardPath), true);
  assert.equal(existsSync(fetchDecisionCardPath), true);
});

test("fetchDecisionCard loads the JSON artifact through the report content API", () => {
  const source = readFileSync(fetchDecisionCardPath, "utf8");

  assert.match(source, /from "\.\/api"/);
  assert.match(source, /getContent\(reportId, path\)/);
  assert.match(source, /JSON\.parse/);
  assert.match(source, /Promise<DecisionCard>/);
  assert.match(source, /fetchDecisionDelta/);
  assert.match(source, /Promise<DecisionDelta>/);
});

test("decisionCard.ts mirrors the backend decision card schema used by the component", () => {
  const source = readFileSync(decisionCardPath, "utf8");

  assert.match(source, /export type PortfolioRating/);
  assert.match(source, /export type PortfolioAction/);
  assert.match(source, /export interface DecisionCard/);
  assert.match(source, /price_plan: PricePlan/);
  assert.match(source, /key_reasons: EvidenceItem\[\]/);
  assert.match(source, /export type TradeReadiness/);
  assert.match(source, /export type DataQualityLevel/);
  assert.match(source, /export interface WhyNot/);
  assert.match(source, /export interface ActionPlaybook/);
  assert.match(source, /export interface PositionGuidance/);
  assert.match(source, /export interface DecisionDelta/);
});
