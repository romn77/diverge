import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import path from "node:path";
import test from "node:test";

const activityRoutePath = path.join(
  import.meta.dirname,
  "(workbench)",
  "activity",
  "page.tsx"
);

test("activity route renders the shared activity dashboard", () => {
  const source = readFileSync(activityRoutePath, "utf8");

  assert.match(source, /ActivityDashboard/);
});
