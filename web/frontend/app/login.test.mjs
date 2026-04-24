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
  assert.match(source, /Sign In/);
  assert.match(source, /Diverge/);
  assert.match(source, /Sign in to continue to your requested page\./);
});

test("login page uses theme-aware surface and text tokens for the signed-out layout", () => {
  const source = readFileSync(loginPagePath, "utf8");

  assert.match(source, /card-surface/);
  assert.doesNotMatch(source, /bg-\[rgba\(255,252,246,0\.92\)\]/);
  assert.doesNotMatch(source, /bg-white\/82/);
  assert.doesNotMatch(source, /className="mt-2 bg-white"/);
  assert.doesNotMatch(source, /text-slate-(900|800|600|500)/);
});
