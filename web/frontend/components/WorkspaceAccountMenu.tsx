"use client";

import Link from "next/link";
import { useEffect, useId, useRef, useState } from "react";

import { usePreferences } from "@/components/PreferencesProvider";
import { getConfigOptions, type AuthUser, type ConfigOptions } from "@/lib/api";

interface WorkspaceAccountMenuProps {
  authEnabled: boolean;
  authUser: AuthUser | null;
  canManageUsers: boolean;
  onLogout: () => void;
  onOpenSidebar?: () => void;
  loggingOut: boolean;
  selectedOutputLanguage: string | null;
  onOutputLanguageChange: (value: string) => void;
}

export function WorkspaceAccountMenu({
  authEnabled,
  authUser,
  canManageUsers,
  onLogout,
  onOpenSidebar,
  loggingOut,
  selectedOutputLanguage,
  onOutputLanguageChange,
}: WorkspaceAccountMenuProps) {
  const { language, setLanguage, setTheme, t, theme } = usePreferences();
  const [isAccountOpen, setIsAccountOpen] = useState(false);
  const [isSettingsOpen, setIsSettingsOpen] = useState(false);
  const [settingsConfig, setSettingsConfig] = useState<ConfigOptions | null>(null);
  const [settingsLoading, setSettingsLoading] = useState(false);
  const [settingsError, setSettingsError] = useState<string | null>(null);
  const accountTriggerRef = useRef<HTMLButtonElement>(null);
  const accountPanelRef = useRef<HTMLDivElement>(null);
  const settingsTriggerRef = useRef<HTMLButtonElement>(null);
  const settingsPanelRef = useRef<HTMLDivElement>(null);
  const settingsLanguageSelectRef = useRef<HTMLSelectElement>(null);
  const menuId = useId();
  const settingsDialogId = useId();

  const outputLanguageOptions = settingsConfig?.output_languages ?? [];
  const selectedOutputLanguageValue =
    outputLanguageOptions.find((option) => option.value === selectedOutputLanguage)
      ?.value ??
    outputLanguageOptions[0]?.value ??
    "";

  useEffect(() => {
    if (!isAccountOpen && !isSettingsOpen) {
      return;
    }

    const handlePointerDown = (event: PointerEvent) => {
      const target = event.target;
      if (!(target instanceof Node)) {
        return;
      }

      if (
        accountPanelRef.current?.contains(target) ||
        accountTriggerRef.current?.contains(target) ||
        settingsPanelRef.current?.contains(target) ||
        settingsTriggerRef.current?.contains(target)
      ) {
        return;
      }

      setIsAccountOpen(false);
      setIsSettingsOpen(false);
    };

    const handleKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape") {
        setIsAccountOpen(false);
        setIsSettingsOpen(false);
      }
    };

    window.addEventListener("pointerdown", handlePointerDown);
    window.addEventListener("keydown", handleKeyDown);
    return () => {
      window.removeEventListener("pointerdown", handlePointerDown);
      window.removeEventListener("keydown", handleKeyDown);
    };
  }, [isAccountOpen, isSettingsOpen]);

  useEffect(() => {
    if (!isSettingsOpen || settingsConfig || settingsLoading) {
      return;
    }

    let isActive = true;

    const loadSettingsOptions = async () => {
      setSettingsLoading(true);
      setSettingsError(null);

      try {
        const nextConfig = await getConfigOptions();
        if (!isActive) {
          return;
        }
        setSettingsConfig(nextConfig);
      } catch (nextError) {
        if (isActive) {
          setSettingsError(
            nextError instanceof Error
              ? nextError.message
              : t("sidebar.settingsLoadError", "Unable to load sidebar settings")
          );
        }
      } finally {
        if (isActive) {
          setSettingsLoading(false);
        }
      }
    };

    void loadSettingsOptions();

    return () => {
      isActive = false;
    };
  }, [isSettingsOpen, settingsConfig, settingsLoading, t]);

  useEffect(() => {
    if (!isSettingsOpen) {
      return;
    }

    const rafId = window.requestAnimationFrame(() => {
      settingsLanguageSelectRef.current?.focus();
    });

    return () => {
      window.cancelAnimationFrame(rafId);
    };
  }, [isSettingsOpen, settingsError, settingsLoading]);

  const retrySettingsLoad = async () => {
    setSettingsLoading(true);
    setSettingsError(null);

    try {
      const nextConfig = await getConfigOptions();
      setSettingsConfig(nextConfig);
    } catch (nextError) {
      setSettingsError(
        nextError instanceof Error
          ? nextError.message
          : t("sidebar.settingsLoadError", "Unable to load sidebar settings")
      );
    } finally {
      setSettingsLoading(false);
    }
  };

  const handleSettingsToggle = () => {
    setIsAccountOpen(false);
    setIsSettingsOpen((current) => !current);
  };

  const handleAccountToggle = () => {
    setIsSettingsOpen(false);
    setIsAccountOpen((current) => !current);
  };

  const displayName = authUser?.display_name.trim() || authUser?.email || "TradingAgents";

  return (
    <>
        {onOpenSidebar ? (
          <button
            type="button"
            className="focus-ring fixed left-4 top-4 z-[56] inline-flex h-10 w-10 items-center justify-center rounded-xl border border-[var(--border)] bg-white/92 text-slate-600 shadow-[0_10px_24px_rgba(18,28,41,0.08)] transition hover:border-[var(--primary)] hover:text-[var(--primary)] md:hidden"
            aria-label={t("common.menu", "Menu")}
            onClick={onOpenSidebar}
          >
            <svg viewBox="0 0 20 20" className="h-4 w-4" fill="none" aria-hidden>
              <path
                d="M4 6h12M4 10h12M4 14h12"
                stroke="currentColor"
                strokeWidth="1.7"
                strokeLinecap="round"
              />
            </svg>
          </button>
        ) : null}

        <header className="fixed right-4 top-4 z-[55]">
          <div className="relative inline-flex items-center gap-1.5 rounded-full border border-[rgba(150,118,99,0.18)] bg-[rgba(255,248,243,0.88)] p-1 shadow-[0_8px_22px_rgba(34,26,15,0.04)] backdrop-blur-xl">
          <button
            ref={accountTriggerRef}
            type="button"
            aria-haspopup="menu"
            aria-expanded={isAccountOpen}
            aria-controls={menuId}
            className="focus-ring rounded-full border border-[var(--border)] bg-white/92 p-1 text-left shadow-[0_10px_22px_rgba(18,28,41,0.08)] backdrop-blur transition hover:border-[var(--primary)] hover:shadow-[0_14px_30px_rgba(18,28,41,0.12)]"
            onClick={handleAccountToggle}
            title={displayName}
          >
            <div className="grid h-8 w-8 place-items-center rounded-full bg-[var(--primary-soft)] text-[11px] font-semibold text-[var(--primary-strong)]">
              {authEnabled && authUser
                ? getUserInitials(authUser.display_name, authUser.email)
                : "TA"}
            </div>
          </button>

          <button
            ref={settingsTriggerRef}
            type="button"
            aria-label={t("common.settings", "Settings")}
            aria-haspopup="dialog"
            aria-expanded={isSettingsOpen}
            aria-controls={settingsDialogId}
            className={`focus-ring flex h-8 w-8 items-center justify-center rounded-full border transition ${
              isSettingsOpen
                ? "border-[var(--primary)] bg-[var(--primary-soft)] text-[var(--primary-strong)] shadow-[0_10px_24px_rgba(182,90,43,0.14)]"
                : "border-[var(--border)] bg-white/92 text-slate-600 shadow-[0_10px_24px_rgba(18,28,41,0.08)] hover:border-[var(--primary)] hover:text-[var(--primary)]"
            }`}
            onClick={handleSettingsToggle}
            title={t("common.settings", "Settings")}
          >
            <svg viewBox="0 0 20 20" className="h-4 w-4" fill="none" aria-hidden>
              <path
                d="M8.2 4.75h3.6l.55 1.63 1.66.69 1.53-.64 1.8 3.11-1.2 1.14.12.9 1.08 1.36-1.8 3.11-1.67-.7-1.52.63-.55 1.68H8.2l-.55-1.68-1.52-.63-1.67.7-1.8-3.11 1.08-1.36.12-.9-1.2-1.14 1.8-3.11 1.53.64 1.66-.69.55-1.63Z"
                stroke="currentColor"
                strokeWidth="1.2"
              />
              <circle cx="10" cy="10" r="2.1" stroke="currentColor" strokeWidth="1.4" />
            </svg>
          </button>

          {isSettingsOpen ? (
            <div
              id={settingsDialogId}
              ref={settingsPanelRef}
              role="dialog"
              aria-labelledby="workspace-settings-title"
              className="absolute right-0 top-full mt-2 w-[18rem] max-w-[calc(100vw-2rem)] rounded-[24px] border border-[var(--border)] bg-[rgba(255,253,248,0.98)] p-3 shadow-[0_22px_48px_rgba(18,28,41,0.18)] backdrop-blur-sm"
            >
              <div className="space-y-3">
                <div className="rounded-[24px] border border-[var(--border)] bg-[var(--surface-strong)] p-3">
                  <p
                    id="workspace-settings-title"
                    className="text-[10px] font-semibold uppercase tracking-[0.24em] text-slate-500"
                  >
                    {t("common.interfacePreferences", "Interface Preferences")}
                  </p>
                  <div className="mt-3 space-y-3">
                    <div className="rounded-[22px] border border-[var(--border)] bg-white/80 p-3">
                      <p className="text-[10px] font-semibold uppercase tracking-[0.24em] text-slate-500">
                        {t("preferences.themeLabel", "Theme")}
                      </p>
                      <div className="mt-2 flex gap-2">
                        {(["light", "dark"] as const).map((themeValue) => (
                          <button
                            key={themeValue}
                            type="button"
                            data-active={theme === themeValue}
                            className="pill-tab inline-flex flex-1 items-center justify-center px-3 py-2 text-center"
                            onClick={() => setTheme(themeValue)}
                          >
                            {themeValue === "light"
                              ? t("common.light", "Light")
                              : t("common.dark", "Dark")}
                          </button>
                        ))}
                      </div>
                    </div>

                    <div className="rounded-[22px] border border-[var(--border)] bg-white/80 p-3">
                      <p className="text-[10px] font-semibold uppercase tracking-[0.24em] text-slate-500">
                        {t("preferences.languageLabel", "UI Language")}
                      </p>
                      <div className="mt-2 flex gap-2">
                        {(["en", "zh"] as const).map((languageValue) => (
                          <button
                            key={languageValue}
                            type="button"
                            data-active={language === languageValue}
                            className="pill-tab inline-flex flex-1 items-center justify-center px-3 py-2 text-center"
                            onClick={() => setLanguage(languageValue)}
                          >
                            {languageValue === "en"
                              ? t("common.english", "English")
                              : t("common.chinese", "中文")}
                          </button>
                        ))}
                      </div>
                    </div>

                    {settingsError ? (
                      <div className="rounded-[20px] border border-[rgba(163,53,53,0.2)] bg-[rgba(163,53,53,0.08)] px-4 py-4 text-sm text-[var(--danger)]">
                        <p>{settingsError}</p>
                        <button
                          type="button"
                          className="focus-ring mt-3 rounded-full border border-current px-3 py-1 text-xs font-semibold uppercase tracking-[0.18em]"
                          onClick={() => void retrySettingsLoad()}
                        >
                          {t("sidebar.retry", "Retry")}
                        </button>
                      </div>
                    ) : !settingsLoading && outputLanguageOptions.length === 0 ? (
                      <div className="rounded-[20px] border border-dashed border-[var(--border)] bg-white/80 px-4 py-4 text-sm text-slate-600">
                        {t(
                          "sidebar.noOutputLanguages",
                          "No output languages available."
                        )}
                      </div>
                    ) : !settingsLoading ? (
                      <label className="block rounded-[22px] border border-[var(--border)] bg-white/80 p-3">
                        <span className="text-[10px] font-semibold uppercase tracking-[0.24em] text-slate-500">
                          {t("analysis.outputLanguage", "Output Language")}
                        </span>
                        <select
                          ref={settingsLanguageSelectRef}
                          value={selectedOutputLanguageValue}
                          onChange={(event) => onOutputLanguageChange(event.target.value)}
                          className="focus-ring mt-2 w-full rounded-2xl border border-[var(--border)] bg-[var(--surface-strong)] px-4 py-3 text-sm font-semibold text-slate-900"
                        >
                          {outputLanguageOptions.map((languageOption) => (
                            <option
                              key={languageOption.value}
                              value={languageOption.value}
                            >
                              {languageOption.label}
                            </option>
                          ))}
                        </select>
                        <p className="mt-2 text-xs leading-5 text-slate-500">
                          {t(
                            "sidebar.outputLanguageHint",
                            "New analysis forms start with this output language by default."
                          )}
                        </p>
                      </label>
                    ) : null}
                  </div>
                </div>
              </div>
            </div>
          ) : null}

          {isAccountOpen ? (
            <div
              id={menuId}
              ref={accountPanelRef}
              role="menu"
              className="absolute right-[2.75rem] top-full mt-2 w-[17rem] rounded-[24px] border border-[var(--border)] bg-white/96 p-3 shadow-[0_24px_64px_rgba(18,28,41,0.16)] backdrop-blur"
            >
              {authEnabled ? (
                authUser ? (
                  <>
                    <div className="flex items-start gap-3">
                      <div className="grid h-10 w-10 place-items-center rounded-2xl bg-[var(--primary-soft)] text-sm font-semibold text-[var(--primary-strong)]">
                        {getUserInitials(authUser.display_name, authUser.email)}
                      </div>
                      <div className="min-w-0 flex-1">
                        <p className="text-[10px] font-semibold uppercase tracking-[0.28em] text-slate-500">
                          {t("workspace.access", "Workspace Access")}
                        </p>
                        <p className="mt-1 truncate text-sm font-semibold text-slate-900">
                          {displayName}
                        </p>
                        <p className="truncate text-xs text-slate-500">{authUser.email}</p>
                      </div>
                      <span className="rounded-full border border-[var(--border)] bg-[var(--surface-strong)] px-2.5 py-1 text-[10px] font-semibold uppercase tracking-[0.18em] text-slate-600">
                        {authUser.role}
                      </span>
                    </div>

                    {authUser.must_change_password ? (
                      <p className="mt-4 rounded-2xl border border-[rgba(163,53,53,0.18)] bg-[rgba(163,53,53,0.08)] px-3 py-2 text-xs font-medium leading-5 text-[var(--danger)]">
                        {t(
                          "workspace.passwordResetRequired",
                          "Password reset required on the next credentials update."
                        )}
                      </p>
                    ) : null}

                    <div className="mt-4 flex justify-end gap-2">
                      {canManageUsers ? (
                        <Link
                          href="/admin/users"
                          role="menuitem"
                          className="focus-ring inline-flex items-center rounded-full border border-[var(--primary)] bg-[var(--primary)] px-3 py-2 text-[11px] font-semibold uppercase tracking-[0.18em] text-white"
                          onClick={() => setIsAccountOpen(false)}
                        >
                          {t("workspace.adminConsole", "Admin Console")}
                        </Link>
                      ) : null}
                      <button
                        type="button"
                        role="menuitem"
                        className="focus-ring inline-flex items-center rounded-full border border-[var(--border-strong)] bg-white px-3 py-2 text-[11px] font-semibold uppercase tracking-[0.18em] text-slate-700"
                        onClick={onLogout}
                        disabled={loggingOut}
                      >
                        {loggingOut
                          ? t("workspace.signingOut", "Signing Out")
                          : t("workspace.signOut", "Sign Out")}
                      </button>
                    </div>
                  </>
                ) : (
                  <div className="rounded-[20px] border border-dashed border-[var(--border)] bg-[var(--surface-strong)] px-4 py-4 text-sm text-slate-600">
                    {t("workspace.syncing", "Session details are still syncing.")}
                  </div>
                )
              ) : (
                <div className="rounded-[20px] border border-dashed border-[var(--border)] bg-[var(--surface-strong)] px-4 py-4 text-sm text-slate-600">
                  <p className="text-[10px] font-semibold uppercase tracking-[0.28em] text-slate-500">
                    {t("workspace.openMode", "Open Workspace")}
                  </p>
                  <p className="mt-2 leading-6">
                    {t(
                      "workspace.openModeHint",
                      "Auth is disabled for this environment."
                    )}
                  </p>
                </div>
              )}
            </div>
          ) : null}
          </div>
        </header>
    </>
  );
}

function getUserInitials(displayName: string, email: string): string {
  const source = displayName.trim() || email.trim();
  if (!source) {
    return "TA";
  }

  const words = source.split(/\s+/).filter(Boolean);
  if (words.length >= 2) {
    return `${words[0][0]}${words[1][0]}`.toUpperCase();
  }

  return source.slice(0, 2).toUpperCase();
}
