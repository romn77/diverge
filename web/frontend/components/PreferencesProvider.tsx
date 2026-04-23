"use client";

import {
  useCallback,
  createContext,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from "react";
import {
  createPreferenceCookieString,
  isLanguage,
  isTheme,
  LANGUAGE_COOKIE_NAME,
  LANGUAGE_STORAGE_KEY,
  THEME_COOKIE_NAME,
  THEME_STORAGE_KEY,
  toHtmlLang,
  toLocale,
  translate,
  type Language,
  type Theme,
  type TranslationParams,
  type TranslationTemplate,
} from "@/lib/uiPreferences";

interface PreferencesContextValue {
  language: Language;
  locale: string;
  setLanguage: (language: Language) => void;
  setTheme: (theme: Theme) => void;
  t: (
    key: string,
    fallback: TranslationTemplate,
    params?: TranslationParams
  ) => string;
  theme: Theme;
}

const PreferencesContext = createContext<PreferencesContextValue | null>(null);

export function PreferencesProvider({
  children,
  initialLanguage,
  initialTheme,
}: {
  children: ReactNode;
  initialLanguage: Language;
  initialTheme: Theme;
}) {
  const [theme, setTheme] = useState<Theme>(() => {
    if (typeof document !== "undefined") {
      const nextTheme = document.documentElement.dataset.theme;
      if (isTheme(nextTheme)) {
        return nextTheme;
      }
    }
    return initialTheme;
  });
  const [language, setLanguage] = useState<Language>(() => {
    if (typeof document !== "undefined") {
      const nextLanguage = document.documentElement.dataset.uiLanguage;
      if (isLanguage(nextLanguage)) {
        return nextLanguage;
      }
    }
    return initialLanguage;
  });

  useEffect(() => {
    const root = document.documentElement;
    root.dataset.theme = theme;
    root.style.colorScheme = theme;
    window.localStorage.setItem(THEME_STORAGE_KEY, theme);
    document.cookie = createPreferenceCookieString(THEME_COOKIE_NAME, theme);
  }, [theme]);

  useEffect(() => {
    const root = document.documentElement;
    root.lang = toHtmlLang(language);
    root.dataset.uiLanguage = language;
    window.localStorage.setItem(LANGUAGE_STORAGE_KEY, language);
    document.cookie = createPreferenceCookieString(LANGUAGE_COOKIE_NAME, language);
  }, [language]);

  const t = useCallback<PreferencesContextValue["t"]>(
    (key, fallback, params) => translate(language, key, fallback, params),
    [language]
  );

  const value = useMemo<PreferencesContextValue>(
    () => ({
      language,
      locale: toLocale(language),
      setLanguage,
      setTheme,
      t,
      theme,
    }),
    [language, t, theme]
  );

  return (
    <PreferencesContext.Provider value={value}>
      {children}
    </PreferencesContext.Provider>
  );
}

export function usePreferences() {
  const context = useContext(PreferencesContext);
  if (!context) {
    throw new Error("usePreferences must be used within a PreferencesProvider.");
  }
  return context;
}
