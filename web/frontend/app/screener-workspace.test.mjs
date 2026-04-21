import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import path from "node:path";
import test from "node:test";

const screenerRoutePath = path.join(
  import.meta.dirname,
  "(workbench)",
  "screeners",
  "page.tsx"
);

test("screener workspace route renders the shared screener dashboard", () => {
  const source = readFileSync(screenerRoutePath, "utf8");

  assert.match(source, /ScreenerDashboard/);
});
