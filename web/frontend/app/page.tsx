"use client";

import { startTransition, useEffect, useMemo, useState } from "react";
import {
  listReports,
  listScreenerRuns,
  listScreenerTasks,
  listTasks,
  type Report,
  type ScreenerRunSummary,
  type ScreenerTask,
  type Task,
} from "@/lib/api";
import { NewAnalysisForm } from "@/components/NewAnalysisForm";
import { NewScreenerForm } from "@/components/NewScreenerForm";
import { ScreenerResultsViewer } from "@/components/ScreenerResultsViewer";
import { ScreenerTaskProgress } from "@/components/ScreenerTaskProgress";
import { Sidebar } from "@/components/Sidebar";
import { ReportViewer } from "@/components/ReportViewer";
import { TaskProgress } from "@/components/TaskProgress";

export default function Home() {
  const [selectedReportId, setSelectedReportId] = useState<string | null>(null);
  const [selectedScreenerRunId, setSelectedScreenerRunId] = useState<string | null>(null);
  const [activeTaskId, setActiveTaskId] = useState<string | null>(null);
  const [activeScreenerTaskId, setActiveScreenerTaskId] = useState<string | null>(null);
  const [showNewAnalysis, setShowNewAnalysis] = useState(false);
  const [showNewScreener, setShowNewScreener] = useState(false);
  const [reports, setReports] = useState<Report[]>([]);
  const [screenerRuns, setScreenerRuns] = useState<ScreenerRunSummary[]>([]);
  const [tasks, setTasks] = useState<Task[]>([]);
  const [screenerTasks, setScreenerTasks] = useState<ScreenerTask[]>([]);
  const [queueLocked, setQueueLocked] = useState(false);
  const [loadingReports, setLoadingReports] = useState(true);
  const [reportsError, setReportsError] = useState<string | null>(null);
  const [searchQuery, setSearchQuery] = useState("");
  const [isSidebarOpen, setIsSidebarOpen] = useState(false);

  const loadReports = async () => {
    setLoadingReports(true);
    setReportsError(null);

    try {
      const data = await listReports();
      setReports(data);
    } catch (error) {
      setReportsError(
        error instanceof Error ? error.message : "Unable to load reports"
      );
    } finally {
      setLoadingReports(false);
    }
  };

  const loadTasks = async () => {
    try {
      const data = await listTasks();
      setTasks(data);
    } catch {
      // Keep the report experience usable even if the queue endpoint is temporarily unavailable.
    }
  };

  const loadScreenerRuns = async () => {
    try {
      const data = await listScreenerRuns();
      setScreenerRuns(data);
    } catch {
      // Keep the existing UI usable even if screener listing is unavailable.
    }
  };

  const loadScreenerTasks = async () => {
    try {
      const data = await listScreenerTasks();
      setScreenerTasks(data);
    } catch {
      // Ignore transient screener queue polling issues in the UI.
    }
  };

  useEffect(() => {
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
        if (isMounted) {
          setReportsError(
            error instanceof Error ? error.message : "Unable to load reports"
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
  }, []);

  useEffect(() => {
    let isMounted = true;

    const loadScreenerRunsSafely = async () => {
      try {
        const data = await listScreenerRuns();
        if (isMounted) {
          setScreenerRuns(data);
        }
      } catch {
        // Ignore screener run loading issues in the main page.
      }
    };

    void loadScreenerRunsSafely();
    return () => {
      isMounted = false;
    };
  }, []);

  useEffect(() => {
    let isMounted = true;

    const loadTasksSafely = async () => {
      try {
        const data = await listTasks();
        if (isMounted) {
          setTasks(data);
        }
      } catch {
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
  }, []);

  useEffect(() => {
    let isMounted = true;

    const loadScreenerTasksSafely = async () => {
      try {
        const data = await listScreenerTasks();
        if (isMounted) {
          setScreenerTasks(data);
        }
      } catch {
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
  }, []);

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
    (selectedReportId || selectedScreenerRunId || activeScreenerTaskId
      ? null
      : visibleTaskQueue[0]?.id ?? null);
  const currentScreenerTaskId =
    activeScreenerTaskId ??
    (selectedReportId || selectedScreenerRunId || currentTaskId
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

  return (
    <div className="app-shell relative min-h-screen bg-[var(--bg)] md:flex md:items-stretch">
      <Sidebar
        selectedReportId={selectedReportId}
        selectedScreenerRunId={selectedScreenerRunId}
        onSelectReport={(reportId) => {
          setSelectedReportId(reportId);
          setSelectedScreenerRunId(null);
          setActiveTaskId(null);
          setActiveScreenerTaskId(null);
          setIsSidebarOpen(false);
        }}
        onSelectScreenerRun={(runId) => {
          setSelectedScreenerRunId(runId);
          setSelectedReportId(null);
          setActiveTaskId(null);
          setActiveScreenerTaskId(null);
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
          setIsSidebarOpen(false);
        }}
        onSelectScreenerTask={(taskId) => {
          setSelectedReportId(null);
          setSelectedScreenerRunId(null);
          setActiveTaskId(null);
          setActiveScreenerTaskId(taskId);
          setIsSidebarOpen(false);
        }}
        onNewAnalysis={() => {
          if (newAnalysisDisabled) {
            return;
          }
          setShowNewAnalysis(true);
          setShowNewScreener(false);
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
          setSelectedReportId(null);
          setSelectedScreenerRunId(null);
          setIsSidebarOpen(false);
        }}
        newAnalysisDisabled={newAnalysisDisabled}
        newScreenerDisabled={newScreenerDisabled}
        isOpen={isSidebarOpen}
        onClose={() => setIsSidebarOpen(false)}
      />

      <NewAnalysisForm
        isOpen={showNewAnalysis}
        onClose={() => setShowNewAnalysis(false)}
        onTaskCreated={(taskId) => {
          setShowNewAnalysis(false);
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
                    TradingAgents Report Center
                  </p>
                  <h1 className="font-heading mt-3 text-3xl font-bold tracking-tight text-slate-900 md:text-4xl">
                    Content-first research workbench
                  </h1>
                  <p className="mt-2 max-w-2xl text-sm leading-6 text-slate-600">
                    Jump straight into the freshest report, search across tickers,
                    launch a brand-new background analysis, or build a ranked screener pool.
                  </p>
                </div>
                <button
                  type="button"
                  className="group md:hidden"
                  onClick={() => setIsSidebarOpen(true)}
                  aria-label="Open sidebar"
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
                    Search reports
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
                      placeholder="Search by ticker or report id"
                      className="focus-ring w-full rounded-2xl border border-[var(--border-strong)] bg-slate-50 py-3 pl-10 pr-4 text-sm font-medium text-slate-800 transition focus:border-[var(--primary)]"
                    />
                  </div>
                  <p className="mt-1 text-xs text-slate-500">
                    Filter by ticker, report id, or use the quick chips below.
                  </p>
                </div>
                <div className="flex flex-wrap gap-3">
                  <button
                    type="button"
                    className="interactive-button focus-ring rounded-full border border-[var(--primary)] bg-[var(--primary)] px-5 py-3 text-xs font-semibold uppercase tracking-[0.2em] text-white"
                    disabled={newAnalysisDisabled}
                    onClick={() => setShowNewAnalysis(true)}
                  >
                    Launch Analysis
                  </button>
                  <button
                    type="button"
                    className="interactive-button focus-ring rounded-full border border-[var(--accent)] bg-[var(--accent)] px-5 py-3 text-xs font-semibold uppercase tracking-[0.2em] text-white"
                    disabled={newScreenerDisabled}
                    onClick={() => setShowNewScreener(true)}
                  >
                    Launch Screener
                  </button>
                </div>
              </div>

              <div className="mt-10 grid gap-6 md:grid-cols-2">
                <section className="space-y-3">
                  <div className="flex items-center justify-between">
                    <h2 className="text-sm font-semibold uppercase tracking-[0.3em] text-slate-500">
                      Recent reports
                    </h2>
                    <span className="text-xs font-semibold uppercase tracking-[0.3em] text-slate-400">
                      Latest
                    </span>
                  </div>
                  <ul className="divide-y divide-slate-100 rounded-2xl border border-slate-100 bg-slate-50 text-sm shadow-sm">
                    {recentReports.length === 0 ? (
                      <li className="px-4 py-4 text-xs font-medium text-slate-500">
                        Reports will appear here as soon as they are generated.
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
                              {formatReportDate(report)}
                            </p>
                          </div>
                          <span className="text-xs font-semibold text-[var(--primary)]">
                            Open
                          </span>
                        </li>
                      ))
                    )}
                  </ul>
                </section>

                <section className="space-y-3">
                  <h2 className="text-sm font-semibold uppercase tracking-[0.3em] text-slate-500">
                    Recent tickers
                  </h2>
                  <div className="flex flex-wrap gap-2">
                    {recentTickers.length === 0 ? (
                      <span className="rounded-full border border-[var(--border)] px-3 py-1 text-xs font-semibold text-slate-500">
                        Waiting for reports
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

function formatReportDate(report: Report) {
  if (report.date && report.time) {
    return `${report.date} · ${report.time}`;
  }
  if (report.date) {
    return report.date;
  }
  return "Unknown date";
}
