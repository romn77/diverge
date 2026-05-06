import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import path from "node:path";
import test from "node:test";

const componentPath = path.join(import.meta.dirname, "TradeReviewForm.tsx");

test("TradeReviewForm keeps manual entry and exit reviews focused on price-action context", () => {
  const source = readFileSync(componentPath, "utf8");

  assert.match(source, /from "@\/components\/ui\/button"/);
  assert.match(source, /from "@\/components\/ui\/dialog"/);
  assert.match(source, /from "@\/components\/ui\/textarea"/);
  assert.match(source, /DialogContent/);
  assert.doesNotMatch(source, /role="dialog"/);
  assert.match(source, /saveTradeReview/);
  assert.match(source, /Entry Review/);
  assert.match(source, /Exit Review/);
  assert.match(source, /Manual Adjustments/);
  assert.match(source, /The original trade plan and reasons are already part of the trade record/);
  assert.match(source, /buildDefaultDecisionContext/);
  assert.match(source, /Price Assessment/);
  assert.match(source, /Next-Time Guardrail/);
  assert.match(source, /optionalText/);
  assert.match(source, /splitOptionalMultilineList/);
  assert.match(source, /buildDefaultSizingAssessment/);
  assert.match(source, /buildDefaultDisciplineAssessment/);
  assert.match(source, /buildDefaultPriceAssessment/);
  assert.match(source, /Optional before saving/);
  assert.doesNotMatch(source, /Review Brief/);
  assert.doesNotMatch(source, /Decision Context/);
  assert.doesNotMatch(source, /Advanced Structured Fields/);
  assert.doesNotMatch(source, /Sizing Assessment/);
  assert.doesNotMatch(source, /Discipline Assessment/);
  assert.doesNotMatch(source, /Outcome Summary/);
  assert.doesNotMatch(source, /Ticker-Specific Lessons/);
  assert.doesNotMatch(source, /Cross-Ticker Tags/);
  assert.doesNotMatch(source, /Add at least one list item before saving the review/);
});

test("TradeReviewForm can request an AI-generated review before manual editing", () => {
  const source = readFileSync(componentPath, "utf8");

  assert.doesNotMatch(source, /createTradeReview/);
  assert.match(source, /generateReview/);
  assert.match(source, /onGenerateReview/);
  assert.doesNotMatch(source, /Apply generated review/);
  assert.match(source, /admin-configured trade journal review model/);
  assert.doesNotMatch(source, /llm_provider/);
  assert.doesNotMatch(source, /model:/);
});

test("TradeReviewForm treats linked snapshots as optional AI context", () => {
  const source = readFileSync(componentPath, "utf8");

  assert.doesNotMatch(source, /Link at least one analysis snapshot on the trade record before saving a review\./);
  assert.doesNotMatch(source, /Link at least one analysis snapshot on the trade record before generating a review\./);
  assert.match(source, /No analysis references are currently attached\. AI can still review the saved trade record/);
  assert.match(source, /analysis_references: referenceSummary\.length > 0 \? referenceSummary : undefined/);
  assert.match(source, /splitOptionalMultilineList/);
  assert.match(source, /splitTagList/);
  assert.equal(
    source.includes("Add at least one cross-ticker tag before saving the review."),
    false
  );
});
