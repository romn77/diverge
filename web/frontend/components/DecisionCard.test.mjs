import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import path from "node:path";
import test from "node:test";

const decisionCardPath = path.join(import.meta.dirname, "DecisionCard.tsx");

test("DecisionCard renders compact intelligence sections without replacing rating with probability", () => {
  const source = readFileSync(decisionCardPath, "utf8");

  assert.match(source, /Final Portfolio Ruling/);
  assert.match(source, /Why Not\?/);
  assert.match(source, /Action Playbook/);
  assert.match(source, /Position Guidance/);
  assert.match(source, /Since Last Analysis/);
  assert.match(source, /Evidence and Details/);
  assert.match(source, /decision-evidence-details/);
  assert.match(source, /Data Quality/);
  assert.match(source, /card\.conviction_score\} \/ 100/);
  assert.doesNotMatch(source, /probability/i);
});
