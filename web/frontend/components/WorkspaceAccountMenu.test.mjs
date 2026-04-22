import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import path from "node:path";
import test from "node:test";

const componentPath = path.join(import.meta.dirname, "WorkspaceAccountMenu.tsx");

test("WorkspaceAccountMenu exposes an in-flow utility bar instead of a fixed top-right overlay", () => {
  const source = readFileSync(componentPath, "utf8");

  assert.match(source, /authEnabled:\s*boolean/);
  assert.match(source, /authUser:\s*AuthUser \| null/);
  assert.match(source, /canManageUsers:\s*boolean/);
  assert.match(source, /onLogout:\s*\(\)\s*=>\s*void/);
  assert.match(source, /loggingOut:\s*boolean/);
  assert.match(source, /selectedOutputLanguage:\s*string \| null/);
  assert.match(source, /onOutputLanguageChange:\s*\(value:\s*string\)/);
  assert.match(source, /className="flex items-start justify-between gap-3 px-4 pt-4 md:px-6"/);
  assert.match(source, /inline-flex items-center gap-1\.5 rounded-full/);
  assert.match(source, /h-8 w-8/);
  assert.doesNotMatch(source, /max-w-\[1600px\]/);
  assert.doesNotMatch(source, /fixed right-4 top-4 z-\[55\]/);
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
  assert.match(source, /onOpenSidebar\?: \(\) => void/);
  assert.match(source, /aria-label=\{t\("common\.menu", "Menu"\)\}/);
  assert.match(source, /md:hidden/);

  const accountIndex = source.indexOf("aria-haspopup=\"menu\"");
  const settingsIndex = source.indexOf("aria-haspopup=\"dialog\"");
  assert.notEqual(accountIndex, -1);
  assert.notEqual(settingsIndex, -1);
  assert.ok(accountIndex < settingsIndex, "account trigger should render before settings");
  assert.doesNotMatch(source, /Research Suite/);
  assert.doesNotMatch(source, /Workspace controls and session access/);
  assert.match(source, /rounded-full border border-\[var\(--border\)\] bg-white\/92 p-1/);
  assert.match(source, /grid h-8 w-8 place-items-center/);
  assert.match(source, /flex h-8 w-8 items-center justify-center/);
});
