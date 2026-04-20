"use client";

import Link from "next/link";
import { startTransition, useDeferredValue, useEffect, useMemo, useState } from "react";
import { useRouter } from "next/navigation";
import { useWorkbenchChrome } from "@/components/WorkbenchShell";
import { useWorkbench } from "@/components/WorkbenchProvider";
import {
  buildHomeHref,
  buildJournalHref,
  buildReportHref,
  buildScreenerRunHref,
  buildScreenerTaskHref,
  buildTaskHref,
} from "@/lib/workbenchRoutes";

interface HomeDashboardProps {
  initialSearchQuery: string;
}

export function HomeDashboard({ initialSearchQuery }: HomeDashboardProps) {
  const router = useRouter();
  const { openAnalysisDialog, openScreenerDialog } = useWorkbenchChrome();
  const {
    activeScreenerTasks,
    activeTasks,
    loadingReports,
    newAnalysisDisabled,
    newScreenerDisabled,
    recentReports,
    recentTickers,
    reports,
    reportsError,
    screenerRuns,
  } = useWorkbench();
  const [searchQuery, setSearchQuery] = useState(initialSearchQuery);
  const deferredSearchQuery = useDeferredValue(searchQuery.trim().toLowerCase());

  useEffect(() => {
    setSearchQuery(initialSearchQuery);
  }, [initialSearchQuery]);

  useEffect(() => {
    const timeoutId = window.setTimeout(() => {
      startTransition(() => {
        router.replace(buildHomeHref(searchQuery));
      });
    }, 180);

    return () => {
      window.clearTimeout(timeoutId);
    };
  }, [router, searchQuery]);

  const matchingReports = useMemo(() => {
    if (!deferredSearchQuery) {
      return recentReports;
    }

    return reports.filter(
      (report) =>
        report.ticker.toLowerCase().includes(deferredSearchQuery) ||
        report.id.toLowerCase().includes(deferredSearchQuery)
    );
  }, [deferredSearchQuery, recentReports, reports]);

  const matchingScreenerRuns = useMemo(() => {
    if (!deferredSearchQuery) {
      return screenerRuns.slice(0, 4);
    }

    return screenerRuns.filter((run) =>
      run.id.toLowerCase().includes(deferredSearchQuery)
    );
  }, [deferredSearchQuery, screenerRuns]);

  const heroTitle = deferredSearchQuery
    ? `Search results for ${searchQuery.trim()}`
    : "Research workbench";

  return (
    <main className="flex min-h-[100vh] flex-1 flex-col px-4 py-6 md:px-7 lg:px-9">
      <div className="mx-auto w-full max-w-6xl space-y-6">
        <section className="card-surface rounded-[32px] px-6 py-8 md:px-8 md:py-10">
          <div className="flex flex-col gap-8 lg:flex-row lg:items-end lg:justify-between">
            <div className="max-w-3xl">
              <p className="text-[12px] font-semibold uppercase tracking-[0.38em] text-[var(--primary)]">
                TradingAgents
              </p>
              <h1 className="font-heading mt-4 text-4xl font-bold tracking-tight text-slate-900 md:text-5xl">
                {heroTitle}
              </h1>
              <p className="mt-4 max-w-2xl text-sm leading-7 text-slate-600">
                Reports, running research tasks, screener builds, and the manual
                journal now live as direct destinations instead of temporary panels.
              </p>
            </div>

            <div className="flex flex-wrap gap-3">
              <button
                type="button"
                className="interactive-button focus-ring rounded-full border border-[var(--primary)] bg-[var(--primary)] px-5 py-3 text-xs font-semibold uppercase tracking-[0.2em] text-white disabled:cursor-not-allowed disabled:opacity-70"
                disabled={newAnalysisDisabled}
                onClick={openAnalysisDialog}
              >
                Launch Analysis
              </button>
              <button
                type="button"
                className="interactive-button focus-ring rounded-full border border-[var(--accent)] bg-[var(--accent)] px-5 py-3 text-xs font-semibold uppercase tracking-[0.2em] text-white disabled:cursor-not-allowed disabled:opacity-70"
                disabled={newScreenerDisabled}
                onClick={openScreenerDialog}
              >
                Launch Screener
              </button>
              <Link
                href={buildJournalHref()}
                className="interactive-button focus-ring rounded-full border border-[var(--border-strong)] bg-white px-5 py-3 text-xs font-semibold uppercase tracking-[0.2em] text-slate-700"
              >
                Open Trade Journal
              </Link>
            </div>
          </div>

          <div className="mt-8 rounded-[28px] border border-[var(--border)] bg-white/88 p-4 md:p-5">
            <label
              htmlFor="home-report-search"
              className="text-xs font-semibold uppercase tracking-[0.28em] text-slate-500"
            >
              Search reports from home
            </label>
            <input
              id="home-report-search"
              type="search"
              value={searchQuery}
              onChange={(event) => setSearchQuery(event.target.value)}
              placeholder="Ticker or report id"
              className="focus-ring mt-3 w-full rounded-[22px] border border-[var(--border-strong)] bg-[var(--surface-strong)] px-4 py-3 text-sm font-medium text-slate-900"
            />
            <p className="mt-2 text-sm text-slate-500">
              Results render in this page immediately and the query is reflected in the
              URL for deep-linking.
            </p>
          </div>
        </section>

        <section className="grid gap-6 xl:grid-cols-[minmax(0,1.1fr)_minmax(0,0.9fr)]">
          <div className="space-y-6">
            <section className="viewer-frame px-6 py-6 md:px-8">
              <div className="flex items-center justify-between gap-4">
                <div>
                  <p className="text-[11px] font-semibold uppercase tracking-[0.3em] text-slate-500">
                    {deferredSearchQuery ? "Matching Reports" : "Recent Reports"}
                  </p>
                  <h2 className="mt-2 text-2xl font-semibold tracking-tight text-slate-900">
                    {deferredSearchQuery
                      ? `${matchingReports.length} report results`
                      : "Jump back into analysis"}
                  </h2>
                </div>
                {deferredSearchQuery ? (
                  <Link
                    href={buildHomeHref("")}
                    className="text-xs font-semibold uppercase tracking-[0.24em] text-[var(--primary)]"
                  >
                    Clear Search
                  </Link>
                ) : null}
              </div>

              {reportsError ? (
                <div className="mt-5 rounded-[24px] border border-[rgba(163,53,53,0.2)] bg-[rgba(163,53,53,0.08)] px-4 py-4 text-sm text-[var(--danger)]">
                  {reportsError}
                </div>
              ) : loadingReports ? (
                <div className="mt-5 rounded-[24px] border border-dashed border-[var(--border)] bg-[var(--surface-strong)] px-5 py-8 text-sm text-slate-500">
                  Loading report index...
                </div>
              ) : matchingReports.length === 0 ? (
                <div className="mt-5 rounded-[24px] border border-dashed border-[var(--border)] bg-[var(--surface-strong)] px-5 py-8 text-sm text-slate-500">
                  No reports match this search yet.
                </div>
              ) : (
                <div className="mt-5 space-y-3">
                  {matchingReports.slice(0, 8).map((report) => (
                    <Link
                      key={report.id}
                      href={buildReportHref(report.id)}
                      className="group flex items-center justify-between gap-4 rounded-[24px] border border-[var(--border)] bg-white/88 px-4 py-4 transition hover:border-[var(--primary)] hover:shadow-[0_18px_38px_rgba(18,28,41,0.08)]"
                    >
                      <div className="min-w-0">
                        <p className="text-lg font-semibold text-slate-900">{report.ticker}</p>
                        <p className="mt-1 truncate font-mono text-[11px] text-slate-500">
                          {report.id}
                        </p>
                      </div>
                      <span className="text-xs font-semibold uppercase tracking-[0.22em] text-[var(--primary)]">
                        Open
                      </span>
                    </Link>
                  ))}
                </div>
              )}
            </section>

            <section className="card-surface rounded-[30px] px-6 py-6">
              <div className="flex items-center justify-between gap-4">
                <div>
                  <p className="text-[11px] font-semibold uppercase tracking-[0.3em] text-slate-500">
                    Active Work
                  </p>
                  <h2 className="mt-2 text-2xl font-semibold tracking-tight text-slate-900">
                    Background queues
                  </h2>
                </div>
                <span className="rounded-full border border-[var(--border)] bg-white px-3 py-1 text-xs font-semibold uppercase tracking-[0.18em] text-slate-500">
                  {activeTasks.length + activeScreenerTasks.length} active
                </span>
              </div>

              <div className="mt-5 grid gap-4 md:grid-cols-2">
                <QueueCard
                  title="Analysis Tasks"
                  emptyLabel="No active analysis tasks."
                  items={activeTasks.map((task) => ({
                    href: buildTaskHref(task.id),
                    label: task.ticker,
                    meta: task.status,
                  }))}
                />
                <QueueCard
                  title="Screener Tasks"
                  emptyLabel="No active screener tasks."
                  items={activeScreenerTasks.map((task) => ({
                    href: buildScreenerTaskHref(task.id),
                    label: "Candidate pool build",
                    meta: task.status,
                  }))}
                />
              </div>
            </section>
          </div>

          <div className="space-y-6">
            <section className="card-surface rounded-[30px] px-6 py-6">
              <p className="text-[11px] font-semibold uppercase tracking-[0.3em] text-slate-500">
                Recent Tickers
              </p>
              <div className="mt-4 flex flex-wrap gap-2">
                {recentTickers.length === 0 ? (
                  <span className="rounded-full border border-[var(--border)] bg-white px-3 py-2 text-xs font-semibold text-slate-500">
                    Waiting for reports
                  </span>
                ) : (
                  recentTickers.map((ticker) => (
                    <Link
                      key={ticker}
                      href={buildHomeHref(ticker)}
                      className="rounded-full border border-[var(--border)] bg-white px-3 py-2 text-xs font-semibold text-slate-700 transition hover:border-[var(--primary)] hover:text-[var(--primary)]"
                    >
                      {ticker}
                    </Link>
                  ))
                )}
              </div>
            </section>

            <section className="card-surface rounded-[30px] px-6 py-6">
              <div className="flex items-center justify-between gap-4">
                <div>
                  <p className="text-[11px] font-semibold uppercase tracking-[0.3em] text-slate-500">
                    Screener Runs
                  </p>
                  <h2 className="mt-2 text-2xl font-semibold tracking-tight text-slate-900">
                    Ranked pools
                  </h2>
                </div>
              </div>

              {matchingScreenerRuns.length === 0 ? (
                <div className="mt-5 rounded-[24px] border border-dashed border-[var(--border)] bg-[var(--surface-strong)] px-5 py-8 text-sm text-slate-500">
                  No screener runs match this search yet.
                </div>
              ) : (
                <div className="mt-5 space-y-3">
                  {matchingScreenerRuns.slice(0, 6).map((run) => (
                    <Link
                      key={run.id}
                      href={buildScreenerRunHref(run.id)}
                      className="flex items-center justify-between gap-4 rounded-[24px] border border-[var(--border)] bg-white/88 px-4 py-4 transition hover:border-[var(--accent)] hover:shadow-[0_18px_38px_rgba(18,28,41,0.08)]"
                    >
                      <div className="min-w-0">
                        <p className="truncate text-sm font-semibold text-slate-900">
                          {run.id}
                        </p>
                        <p className="mt-1 text-xs uppercase tracking-[0.22em] text-slate-500">
                          {run.candidate_count} candidates
                        </p>
                      </div>
                      <span className="text-xs font-semibold uppercase tracking-[0.22em] text-[var(--accent)]">
                        Open
                      </span>
                    </Link>
                  ))}
                </div>
              )}
            </section>
          </div>
        </section>
      </div>
    </main>
  );
}

function QueueCard({
  title,
  emptyLabel,
  items,
}: {
  title: string;
  emptyLabel: string;
  items: Array<{ href: string; label: string; meta: string }>;
}) {
  return (
    <section className="rounded-[26px] border border-[var(--border)] bg-white/88 p-4">
      <p className="text-xs font-semibold uppercase tracking-[0.24em] text-slate-500">
        {title}
      </p>
      {items.length === 0 ? (
        <p className="mt-3 text-sm text-slate-500">{emptyLabel}</p>
      ) : (
        <div className="mt-3 space-y-2">
          {items.map((item) => (
            <Link
              key={`${item.href}-${item.label}`}
              href={item.href}
              className="flex items-center justify-between gap-3 rounded-[20px] border border-[var(--border)] bg-[var(--surface-strong)] px-3 py-3 text-sm transition hover:border-[var(--accent)] hover:bg-white"
            >
              <span className="font-semibold text-slate-900">{item.label}</span>
              <span className="text-xs font-semibold uppercase tracking-[0.2em] text-slate-500">
                {item.meta}
              </span>
            </Link>
          ))}
        </div>
      )}
    </section>
  );
}
