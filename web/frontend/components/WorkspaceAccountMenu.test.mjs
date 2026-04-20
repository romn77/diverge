import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import path from "node:path";
import test from "node:test";

const componentPath = path.join(import.meta.dirname, "WorkspaceAccountMenu.tsx");

test("WorkspaceAccountMenu exposes a compact top-right account menu for authenticated sessions", () => {
  const source = readFileSync(componentPath, "utf8");

  assert.match(source, /authEnabled:\s*boolean/);
  assert.match(source, /authUser:\s*AuthUser \| null/);
  assert.match(source, /canManageUsers:\s*boolean/);
  assert.match(source, /onLogout:\s*\(\)\s*=>\s*void/);
  assert.match(source, /loggingOut:\s*boolean/);
  assert.match(source, /selectedOutputLanguage:\s*string \| null/);
  assert.match(source, /onOutputLanguageChange:\s*\(value:\s*string\)/);
  assert.match(source, /sticky top-0 z-\[45\] border-b .* px-4 py-2/);
  assert.match(source, /border-b border-\[rgba\(150,118,99,0\.18\)\]/);
  assert.match(source, /flex w-full items-center justify-end gap-2/);
  assert.doesNotMatch(source, /max-w-6xl/);
  assert.match(source, /items-center justify-end gap-2/);
  assert.match(source, /Interface Preferences/);
  assert.match(source, /Output Language/);
  assert.match(source, /settingsLanguageSelectRef/);
  assert.match(source, /getConfigOptions/);
  assert.match(source, /Workspace Access/);
  assert.match(source, /Admin Console/);
  assert.match(source, /Sign Out/);
  assert.match(source, /Open Workspace/);
  assert.match(source, /must_change_password/);
  assert.match(source, /aria-haspopup="menu"/);
  assert.match(source, /aria-haspopup="dialog"/);
  assert.match(source, /role="menu"/);
  assert.match(source, /role="dialog"/);
  assert.match(source, /event\.key === "Escape"/);
  assert.match(source, /pointerdown/);

  const accountIndex = source.indexOf("aria-haspopup=\"menu\"");
  const settingsIndex = source.indexOf("aria-haspopup=\"dialog\"");
  assert.notEqual(accountIndex, -1);
  assert.notEqual(settingsIndex, -1);
  assert.ok(accountIndex < settingsIndex, "account trigger should render before settings");
  assert.doesNotMatch(source, /Research Suite/);
  assert.doesNotMatch(source, /Workspace controls and session access/);
  assert.match(source, /rounded-full border border-\[var\(--border\)\] bg-white\/92 px-2\.5 py-1\.5/);
  assert.match(source, /grid h-9 w-9 place-items-center/);
  assert.match(source, /flex h-9 w-9 items-center justify-center/);
});
