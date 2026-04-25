import type { Metadata } from "next";
import { cookies, headers } from "next/headers";
import { AuthProvider } from "@/components/AuthProvider";
import { PreferencesProvider } from "@/components/PreferencesProvider";
import {
  buildPreferencesBootstrapScript,
  isTheme,
  LANGUAGE_COOKIE_NAME,
  resolveServerLanguage,
  resolveServerTheme,
  resolveServerVisualStyle,
  THEME_COOKIE_NAME,
  toColorScheme,
  toHtmlLang,
  VISUAL_STYLE_COOKIE_NAME,
} from "@/lib/uiPreferences";
import "./globals.css";
import "./stylful.css";

export const metadata: Metadata = {
  title: "Diverge Research Workbench",
  description: "Browse and read analysis reports from Diverge",
};

export default async function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  const [cookieStore, headerStore] = await Promise.all([cookies(), headers()]);
  const themeCookie = cookieStore.get(THEME_COOKIE_NAME)?.value;
  const initialTheme = resolveServerTheme(themeCookie);
  const initialVisualStyle = resolveServerVisualStyle(
    cookieStore.get(VISUAL_STYLE_COOKIE_NAME)?.value
  );
  const initialLanguage = resolveServerLanguage(
    cookieStore.get(LANGUAGE_COOKIE_NAME)?.value,
    headerStore.get("accept-language")
  );
  const preferencesBootstrapScript = buildPreferencesBootstrapScript({
    initialLanguage,
    initialTheme,
    initialVisualStyle,
    preferSystemTheme: !isTheme(themeCookie),
  });

  return (
    <html
      lang={toHtmlLang(initialLanguage)}
      data-theme={initialTheme}
      data-ui-language={initialLanguage}
      data-visual-style={initialVisualStyle}
      style={{ colorScheme: toColorScheme(initialTheme) }}
      suppressHydrationWarning
    >
      <head>
        <link rel="preconnect" href="https://fonts.googleapis.com" />
        <link rel="preconnect" href="https://fonts.gstatic.com" crossOrigin="anonymous" />
        <link
          href="https://fonts.googleapis.com/css2?family=Caveat:wght@600;700&family=DM+Sans:wght@400;500;600;700&display=swap"
          rel="stylesheet"
        />
        <script
          id="preferences-bootstrap"
          dangerouslySetInnerHTML={{ __html: preferencesBootstrapScript }}
        />
      </head>
      <body className="antialiased">
        <PreferencesProvider
          initialLanguage={initialLanguage}
          initialTheme={initialTheme}
          initialVisualStyle={initialVisualStyle}
        >
          <AuthProvider>{children}</AuthProvider>
        </PreferencesProvider>
      </body>
    </html>
  );
}
