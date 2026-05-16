import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import path from "node:path";
import test from "node:test";

const componentPath = path.join(import.meta.dirname, "OpportunityTaskProgress.tsx");

test("OpportunityTaskProgress streams radar task updates and links to completed results", () => {
  const source = readFileSync(componentPath, "utf8");

  assert.match(source, /from "@\/components\/ui\/badge"/);
  assert.match(source, /from "@\/components\/ui\/button"/);
  assert.match(source, /from "@\/components\/ui\/card"/);
  assert.match(source, /from "@\/components\/ui\/scroll-area"/);
  assert.match(source, /getOpportunityTask/);
  assert.match(source, /subscribeToOpportunityTask/);
  assert.match(source, /cancelOpportunityTask/);
  assert.match(source, /nextTask\.progress_events \?\? \[\]/);
  assert.match(source, /existingEvents\.length/);
  assert.match(source, /getOpportunityRunId/);
  assert.match(source, /onViewRun:\s*\(runId:\s*string\)/);
  assert.match(source, /opportunityTask\.viewResults/);
  assert.match(source, /opportunityTask\.stage\.\$\{stage\}/);
  assert.match(source, /normalizeStageState/);
  assert.match(source, /value === "running"/);
});
