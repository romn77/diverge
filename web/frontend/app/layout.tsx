import type { Metadata } from "next";
import { cookies, headers } from "next/headers";
import Script from "next/script";
import { PreferencesProvider } from "@/components/PreferencesProvider";
import {
  buildPreferencesBootstrapScript,
  LANGUAGE_COOKIE_NAME,
  resolveServerLanguage,
  resolveServerTheme,
  THEME_COOKIE_NAME,
  toHtmlLang,
} from "@/lib/uiPreferences";
import "./globals.css";

export const metadata: Metadata = {
  title: "TradingAgents Report Viewer",
  description: "Browse and read analysis reports from TradingAgents",
};

export default async function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  const [cookieStore, headerStore] = await Promise.all([cookies(), headers()]);
  const themeCookie = cookieStore.get(THEME_COOKIE_NAME)?.value;
  const initialTheme = resolveServerTheme(themeCookie);
  const initialLanguage = resolveServerLanguage(
    cookieStore.get(LANGUAGE_COOKIE_NAME)?.value,
    headerStore.get("accept-language")
  );
  const preferencesBootstrapScript = buildPreferencesBootstrapScript({
    initialLanguage,
    initialTheme,
    preferSystemTheme: themeCookie !== "light" && themeCookie !== "dark",
  });

  return (
    <html
      lang={toHtmlLang(initialLanguage)}
      data-theme={initialTheme}
      data-ui-language={initialLanguage}
      style={{ colorScheme: initialTheme }}
      suppressHydrationWarning
    >
      <head>
        <script
          id="preferences-bootstrap"
          dangerouslySetInnerHTML={{ __html: preferencesBootstrapScript }}
        />
        {process.env.NODE_ENV === "development" && (
          <Script
            src="//unpkg.com/react-grab/dist/index.global.js"
            crossOrigin="anonymous"
            strategy="beforeInteractive"
          />
        )}
      </head>
      <body className="antialiased">
        <PreferencesProvider
          initialLanguage={initialLanguage}
          initialTheme={initialTheme}
        >
          {children}
        </PreferencesProvider>
      </body>
    </html>
  );
}
