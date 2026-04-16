"use client";

import {
  useEffect,
  useMemo,
  useRef,
  useState,
  type CSSProperties,
  type ReactNode,
} from "react";
import { usePreferences } from "@/components/PreferencesProvider";
import {
  getConfigOptions,
  type ConfigOptions,
  type Report,
  type ScreenerRunSummary,
  type ScreenerTask,
  type Task,
} from "@/lib/api";

type FocusTarget =
  | "taskQueue"
  | "screenerTaskQueue"
  | "search"
  | "screeners"
  | "recentReports"
  | "allTickers";

interface SidebarProps {
  selectedReportId: string | null;
  selectedScreenerRunId: string | null;
  selectedTradeJournal: boolean;
  onSelectReport: (reportId: string) => void;
  onSelectScreenerRun: (runId: string) => void;
  onSelectTradeJournal: () => void;
  reports: Report[];
  screenerRuns: ScreenerRunSummary[];
  loading: boolean;
  error: string | null;
  searchQuery: string;
  onSearchQueryChange: (value: string) => void;
  taskQueue: Task[];
  screenerTaskQueue: ScreenerTask[];
  activeTaskId: string | null;
  activeScreenerTaskId: string | null;
  onSelectTask: (taskId: string) => void;
  onSelectScreenerTask: (taskId: string) => void;
  onNewAnalysis: () => void;
  onNewScreener: () => void;
  newAnalysisDisabled: boolean;
  newScreenerDisabled: boolean;
  isOpen: boolean;
  onClose: () => void;
  selectedOutputLanguage: string | null;
  onOutputLanguageChange: (value: string) => void;
}

export function Sidebar({
  selectedReportId,
  selectedScreenerRunId,
  selectedTradeJournal,
  onSelectReport,
  onSelectScreenerRun,
  onSelectTradeJournal,
  reports,
  screenerRuns,
  loading,
  error,
  searchQuery,
  onSearchQueryChange,
  taskQueue,
  screenerTaskQueue,
  activeTaskId,
  activeScreenerTaskId,
  onSelectTask,
  onSelectScreenerTask,
  onNewAnalysis,
  onNewScreener,
  newAnalysisDisabled,
  newScreenerDisabled,
  isOpen,
  onClose,
  selectedOutputLanguage,
  onOutputLanguageChange,
}: SidebarProps) {
  const { language, locale, setLanguage, setTheme, t, theme } = usePreferences();
  const [tickerOverrides, setTickerOverrides] = useState<Record<string, boolean>>(
    () => ({})
  );
  const [isRecentReportsOpen, setIsRecentReportsOpen] = useState(true);
  const [isAllTickersOpen, setIsAllTickersOpen] = useState(false);
  const [isMobileViewport, setIsMobileViewport] = useState(false);
  const [isDesktopCollapsed, setIsDesktopCollapsed] = useState(false);
  const [isSettingsOpen, setIsSettingsOpen] = useState(false);
  const [settingsConfig, setSettingsConfig] = useState<ConfigOptions | null>(null);
  const [settingsLoading, setSettingsLoading] = useState(false);
  const [settingsError, setSettingsError] = useState<string | null>(null);
  const [pendingFocusTarget, setPendingFocusTarget] = useState<FocusTarget | null>(
    null
  );
  const searchInputRef = useRef<HTMLInputElement>(null);
  const taskQueueFirstButtonRef = useRef<HTMLButtonElement>(null);
  const screenerTaskFirstButtonRef = useRef<HTMLButtonElement>(null);
  const recentScreenersFirstButtonRef = useRef<HTMLButtonElement>(null);
  const recentReportsToggleRef = useRef<HTMLButtonElement>(null);
  const firstRecentReportButtonRef = useRef<HTMLButtonElement>(null);
  const allTickersToggleRef = useRef<HTMLButtonElement>(null);
  const firstTickerButtonRef = useRef<HTMLButtonElement>(null);
  const settingsTriggerRef = useRef<HTMLButtonElement>(null);
  const settingsPopoverRef = useRef<HTMLDivElement>(null);
  const settingsLanguageSelectRef = useRef<HTMLSelectElement>(null);
  const [settingsPopoverStyle, setSettingsPopoverStyle] =
    useState<CSSProperties | null>(null);

  const sortedReports = useMemo(() => {
    return [...reports].sort(
      (a, b) => parseReportTimestamp(b) - parseReportTimestamp(a)
    );
  }, [reports]);

  const filteredReports = useMemo(() => {
    if (!searchQuery.trim()) {
      return sortedReports;
    }
    const normalized = searchQuery.toLowerCase();
    return sortedReports.filter(
      (report) =>
        report.ticker.toLowerCase().includes(normalized) ||
        report.id.toLowerCase().includes(normalized)
    );
  }, [searchQuery, sortedReports]);

  const groupedByTicker = useMemo(() => {
    return filteredReports.reduce<Record<string, Report[]>>((acc, report) => {
      const ticker = report.ticker;
      if (!acc[ticker]) {
        acc[ticker] = [];
      }
      acc[ticker].push(report);
      return acc;
    }, {});
  }, [filteredReports]);

  const tickerOrder = useMemo(() => {
    return Object.entries(groupedByTicker)
      .sort(
        ([, reportsA], [, reportsB]) =>
          Math.max(...reportsB.map(parseReportTimestamp)) -
          Math.max(...reportsA.map(parseReportTimestamp))
      )
      .map(([ticker]) => ticker);
  }, [groupedByTicker]);

  const recentReports = useMemo(() => sortedReports.slice(0, 3), [sortedReports]);
  const isMobileDrawerOpen = isMobileViewport && isOpen;
  const isDesktopRail = !isMobileViewport && isDesktopCollapsed;
  const autoExpandedTicker = useMemo(() => {
    if (loading || reports.length === 0) {
      return null;
    }

    return findTickerForReport(reports, selectedReportId) ?? getMostRecentTicker(reports);
  }, [loading, reports, selectedReportId]);

  const outputLanguageOptions = settingsConfig?.output_languages ?? [];
  const selectedOutputLanguageValue =
    outputLanguageOptions.find((option) => option.value === selectedOutputLanguage)
      ?.value ??
    outputLanguageOptions[0]?.value ??
    "";

  useEffect(() => {
    const mediaQuery = window.matchMedia("(max-width: 767px)");
    const syncViewport = (event?: MediaQueryListEvent) => {
      setIsMobileViewport(event ? event.matches : mediaQuery.matches);
    };

    syncViewport();
    mediaQuery.addEventListener("change", syncViewport);
    return () => {
      mediaQuery.removeEventListener("change", syncViewport);
    };
  }, []);

  useEffect(() => {
    if (!isMobileDrawerOpen) {
      document.body.style.overflow = "";
      return;
    }

    document.body.style.overflow = "hidden";
    return () => {
      document.body.style.overflow = "";
    };
  }, [isMobileDrawerOpen]);

  useEffect(() => {
    if (!isMobileDrawerOpen || isSettingsOpen) {
      return;
    }

    const handleKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape") {
        onClose();
      }
    };

    window.addEventListener("keydown", handleKeyDown);
    return () => {
      window.removeEventListener("keydown", handleKeyDown);
    };
  }, [isMobileDrawerOpen, isSettingsOpen, onClose]);

  useEffect(() => {
    if (!isSettingsOpen) {
      return;
    }

    const handlePointerDown = (event: PointerEvent) => {
      const target = event.target;
      if (!(target instanceof Node)) {
        return;
      }
      if (settingsPopoverRef.current?.contains(target)) {
        return;
      }
      if (settingsTriggerRef.current?.contains(target)) {
        return;
      }
      setIsSettingsOpen(false);
    };

    const handleKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape") {
        closeSettingsPopover();
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
    if (isMobileDrawerOpen) {
      searchInputRef.current?.focus();
    }
  }, [isMobileDrawerOpen]);

  useEffect(() => {
    if (!isDesktopCollapsed) {
      return;
    }

    setIsSettingsOpen(false);
  }, [isDesktopCollapsed]);

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
    if (isDesktopRail || pendingFocusTarget === null) {
      return;
    }

    const targetElement =
      pendingFocusTarget === "search"
        ? searchInputRef.current
        : pendingFocusTarget === "taskQueue"
          ? taskQueueFirstButtonRef.current
          : pendingFocusTarget === "screenerTaskQueue"
            ? screenerTaskFirstButtonRef.current
            : pendingFocusTarget === "screeners"
              ? recentScreenersFirstButtonRef.current
              : pendingFocusTarget === "recentReports"
                ? firstRecentReportButtonRef.current ?? recentReportsToggleRef.current
                : pendingFocusTarget === "allTickers"
                  ? firstTickerButtonRef.current ?? allTickersToggleRef.current
                  : null;

    if (!targetElement) {
      setPendingFocusTarget(null);
      return;
    }

    const rafId = window.requestAnimationFrame(() => {
      targetElement.focus();
      setPendingFocusTarget(null);
    });

    return () => {
      window.cancelAnimationFrame(rafId);
    };
  }, [
    isAllTickersOpen,
    isDesktopRail,
    isRecentReportsOpen,
    pendingFocusTarget,
    recentReports.length,
    screenerRuns.length,
    taskQueue.length,
    screenerTaskQueue.length,
    tickerOrder.length,
  ]);

  useEffect(() => {
    if (!isSettingsOpen) {
      setSettingsPopoverStyle(null);
      return;
    }

    const updateSettingsPopoverPosition = () => {
      const trigger = settingsTriggerRef.current;
      if (!trigger) {
        return;
      }
      const panelWidth = settingsPopoverRef.current?.offsetWidth ?? 320;
      const triggerRect = trigger.getBoundingClientRect();
      const viewportPadding = 16;
      const gap = 12;
      const left = isDesktopRail
        ? Math.min(
            window.innerWidth - panelWidth - viewportPadding,
            triggerRect.right + gap
          )
        : Math.min(
            window.innerWidth - panelWidth - viewportPadding,
            Math.max(viewportPadding, triggerRect.right - panelWidth)
          );

      setSettingsPopoverStyle({
        left,
        bottom: Math.max(viewportPadding, window.innerHeight - triggerRect.top + gap),
      });
    };

    const rafId = window.requestAnimationFrame(() => {
      updateSettingsPopoverPosition();
      settingsLanguageSelectRef.current?.focus();
    });

    window.addEventListener("resize", updateSettingsPopoverPosition);
    window.addEventListener("scroll", updateSettingsPopoverPosition, true);

    return () => {
      window.cancelAnimationFrame(rafId);
      window.removeEventListener("resize", updateSettingsPopoverPosition);
      window.removeEventListener("scroll", updateSettingsPopoverPosition, true);
    };
  }, [
    isDesktopRail,
    isSettingsOpen,
    outputLanguageOptions.length,
    settingsError,
    settingsLoading,
  ]);

  const toggleTicker = (ticker: string) => {
    setTickerOverrides((current) => {
      const isExpanded = current[ticker] ?? (ticker === autoExpandedTicker);
      return {
        ...current,
        [ticker]: !isExpanded,
      };
    });
  };

  const drawerClasses = [
    "sidebar-surface fixed inset-y-0 left-0 z-50 w-full max-w-xs flex-col overflow-y-auto border-r border-[var(--border)] py-5 shadow-lg transition-[transform,width,padding] duration-300",
    isMobileDrawerOpen ? "flex translate-x-0 px-4" : "hidden -translate-x-full px-4 md:flex md:translate-x-0",
    isDesktopCollapsed ? "md:w-[5.25rem] md:max-w-none md:px-3" : "md:w-[19.2rem] md:max-w-none md:px-4",
    "md:relative md:shrink-0 md:shadow-none md:border-r-0",
  ].join(" ");

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

  const closeSettingsPopover = () => {
    setIsSettingsOpen(false);
    window.requestAnimationFrame(() => {
      settingsTriggerRef.current?.focus();
    });
  };

  const toggleSettingsPopover = () => {
    setPendingFocusTarget(null);
    setIsSettingsOpen((current) => !current);
  };

  const openBrowseTarget = (target: FocusTarget) => {
    if (target === "recentReports") {
      setIsRecentReportsOpen(true);
    }
    if (target === "allTickers") {
      setIsAllTickersOpen(true);
    }

    setPendingFocusTarget(target);

    if (isDesktopRail) {
      setIsDesktopCollapsed(false);
    }
  };

  const toggleDesktopCollapse = () => {
    if (isDesktopRail) {
      setIsDesktopCollapsed(false);
      return;
    }

    setPendingFocusTarget(null);
    setIsDesktopCollapsed(true);
  };

  return (
    <>
      {isMobileDrawerOpen && (
        <div
          className="fixed inset-0 z-40 bg-black/30 md:hidden"
          onClick={onClose}
          aria-hidden="true"
        />
      )}

      <aside
        id="report-navigation"
        className={drawerClasses}
        role={isMobileDrawerOpen ? "dialog" : undefined}
        aria-modal={isMobileDrawerOpen ? true : undefined}
        aria-label="Report navigation"
      >
        <div className="flex min-h-full flex-col">
          <div className="flex items-center justify-between gap-2 border-b border-[var(--border)] pb-4">
            <div className="flex items-center gap-2">
              <div className="grid h-9 w-9 place-items-center rounded-2xl bg-[var(--primary)] text-white shadow-sm">
                <svg viewBox="0 0 24 24" className="h-4 w-4" fill="none" aria-hidden>
                  <path
                    d="M4 16l4.2-4.2L11 14.6l8-8"
                    stroke="currentColor"
                    strokeWidth="2.2"
                    strokeLinecap="round"
                    strokeLinejoin="round"
                  />
                </svg>
              </div>
              {!isDesktopRail && (
                <div>
                  <p className="text-sm font-semibold text-slate-900">TradingAgents</p>
                  <p className="text-xs uppercase tracking-[0.3em] text-slate-500">
                    {t("sidebar.brandSubline", "Research")}
                  </p>
                </div>
              )}
            </div>

            {isMobileViewport ? (
              <button
                type="button"
                className="md:hidden rounded-2xl border border-[var(--border)] px-3 py-2 text-xs font-semibold text-slate-600 transition hover:border-[var(--primary)] hover:text-[var(--primary)]"
                onClick={onClose}
                aria-label={t("sidebar.closeSidebar", "Close sidebar")}
              >
                {t("common.close", "Close")}
              </button>
            ) : (
              <button
                type="button"
                className="interactive-button focus-ring rounded-xl p-2 text-slate-500 transition hover:bg-white/80 hover:text-[var(--primary)]"
                onClick={toggleDesktopCollapse}
                aria-label={
                  isDesktopRail
                    ? t("sidebar.expand", "Expand sidebar")
                    : t("sidebar.collapse", "Collapse sidebar")
                }
                aria-expanded={!isDesktopRail}
                title={
                  isDesktopRail
                    ? t("sidebar.expand", "Expand sidebar")
                    : t("sidebar.collapse", "Collapse sidebar")
                }
              >
                <svg
                  viewBox="0 0 16 16"
                  className={`h-4 w-4 transition-transform ${
                    isDesktopRail ? "rotate-180" : ""
                  }`}
                  fill="none"
                  aria-hidden
                >
                  <path
                    d="M9.5 3.5 5 8l4.5 4.5"
                    stroke="currentColor"
                    strokeWidth="1.8"
                    strokeLinecap="round"
                    strokeLinejoin="round"
                  />
                  <path
                    d="M13 3.5 8.5 8 13 12.5"
                    stroke="currentColor"
                    strokeWidth="1.8"
                    strokeLinecap="round"
                    strokeLinejoin="round"
                  />
                </svg>
              </button>
            )}
          </div>

          {isDesktopRail ? (
            <>
              <div className="mt-4 flex flex-col items-center gap-2">
                <RailButton
                  label="New Analysis"
                  title="New Analysis"
                  disabled={newAnalysisDisabled}
                  onClick={onNewAnalysis}
                >
                  <svg viewBox="0 0 20 20" className="h-4 w-4" fill="none" aria-hidden>
                    <path
                      d="M10 4v12M4 10h12"
                      stroke="currentColor"
                      strokeWidth="1.8"
                      strokeLinecap="round"
                    />
                  </svg>
                </RailButton>

                <RailButton
                  label="New Screener"
                  title="New Screener"
                  disabled={newScreenerDisabled}
                  onClick={onNewScreener}
                >
                  <svg viewBox="0 0 20 20" className="h-4 w-4" fill="none" aria-hidden>
                    <rect
                      x="4"
                      y="4"
                      width="12"
                      height="12"
                      rx="3"
                      stroke="currentColor"
                      strokeWidth="1.6"
                    />
                    <path
                      d="M7 10h6M10 7v6"
                      stroke="currentColor"
                      strokeWidth="1.6"
                      strokeLinecap="round"
                    />
                  </svg>
                </RailButton>

                <RailButton
                  label="Trade Journal"
                  title="Trade Journal"
                  active={selectedTradeJournal}
                  onClick={onSelectTradeJournal}
                >
                  <svg viewBox="0 0 20 20" className="h-4 w-4" fill="none" aria-hidden>
                    <path
                      d="M6 4.75h7.5A1.75 1.75 0 0 1 15.25 6.5v8.75H6A1.75 1.75 0 0 0 4.25 17V6.5A1.75 1.75 0 0 1 6 4.75Z"
                      stroke="currentColor"
                      strokeWidth="1.6"
                      strokeLinejoin="round"
                    />
                    <path
                      d="M7.5 8.25h4.5M7.5 11h4.5"
                      stroke="currentColor"
                      strokeWidth="1.6"
                      strokeLinecap="round"
                    />
                  </svg>
                </RailButton>
              </div>

              <div className="mt-6 flex flex-col items-center gap-2 border-t border-[var(--border)] pt-4">
                {taskQueue.length > 0 ? (
                  <RailButton
                    label="Task Queue"
                    title="Task Queue"
                    active={activeTaskId !== null}
                    count={taskQueue.length}
                    onClick={() => openBrowseTarget("taskQueue")}
                  >
                    <svg viewBox="0 0 20 20" className="h-4 w-4" fill="none" aria-hidden>
                      <path
                        d="M5 6.5h10M5 10h10M5 13.5h6"
                        stroke="currentColor"
                        strokeWidth="1.7"
                        strokeLinecap="round"
                      />
                    </svg>
                  </RailButton>
                ) : null}

                {screenerTaskQueue.length > 0 ? (
                  <RailButton
                    label="Screener Queue"
                    title="Screener Queue"
                    active={activeScreenerTaskId !== null}
                    count={screenerTaskQueue.length}
                    onClick={() => openBrowseTarget("screenerTaskQueue")}
                  >
                    <svg viewBox="0 0 20 20" className="h-4 w-4" fill="none" aria-hidden>
                      <path
                        d="M4.75 5.75h10.5M4.75 10h8.5M4.75 14.25h6.5"
                        stroke="currentColor"
                        strokeWidth="1.7"
                        strokeLinecap="round"
                      />
                      <circle cx="15.25" cy="14.25" r="1.5" fill="currentColor" />
                    </svg>
                  </RailButton>
                ) : null}

                <RailButton
                  label="Search reports"
                  title="Search reports"
                  active={searchQuery.trim().length > 0}
                  onClick={() => openBrowseTarget("search")}
                >
                  <svg viewBox="0 0 20 20" className="h-4 w-4" fill="currentColor" aria-hidden>
                    <path
                      fillRule="evenodd"
                      clipRule="evenodd"
                      d="M8 3a5 5 0 013.872 8.064l3.283 3.283a1 1 0 01-1.415 1.415l-3.283-3.283A5 5 0 118 3zm0 2a3 3 0 100 6 3 3 0 000-6z"
                    />
                  </svg>
                </RailButton>

                <RailButton
                  label="Recent Screeners"
                  title="Recent Screeners"
                  active={selectedScreenerRunId !== null}
                  onClick={() => openBrowseTarget("screeners")}
                >
                  <svg viewBox="0 0 20 20" className="h-4 w-4" fill="none" aria-hidden>
                    <rect
                      x="4"
                      y="4"
                      width="12"
                      height="12"
                      rx="3"
                      stroke="currentColor"
                      strokeWidth="1.6"
                    />
                    <path
                      d="M7 7.5h6M7 10h6M7 12.5h4"
                      stroke="currentColor"
                      strokeWidth="1.6"
                      strokeLinecap="round"
                    />
                  </svg>
                </RailButton>

                <RailButton
                  label="Recent Reports"
                  title="Recent Reports"
                  active={selectedReportId !== null}
                  onClick={() => openBrowseTarget("recentReports")}
                >
                  <svg viewBox="0 0 20 20" className="h-4 w-4" fill="none" aria-hidden>
                    <path
                      d="M6 4.75h8A1.75 1.75 0 0 1 15.75 6.5v7A1.75 1.75 0 0 1 14 15.25H6A1.75 1.75 0 0 1 4.25 13.5v-7A1.75 1.75 0 0 1 6 4.75Z"
                      stroke="currentColor"
                      strokeWidth="1.6"
                    />
                    <path
                      d="M7.25 8h5.5M7.25 10.75h5.5M7.25 13.5h3.5"
                      stroke="currentColor"
                      strokeWidth="1.6"
                      strokeLinecap="round"
                    />
                  </svg>
                </RailButton>

                <RailButton
                  label="All tickers"
                  title="All tickers"
                  active={selectedReportId !== null}
                  onClick={() => openBrowseTarget("allTickers")}
                >
                  <svg viewBox="0 0 20 20" className="h-4 w-4" fill="none" aria-hidden>
                    <path
                      d="M5 14.5 8.5 11l2.5 2.5 4-5"
                      stroke="currentColor"
                      strokeWidth="1.7"
                      strokeLinecap="round"
                      strokeLinejoin="round"
                    />
                    <path
                      d="M4.75 4.75h10.5v10.5H4.75z"
                      stroke="currentColor"
                      strokeWidth="1.4"
                    />
                  </svg>
                </RailButton>
              </div>

              <div className="mt-auto flex flex-col items-center gap-2 border-t border-[var(--border)] pt-4">
                <RailButton
                  label="Settings"
                  title="Settings"
                  active={isSettingsOpen}
                  buttonRef={(element) => {
                    settingsTriggerRef.current = element;
                  }}
                  onClick={toggleSettingsPopover}
                >
                  <svg viewBox="0 0 20 20" className="h-4 w-4" fill="none" aria-hidden>
                    <path
                      d="M8.2 4.75h3.6l.55 1.63 1.66.69 1.53-.64 1.8 3.11-1.2 1.14.12.9 1.08 1.36-1.8 3.11-1.67-.7-1.52.63-.55 1.68H8.2l-.55-1.68-1.52-.63-1.67.7-1.8-3.11 1.08-1.36.12-.9-1.2-1.14 1.8-3.11 1.53.64 1.66-.69.55-1.63Z"
                      stroke="currentColor"
                      strokeWidth="1.2"
                    />
                    <circle cx="10" cy="10" r="2.1" stroke="currentColor" strokeWidth="1.4" />
                  </svg>
                </RailButton>
              </div>
            </>
          ) : (
            <div className="mt-3 flex flex-1 flex-col">
              <button
                type="button"
                className={`interactive-button focus-ring flex w-full items-center justify-between rounded-[22px] border px-4 py-2.5 text-left shadow-[0_14px_28px_rgba(182,90,43,0.20)] ${
                  newAnalysisDisabled
                    ? "cursor-not-allowed border-slate-200 bg-slate-200 text-slate-500 shadow-none opacity-90"
                    : "border-[var(--primary)] bg-[var(--primary)] text-white"
                }`}
                onClick={onNewAnalysis}
                disabled={newAnalysisDisabled}
              >
                <span>
                  <span
                    className={`block text-[10px] font-semibold uppercase tracking-[0.22em] ${
                      newAnalysisDisabled ? "text-slate-500" : "text-white/80"
                    }`}
                  >
                    Launch
                  </span>
                  <span className="mt-1 block text-[13px] font-semibold">
                    New Analysis
                  </span>
                </span>
                <span className="text-[20px] font-medium leading-none">+</span>
              </button>
              {newAnalysisDisabled ? (
                <p className="mt-2 px-1 text-[11px] font-semibold uppercase tracking-[0.18em] text-slate-500">
                  Queue locked until current tasks clear
                </p>
              ) : null}

              <button
                type="button"
                className={`interactive-button focus-ring mt-3 flex w-full items-center justify-between rounded-[22px] border px-4 py-2.5 text-left shadow-[0_14px_28px_rgba(28,56,83,0.14)] ${
                  newScreenerDisabled
                    ? "cursor-not-allowed border-slate-200 bg-slate-200 text-slate-500 shadow-none opacity-90"
                    : "border-[var(--accent)] bg-[var(--accent)] text-white"
                }`}
                onClick={onNewScreener}
                disabled={newScreenerDisabled}
              >
                <span>
                  <span
                    className={`block text-[10px] font-semibold uppercase tracking-[0.22em] ${
                      newScreenerDisabled ? "text-slate-500" : "text-white/80"
                    }`}
                  >
                    Screen
                  </span>
                  <span className="mt-1 block text-[13px] font-semibold">
                    New Screener
                  </span>
                </span>
                <span className="text-[20px] font-medium leading-none">+</span>
              </button>

              <button
                type="button"
                data-active={selectedTradeJournal}
                className={`interactive-button focus-ring mt-3 flex w-full items-center justify-between rounded-[22px] border px-4 py-2.5 text-left ${
                  selectedTradeJournal
                    ? "border-[var(--primary)] bg-[var(--primary-soft)] text-[var(--primary-strong)] shadow-[0_14px_28px_rgba(182,90,43,0.16)]"
                    : "border-[var(--border)] bg-white text-slate-700 shadow-[0_14px_28px_rgba(18,28,41,0.05)]"
                }`}
                onClick={onSelectTradeJournal}
              >
                <span>
                  <span className="block text-[10px] font-semibold uppercase tracking-[0.22em] text-slate-500">
                    Manual
                  </span>
                  <span className="mt-1 block text-[13px] font-semibold">
                    Trade Journal
                  </span>
                </span>
              </button>

              {taskQueue.length > 0 ? (
                <section className="mt-5">
                  <div className="flex items-center justify-between">
                    <h3 className="text-xs font-semibold uppercase tracking-[0.35em] text-slate-500">
                      Task Queue
                    </h3>
                    <span className="text-[10px] font-semibold uppercase tracking-[0.3em] text-slate-400">
                      {taskQueue.length} active
                    </span>
                  </div>
                  <div className="mt-3 space-y-2 rounded-2xl border border-slate-100 bg-slate-50 p-2 text-sm shadow-sm">
                    {taskQueue.map((task, index) => {
                      const isActiveTask = activeTaskId === task.id;
                      const currentAgent = task.latest_progress?.current_agent;
                      return (
                        <button
                          key={task.id}
                          ref={index === 0 ? taskQueueFirstButtonRef : undefined}
                          type="button"
                          data-active={isActiveTask}
                          className={`sidebar-task-card flex w-full items-center justify-between rounded-2xl px-3 py-2.5 text-left transition ${
                            isActiveTask
                              ? "border border-[var(--accent)] bg-[var(--accent-soft)] text-slate-900 shadow-[0_10px_20px_rgba(28,56,83,0.10)]"
                              : "border border-transparent bg-white text-slate-700 hover:bg-white"
                          }`}
                          onClick={() => onSelectTask(task.id)}
                        >
                          <div className="min-w-0">
                            <p className="text-[13px] font-semibold">{task.ticker}</p>
                            <p className="mt-1 text-[10px] uppercase tracking-[0.22em] text-slate-500">
                              {task.status}
                              {currentAgent ? ` · ${currentAgent}` : ""}
                            </p>
                          </div>
                          <div className="flex items-center gap-2">
                            <span
                              className={`inline-flex rounded-full px-2 py-0.5 text-[10px] font-semibold uppercase tracking-[0.24em] ${
                                task.status === "running"
                                  ? "bg-[rgba(28,56,83,0.1)] text-[var(--accent)]"
                                  : "bg-[rgba(182,90,43,0.12)] text-[var(--primary-strong)]"
                              }`}
                            >
                              {task.status}
                            </span>
                            <svg
                              className="h-4 w-4 text-slate-400"
                              viewBox="0 0 20 20"
                              fill="none"
                              stroke="currentColor"
                              aria-hidden
                            >
                              <path
                                d="M7 6l5 4-5 4"
                                strokeWidth="1.8"
                                strokeLinecap="round"
                                strokeLinejoin="round"
                              />
                            </svg>
                          </div>
                        </button>
                      );
                    })}
                  </div>
                </section>
              ) : null}

              {screenerTaskQueue.length > 0 ? (
                <section className="mt-5">
                  <div className="flex items-center justify-between">
                    <h3 className="text-xs font-semibold uppercase tracking-[0.35em] text-slate-500">
                      Screener Queue
                    </h3>
                    <span className="text-[10px] font-semibold uppercase tracking-[0.3em] text-slate-400">
                      {screenerTaskQueue.length} active
                    </span>
                  </div>
                  <div className="mt-3 space-y-2 rounded-2xl border border-slate-100 bg-slate-50 p-2 text-sm shadow-sm">
                    {screenerTaskQueue.map((task, index) => {
                      const isActiveTask = activeScreenerTaskId === task.id;
                      return (
                        <button
                          key={task.id}
                          ref={index === 0 ? screenerTaskFirstButtonRef : undefined}
                          type="button"
                          data-active={isActiveTask}
                          className={`sidebar-task-card flex w-full items-center justify-between rounded-2xl px-3 py-2.5 text-left transition ${
                            isActiveTask
                              ? "border border-[var(--accent)] bg-[var(--accent-soft)] text-slate-900 shadow-[0_10px_20px_rgba(28,56,83,0.10)]"
                              : "border border-transparent bg-white text-slate-700 hover:bg-white"
                          }`}
                          onClick={() => onSelectScreenerTask(task.id)}
                        >
                          <div className="min-w-0">
                            <p className="text-[13px] font-semibold">Screener Run</p>
                            <p className="mt-1 text-[10px] uppercase tracking-[0.22em] text-slate-500">
                              {task.status}
                            </p>
                          </div>
                          <span className="inline-flex rounded-full bg-[rgba(28,56,83,0.1)] px-2 py-0.5 text-[10px] font-semibold uppercase tracking-[0.24em] text-[var(--accent)]">
                            {task.status}
                          </span>
                        </button>
                      );
                    })}
                  </div>
                </section>
              ) : null}

              <div className="mt-5">
                <label
                  className="text-xs font-semibold uppercase tracking-[0.25em] text-slate-500"
                  htmlFor="sidebar-search"
                >
                  Filter reports
                </label>
                <div className="relative mt-2">
                  <span className="pointer-events-none absolute inset-y-0 left-3 flex items-center text-slate-400">
                    <svg
                      className="h-4 w-4"
                      viewBox="0 0 20 20"
                      fill="currentColor"
                      aria-hidden
                    >
                      <path
                        fillRule="evenodd"
                        clipRule="evenodd"
                        d="M8 3a5 5 0 013.872 8.064l3.283 3.283a1 1 0 01-1.415 1.415l-3.283-3.283A5 5 0 118 3zm0 2a3 3 0 100 6 3 3 0 000-6z"
                      />
                    </svg>
                  </span>
                  <input
                    ref={searchInputRef}
                    id="sidebar-search"
                    type="text"
                    value={searchQuery}
                    onChange={(event) => onSearchQueryChange(event.target.value)}
                    placeholder="Ticker or report id"
                    className="focus-ring w-full rounded-2xl border border-[var(--border-strong)] bg-slate-50 py-3 pl-10 pr-12 text-sm font-medium text-slate-800 transition focus:border-[var(--primary)]"
                  />
                  {searchQuery && (
                    <button
                      type="button"
                      className="absolute right-3 top-1/2 -translate-y-1/2 rounded-full border border-[var(--border)] bg-white px-2 py-1 text-[10px] font-semibold text-slate-500 transition hover:text-[var(--primary)]"
                      onClick={() => onSearchQueryChange("")}
                    >
                      Clear
                    </button>
                  )}
                </div>
                <p className="mt-1 text-xs text-slate-500">
                  Filter by ticker or report ID.
                </p>
              </div>

              <div className="mt-6 space-y-4">
                <section>
                  <h3 className="text-xs font-semibold uppercase tracking-[0.4em] text-slate-500">
                    Recent Screeners
                  </h3>
                  <div className="mt-3 space-y-2 rounded-2xl border border-slate-100 bg-slate-50 p-2 text-sm">
                    {screenerRuns.length === 0 ? (
                      <p className="px-3 py-4 text-xs font-semibold text-slate-500">
                        No screener runs yet.
                      </p>
                    ) : (
                      screenerRuns.map((run, index) => (
                        <button
                          key={run.id}
                          ref={index === 0 ? recentScreenersFirstButtonRef : undefined}
                          type="button"
                          className={`flex w-full items-center justify-between rounded-2xl px-3 py-3 text-left transition hover:bg-white hover:text-[var(--primary)] ${
                            selectedScreenerRunId === run.id ? "text-[var(--primary)]" : ""
                          }`}
                          onClick={() => onSelectScreenerRun(run.id)}
                        >
                          <div>
                            <p className="text-sm font-semibold text-slate-900">{run.id}</p>
                            <p className="text-xs uppercase tracking-[0.3em] text-slate-500">
                              {formatReportDate(
                                {
                                  id: run.id,
                                  ticker: "",
                                  date: run.as_of_date,
                                  time: "",
                                },
                                locale,
                                t("common.unknownDate", "Unknown date")
                              )}
                            </p>
                          </div>
                          <span className="text-xs font-semibold text-slate-500">
                            {run.candidate_count}
                          </span>
                        </button>
                      ))
                    )}
                  </div>
                </section>

                <section>
                  <button
                    ref={recentReportsToggleRef}
                    type="button"
                    className="flex w-full items-center justify-between text-left"
                    onClick={() => setIsRecentReportsOpen((current) => !current)}
                    aria-expanded={isRecentReportsOpen}
                    aria-controls="recent-reports-panel"
                  >
                    <h3 className="text-xs font-semibold uppercase tracking-[0.4em] text-slate-500">
                      Recent Reports
                    </h3>
                    <div className="flex items-center gap-2">
                      <span className="text-[10px] font-semibold uppercase tracking-[0.3em] text-slate-400">
                        {recentReports.length} shown
                      </span>
                      <svg
                        className={`h-4 w-4 text-slate-400 transition-transform ${
                          isRecentReportsOpen ? "rotate-90" : ""
                        }`}
                        viewBox="0 0 20 20"
                        fill="none"
                        stroke="currentColor"
                        aria-hidden
                      >
                        <path
                          d="M7 6l5 4-5 4"
                          strokeWidth="1.8"
                          strokeLinecap="round"
                          strokeLinejoin="round"
                        />
                      </svg>
                    </div>
                  </button>
                  {isRecentReportsOpen && (
                    <div
                      id="recent-reports-panel"
                      className="mt-3 space-y-2 rounded-2xl border border-slate-100 bg-slate-50 p-2 text-sm"
                    >
                      {loading ? (
                        <p className="px-3 py-4 text-xs font-semibold text-slate-500">
                          Loading reports...
                        </p>
                      ) : recentReports.length === 0 ? (
                        <p className="px-3 py-4 text-xs font-semibold text-slate-500">
                          No reports yet.
                        </p>
                      ) : (
                        recentReports.map((report, index) => (
                          <button
                            key={report.id}
                            ref={index === 0 ? firstRecentReportButtonRef : undefined}
                            type="button"
                            className="flex w-full items-center justify-between rounded-2xl px-3 py-3 text-left transition hover:bg-white hover:text-[var(--primary)]"
                            onClick={() => onSelectReport(report.id)}
                          >
                            <div>
                              <p className="text-sm font-semibold text-slate-900">
                                {report.ticker}
                              </p>
                              <p className="text-xs uppercase tracking-[0.3em] text-slate-500">
                                {formatReportDate(
                                  report,
                                  locale,
                                  t("common.unknownDate", "Unknown date")
                                )}
                              </p>
                            </div>
                            <svg
                              className="h-4 w-4 text-slate-400"
                              viewBox="0 0 20 20"
                              fill="none"
                              stroke="currentColor"
                              aria-hidden
                            >
                              <path
                                d="M7 6l5 4-5 4"
                                strokeWidth="1.8"
                                strokeLinecap="round"
                                strokeLinejoin="round"
                              />
                            </svg>
                          </button>
                        ))
                      )}
                    </div>
                  )}
                </section>

                <section>
                  <button
                    ref={allTickersToggleRef}
                    type="button"
                    className="flex w-full items-center justify-between text-left"
                    onClick={() => setIsAllTickersOpen((current) => !current)}
                    aria-expanded={isAllTickersOpen}
                    aria-controls="all-tickers-panel"
                  >
                    <h3 className="text-xs font-semibold uppercase tracking-[0.35em] text-slate-500">
                      All tickers
                    </h3>
                    <svg
                      className={`h-4 w-4 text-slate-400 transition-transform ${
                        isAllTickersOpen ? "rotate-90" : ""
                      }`}
                      viewBox="0 0 20 20"
                      fill="none"
                      stroke="currentColor"
                      aria-hidden
                    >
                      <path
                        d="M7 6l5 4-5 4"
                        strokeWidth="1.8"
                        strokeLinecap="round"
                        strokeLinejoin="round"
                      />
                    </svg>
                  </button>
                  {isAllTickersOpen && (
                    <div id="all-tickers-panel" className="mt-3 space-y-3">
                      {tickerOrder.length === 0 ? (
                        <p className="text-xs font-semibold text-slate-500">
                          No tickers match the current filter.
                        </p>
                      ) : (
                        tickerOrder.map((ticker) => {
                          const isExpanded =
                            tickerOverrides[ticker] ?? (ticker === autoExpandedTicker);
                          const panelId = `ticker-panel-${ticker}`;

                          return (
                            <div
                              key={ticker}
                              className="rounded-2xl border border-[var(--border)] bg-white/80"
                            >
                              <button
                                ref={
                                  ticker === tickerOrder[0] ? firstTickerButtonRef : undefined
                                }
                                type="button"
                                onClick={() => toggleTicker(ticker)}
                                className="flex h-[44px] w-full items-center justify-between px-3 py-2 text-sm font-semibold text-slate-800 transition hover:bg-slate-50"
                                aria-expanded={isExpanded}
                                aria-controls={panelId}
                              >
                                <span>{ticker}</span>
                                <svg
                                  className={`h-4 w-4 text-slate-500 transition-transform ${
                                    isExpanded ? "rotate-90" : ""
                                  }`}
                                  viewBox="0 0 20 20"
                                  fill="none"
                                  stroke="currentColor"
                                  aria-hidden
                                >
                                  <path
                                    d="M7 6l5 4-5 4"
                                    strokeWidth="1.8"
                                    strokeLinecap="round"
                                    strokeLinejoin="round"
                                  />
                                </svg>
                              </button>
                              {isExpanded && (
                                <div
                                  id={panelId}
                                  className="flex flex-col gap-1 border-t border-[var(--border)] px-1.5 py-2"
                                >
                                  {groupedByTicker[ticker].map((report) => (
                                    <button
                                      key={report.id}
                                      type="button"
                                      className={`flex min-h-[44px] w-full items-center justify-between rounded-xl px-3 text-sm transition hover:bg-slate-100 ${
                                        selectedReportId === report.id
                                          ? "text-[var(--primary)]"
                                          : "text-slate-600"
                                      }`}
                                      onClick={() => onSelectReport(report.id)}
                                      aria-current={
                                        selectedReportId === report.id
                                          ? "true"
                                          : undefined
                                      }
                                    >
                                      <div>
                                        <p className="font-medium">
                                          {report.date ??
                                            t("common.unknownDate", "Unknown date")}
                                        </p>
                                        <p className="text-[11px] text-slate-500">
                                          {report.time ?? "--:--:--"}
                                        </p>
                                      </div>
                                      <span className="text-[10px] font-semibold uppercase tracking-[0.3em]">
                                        {selectedReportId === report.id
                                          ? t("common.active", "Active")
                                          : t("sidebar.viewLabel", "View")}
                                      </span>
                                    </button>
                                  ))}
                                </div>
                              )}
                            </div>
                          );
                        })
                      )}
                    </div>
                  )}
                </section>

                {error ? (
                  <div className="text-xs font-semibold text-rose-600">{error}</div>
                ) : null}
              </div>

              <div className="mt-auto border-t border-[var(--border)] pt-4">
                <div className="flex justify-end">
                  <button
                    ref={settingsTriggerRef}
                    type="button"
                    className={`interactive-button focus-ring flex h-11 w-11 items-center justify-center rounded-2xl border transition ${
                      isSettingsOpen
                        ? "border-[var(--primary)] bg-[var(--primary-soft)] text-[var(--primary-strong)] shadow-[0_10px_24px_rgba(182,90,43,0.14)]"
                        : "border-[var(--border)] bg-white text-slate-600 shadow-[0_10px_24px_rgba(18,28,41,0.08)] hover:border-[var(--primary)] hover:text-[var(--primary)]"
                    }`}
                    onClick={toggleSettingsPopover}
                    aria-label={t("sidebar.openSettings", "Open settings")}
                    aria-haspopup="dialog"
                    aria-expanded={isSettingsOpen}
                    title={t("common.settings", "Settings")}
                  >
                    <svg
                      viewBox="0 0 20 20"
                      className="h-4 w-4"
                      fill="none"
                      aria-hidden
                    >
                      <path
                        d="M8.2 4.75h3.6l.55 1.63 1.66.69 1.53-.64 1.8 3.11-1.2 1.14.12.9 1.08 1.36-1.8 3.11-1.67-.7-1.52.63-.55 1.68H8.2l-.55-1.68-1.52-.63-1.67.7-1.8-3.11 1.08-1.36.12-.9-1.2-1.14 1.8-3.11 1.53.64 1.66-.69.55-1.63Z"
                        stroke="currentColor"
                        strokeWidth="1.2"
                      />
                      <circle
                        cx="10"
                        cy="10"
                        r="2.1"
                        stroke="currentColor"
                        strokeWidth="1.4"
                      />
                    </svg>
                  </button>
                </div>
              </div>
            </div>
          )}
        </div>
      </aside>

      {isSettingsOpen ? (
        <div
          ref={settingsPopoverRef}
          id="sidebar-settings-dialog"
          role="dialog"
          aria-labelledby="sidebar-settings-title"
          className="fade-in fixed z-[90] w-[20rem] max-w-[calc(100vw-2rem)] rounded-[26px] border border-[var(--border)] bg-[rgba(255,253,248,0.98)] p-4 shadow-[0_22px_48px_rgba(18,28,41,0.18)] backdrop-blur-sm"
          style={settingsPopoverStyle ?? { visibility: "hidden" }}
        >
          <div className="space-y-3">
            <div className="rounded-[24px] border border-[var(--border)] bg-[var(--surface-strong)] p-3">
              <p className="text-[10px] font-semibold uppercase tracking-[0.24em] text-slate-500">
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
                      onChange={(event) =>
                        onOutputLanguageChange(event.target.value)
                      }
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
    </>
  );
}

interface RailButtonProps {
  label: string;
  title: string;
  active?: boolean;
  disabled?: boolean;
  count?: number;
  buttonRef?: (element: HTMLButtonElement | null) => void;
  onClick: () => void;
  children: ReactNode;
}

function RailButton({
  label,
  title,
  active = false,
  disabled = false,
  count,
  buttonRef,
  onClick,
  children,
}: RailButtonProps) {
  return (
    <div className="group relative flex justify-center">
      <button
        ref={buttonRef}
        type="button"
        data-active={active}
        className={`interactive-button focus-ring relative flex h-12 w-12 items-center justify-center rounded-2xl border transition ${
          active
            ? "border-[var(--primary)] bg-[var(--primary-soft)] text-[var(--primary-strong)] shadow-[0_10px_24px_rgba(182,90,43,0.14)]"
            : disabled
              ? "cursor-not-allowed border-slate-200 bg-slate-200 text-slate-500"
              : "border-[var(--border)] bg-white text-slate-700 shadow-[0_10px_24px_rgba(18,28,41,0.08)] hover:border-[var(--primary)] hover:text-[var(--primary)]"
        }`}
        onClick={onClick}
        disabled={disabled}
        aria-label={label}
        aria-haspopup={label === "Settings" ? "dialog" : undefined}
        aria-expanded={label === "Settings" ? active : undefined}
        title={title}
      >
        {children}
        {typeof count === "number" && count > 0 ? (
          <span className="absolute -right-1 -top-1 inline-flex min-w-[1.15rem] items-center justify-center rounded-full bg-[var(--accent)] px-1.5 py-0.5 text-[10px] font-semibold text-white">
            {count}
          </span>
        ) : null}
      </button>
      <span className="pointer-events-none absolute left-full top-1/2 ml-3 -translate-y-1/2 rounded-full bg-slate-900 px-3 py-1 text-[11px] font-semibold text-white opacity-0 shadow-lg transition group-focus-within:opacity-100 group-hover:opacity-100">
        {label}
      </span>
    </div>
  );
}

function parseReportTimestamp(report: Report): number {
  if (report.date) {
    const isoLike = `${report.date}T${report.time ?? "00:00:00"}`;
    const parsed = Date.parse(isoLike);
    if (!Number.isNaN(parsed)) {
      return parsed;
    }
  }

  const fallback = Date.parse(report.id);
  if (!Number.isNaN(fallback)) {
    return fallback;
  }

  return Number.NEGATIVE_INFINITY;
}

function getMostRecentTicker(reports: Report[]): string | null {
  if (reports.length === 0) {
    return null;
  }

  const recent = reports.reduce((best, current) =>
    parseReportTimestamp(current) > parseReportTimestamp(best) ? current : best
  );
  return recent.ticker;
}

function findTickerForReport(reports: Report[], reportId: string | null): string | null {
  if (!reportId) {
    return null;
  }
  return reports.find((report) => report.id === reportId)?.ticker ?? null;
}

function formatReportDate(report: Report, locale: string, unknownDateLabel: string) {
  if (report.date && report.time) {
    const parsed = new Date(`${report.date}T${report.time}`);
    if (!Number.isNaN(parsed.getTime())) {
      return new Intl.DateTimeFormat(locale, {
        year: "numeric",
        month: "short",
        day: "numeric",
        hour: "2-digit",
        minute: "2-digit",
      }).format(parsed);
    }

    return `${report.date} · ${report.time}`;
  }
  if (report.date) {
    const parsed = new Date(`${report.date}T00:00:00`);
    if (!Number.isNaN(parsed.getTime())) {
      return new Intl.DateTimeFormat(locale, {
        year: "numeric",
        month: "short",
        day: "numeric",
      }).format(parsed);
    }

    return report.date;
  }
  return unknownDateLabel;
}
