import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import path from "node:path";
import test from "node:test";

const providerPath = path.join(import.meta.dirname, "PreferencesProvider.tsx");
const preferencesPath = path.join(import.meta.dirname, "..", "lib", "uiPreferences.ts");

test("PreferencesProvider syncs theme, language, and visual style state to document attributes and localStorage", () => {
  const source = readFileSync(providerPath, "utf8");

  assert.match(source, /document\.documentElement/);
  assert.match(source, /useState<Theme>\(\(\) => \{/);
  assert.match(source, /useState<Language>\(\(\) => \{/);
  assert.match(source, /useState<VisualStyle>\(\(\) => \{/);
  assert.match(source, /return initialTheme/);
  assert.match(source, /return initialLanguage/);
  assert.match(source, /return initialVisualStyle/);
  assert.match(source, /root\.dataset\.theme = theme/);
  assert.match(source, /root\.style\.colorScheme = toColorScheme\(theme\)/);
  assert.match(source, /root\.lang = toHtmlLang\(language\)/);
  assert.match(source, /root\.dataset\.visualStyle = visualStyle/);
  assert.match(source, /window\.localStorage\.setItem\(THEME_STORAGE_KEY, theme\)/);
  assert.match(source, /window\.localStorage\.setItem\(LANGUAGE_STORAGE_KEY, language\)/);
  assert.match(source, /window\.localStorage\.setItem\(VISUAL_STYLE_STORAGE_KEY, visualStyle\)/);
  assert.match(source, /document\.cookie = createPreferenceCookieString\(THEME_COOKIE_NAME, theme\)/);
  assert.match(
    source,
    /document\.cookie = createPreferenceCookieString\(LANGUAGE_COOKIE_NAME, language\)/
  );
  assert.match(source, /VISUAL_STYLE_COOKIE_NAME/);
  assert.match(source, /useCallback<PreferencesContextValue\["t"\]>/);
  assert.match(source, /\[language\]\s*\)/);
});

test("uiPreferences defines persisted preference cookie keys with zh translations", () => {
  const source = readFileSync(preferencesPath, "utf8");

  assert.match(source, /THEME_STORAGE_KEY = "diverge\.ui\.theme"/);
  assert.match(source, /LANGUAGE_STORAGE_KEY = "diverge\.ui\.language"/);
  assert.match(source, /VISUAL_STYLE_STORAGE_KEY = "diverge\.ui\.visualStyle"/);
  assert.match(source, /THEME_COOKIE_NAME = THEME_STORAGE_KEY/);
  assert.match(source, /LANGUAGE_COOKIE_NAME = LANGUAGE_STORAGE_KEY/);
  assert.match(source, /VISUAL_STYLE_COOKIE_NAME = VISUAL_STYLE_STORAGE_KEY/);
  assert.match(source, /THEME_VALUES = \["light", "dark", "proof", "everforest"\] as const/);
  assert.match(source, /export type VisualStyle = "normal" \| "stylful"/);
  assert.match(source, /"common\.interfacePreferences": "界面偏好"/);
  assert.match(source, /"common\.dark": "深色"/);
  assert.match(source, /"common\.proof": "Proof"/);
  assert.match(source, /"common\.everforest": "Everforest"/);
  assert.match(source, /"common\.normal": "标准"/);
  assert.match(source, /"common\.stylful": "个性"/);
  assert.match(source, /"common\.chinese": "中文"/);
  assert.match(source, /"common\.settings": "设置"/);
  assert.match(source, /"preferences\.visualStyleLabel": "界面风格"/);
  assert.match(source, /"workspace\.resetRequired": "需要重置"/);
  assert.match(source, /"sidebar\.nav\.assets": "资产"/);
  assert.match(source, /"activity\.title": "后台任务"/);
  assert.match(source, /"assets\.title": "组合资产台账"/);
  assert.match(source, /"screenerDashboard\.queueSnapshot": "队列快照"/);
  assert.match(source, /"screenerDashboard\.staleResultTitle": "筛选条件已变更"/);
  assert.match(source, /"screenerDashboard\.placeholderReadyTitle": "等待运行"/);
  assert.match(source, /"trade\.status\.closed": "已平仓"/);
});
