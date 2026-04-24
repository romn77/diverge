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
  isVisualStyle,
  LANGUAGE_COOKIE_NAME,
  LANGUAGE_STORAGE_KEY,
  THEME_COOKIE_NAME,
  THEME_STORAGE_KEY,
  toColorScheme,
  toHtmlLang,
  toLocale,
  translate,
  VISUAL_STYLE_COOKIE_NAME,
  VISUAL_STYLE_STORAGE_KEY,
  type Language,
  type Theme,
  type TranslationParams,
  type TranslationTemplate,
  type VisualStyle,
} from "@/lib/uiPreferences";

interface PreferencesContextValue {
  language: Language;
  locale: string;
  setLanguage: (language: Language) => void;
  setTheme: (theme: Theme) => void;
  setVisualStyle: (visualStyle: VisualStyle) => void;
  t: (
    key: string,
    fallback: TranslationTemplate,
    params?: TranslationParams
  ) => string;
  theme: Theme;
  visualStyle: VisualStyle;
}

const PreferencesContext = createContext<PreferencesContextValue | null>(null);

export function PreferencesProvider({
  children,
  initialLanguage,
  initialTheme,
  initialVisualStyle,
}: {
  children: ReactNode;
  initialLanguage: Language;
  initialTheme: Theme;
  initialVisualStyle: VisualStyle;
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
  const [visualStyle, setVisualStyle] = useState<VisualStyle>(() => {
    if (typeof document !== "undefined") {
      const nextVisualStyle = document.documentElement.dataset.visualStyle;
      if (isVisualStyle(nextVisualStyle)) {
        return nextVisualStyle;
      }
    }
    return initialVisualStyle;
  });

  useEffect(() => {
    const root = document.documentElement;
    root.dataset.theme = theme;
    root.style.colorScheme = toColorScheme(theme);
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

  useEffect(() => {
    const root = document.documentElement;
    root.dataset.visualStyle = visualStyle;
    window.localStorage.setItem(VISUAL_STYLE_STORAGE_KEY, visualStyle);
    document.cookie = createPreferenceCookieString(
      VISUAL_STYLE_COOKIE_NAME,
      visualStyle
    );
  }, [visualStyle]);

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
      setVisualStyle,
      t,
      theme,
      visualStyle,
    }),
    [language, t, theme, visualStyle]
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
