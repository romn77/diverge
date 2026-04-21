"use client";

import Link from "next/link";
import { useMemo } from "react";
import { useWorkbenchChrome } from "@/components/WorkbenchShell";
import { useWorkbench } from "@/components/WorkbenchProvider";
import {
  buildActivityHref,
  buildScreenerRunHref,
  buildScreenerTaskHref,
} from "@/lib/workbenchRoutes";

export function ScreenerDashboard() {
  const { openScreenerDialog } = useWorkbenchChrome();
  const { activeScreenerTasks, screenerRuns } = useWorkbench();
  const recentRuns = screenerRuns.slice(0, 8);
  const firstActiveScreenerTask = activeScreenerTasks[0];
  const recentMarkets = useMemo(() => {
    const values = new Set<string>();

    for (const run of screenerRuns) {
      for (const market of run.markets) {
        values.add(market);
      }
      if (values.size >= 6) {
        break;
      }
    }

    return Array.from(values).slice(0, 6);
  }, [screenerRuns]);

  return (
    <main className="flex min-h-[100vh] flex-1 flex-col px-4 py-6 md:px-7 lg:px-9">
      <div className="mx-auto w-full max-w-6xl space-y-6">
        <section className="card-surface rounded-[30px] px-6 py-8 md:px-8">
          <div className="flex flex-col gap-6 lg:flex-row lg:items-end lg:justify-between">
            <div className="max-w-3xl">
              <p className="text-[11px] font-semibold uppercase tracking-[0.24em] text-[var(--accent)]">
                Screener
              </p>
              <h1 className="mt-3 text-4xl font-semibold tracking-tight text-slate-900 md:text-[3.2rem]">
                Candidate workspace
              </h1>
              <p className="mt-4 max-w-2xl text-sm leading-7 text-slate-600">
                Launch fresh screens, revisit ranked pools, and keep the screener
                workspace separate from report browsing.
              </p>
            </div>

            <div className="flex flex-wrap gap-3">
              <button
                type="button"
                className="interactive-button focus-ring rounded-full border border-[var(--accent)] bg-[var(--accent)] px-5 py-3 text-xs font-semibold tracking-[0.04em] text-white"
                onClick={openScreenerDialog}
              >
                New Screener
              </button>
              <Link
                href={buildActivityHref()}
                className="interactive-button focus-ring rounded-full border border-[var(--border-strong)] bg-white px-5 py-3 text-xs font-semibold tracking-[0.04em] text-slate-700"
              >
                View Activity
              </Link>
            </div>
          </div>

          <div className="mt-8 grid gap-4 md:grid-cols-3">
            <ScreenerMetric
              label="Recent Runs"
              value={`${screenerRuns.length}`}
              meta="Saved candidate pools"
            />
            <ScreenerMetric
              label="Active Builds"
              value={`${activeScreenerTasks.length}`}
              meta="Background screener jobs"
            />
            <ScreenerMetric
              label="Markets"
              value={`${recentMarkets.length}`}
              meta="Recent market coverage"
            />
          </div>
        </section>

        <section className="grid gap-6 xl:grid-cols-[minmax(0,1.1fr)_minmax(0,0.9fr)]">
          <section className="viewer-frame px-6 py-6 md:px-8">
            <div className="flex items-center justify-between gap-4">
              <div>
                <p className="text-[11px] font-semibold uppercase tracking-[0.2em] text-slate-500">
                  Recent Runs
                </p>
                <h2 className="mt-2 text-2xl font-semibold tracking-tight text-slate-900">
                  Ranked candidate pools
                </h2>
              </div>
              {activeScreenerTasks.length > 0 ? (
                <Link
                  href={
                    firstActiveScreenerTask
                      ? buildScreenerTaskHref(firstActiveScreenerTask.id)
                      : buildActivityHref()
                  }
                  className="text-xs font-semibold uppercase tracking-[0.16em] text-[var(--accent)]"
                >
                  Active build
                </Link>
              ) : null}
            </div>

            {recentRuns.length === 0 ? (
              <div className="mt-5 rounded-[24px] border border-dashed border-[var(--border)] bg-[var(--surface-strong)] px-5 py-8 text-sm text-slate-500">
                No screener runs yet. Launch a new screener to generate the first ranked pool.
              </div>
            ) : (
              <div className="mt-5 space-y-3">
                {recentRuns.map((run) => (
                  <Link
                    key={run.id}
                    href={buildScreenerRunHref(run.id)}
                    className="group flex items-center justify-between gap-4 rounded-[24px] border border-[var(--border)] bg-white/88 px-4 py-4 transition hover:border-[var(--accent)] hover:shadow-[0_18px_38px_rgba(18,28,41,0.08)]"
                  >
                    <div className="min-w-0">
                      <p className="truncate text-base font-semibold text-slate-900">{run.id}</p>
                      <p className="mt-1 truncate text-xs uppercase tracking-[0.16em] text-slate-500">
                        {run.markets.join(", ")} · {run.candidate_count} candidates
                      </p>
                    </div>
                    <span className="text-xs font-semibold uppercase tracking-[0.16em] text-[var(--accent)]">
                      {formatRunDate(run.as_of_date)}
                    </span>
                  </Link>
                ))}
              </div>
            )}
          </section>

          <div className="space-y-6">
            <section className="card-surface rounded-[28px] px-6 py-6">
              <p className="text-[11px] font-semibold uppercase tracking-[0.2em] text-slate-500">
                Market Coverage
              </p>
              <div className="mt-4 flex flex-wrap gap-2">
                {recentMarkets.length === 0 ? (
                  <span className="rounded-full border border-[var(--border)] bg-white px-3 py-2 text-xs font-semibold text-slate-500">
                    Waiting for screener history
                  </span>
                ) : (
                  recentMarkets.map((market) => (
                    <span
                      key={market}
                      className="rounded-full border border-[var(--border)] bg-white px-3 py-2 text-xs font-semibold text-slate-700"
                    >
                      {market}
                    </span>
                  ))
                )}
              </div>
            </section>

            <section className="card-surface rounded-[28px] px-6 py-6">
              <p className="text-[11px] font-semibold uppercase tracking-[0.2em] text-slate-500">
                Queue Snapshot
              </p>
              <div className="mt-4 rounded-[24px] border border-[var(--border)] bg-white/88 px-4 py-4">
                <p className="text-3xl font-semibold tracking-tight text-slate-900">
                  {activeScreenerTasks.length}
                </p>
                <p className="mt-2 text-sm leading-6 text-slate-600">
                  Screener builds currently in motion. Use Activity for task-by-task monitoring.
                </p>
                <Link
                  href={buildActivityHref()}
                  className="mt-4 inline-flex text-xs font-semibold uppercase tracking-[0.16em] text-[var(--primary)]"
                >
                  Open Activity
                </Link>
              </div>
            </section>
          </div>
        </section>
      </div>
    </main>
  );
}

function ScreenerMetric({
  label,
  value,
  meta,
}: {
  label: string;
  value: string;
  meta: string;
}) {
  return (
    <div className="rounded-[24px] border border-[var(--border)] bg-white/88 px-4 py-4">
      <p className="text-[11px] font-semibold uppercase tracking-[0.18em] text-slate-500">
        {label}
      </p>
      <p className="mt-3 text-3xl font-semibold tracking-tight text-slate-900">{value}</p>
      <p className="mt-2 text-sm text-slate-500">{meta}</p>
    </div>
  );
}

function formatRunDate(value: string): string {
  const parsed = new Date(`${value}T00:00:00`);
  if (!Number.isNaN(parsed.getTime())) {
    return new Intl.DateTimeFormat("en", {
      month: "short",
      day: "numeric",
    }).format(parsed);
  }

  return value;
}
