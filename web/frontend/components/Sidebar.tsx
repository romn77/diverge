"use client";

import Link from "next/link";
import {
  type FormEvent,
  type ReactNode,
  startTransition,
  useEffect,
  useRef,
  useState,
} from "react";
import { usePathname, useRouter, useSearchParams } from "next/navigation";
import { usePreferences } from "@/components/PreferencesProvider";
import { useWorkbench } from "@/components/WorkbenchProvider";
import {
  buildHomeHref,
  buildJournalHref,
  buildReportHref,
  buildScreenerRunHref,
  buildScreenerTaskHref,
  buildTaskHref,
} from "@/lib/workbenchRoutes";

type FocusTarget =
  | "taskQueue"
  | "screenerTaskQueue"
  | "search"
  | "screeners"
  | "recentReports"
  | "allTickers";

interface SidebarProps {
  isOpen: boolean;
  onClose: () => void;
  onNewAnalysis: () => void;
  onNewScreener: () => void;
}

export function Sidebar({
  isOpen,
  onClose,
  onNewAnalysis,
  onNewScreener,
}: SidebarProps) {
  const pathname = usePathname();
  const router = useRouter();
  const searchParams = useSearchParams();
  const { locale, t } = usePreferences();
  const {
    activeScreenerTasks,
    activeTasks,
    loadingReports,
    newAnalysisDisabled,
    newScreenerDisabled,
    recentReports,
    reportsByTicker,
    reportsError,
    screenerRuns,
  } = useWorkbench();
  const [searchQuery, setSearchQuery] = useState(searchParams.get("q") ?? "");
  const [isRecentReportsOpen, setIsRecentReportsOpen] = useState(true);
  const [isAllTickersOpen, setIsAllTickersOpen] = useState(false);
  const [isMobileViewport, setIsMobileViewport] = useState(false);
  const [isDesktopCollapsed, setIsDesktopCollapsed] = useState(false);
  const [pendingFocusTarget, setPendingFocusTarget] = useState<FocusTarget | null>(
    null
  );
  const searchInputRef = useRef<HTMLInputElement>(null);
  const taskQueueFirstButtonRef = useRef<HTMLAnchorElement>(null);
  const screenerTaskFirstButtonRef = useRef<HTMLAnchorElement>(null);
  const recentScreenersFirstButtonRef = useRef<HTMLAnchorElement>(null);
  const recentReportsToggleRef = useRef<HTMLButtonElement>(null);
  const firstRecentReportButtonRef = useRef<HTMLAnchorElement>(null);
  const allTickersToggleRef = useRef<HTMLButtonElement>(null);
  const firstTickerButtonRef = useRef<HTMLAnchorElement>(null);

  useEffect(() => {
    setSearchQuery(searchParams.get("q") ?? "");
  }, [searchParams]);

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

  const isMobileDrawerOpen = isMobileViewport && isOpen;
  const isDesktopRail = !isMobileViewport && isDesktopCollapsed;

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
    reportsByTicker.length,
    screenerRuns.length,
    activeTasks.length,
    activeScreenerTasks.length,
  ]);

  const drawerClasses = [
    "sidebar-surface fixed left-0 top-0 bottom-0 z-50 w-full max-w-xs flex-col overflow-y-auto border-r border-[var(--border)] py-5 shadow-lg transition-[transform,width,padding] duration-300",
    isMobileDrawerOpen
      ? "flex translate-x-0 px-4"
      : "hidden -translate-x-full px-4 md:flex md:translate-x-0",
    isDesktopCollapsed
      ? "md:w-[5.25rem] md:max-w-none md:px-3"
      : "md:w-[19.2rem] md:max-w-none md:px-4",
    "md:relative md:top-auto md:bottom-auto md:shrink-0 md:shadow-none md:border-r-0",
  ].join(" ");

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

  const handleSearchSubmit = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    startTransition(() => {
      router.replace(buildHomeHref(searchQuery));
    });
    if (isMobileDrawerOpen) {
      onClose();
    }
  };

  const isTradeJournalActive = pathname === buildJournalHref();
  const isTaskQueueActive = pathname.startsWith("/tasks/");
  const isScreenerTaskQueueActive = pathname.startsWith("/screener-tasks/");
  const isScreenerRunActive = pathname.startsWith("/screeners/");
  const isReportActive = pathname.startsWith("/reports/");

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
            <Link href={buildHomeHref(searchQuery)} className="flex min-w-0 items-center gap-2">
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
              {!isDesktopRail ? (
                <div className="min-w-0">
                  <p className="text-sm font-semibold text-slate-900">
                    TradingAgents
                  </p>
                  <p className="text-xs uppercase tracking-[0.3em] text-slate-500">
                    {t("sidebar.brandSubline", "Research")}
                  </p>
                </div>
              ) : null}
            </Link>

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

                <RailLinkButton
                  href={buildJournalHref()}
                  label="Trade Journal"
                  title="Trade Journal"
                  active={isTradeJournalActive}
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
                </RailLinkButton>
              </div>

              <div className="mt-6 flex flex-col items-center gap-2 border-t border-[var(--border)] pt-4">
                {activeTasks.length > 0 ? (
                  <RailButton
                    label="Task Queue"
                    title="Task Queue"
                    active={isTaskQueueActive}
                    count={activeTasks.length}
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

                {activeScreenerTasks.length > 0 ? (
                  <RailButton
                    label="Screener Queue"
                    title="Screener Queue"
                    active={isScreenerTaskQueueActive}
                    count={activeScreenerTasks.length}
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
                  active={isScreenerRunActive}
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
                  active={isReportActive}
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
                  active={isReportActive}
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

              <Link
                href={buildJournalHref()}
                data-active={isTradeJournalActive}
                className={`interactive-button focus-ring mt-3 flex w-full items-center justify-between rounded-[22px] border px-4 py-2.5 text-left ${
                  isTradeJournalActive
                    ? "border-[var(--primary)] bg-[var(--primary-soft)] text-[var(--primary-strong)] shadow-[0_14px_28px_rgba(182,90,43,0.16)]"
                    : "border-[var(--border)] bg-white text-slate-700 shadow-[0_14px_28px_rgba(18,28,41,0.05)]"
                }`}
                onClick={onClose}
              >
                <span>
                  <span className="block text-[10px] font-semibold uppercase tracking-[0.22em] text-slate-500">
                    Manual
                  </span>
                  <span className="mt-1 block text-[13px] font-semibold">
                    Trade Journal
                  </span>
                </span>
              </Link>

              {activeTasks.length > 0 ? (
                <section className="mt-5">
                  <div className="flex items-center justify-between">
                    <h3 className="text-xs font-semibold uppercase tracking-[0.35em] text-slate-500">
                      Task Queue
                    </h3>
                    <span className="text-[10px] font-semibold uppercase tracking-[0.3em] text-slate-400">
                      {activeTasks.length} active
                    </span>
                  </div>
                  <div className="mt-3 space-y-2 rounded-2xl border border-slate-100 bg-slate-50 p-2 text-sm shadow-sm">
                    {activeTasks.map((task, index) => {
                      const href = buildTaskHref(task.id);
                      return (
                        <Link
                          key={task.id}
                          ref={index === 0 ? taskQueueFirstButtonRef : undefined}
                          href={href}
                          className={`sidebar-task-card group flex rounded-2xl px-3 py-2.5 text-left transition ${
                            pathname === href
                              ? "border border-[var(--accent)] bg-[var(--accent-soft)] text-slate-900 shadow-[0_10px_20px_rgba(28,56,83,0.10)]"
                              : "border border-transparent bg-white text-slate-700 hover:bg-white"
                          }`}
                          onClick={onClose}
                        >
                          <div className="min-w-0 flex-1">
                            <p className="text-[12px] font-semibold">{task.ticker}</p>
                            <p className="mt-1 text-[10px] uppercase tracking-[0.22em] text-slate-500">
                              {task.status}
                              {task.latest_progress?.current_agent
                                ? ` · ${task.latest_progress.current_agent}`
                                : ""}
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
                            <span className="group-focus-within:opacity-100 opacity-0 transition group-hover:opacity-100 text-slate-400">
                              ›
                            </span>
                          </div>
                        </Link>
                      );
                    })}
                  </div>
                </section>
              ) : null}

              {activeScreenerTasks.length > 0 ? (
                <section className="mt-5">
                  <div className="flex items-center justify-between">
                    <h3 className="text-xs font-semibold uppercase tracking-[0.35em] text-slate-500">
                      Screener Queue
                    </h3>
                    <span className="text-[10px] font-semibold uppercase tracking-[0.3em] text-slate-400">
                      {activeScreenerTasks.length} active
                    </span>
                  </div>
                  <div className="mt-3 space-y-2 rounded-2xl border border-slate-100 bg-slate-50 p-2 text-sm shadow-sm">
                    {activeScreenerTasks.map((task, index) => {
                      const href = buildScreenerTaskHref(task.id);
                      return (
                        <Link
                          key={task.id}
                          ref={index === 0 ? screenerTaskFirstButtonRef : undefined}
                          href={href}
                          className={`sidebar-task-card group flex rounded-2xl px-3 py-2.5 text-left transition ${
                            pathname === href
                              ? "border border-[var(--accent)] bg-[var(--accent-soft)] text-slate-900 shadow-[0_10px_20px_rgba(28,56,83,0.10)]"
                              : "border border-transparent bg-white text-slate-700 hover:bg-white"
                          }`}
                          onClick={onClose}
                        >
                          <div className="min-w-0 flex-1">
                            <p className="text-[12px] font-semibold">Screener Run</p>
                            <p className="mt-1 text-[10px] uppercase tracking-[0.22em] text-slate-500">
                              {task.status}
                            </p>
                          </div>
                          <span className="inline-flex rounded-full bg-[rgba(28,56,83,0.1)] px-2 py-0.5 text-[10px] font-semibold uppercase tracking-[0.24em] text-[var(--accent)]">
                            {task.status}
                          </span>
                        </Link>
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
                  Filter reports from home
                </label>
                <form className="mt-2" onSubmit={handleSearchSubmit}>
                  <div className="relative">
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
                      type="search"
                      value={searchQuery}
                      onChange={(event) => setSearchQuery(event.target.value)}
                      placeholder="Ticker or report id"
                      className="focus-ring w-full rounded-2xl border border-[var(--border-strong)] bg-slate-50 py-3 pl-10 pr-4 text-sm font-medium text-slate-800 transition focus:border-[var(--primary)]"
                    />
                  </div>

                  <div className="mt-2 flex items-center gap-2">
                    <button
                      type="submit"
                      className="focus-ring rounded-full border border-[var(--primary)] bg-[var(--primary)] px-3 py-1.5 text-[10px] font-semibold uppercase tracking-[0.2em] text-white"
                    >
                      Open results
                    </button>
                    <Link
                      href={buildHomeHref(searchQuery)}
                      className="text-[10px] font-semibold uppercase tracking-[0.2em] text-[var(--primary)]"
                      onClick={onClose}
                    >
                      Open home results
                    </Link>
                    {searchQuery ? (
                      <button
                        type="button"
                        className="rounded-full border border-[var(--border)] bg-white px-2 py-1 text-[10px] font-semibold text-slate-500 transition hover:text-[var(--primary)]"
                        onClick={() => setSearchQuery("")}
                      >
                        Clear
                      </button>
                    ) : null}
                  </div>
                </form>

                <p className="mt-1 text-xs text-slate-500">
                  Search reports in a URL-driven view instead of filtering hidden panels.
                </p>
              </div>

              <section className="mt-6">
                <h3 className="text-xs font-semibold uppercase tracking-[0.4em] text-slate-500">
                  Recent Screeners
                </h3>
                <div className="mt-3 space-y-2 rounded-2xl border border-slate-100 bg-slate-50 p-2 text-sm">
                  {screenerRuns.length === 0 ? (
                    <p className="px-3 py-4 text-xs font-semibold text-slate-500">
                      No screener runs yet.
                    </p>
                  ) : (
                    screenerRuns.map((run, index) => {
                      const href = buildScreenerRunHref(run.id);
                      return (
                        <Link
                          key={run.id}
                          ref={index === 0 ? recentScreenersFirstButtonRef : undefined}
                          href={href}
                          className={`flex items-center justify-between rounded-2xl px-3 py-3 text-left transition hover:bg-white hover:text-[var(--primary)] ${
                            pathname === href
                              ? "text-[var(--primary)]"
                              : ""
                          }`}
                          onClick={onClose}
                        >
                          <div>
                            <p className="text-sm font-semibold text-slate-900">{run.id}</p>
                            <p className="text-xs uppercase tracking-[0.3em] text-slate-500">
                              {run.candidate_count} candidates
                            </p>
                          </div>
                          <span className="text-xs font-semibold text-slate-500">
                            {formatRunDate(run.as_of_date, locale)}
                          </span>
                        </Link>
                      );
                    })
                  )}
                </div>
              </section>

              <section className="mt-6">
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
                    <span className="text-slate-400">{isRecentReportsOpen ? "›" : "‹"}</span>
                  </div>
                </button>
                {isRecentReportsOpen && (
                  <div
                    id="recent-reports-panel"
                    className="mt-3 space-y-2 rounded-2xl border border-slate-100 bg-slate-50 p-2 text-sm"
                  >
                    {reportsError ? (
                      <p className="px-3 py-4 text-xs font-semibold text-[var(--danger)]">
                        {reportsError}
                      </p>
                    ) : loadingReports ? (
                      <p className="px-3 py-4 text-xs font-semibold text-slate-500">
                        Loading reports...
                      </p>
                    ) : recentReports.length === 0 ? (
                      <p className="px-3 py-4 text-xs font-semibold text-slate-500">
                        No reports yet.
                      </p>
                    ) : (
                      recentReports.map((report, index) => {
                        const href = buildReportHref(report.id);
                        return (
                          <Link
                            key={report.id}
                            ref={index === 0 ? firstRecentReportButtonRef : undefined}
                            href={href}
                            className="flex items-center justify-between rounded-2xl px-3 py-3 text-left transition hover:bg-white hover:text-[var(--primary)]"
                            onClick={onClose}
                          >
                            <div>
                              <p className="text-sm font-semibold text-slate-900">
                                {report.ticker}
                              </p>
                              <p className="text-xs uppercase tracking-[0.3em] text-slate-500">
                                {formatReportDate(report, locale)}
                              </p>
                            </div>
                            <span className="text-xs font-semibold text-slate-500">
                              Open
                            </span>
                          </Link>
                        );
                      })
                    )}
                  </div>
                )}
              </section>

              <section className="mt-6">
                <button
                  ref={allTickersToggleRef}
                  type="button"
                  className="flex w-full items-center justify-between text-left"
                  onClick={() => setIsAllTickersOpen((current) => !current)}
                  aria-expanded={isAllTickersOpen}
                  aria-controls="all-tickers-panel"
                >
                  <h3 className="text-xs font-semibold uppercase tracking-[0.4em] text-slate-500">
                    All tickers
                  </h3>
                  <div className="flex items-center gap-2">
                    <span className="text-[10px] font-semibold uppercase tracking-[0.3em] text-slate-400">
                      {reportsByTicker.length} tracked
                    </span>
                    <span className="text-slate-400">{isAllTickersOpen ? "›" : "‹"}</span>
                  </div>
                </button>
                {isAllTickersOpen && (
                  <div
                    id="all-tickers-panel"
                    className="mt-3 space-y-3 rounded-2xl border border-slate-100 bg-slate-50 p-2 text-sm"
                  >
                    {reportsByTicker.length === 0 ? (
                      <p className="px-3 py-4 text-xs font-semibold text-slate-500">
                        No tickers yet.
                      </p>
                    ) : (
                      reportsByTicker.map((group, index) => (
                        <div
                          key={group.ticker}
                          className="rounded-2xl border border-transparent bg-white/90 p-3"
                        >
                          <div className="flex items-center justify-between gap-3">
                            <p className="text-sm font-semibold text-slate-900">
                              {group.ticker}
                            </p>
                            <span className="rounded-full bg-[var(--surface-strong)] px-2 py-0.5 text-[10px] font-semibold uppercase tracking-[0.22em] text-slate-500">
                              {group.reports.length}
                            </span>
                          </div>
                          <div className="mt-3 space-y-2">
                            {group.reports.slice(0, 3).map((report, reportIndex) => {
                              const href = buildReportHref(report.id);
                              const shouldFocus = index === 0 && reportIndex === 0;
                              return (
                                <Link
                                  key={report.id}
                                  ref={shouldFocus ? firstTickerButtonRef : undefined}
                                  href={href}
                                  className={`flex items-center justify-between rounded-2xl px-3 py-2.5 text-left transition ${
                                    pathname === href
                                      ? "border border-[var(--accent)] bg-[var(--accent-soft)] text-slate-900 shadow-[0_10px_20px_rgba(28,56,83,0.10)]"
                                      : "border border-transparent bg-white text-slate-700 hover:bg-white"
                                  }`}
                                  onClick={onClose}
                                >
                                  <div>
                                    <p className="text-[13px] font-semibold">{report.id}</p>
                                    <p className="text-[10px] uppercase tracking-[0.22em] text-slate-500">
                                      {formatReportDate(report, locale)}
                                    </p>
                                  </div>
                                  <span className="rounded-full px-2 py-0.5 text-[10px] font-semibold uppercase tracking-[0.24em] text-slate-500">
                                    Open
                                  </span>
                                </Link>
                              );
                            })}
                          </div>
                        </div>
                      ))
                    )}
                  </div>
                )}
              </section>
            </div>
          )}
        </div>
      </aside>
    </>
  );
}

function RailButton({
  label,
  title,
  active = false,
  count,
  disabled = false,
  onClick,
  children,
}: {
  label: string;
  title: string;
  active?: boolean;
  count?: number;
  disabled?: boolean;
  onClick: () => void;
  children: ReactNode;
}) {
  return (
    <button
      type="button"
      title={title}
      aria-label={label}
      disabled={disabled}
      onClick={onClick}
      className={`group relative inline-flex h-11 w-11 items-center justify-center rounded-2xl border transition ${
        active
          ? "border-[var(--primary)] bg-[var(--primary-soft)] text-[var(--primary-strong)]"
          : "border-[var(--border)] bg-white text-slate-600 hover:border-[var(--primary)] hover:text-[var(--primary)]"
      } ${disabled ? "cursor-not-allowed opacity-50" : ""}`}
    >
      {children}
      {typeof count === "number" ? (
        <span className="absolute -right-1 -top-1 rounded-full bg-[var(--primary)] px-1.5 py-0.5 text-[10px] font-semibold text-white">
          {count}
        </span>
      ) : null}
    </button>
  );
}

function RailLinkButton({
  href,
  label,
  title,
  active = false,
  children,
}: {
  href: string;
  label: string;
  title: string;
  active?: boolean;
  children: ReactNode;
}) {
  return (
    <Link
      href={href}
      title={title}
      aria-label={label}
      className={`inline-flex h-11 w-11 items-center justify-center rounded-2xl border transition ${
        active
          ? "border-[var(--primary)] bg-[var(--primary-soft)] text-[var(--primary-strong)]"
          : "border-[var(--border)] bg-white text-slate-600 hover:border-[var(--primary)] hover:text-[var(--primary)]"
      }`}
    >
      {children}
    </Link>
  );
}

function formatReportDate(
  report: { date: string; time: string },
  locale: string
): string {
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

    return `${report.date} ${report.time}`;
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
  }

  return "Unknown date";
}

function formatRunDate(value: string, locale: string): string {
  const parsed = new Date(`${value}T00:00:00`);
  if (!Number.isNaN(parsed.getTime())) {
    return new Intl.DateTimeFormat(locale, {
      month: "short",
      day: "numeric",
    }).format(parsed);
  }

  return value;
}
