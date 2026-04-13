import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import path from "node:path";
import test from "node:test";

const componentPath = path.join(import.meta.dirname, "TradeReviewForm.tsx");

test("TradeReviewForm saves structured manual entry and exit reviews with required assessment fields", () => {
  const source = readFileSync(componentPath, "utf8");

  assert.match(source, /saveTradeReview/);
  assert.match(source, /Entry Review/);
  assert.match(source, /Exit Review/);
  assert.match(source, /Thesis Assessment/);
  assert.match(source, /Timing Assessment/);
  assert.match(source, /Sizing Assessment/);
  assert.match(source, /Discipline Assessment/);
  assert.match(source, /Outcome Summary/);
  assert.match(source, /Improvement Actions/);
  assert.match(source, /Ticker-Specific Lessons/);
  assert.match(source, /Cross-Ticker Tags/);
});

test("TradeReviewForm stays manual-only and requires linked snapshot references before saving", () => {
  const source = readFileSync(componentPath, "utf8");

  assert.match(source, /Manual-only MVP/);
  assert.match(source, /Link at least one analysis snapshot on the trade record before saving a review\./);
  assert.match(source, /No analysis references are currently attached to this trade\./);
  assert.match(source, /splitMultilineList/);
  assert.match(source, /splitTagList/);
  assert.match(source, /Optional\. Use one per line or separate with commas\./);
  assert.equal(
    source.includes("Add at least one cross-ticker tag before saving the review."),
    false
  );
});
