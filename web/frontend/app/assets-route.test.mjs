import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import path from "node:path";
import test from "node:test";

const assetsRoutePath = path.join(
  import.meta.dirname,
  "(workbench)",
  "assets",
  "page.tsx"
);

test("assets route renders the shared assets workspace", () => {
  const source = readFileSync(assetsRoutePath, "utf8");

  assert.match(source, /AssetsWorkspace/);
});
