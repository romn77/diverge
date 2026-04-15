import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import path from "node:path";
import test from "node:test";

const layoutPath = path.join(import.meta.dirname, "layout.tsx");

test("layout seeds server preferences and bootstraps the client before hydration", () => {
  const source = readFileSync(layoutPath, "utf8");

  assert.match(source, /cookies, headers/);
  assert.match(source, /buildPreferencesBootstrapScript/);
  assert.match(source, /resolveServerLanguage/);
  assert.match(source, /resolveServerTheme/);
  assert.match(source, /lang=\{toHtmlLang\(initialLanguage\)\}/);
  assert.match(source, /data-theme=\{initialTheme\}/);
  assert.match(source, /data-ui-language=\{initialLanguage\}/);
  assert.match(source, /dangerouslySetInnerHTML=\{\{ __html: preferencesBootstrapScript \}\}/);
  assert.match(source, /PreferencesProvider/);
  assert.match(source, /suppressHydrationWarning/);
  assert.match(source, /initialLanguage=\{initialLanguage\}/);
  assert.match(source, /initialTheme=\{initialTheme\}/);
});
