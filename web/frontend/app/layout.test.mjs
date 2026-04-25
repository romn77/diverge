import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import path from "node:path";
import test from "node:test";

const layoutPath = path.join(import.meta.dirname, "layout.tsx");
const packageJsonPath = path.join(import.meta.dirname, "..", "package.json");

test("layout seeds server preferences and bootstraps the client before hydration", () => {
  const source = readFileSync(layoutPath, "utf8");

  assert.match(source, /cookies, headers/);
  assert.match(source, /buildPreferencesBootstrapScript/);
  assert.match(source, /isTheme/);
  assert.match(source, /resolveServerLanguage/);
  assert.match(source, /resolveServerTheme/);
  assert.match(source, /resolveServerVisualStyle/);
  assert.match(source, /lang=\{toHtmlLang\(initialLanguage\)\}/);
  assert.match(source, /data-theme=\{initialTheme\}/);
  assert.match(source, /data-ui-language=\{initialLanguage\}/);
  assert.match(source, /data-visual-style=\{initialVisualStyle\}/);
  assert.match(source, /dangerouslySetInnerHTML=\{\{ __html: preferencesBootstrapScript \}\}/);
  assert.match(source, /PreferencesProvider/);
  assert.match(source, /AuthProvider/);
  assert.match(source, /suppressHydrationWarning/);
  assert.match(source, /initialLanguage=\{initialLanguage\}/);
  assert.match(source, /initialTheme=\{initialTheme\}/);
  assert.match(source, /initialVisualStyle=\{initialVisualStyle\}/);
  assert.match(source, /preferSystemTheme:\s*!isTheme\(themeCookie\)/);
});

test("layout does not inject development component inspector overlays", () => {
  const layoutSource = readFileSync(layoutPath, "utf8");
  const packageSource = readFileSync(packageJsonPath, "utf8");

  assert.doesNotMatch(layoutSource, /react-grab/);
  assert.doesNotMatch(layoutSource, /unpkg\.com/);
  assert.doesNotMatch(layoutSource, /next\/script/);
  assert.doesNotMatch(packageSource, /react-grab/);
});
