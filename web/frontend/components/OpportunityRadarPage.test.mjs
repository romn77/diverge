import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import path from "node:path";
import test from "node:test";

const componentPath = path.join(
  import.meta.dirname,
  "opportunity",
  "OpportunityRadarPage.tsx"
);

test("OpportunityRadarPage routes new radar runs through task progress before reading artifacts", () => {
  const source = readFileSync(componentPath, "utf8");

  assert.match(source, /ApiError/);
  assert.match(source, /buildOpportunityTaskHref/);
  assert.match(source, /activeOpportunityTasks/);
  assert.match(source, /refreshOpportunityTasks/);
  assert.match(source, /ignoreMissingOpportunityArtifact/);
  assert.match(source, /error instanceof ApiError && error\.status === 404/);
  assert.match(source, /const requestedRun = requestedRunId/);
  assert.match(source, /nextRuns\.find\(\(run\) => run\.run_id === requestedRunId\)/);
  assert.match(source, /if \(!selectedRunId \|\| !selectedRun \|\| !canAccessOpportunityRadar\)/);
  assert.match(source, /result\.task_id && result\.status !== "completed" && !result\.cached/);
  assert.match(source, /router\.push\(buildOpportunityTaskHref\(result\.task_id\)\)/);
  assert.match(source, /opportunity\.activeTask/);
  assert.match(source, /localizeOpportunityCode/);
  assert.match(source, /localizeOpportunityText/);
  assert.match(source, /formatThemeName/);
  assert.match(source, /opportunity\.enum\.candidateType/);
  assert.match(source, /opportunity\.enum\.event/);
  assert.match(source, /opportunity\.reason\.weightedFactors/);
  assert.match(source, /const \{ language, t \} = usePreferences\(\)/);
  assert.match(source, /output_language:\s*language === "zh" \? "cn" : "en"/);
});
