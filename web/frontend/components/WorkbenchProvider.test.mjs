import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import path from "node:path";
import test from "node:test";

const componentPath = path.join(import.meta.dirname, "WorkbenchProvider.tsx");

test("WorkbenchProvider deduplicates screener runs before storing workspace state", () => {
  const source = readFileSync(componentPath, "utf8");

  assert.match(source, /function dedupeScreenerRuns/);
  assert.match(source, /setScreenerRuns\(dedupeScreenerRuns\(await listScreenerRuns\(\)\)\)/);
});
