import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import path from "node:path";
import test from "node:test";

const componentPath = path.join(import.meta.dirname, "ScreenerTaskProgress.tsx");

test("ScreenerTaskProgress streams screener task updates and exposes a result action", () => {
  const source = readFileSync(componentPath, "utf8");

  assert.match(source, /from "@\/components\/ui\/badge"/);
  assert.match(source, /from "@\/components\/ui\/button"/);
  assert.match(source, /from "@\/components\/ui\/card"/);
  assert.match(source, /from "@\/components\/ui\/scroll-area"/);
  assert.match(source, /<Card/);
  assert.match(source, /<Button/);
  assert.match(source, /<Badge/);
  assert.match(source, /<ScrollArea/);
  assert.match(source, /getScreenerTask/);
  assert.match(source, /subscribeToScreenerTask/);
  assert.match(source, /onViewRun:\s*\(runId:\s*string\)/);
  assert.match(source, /Universe/);
  assert.match(source, /History/);
  assert.match(source, /Features/);
  assert.match(source, /Filters/);
  assert.match(source, /Ranking/);
  assert.match(source, /Export/);
  assert.match(source, /View Results/);
});
