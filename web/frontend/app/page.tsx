"use client";

import { startTransition, useCallback, useEffect, useMemo, useState } from "react";
import { useRouter } from "next/navigation";
import {
  ApiError,
  listReports,
  listScreenerRuns,
  listScreenerTasks,
  listTasks,
  type Report,
  type ScreenerRunSummary,
  type ScreenerTask,
  type Task,
} from "@/lib/api";
import { useAuth } from "@/components/AuthProvider";
import { NewAnalysisForm } from "@/components/NewAnalysisForm";
import { NewScreenerForm } from "@/components/NewScreenerForm";
import { usePreferences } from "@/components/PreferencesProvider";
import { ScreenerResultsViewer } from "@/components/ScreenerResultsViewer";
import { ScreenerTaskProgress } from "@/components/ScreenerTaskProgress";
import { Sidebar } from "@/components/Sidebar";
import { TradeJournal } from "@/components/TradeJournal";
import { ReportViewer } from "@/components/ReportViewer";
import { TaskProgress } from "@/components/TaskProgress";

export default function Home() {
  const router = useRouter();
  const { locale, t } = usePreferences();
  const { authError, authState, authStatus, refreshSession, logout } = useAuth();
  const [selectedReportId, setSelectedReportId] = useState<string | null>(null);
  const [selectedScreenerRunId, setSelectedScreenerRunId] = useState<string | null>(null);
  const [activeTaskId, setActiveTaskId] = useState<string | null>(null);
  const [activeScreenerTaskId, setActiveScreenerTaskId] = useState<string | null>(null);
  const [showNewAnalysis, setShowNewAnalysis] = useState(false);
  const [showNewScreener, setShowNewScreener] = useState(false);
  const [showTradeJournal, setShowTradeJournal] = useState(false);
  const [reports, setReports] = useState<Report[]>([]);
  const [screenerRuns, setScreenerRuns] = useState<ScreenerRunSummary[]>([]);
  const [tasks, setTasks] = useState<Task[]>([]);
  const [screenerTasks, setScreenerTasks] = useState<ScreenerTask[]>([]);
  const [queueLocked, setQueueLocked] = useState(false);
  const [loadingReports, setLoadingReports] = useState(true);
  const [reportsError, setReportsError] = useState<string | null>(null);
  const [searchQuery, setSearchQuery] = useState("");
  const [isSidebarOpen, setIsSidebarOpen] = useState(false);
  const [isLoggingOut, setIsLoggingOut] = useState(false);
  const [defaultOutputLanguage, setDefaultOutputLanguage] = useState<string | null>(
    null
  );
  const authEnabled = authState?.enabled ?? false;
  const canAccessWorkbench =
    authStatus === "ready" && (!authEnabled || Boolean(authState?.authenticated));
  const shouldRedirectToLogin =
    authStatus === "ready" && authEnabled && !authState?.authenticated;
  const canManageUsers = authState?.user?.role === "admin";

  const handleProtectedError = useCallback(
    (error: unknown): boolean => {
      if (error instanceof ApiError && error.status === 401) {
        void refreshSession({ silent: true });
        return true;
      }
      return false;
    },
    [refreshSession]
  );

  const handleLogout = async () => {
    setIsLoggingOut(true);

    try {
      await logout();
      startTransition(() => {
        router.replace("/login?next=/");
      });
    } finally {
      setIsLoggingOut(false);
    }
  };

  const loadReports = async () => {
    if (!canAccessWorkbench) {
      return;
    }

    setLoadingReports(true);
    setReportsError(null);

    try {
      const data = await listReports();
      setReports(data);
    } catch (error) {
      if (handleProtectedError(error)) {
        return;
      }
      setReportsError(
        error instanceof Error
          ? error.message
          : t("page.error.loadReports", "Unable to load reports")
      );
    } finally {
      setLoadingReports(false);
    }
  };

  const loadTasks = async () => {
    if (!canAccessWorkbench) {
      return;
    }

    try {
      const data = await listTasks();
      setTasks(data);
    } catch (error) {
      if (handleProtectedError(error)) {
        return;
      }
      // Keep the report experience usable even if the queue endpoint is temporarily unavailable.
    }
  };

  const loadScreenerRuns = async () => {
    if (!canAccessWorkbench) {
      return;
    }

    try {
      const data = await listScreenerRuns();
      setScreenerRuns(data);
    } catch (error) {
      if (handleProtectedError(error)) {
        return;
      }
      // Keep the existing UI usable even if screener listing is unavailable.
    }
  };

  const loadScreenerTasks = async () => {
    if (!canAccessWorkbench) {
      return;
    }

    try {
      const data = await listScreenerTasks();
      setScreenerTasks(data);
    } catch (error) {
      if (handleProtectedError(error)) {
        return;
      }
      // Ignore transient screener queue polling issues in the UI.
    }
  };

  useEffect(() => {
    if (!shouldRedirectToLogin) {
      return;
    }

    startTransition(() => {
      router.replace("/login?next=/");
    });
  }, [router, shouldRedirectToLogin]);

  useEffect(() => {
    if (!canAccessWorkbench) {
      return;
    }

    let isMounted = true;

    const loadReportsSafely = async () => {
      setLoadingReports(true);
      setReportsError(null);

        try {
          const data = await listReports();
          if (isMounted) {
            setReports(data);
          }
        } catch (error) {
          if (handleProtectedError(error)) {
            return;
          }
          if (isMounted) {
            setReportsError(
              error instanceof Error
              ? error.message
              : t("page.error.loadReports", "Unable to load reports")
          );
        }
      } finally {
        if (isMounted) {
          setLoadingReports(false);
        }
      }
    };

    void loadReportsSafely();

    return () => {
      isMounted = false;
    };
  }, [canAccessWorkbench, handleProtectedError, t]);

  useEffect(() => {
    if (!canAccessWorkbench) {
      return;
    }

    let isMounted = true;

    const loadScreenerRunsSafely = async () => {
      try {
        const data = await listScreenerRuns();
        if (isMounted) {
          setScreenerRuns(data);
        }
      } catch (error) {
        if (handleProtectedError(error)) {
          return;
        }
        // Ignore screener run loading issues in the main page.
      }
    };

    void loadScreenerRunsSafely();
    return () => {
      isMounted = false;
    };
  }, [canAccessWorkbench, handleProtectedError]);

  useEffect(() => {
    if (!canAccessWorkbench) {
      return;
    }

    let isMounted = true;

    const loadTasksSafely = async () => {
      try {
        const data = await listTasks();
        if (isMounted) {
          setTasks(data);
        }
      } catch (error) {
        if (handleProtectedError(error)) {
          return;
        }
        // Ignore transient queue polling issues in the UI.
      }
    };

    void loadTasksSafely();
    const intervalId = window.setInterval(() => {
      void loadTasksSafely();
    }, 3000);

    return () => {
      isMounted = false;
      window.clearInterval(intervalId);
    };
  }, [canAccessWorkbench, handleProtectedError]);

  useEffect(() => {
    if (!canAccessWorkbench) {
      return;
    }

    let isMounted = true;

    const loadScreenerTasksSafely = async () => {
      try {
        const data = await listScreenerTasks();
        if (isMounted) {
          setScreenerTasks(data);
        }
      } catch (error) {
        if (handleProtectedError(error)) {
          return;
        }
        // Ignore transient screener queue polling issues in the UI.
      }
    };

    void loadScreenerTasksSafely();
    const intervalId = window.setInterval(() => {
      void loadScreenerTasksSafely();
    }, 3000);

    return () => {
      isMounted = false;
      window.clearInterval(intervalId);
    };
  }, [canAccessWorkbench, handleProtectedError]);

  const sortedReports = useMemo(() => {
    const reportsWithTimestamp = reports.map((report) => ({
      report,
      timestamp: parseReportTimestamp(report),
    }));

    return reportsWithTimestamp
      .sort((a, b) => b.timestamp - a.timestamp)
      .map(({ report }) => report);
  }, [reports]);

  const recentReports = useMemo(() => sortedReports.slice(0, 5), [sortedReports]);
  const activeTasks = useMemo(
    () => tasks.filter((task) => task.status === "pending" || task.status === "running"),
    [tasks]
  );
  const activeScreenerTasks = useMemo(
    () =>
      screenerTasks.filter(
        (task) => task.status === "pending" || task.status === "running"
      ),
    [screenerTasks]
  );
  const visibleTaskQueue = useMemo(() => activeTasks.slice(0, 2), [activeTasks]);
  const visibleScreenerTaskQueue = useMemo(
    () => activeScreenerTasks.slice(0, 2),
    [activeScreenerTasks]
  );
  const currentTaskId =
    activeTaskId ??
    (selectedReportId ||
    selectedScreenerRunId ||
    activeScreenerTaskId ||
    showTradeJournal
      ? null
      : visibleTaskQueue[0]?.id ?? null);
  const currentScreenerTaskId =
    activeScreenerTaskId ??
    (selectedReportId || selectedScreenerRunId || currentTaskId || showTradeJournal
      ? null
      : visibleScreenerTaskQueue[0]?.id ?? null);
  const combinedActiveCount = visibleTaskQueue.length + visibleScreenerTaskQueue.length;
  const newAnalysisDisabled = queueLocked || combinedActiveCount >= 2;
  const newScreenerDisabled = queueLocked || combinedActiveCount >= 2;
  const recentTickers = useMemo(() => {
    const seen = new Set<string>();
    return sortedReports.reduce<string[]>((acc, report) => {
      if (acc.length >= 5) {
        return acc;
      }
      if (!seen.has(report.ticker)) {
        seen.add(report.ticker);
        acc.push(report.ticker);
      }
      return acc;
    }, []);
  }, [sortedReports]);

  useEffect(() => {
    if (combinedActiveCount >= 2) {
      setQueueLocked(true);
      return;
    }
    if (combinedActiveCount === 0) {
      setQueueLocked(false);
    }
  }, [combinedActiveCount]);

  if (authStatus === "loading") {
    return (
      <main className="flex min-h-screen items-center justify-center px-6 py-10">
        <div className="card-surface w-full max-w-xl rounded-[32px] px-8 py-10 text-center">
          <p className="text-[12px] font-semibold uppercase tracking-[0.36em] text-[var(--primary)]">
            Session Bootstrap
          </p>
          <h1 className="font-heading mt-4 text-3xl font-bold tracking-tight text-slate-900">
            Verifying workspace access
          </h1>
          <p className="mt-3 text-sm leading-6 text-slate-600">
            TradingAgents is checking the current session before it touches any
            protected workbench data.
          </p>
        </div>
      </main>
    );
  }

  if (authStatus === "error") {
    return (
      <main className="flex min-h-screen items-center justify-center px-6 py-10">
        <div className="card-surface w-full max-w-xl rounded-[32px] px-8 py-10 text-center">
          <p className="text-[12px] font-semibold uppercase tracking-[0.36em] text-[var(--danger)]">
            Auth Unavailable
          </p>
          <h1 className="font-heading mt-4 text-3xl font-bold tracking-tight text-slate-900">
            Unable to load session state
          </h1>
          <p className="mt-3 text-sm leading-6 text-slate-600">
            {authError ??
              "The frontend could not reach /api/auth/me, so protected navigation is paused."}
          </p>
          <button
            type="button"
            className="interactive-button focus-ring mt-6 rounded-full border border-[var(--primary)] bg-[var(--primary)] px-5 py-3 text-xs font-semibold uppercase tracking-[0.22em] text-white"
            onClick={() => void refreshSession()}
          >
            Retry Session Bootstrap
          </button>
        </div>
      </main>
    );
  }

  if (shouldRedirectToLogin) {
    return (
      <main className="flex min-h-screen items-center justify-center px-6 py-10">
        <div className="card-surface w-full max-w-xl rounded-[32px] px-8 py-10 text-center">
          <p className="text-[12px] font-semibold uppercase tracking-[0.36em] text-[var(--primary)]">
            Login Required
          </p>
          <h1 className="font-heading mt-4 text-3xl font-bold tracking-tight text-slate-900">
            Redirecting to the sign-in screen
          </h1>
          <p className="mt-3 text-sm leading-6 text-slate-600">
            This workbench is protected when auth is enabled, so TradingAgents is
            routing the session back through `/login`.
          </p>
        </div>
      </main>
    );
  }

  return (
    <div className="app-shell relative min-h-screen bg-[var(--bg)] md:flex md:items-stretch">
      <Sidebar
        authEnabled={authEnabled}
        authUser={authState?.user ?? null}
        canManageUsers={canManageUsers}
        onLogout={handleLogout}
        loggingOut={isLoggingOut}
        selectedReportId={selectedReportId}
        selectedScreenerRunId={selectedScreenerRunId}
        onSelectReport={(reportId) => {
          setSelectedReportId(reportId);
          setSelectedScreenerRunId(null);
          setActiveTaskId(null);
          setActiveScreenerTaskId(null);
          setShowTradeJournal(false);
          setIsSidebarOpen(false);
        }}
        onSelectScreenerRun={(runId) => {
          setSelectedScreenerRunId(runId);
          setSelectedReportId(null);
          setActiveTaskId(null);
          setActiveScreenerTaskId(null);
          setShowTradeJournal(false);
          setIsSidebarOpen(false);
        }}
        selectedTradeJournal={showTradeJournal}
        onSelectTradeJournal={() => {
          setShowTradeJournal(true);
          setSelectedReportId(null);
          setSelectedScreenerRunId(null);
          setActiveTaskId(null);
          setActiveScreenerTaskId(null);
          setShowNewAnalysis(false);
          setShowNewScreener(false);
          setIsSidebarOpen(false);
        }}
        reports={reports}
        screenerRuns={screenerRuns}
        loading={loadingReports}
        error={reportsError}
        searchQuery={searchQuery}
        onSearchQueryChange={(value) => setSearchQuery(value)}
        taskQueue={visibleTaskQueue}
        screenerTaskQueue={visibleScreenerTaskQueue}
        activeTaskId={currentTaskId}
        activeScreenerTaskId={currentScreenerTaskId}
        onSelectTask={(taskId) => {
          setSelectedReportId(null);
          setSelectedScreenerRunId(null);
          setActiveTaskId(taskId);
          setActiveScreenerTaskId(null);
          setShowTradeJournal(false);
          setIsSidebarOpen(false);
        }}
        onSelectScreenerTask={(taskId) => {
          setSelectedReportId(null);
          setSelectedScreenerRunId(null);
          setActiveTaskId(null);
          setActiveScreenerTaskId(taskId);
          setShowTradeJournal(false);
          setIsSidebarOpen(false);
        }}
        onNewAnalysis={() => {
          if (newAnalysisDisabled) {
            return;
          }
          setShowNewAnalysis(true);
          setShowNewScreener(false);
          setShowTradeJournal(false);
          setSelectedReportId(null);
          setSelectedScreenerRunId(null);
          setIsSidebarOpen(false);
        }}
        onNewScreener={() => {
          if (newScreenerDisabled) {
            return;
          }
          setShowNewScreener(true);
          setShowNewAnalysis(false);
          setShowTradeJournal(false);
          setSelectedReportId(null);
          setSelectedScreenerRunId(null);
          setIsSidebarOpen(false);
        }}
        newAnalysisDisabled={newAnalysisDisabled}
        newScreenerDisabled={newScreenerDisabled}
        isOpen={isSidebarOpen}
        onClose={() => setIsSidebarOpen(false)}
        selectedOutputLanguage={defaultOutputLanguage}
        onOutputLanguageChange={(value) => setDefaultOutputLanguage(value)}
      />

      <NewAnalysisForm
        isOpen={showNewAnalysis}
        onClose={() => setShowNewAnalysis(false)}
        defaultOutputLanguage={defaultOutputLanguage}
        onTaskCreated={(taskId) => {
          setShowNewAnalysis(false);
          setShowTradeJournal(false);
          void loadTasks();
          startTransition(() => {
            setSelectedReportId(null);
            setActiveTaskId(taskId);
          });
        }}
      />

      <NewScreenerForm
        isOpen={showNewScreener}
        onClose={() => setShowNewScreener(false)}
        onTaskCreated={(taskId) => {
          setShowNewScreener(false);
          setShowTradeJournal(false);
          void loadScreenerTasks();
          startTransition(() => {
            setSelectedReportId(null);
            setSelectedScreenerRunId(null);
            setActiveTaskId(null);
            setActiveScreenerTaskId(taskId);
          });
        }}
      />

      {selectedReportId ? (
        <ReportViewer reportId={selectedReportId} />
      ) : selectedScreenerRunId ? (
        <ScreenerResultsViewer runId={selectedScreenerRunId} />
      ) : showTradeJournal ? (
        <TradeJournal
          reports={sortedReports}
          onOpenSidebar={() => setIsSidebarOpen(true)}
          sidebarOpen={isSidebarOpen}
        />
      ) : currentTaskId ? (
        <TaskProgress
          key={currentTaskId}
          taskId={currentTaskId}
          onTaskComplete={() => {
            void loadReports();
            void loadTasks();
          }}
          onViewReport={(reportId) => {
            setSelectedReportId(reportId);
          }}
        />
      ) : currentScreenerTaskId ? (
        <ScreenerTaskProgress
          key={currentScreenerTaskId}
          taskId={currentScreenerTaskId}
          onTaskComplete={(runId) => {
            void loadScreenerRuns();
            void loadScreenerTasks();
            if (runId) {
              setSelectedScreenerRunId(runId);
              setActiveScreenerTaskId(null);
            }
          }}
          onViewRun={(runId) => {
            setSelectedScreenerRunId(runId);
            setActiveScreenerTaskId(null);
          }}
        />
      ) : (
        <main className="flex min-h-[100vh] flex-1 flex-col px-4 py-6 md:px-7 lg:px-9">
          <div className="mx-auto w-full max-w-5xl">
            <div className="glass-panel fade-in rounded-3xl border border-[var(--border)] bg-white/95 px-6 py-8 shadow-sm md:px-8 md:py-10">
              <div className="flex items-start justify-between gap-4">
                <div>
                  <p className="text-[12px] font-semibold uppercase tracking-[0.4em] text-[var(--primary)]">
                    {t("home.heroKicker", "TradingAgents Report Center")}
                  </p>
                  <h1 className="font-heading mt-3 text-3xl font-bold tracking-tight text-slate-900 md:text-4xl">
                    {t("home.heroTitle", "Content-first research workbench")}
                  </h1>
                  <p className="mt-2 max-w-2xl text-sm leading-6 text-slate-600">
                    {t(
                      "home.heroDescription",
                      "Jump straight into the freshest report, search across tickers, launch a brand-new background analysis, or build a ranked screener pool."
                    )}
                  </p>
                </div>
                <button
                  type="button"
                  className="group md:hidden"
                  onClick={() => setIsSidebarOpen(true)}
                  aria-label={t("home.openSidebar", "Open sidebar")}
                >
                  <span className="flex h-12 w-12 items-center justify-center rounded-2xl border border-[var(--border)] text-slate-700 transition hover:border-[var(--primary)]">
                    <svg
                      className="h-5 w-5"
                      fill="none"
                      stroke="currentColor"
                      viewBox="0 0 24 24"
                      aria-hidden
                    >
                      <path
                        strokeLinecap="round"
                        strokeLinejoin="round"
                        strokeWidth="2"
                        d="M4 6h16M4 12h16M4 18h16"
                      />
                    </svg>
                  </span>
                </button>
              </div>

              <div className="mt-8 space-y-4">
                <div>
                  <label
                    className="text-xs font-semibold uppercase tracking-[0.3em] text-slate-500"
                    htmlFor="page-search"
                  >
                    {t("home.searchLabel", "Search reports")}
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
                      id="page-search"
                      type="text"
                      value={searchQuery}
                      onChange={(event) => setSearchQuery(event.target.value)}
                      placeholder={t(
                        "home.searchPlaceholder",
                        "Search by ticker or report id"
                      )}
                      className="focus-ring w-full rounded-2xl border border-[var(--border-strong)] bg-slate-50 py-3 pl-10 pr-4 text-sm font-medium text-slate-800 transition focus:border-[var(--primary)]"
                    />
                  </div>
                  <p className="mt-1 text-xs text-slate-500">
                    {t(
                      "home.searchHint",
                      "Filter by ticker, report id, or use the quick chips below."
                    )}
                  </p>
                </div>
                <div className="flex flex-wrap gap-3">
                  <button
                    type="button"
                    className="interactive-button focus-ring rounded-full border border-[var(--primary)] bg-[var(--primary)] px-5 py-3 text-xs font-semibold uppercase tracking-[0.2em] text-white"
                    disabled={newAnalysisDisabled}
                    onClick={() => {
                      setShowTradeJournal(false);
                      setShowNewAnalysis(true);
                    }}
                  >
                    {t("home.launchAnalysis", "Launch Analysis")}
                  </button>
                  <button
                    type="button"
                    className="interactive-button focus-ring rounded-full border border-[var(--accent)] bg-[var(--accent)] px-5 py-3 text-xs font-semibold uppercase tracking-[0.2em] text-white"
                    disabled={newScreenerDisabled}
                    onClick={() => {
                      setShowTradeJournal(false);
                      setShowNewScreener(true);
                    }}
                  >
                    {t("home.launchScreener", "Launch Screener")}
                  </button>
                  <button
                    type="button"
                    className="interactive-button focus-ring rounded-full border border-[var(--border-strong)] bg-white px-5 py-3 text-xs font-semibold uppercase tracking-[0.2em] text-slate-700"
                    onClick={() => setShowTradeJournal(true)}
                  >
                    {t("home.openManualJournal", "Open Manual Journal")}
                  </button>
                </div>
              </div>

              <div className="mt-10 grid gap-6 md:grid-cols-2">
                <section className="space-y-3">
                  <div className="flex items-center justify-between">
                    <h2 className="text-sm font-semibold uppercase tracking-[0.3em] text-slate-500">
                      {t("home.recentReports", "Recent reports")}
                    </h2>
                    <span className="text-xs font-semibold uppercase tracking-[0.3em] text-slate-400">
                      {t("home.reportsLatest", "Latest")}
                    </span>
                  </div>
                  <ul className="divide-y divide-slate-100 rounded-2xl border border-slate-100 bg-slate-50 text-sm shadow-sm">
                    {recentReports.length === 0 ? (
                      <li className="px-4 py-4 text-xs font-medium text-slate-500">
                        {t(
                          "home.reportsEmpty",
                          "Reports will appear here as soon as they are generated."
                        )}
                      </li>
                    ) : (
                      recentReports.map((report) => (
                        <li
                          key={report.id}
                          className="group flex cursor-pointer items-center justify-between gap-4 px-4 py-3 hover:bg-white focus:outline-none focus-visible:ring-2 focus-visible:ring-[var(--primary)]"
                          onClick={() => setSelectedReportId(report.id)}
                        >
                          <div>
                            <p className="text-sm font-semibold text-slate-900">
                              {report.ticker}
                            </p>
                            <p className="text-xs uppercase tracking-[0.2em] text-slate-500">
                              {formatReportDate(
                                report,
                                locale,
                                t("common.unknownDate", "Unknown date")
                              )}
                            </p>
                          </div>
                          <span className="text-xs font-semibold text-[var(--primary)]">
                            {t("common.open", "Open")}
                          </span>
                        </li>
                      ))
                    )}
                  </ul>
                </section>

                <section className="space-y-3">
                  <h2 className="text-sm font-semibold uppercase tracking-[0.3em] text-slate-500">
                    {t("home.recentTickers", "Recent tickers")}
                  </h2>
                  <div className="flex flex-wrap gap-2">
                    {recentTickers.length === 0 ? (
                      <span className="rounded-full border border-[var(--border)] px-3 py-1 text-xs font-semibold text-slate-500">
                        {t("home.waitingForReports", "Waiting for reports")}
                      </span>
                    ) : (
                      recentTickers.map((ticker) => (
                        <button
                          key={ticker}
                          type="button"
                          className="rounded-full border border-[var(--border)] bg-white px-3 py-2 text-xs font-semibold text-slate-700 transition hover:border-[var(--primary)] hover:text-[var(--primary)]"
                          onClick={() => setSearchQuery(ticker)}
                        >
                          {ticker}
                        </button>
                      ))
                    )}
                  </div>
                </section>
              </div>
            </div>
          </div>
        </main>
      )}
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
