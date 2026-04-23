import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import path from "node:path";
import test from "node:test";

const loginPagePath = path.join(import.meta.dirname, "login", "page.tsx");

test("login page bootstraps from auth state and preserves the requested destination", () => {
  const source = readFileSync(loginPagePath, "utf8");

  assert.match(source, /from "@\/components\/ui\/button"/);
  assert.match(source, /from "@\/components\/ui\/card"/);
  assert.match(source, /from "@\/components\/ui\/input"/);
  assert.match(source, /resolveNextPath/);
  assert.match(source, /useAuth/);
  assert.match(source, /router\.replace\(nextPath\)/);
  assert.match(source, /<Input/);
  assert.match(source, /await login\(\{/);
  assert.match(source, /Protected by backend session cookies/);
  assert.match(source, /Sign In/);
  assert.match(source, /Return to the research workbench/);
});
