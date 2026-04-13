import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import path from "node:path";
import test from "node:test";

const packageJsonPath = path.join(import.meta.dirname, "..", "package.json");

test("frontend dev script uses webpack instead of turbopack", () => {
  const packageJson = JSON.parse(readFileSync(packageJsonPath, "utf8"));

  assert.equal(packageJson.scripts.dev, "next dev --webpack");
});
