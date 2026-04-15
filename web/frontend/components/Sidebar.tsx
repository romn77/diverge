"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import { usePreferences } from "@/components/PreferencesProvider";
import type { Report, ScreenerRunSummary, ScreenerTask, Task } from "@/lib/api";

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
}: SidebarProps) {
  const { language, locale, setLanguage, setTheme, t, theme } = usePreferences();
  const [tickerOverrides, setTickerOverrides] = useState<Record<string, boolean>>(
    () => ({})
  );
  const [isRecentReportsOpen, setIsRecentReportsOpen] = useState(true);
  const [isAllTickersOpen, setIsAllTickersOpen] = useState(false);
  const [isMobileViewport, setIsMobileViewport] = useState(false);
  const searchInputRef = useRef<HTMLInputElement>(null);

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
  const autoExpandedTicker = useMemo(() => {
    if (loading || reports.length === 0) {
      return null;
    }

    return findTickerForReport(reports, selectedReportId) ?? getMostRecentTicker(reports);
  }, [loading, reports, selectedReportId]);

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
    if (!isMobileDrawerOpen) {
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
  }, [isMobileDrawerOpen, onClose]);

  useEffect(() => {
    if (isMobileDrawerOpen) {
      searchInputRef.current?.focus();
    }
  }, [isMobileDrawerOpen]);

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
    "sidebar-surface fixed inset-y-0 left-0 z-50 w-full max-w-xs flex-col overflow-y-auto border-r border-[var(--border)] px-4 py-5 shadow-lg transition-transform duration-300",
    "hidden md:flex -translate-x-full md:translate-x-0",
    isMobileDrawerOpen ? "flex translate-x-0" : "",
    "md:relative md:w-[19.2rem] md:shadow-none md:border-r-0",
  ].join(" ");

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
        aria-label={t("sidebar.reportNavigation", "Report navigation")}
      >
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
            <div>
              <p className="text-sm font-semibold text-slate-900">TradingAgents</p>
              <p className="text-xs uppercase tracking-[0.3em] text-slate-500">
                {t("sidebar.brandSubline", "Research")}
              </p>
            </div>
          </div>
          <button
            type="button"
            className="md:hidden rounded-2xl border border-[var(--border)] px-3 py-2 text-xs font-semibold text-slate-600 transition hover:border-[var(--primary)] hover:text-[var(--primary)]"
            onClick={onClose}
            aria-label={t("sidebar.closeSidebar", "Close sidebar")}
          >
            {t("common.close", "Close")}
          </button>
        </div>

        <section className="mt-4 rounded-[24px] border border-[var(--border)] bg-[var(--surface-strong)]/80 p-3">
          <div>
            <p className="text-[10px] font-semibold uppercase tracking-[0.26em] text-slate-500">
              {t("common.interfacePreferences", "Interface Preferences")}
            </p>
            <div className="mt-3 grid gap-3">
              <div>
                <p className="text-[10px] font-semibold uppercase tracking-[0.22em] text-slate-500">
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
              <div>
                <p className="text-[10px] font-semibold uppercase tracking-[0.22em] text-slate-500">
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
            </div>
          </div>
        </section>

        <button
          type="button"
          className={`interactive-button focus-ring mt-3 flex w-full items-center justify-between rounded-[22px] border px-4 py-2.5 text-left shadow-[0_14px_28px_rgba(182,90,43,0.20)] ${
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
              {t("sidebar.launch", "Launch")}
            </span>
            <span className="mt-1 block text-[13px] font-semibold">
              {t("sidebar.newAnalysis", "New Analysis")}
            </span>
          </span>
          <span className="text-[20px] font-medium leading-none">+</span>
        </button>
        {newAnalysisDisabled ? (
          <p className="mt-2 px-1 text-[11px] font-semibold uppercase tracking-[0.18em] text-slate-500">
            {t(
              "sidebar.queueLocked",
              "Queue locked until current tasks clear"
            )}
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
              {t("sidebar.screen", "Screen")}
            </span>
            <span className="mt-1 block text-[13px] font-semibold">
              {t("sidebar.newScreener", "New Screener")}
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
              {t("sidebar.manual", "Manual")}
            </span>
            <span className="mt-1 block text-[13px] font-semibold">
              {t("sidebar.tradeJournal", "Trade Journal")}
            </span>
          </span>
        </button>

        {taskQueue.length > 0 ? (
          <section className="mt-5">
            <div className="flex items-center justify-between">
              <h3 className="text-xs font-semibold uppercase tracking-[0.35em] text-slate-500">
                {t("sidebar.taskQueue", "Task Queue")}
              </h3>
              <span className="text-[10px] font-semibold uppercase tracking-[0.3em] text-slate-400">
                {t("sidebar.activeCount", ({ count }) => `${count} active`, {
                  count: taskQueue.length,
                })}
              </span>
            </div>
            <div className="mt-3 space-y-2 rounded-2xl border border-slate-100 bg-slate-50 p-2 text-sm shadow-sm">
              {taskQueue.map((task) => {
                const isActiveTask = activeTaskId === task.id;
                const currentAgent = task.latest_progress?.current_agent;
                return (
                  <button
                    key={task.id}
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
                        {t(
                          `task.status.${task.status}`,
                          task.status
                        )}
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
                        {t(`task.status.${task.status}`, task.status)}
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
                {t("sidebar.screenerQueue", "Screener Queue")}
              </h3>
              <span className="text-[10px] font-semibold uppercase tracking-[0.3em] text-slate-400">
                {t("sidebar.activeCount", ({ count }) => `${count} active`, {
                  count: screenerTaskQueue.length,
                })}
              </span>
            </div>
            <div className="mt-3 space-y-2 rounded-2xl border border-slate-100 bg-slate-50 p-2 text-sm shadow-sm">
              {screenerTaskQueue.map((task) => {
                const isActiveTask = activeScreenerTaskId === task.id;
                return (
                  <button
                    key={task.id}
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
                      <p className="text-[13px] font-semibold">
                        {t("sidebar.screenerRun", "Screener Run")}
                      </p>
                      <p className="mt-1 text-[10px] uppercase tracking-[0.22em] text-slate-500">
                        {t(`task.status.${task.status}`, task.status)}
                      </p>
                    </div>
                    <span className="inline-flex rounded-full px-2 py-0.5 text-[10px] font-semibold uppercase tracking-[0.24em] bg-[rgba(28,56,83,0.1)] text-[var(--accent)]">
                      {t(`task.status.${task.status}`, task.status)}
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
            {t("sidebar.filterReports", "Filter reports")}
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
              placeholder={t(
                "sidebar.filterReportsPlaceholder",
                "Ticker or report id"
              )}
              className="focus-ring w-full rounded-2xl border border-[var(--border-strong)] bg-slate-50 py-3 pl-10 pr-12 text-sm font-medium text-slate-800 transition focus:border-[var(--primary)]"
            />
            {searchQuery && (
              <button
                type="button"
                className="absolute right-3 top-1/2 -translate-y-1/2 rounded-full border border-[var(--border)] bg-white px-2 py-1 text-[10px] font-semibold text-slate-500 transition hover:text-[var(--primary)]"
                onClick={() => onSearchQueryChange("")}
              >
                {t("common.clear", "Clear")}
              </button>
            )}
          </div>
          <p className="mt-1 text-xs text-slate-500">
            {t("sidebar.filterReportsHint", "Filter by ticker or report ID.")}
          </p>
        </div>

        <div className="mt-6 space-y-4">
          <section>
            <h3 className="text-xs font-semibold uppercase tracking-[0.4em] text-slate-500">
              {t("sidebar.recentScreeners", "Recent Screeners")}
            </h3>
            <div className="mt-3 space-y-2 rounded-2xl border border-slate-100 bg-slate-50 p-2 text-sm">
              {screenerRuns.length === 0 ? (
                <p className="px-3 py-4 text-xs font-semibold text-slate-500">
                  {t("sidebar.noScreenerRuns", "No screener runs yet.")}
                </p>
              ) : (
                screenerRuns.map((run) => (
                  <button
                    key={run.id}
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
                          { id: run.id, ticker: "", date: run.as_of_date, time: "" },
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
              type="button"
              className="flex w-full items-center justify-between text-left"
              onClick={() => setIsRecentReportsOpen((current) => !current)}
              aria-expanded={isRecentReportsOpen}
              aria-controls="recent-reports-panel"
            >
              <h3 className="text-xs font-semibold uppercase tracking-[0.4em] text-slate-500">
                {t("sidebar.recentReports", "Recent Reports")}
              </h3>
              <div className="flex items-center gap-2">
                <span className="text-[10px] font-semibold uppercase tracking-[0.3em] text-slate-400">
                  {t("sidebar.shownCount", ({ count }) => `${count} shown`, {
                    count: recentReports.length,
                  })}
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
                    {t("sidebar.loadingReports", "Loading reports...")}
                  </p>
                ) : recentReports.length === 0 ? (
                  <p className="px-3 py-4 text-xs font-semibold text-slate-500">
                    {t("sidebar.noReports", "No reports yet.")}
                  </p>
                ) : (
                  recentReports.map((report) => (
                    <button
                      key={report.id}
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
              type="button"
              className="flex w-full items-center justify-between text-left"
              onClick={() => setIsAllTickersOpen((current) => !current)}
              aria-expanded={isAllTickersOpen}
              aria-controls="all-tickers-panel"
            >
              <h3 className="text-xs font-semibold uppercase tracking-[0.35em] text-slate-500">
                {t("sidebar.allTickers", "All tickers")}
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
                    {t(
                      "sidebar.noTickerMatches",
                      "No tickers match the current filter."
                    )}
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
                                  selectedReportId === report.id ? "true" : undefined
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
      </aside>
    </>
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
