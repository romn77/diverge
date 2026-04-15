import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import path from "node:path";
import test from "node:test";

const providerPath = path.join(import.meta.dirname, "PreferencesProvider.tsx");
const preferencesPath = path.join(import.meta.dirname, "..", "lib", "uiPreferences.ts");

test("PreferencesProvider syncs theme and language state to document attributes and localStorage", () => {
  const source = readFileSync(providerPath, "utf8");

  assert.match(source, /document\.documentElement/);
  assert.match(source, /useState<Theme>\(initialTheme\)/);
  assert.match(source, /useState<Language>\(initialLanguage\)/);
  assert.match(source, /root\.dataset\.theme = theme/);
  assert.match(source, /root\.lang = toHtmlLang\(language\)/);
  assert.match(source, /window\.localStorage\.setItem\(THEME_STORAGE_KEY, theme\)/);
  assert.match(source, /window\.localStorage\.setItem\(LANGUAGE_STORAGE_KEY, language\)/);
  assert.match(source, /document\.cookie = createPreferenceCookieString\(THEME_COOKIE_NAME, theme\)/);
  assert.match(
    source,
    /document\.cookie = createPreferenceCookieString\(LANGUAGE_COOKIE_NAME, language\)/
  );
  assert.match(source, /useCallback<PreferencesContextValue\["t"\]>/);
  assert.match(source, /\[language\]\s*\)/);
});

test("uiPreferences defines persisted theme and language cookie keys with zh translations", () => {
  const source = readFileSync(preferencesPath, "utf8");

  assert.match(source, /THEME_STORAGE_KEY = "tradingagents\.ui\.theme"/);
  assert.match(source, /LANGUAGE_STORAGE_KEY = "tradingagents\.ui\.language"/);
  assert.match(source, /THEME_COOKIE_NAME = THEME_STORAGE_KEY/);
  assert.match(source, /LANGUAGE_COOKIE_NAME = LANGUAGE_STORAGE_KEY/);
  assert.match(source, /"common\.interfacePreferences": "界面偏好"/);
  assert.match(source, /"common\.dark": "深色"/);
  assert.match(source, /"common\.chinese": "中文"/);
});
