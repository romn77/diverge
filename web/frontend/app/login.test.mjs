import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import path from "node:path";
import test from "node:test";

const loginPagePath = path.join(import.meta.dirname, "login", "page.tsx");

test("login page bootstraps from auth state and preserves the requested destination", () => {
  const source = readFileSync(loginPagePath, "utf8");

  assert.match(source, /resolveNextPath/);
  assert.match(source, /useAuth/);
  assert.match(source, /router\.replace\(nextPath\)/);
  assert.match(source, /type="email"/);
  assert.match(source, /type="password"/);
  assert.match(source, /await login\(\{/);
  assert.match(source, /Protected by backend session cookies/);
  assert.match(source, /Sign In/);
});
