"use client";

import Link from "next/link";
import { useEffect, useId, useRef, useState } from "react";

import { usePreferences } from "@/components/PreferencesProvider";
import { Button } from "@/components/ui/button";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
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
  const {
    language,
    setLanguage,
    setTheme,
    setVisualStyle,
    t,
    theme,
    visualStyle,
  } = usePreferences();
  const [isAccountOpen, setIsAccountOpen] = useState(false);
  const [isSettingsOpen, setIsSettingsOpen] = useState(false);
  const [settingsConfig, setSettingsConfig] = useState<ConfigOptions | null>(null);
  const [settingsLoading, setSettingsLoading] = useState(false);
  const [settingsError, setSettingsError] = useState<string | null>(null);
  const settingsTriggerRef = useRef<HTMLButtonElement>(null);
  const settingsPanelRef = useRef<HTMLDivElement>(null);
  const settingsDialogId = useId();

  const outputLanguageOptions = settingsConfig?.output_languages ?? [];
  const selectedOutputLanguageValue =
    outputLanguageOptions.find((option) => option.value === selectedOutputLanguage)
      ?.value ??
    outputLanguageOptions[0]?.value ??
    "";

  useEffect(() => {
    if (!isSettingsOpen) {
      return;
    }

    const handlePointerDown = (event: PointerEvent) => {
      const target = event.target;
      if (!(target instanceof Node)) {
        return;
      }

      if (settingsPanelRef.current?.contains(target) || settingsTriggerRef.current?.contains(target)) {
        return;
      }

      setIsSettingsOpen(false);
    };

    const handleKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape") {
        setIsSettingsOpen(false);
      }
    };

    window.addEventListener("pointerdown", handlePointerDown);
    window.addEventListener("keydown", handleKeyDown);
    return () => {
      window.removeEventListener("pointerdown", handlePointerDown);
      window.removeEventListener("keydown", handleKeyDown);
    };
  }, [isSettingsOpen]);

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

  const displayName = authUser?.display_name.trim() || authUser?.email || "Diverge";

  return (
    <div className="workbench-account-menu pointer-events-auto relative z-[var(--z-sidebar)] ml-auto flex shrink-0 items-center gap-2">
      {onOpenSidebar ? (
        <Button
          type="button"
          variant="secondary"
          size="icon"
          className="rounded-xl md:hidden"
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
        </Button>
      ) : null}

        <div className="relative inline-flex items-center gap-1.5 rounded-full border border-[var(--border)] bg-[var(--popover)] p-1 shadow-[0_8px_22px_rgba(34,26,15,0.04)] backdrop-blur-xl">
          <DropdownMenu
            open={isAccountOpen}
            onOpenChange={(open) => {
              setIsSettingsOpen(false);
              setIsAccountOpen(open);
            }}
          >
            <DropdownMenuTrigger asChild>
              <Button
                type="button"
                variant="secondary"
                size="icon"
                className="size-10 rounded-full border-[var(--border)] p-1"
                title={displayName}
              >
                <div className="grid h-8 w-8 place-items-center rounded-full bg-[var(--primary-soft)] text-[11px] font-semibold text-[var(--primary-strong)]">
                  {authEnabled && authUser
                    ? getUserInitials(authUser.display_name, authUser.email)
                    : "DV"}
                </div>
              </Button>
            </DropdownMenuTrigger>
            <DropdownMenuContent className="mr-12 w-[17rem]">
              {authEnabled ? (
                authUser ? (
                  <>
                    <div className="flex items-start gap-3 rounded-[20px] bg-[var(--surface-strong)]/70 px-3 py-3">
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
                    </div>

                    <div className="mt-3 flex items-center justify-between gap-3 px-1">
                      <span className="rounded-full border border-[var(--border)] bg-[var(--surface-strong)] px-2.5 py-1 text-[10px] font-semibold uppercase tracking-[0.18em] text-slate-600">
                        {authUser.role}
                      </span>
                      {authUser.must_change_password ? (
                        <span className="rounded-full border border-[rgba(163,53,53,0.18)] bg-[rgba(163,53,53,0.08)] px-2.5 py-1 text-[10px] font-semibold uppercase tracking-[0.18em] text-[var(--danger)]">
                          {t("workspace.resetRequired", "Reset required")}
                        </span>
                      ) : null}
                    </div>

                    <div className="mt-4 flex flex-wrap justify-end gap-2">
                      {canManageUsers ? (
                        <Button asChild size="sm" onClick={() => setIsAccountOpen(false)}>
                          <Link href="/admin/users">
                            {t("workspace.adminConsole", "Admin Console")}
                          </Link>
                        </Button>
                      ) : null}
                      <Button
                        type="button"
                        variant="secondary"
                        size="sm"
                        onClick={onLogout}
                        disabled={loggingOut}
                      >
                        {loggingOut
                          ? t("workspace.signingOut", "Signing Out")
                          : t("workspace.signOut", "Sign Out")}
                      </Button>
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
            </DropdownMenuContent>
          </DropdownMenu>

          <Button
            ref={settingsTriggerRef}
            type="button"
            aria-label={t("common.settings", "Settings")}
            aria-haspopup="dialog"
            aria-expanded={isSettingsOpen}
            aria-controls={settingsDialogId}
            variant="secondary"
            size="icon"
              className={`rounded-full ${
                isSettingsOpen
                  ? "border-[var(--primary)] bg-[var(--primary-soft)] text-[var(--primary-strong)] shadow-[var(--button-primary-shadow)]"
                : "text-[var(--muted)]"
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
          </Button>

          {isSettingsOpen ? (
            <div
              id={settingsDialogId}
              ref={settingsPanelRef}
              role="dialog"
              aria-labelledby="workspace-settings-title"
              className="absolute right-0 top-full mt-2 w-[18rem] max-w-[calc(100vw-2rem)] rounded-[24px] border border-[var(--border)] bg-[var(--popover)] p-3 shadow-[0_22px_48px_rgba(18,28,41,0.18)] backdrop-blur-sm"
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
                    <div className="rounded-[22px] border border-[var(--border)] bg-[var(--surface)] p-3">
                      <p className="text-[10px] font-semibold uppercase tracking-[0.24em] text-slate-500">
                        {t("preferences.themeLabel", "Theme")}
                      </p>
                      <div className="mt-2 grid grid-cols-2 gap-2">
                        {(["light", "dark", "proof", "everforest"] as const).map((themeValue) => (
                          <Button
                            key={themeValue}
                            type="button"
                            variant={theme === themeValue ? "default" : "secondary"}
                            size="sm"
                            data-active={theme === themeValue}
                            className="pill-tab flex-1 justify-center px-3 py-2 text-center"
                            onClick={() => setTheme(themeValue)}
                          >
                            {themeValue === "light"
                              ? t("common.light", "Light")
                              : themeValue === "dark"
                                ? t("common.dark", "Dark")
                                : themeValue === "proof"
                                  ? t("common.proof", "Proof")
                                  : t("common.everforest", "Everforest")}
                          </Button>
                        ))}
                      </div>
                    </div>

                    <div className="rounded-[22px] border border-[var(--border)] bg-[var(--surface)] p-3">
                      <p className="text-[10px] font-semibold uppercase tracking-[0.24em] text-slate-500">
                        {t("preferences.languageLabel", "UI Language")}
                      </p>
                      <div className="mt-2 flex gap-2">
                        {(["en", "zh"] as const).map((languageValue) => (
                          <Button
                            key={languageValue}
                            type="button"
                            variant={language === languageValue ? "default" : "secondary"}
                            size="sm"
                            data-active={language === languageValue}
                            className="pill-tab flex-1 justify-center px-3 py-2 text-center"
                            onClick={() => setLanguage(languageValue)}
                          >
                            {languageValue === "en"
                              ? t("common.english", "English")
                              : t("common.chinese", "中文")}
                          </Button>
                        ))}
                      </div>
                    </div>

                    <div className="rounded-[22px] border border-[var(--border)] bg-[var(--surface)] p-3">
                      <p className="text-[10px] font-semibold uppercase tracking-[0.24em] text-slate-500">
                        {t("preferences.visualStyleLabel", "Visual Style")}
                      </p>
                      <div className="mt-2 flex gap-2">
                        {(["normal", "stylful"] as const).map((styleValue) => (
                          <Button
                            key={styleValue}
                            type="button"
                            variant={visualStyle === styleValue ? "default" : "secondary"}
                            size="sm"
                            data-active={visualStyle === styleValue}
                            className="pill-tab flex-1 justify-center px-3 py-2 text-center"
                            onClick={() => setVisualStyle(styleValue)}
                          >
                            {styleValue === "normal"
                              ? t("common.normal", "Normal")
                              : t("common.stylful", "Stylful")}
                          </Button>
                        ))}
                      </div>
                    </div>

                    {settingsError ? (
                      <div className="rounded-[20px] border border-[rgba(163,53,53,0.2)] bg-[rgba(163,53,53,0.08)] px-4 py-4 text-sm text-[var(--danger)]">
                        <p>{settingsError}</p>
                        <Button
                          type="button"
                          variant="outline"
                          size="sm"
                          className="mt-3 border-current text-current hover:bg-transparent hover:text-current"
                          onClick={() => void retrySettingsLoad()}
                        >
                          {t("sidebar.retry", "Retry")}
                        </Button>
                      </div>
                    ) : !settingsLoading && outputLanguageOptions.length === 0 ? (
                      <div className="rounded-[20px] border border-dashed border-[var(--border)] bg-[var(--surface)] px-4 py-4 text-sm text-slate-600">
                        {t(
                          "sidebar.noOutputLanguages",
                          "No output languages available."
                        )}
                      </div>
                    ) : !settingsLoading ? (
                      <label className="block rounded-[22px] border border-[var(--border)] bg-[var(--surface)] p-3">
                        <span className="text-[10px] font-semibold uppercase tracking-[0.24em] text-slate-500">
                          {t("analysis.outputLanguage", "Output Language")}
                        </span>
                        <Select
                          value={selectedOutputLanguageValue}
                          onValueChange={onOutputLanguageChange}
                        >
                          <SelectTrigger className="mt-2 border-[var(--border)] bg-[var(--surface-strong)] font-semibold text-slate-900">
                            <SelectValue placeholder={t("analysis.outputLanguage", "Output Language")} />
                          </SelectTrigger>
                          <SelectContent>
                          {outputLanguageOptions.map((languageOption) => (
                            <SelectItem
                              key={languageOption.value}
                              value={languageOption.value}
                            >
                              {t(
                                `analysis.outputLanguage.${languageOption.value}`,
                                languageOption.label
                              )}
                            </SelectItem>
                          ))}
                          </SelectContent>
                        </Select>
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
        </div>
    </div>
  );
}

function getUserInitials(displayName: string, email: string): string {
  const source = displayName.trim() || email.trim();
  if (!source) {
    return "DV";
  }

  const words = source.split(/\s+/).filter(Boolean);
  if (words.length >= 2) {
    return `${words[0][0]}${words[1][0]}`.toUpperCase();
  }

  return source.slice(0, 2).toUpperCase();
}
