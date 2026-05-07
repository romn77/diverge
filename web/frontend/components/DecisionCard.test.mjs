import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import path from "node:path";
import test from "node:test";

const decisionCardPath = path.join(import.meta.dirname, "DecisionCard.tsx");

test("DecisionCard renders final ruling sections without replacing rating with probability", () => {
  const source = readFileSync(decisionCardPath, "utf8");

  assert.match(source, /Final Portfolio Ruling/);
  assert.match(source, /Execution Plan/);
  assert.match(source, /Key Reasons/);
  assert.match(source, /Key Risks/);
  assert.match(source, /Data Quality/);
  assert.match(source, /card\.conviction_score\} \/ 100/);
  assert.doesNotMatch(source, /probability/i);
});
