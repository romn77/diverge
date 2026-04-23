"use client";

import Link from "next/link";
import { useWorkbench } from "@/components/WorkbenchProvider";
import {
  buildHomeHref,
  buildScreenerHref,
  buildScreenerTaskHref,
  buildTaskHref,
} from "@/lib/workbenchRoutes";

export function ActivityDashboard() {
  const { activeScreenerTasks, activeTasks } = useWorkbench();
  const totalActive = activeTasks.length + activeScreenerTasks.length;

  return (
    <main className="flex min-h-[100vh] flex-1 flex-col px-4 py-6 md:px-7 lg:px-9">
      <div className="mx-auto w-full max-w-6xl space-y-6">
        <section className="card-surface rounded-[30px] px-6 py-8 md:px-8">
          <div className="flex flex-col gap-6 lg:flex-row lg:items-end lg:justify-between">
            <div className="max-w-3xl">
              <p className="text-[11px] font-semibold uppercase tracking-[0.24em] text-[var(--primary)]">
                Activity
              </p>
              <h1 className="mt-3 text-4xl font-semibold tracking-tight text-slate-900 md:text-[3.2rem]">
                Background work
              </h1>
              <p className="mt-4 max-w-2xl text-sm leading-7 text-slate-600">
                Monitor in-flight analysis and screener jobs from one place instead of
                stacking task queues into the navigation rail.
              </p>
            </div>

            <div className="flex flex-wrap gap-3">
              <Link
                href={buildHomeHref()}
                className="interactive-button focus-ring rounded-full border border-[var(--border-strong)] bg-white px-5 py-3 text-xs font-semibold tracking-[0.04em] text-slate-700"
              >
                Analysis
              </Link>
              <Link
                href={buildScreenerHref()}
                className="interactive-button focus-ring rounded-full border border-[var(--border-strong)] bg-white px-5 py-3 text-xs font-semibold tracking-[0.04em] text-slate-700"
              >
                Screener
              </Link>
            </div>
          </div>

          <div className="mt-8 grid gap-4 md:grid-cols-3">
            <ActivityMetric
              label="Total Active"
              value={`${totalActive}`}
              meta="Combined background jobs"
            />
            <ActivityMetric
              label="Analysis Jobs"
              value={`${activeTasks.length}`}
              meta="Research tasks in flight"
            />
            <ActivityMetric
              label="Screener Jobs"
              value={`${activeScreenerTasks.length}`}
              meta="Candidate builds in flight"
            />
          </div>
        </section>

        <section className="grid gap-6 xl:grid-cols-2">
          <ActivityQueueSection
            title="Analysis tasks"
            description="Research jobs waiting or running."
            emptyLabel="No active analysis jobs."
            items={activeTasks.map((task) => ({
              href: buildTaskHref(task.id),
              label: task.ticker,
              meta: task.latest_progress?.current_agent ?? task.analysis_date,
              status: task.status,
            }))}
          />
          <ActivityQueueSection
            title="Screener tasks"
            description="Candidate-pool builds currently in motion."
            emptyLabel="No active screener jobs."
            items={activeScreenerTasks.map((task) => ({
              href: buildScreenerTaskHref(task.id),
              label: task.request_payload?.markets.join(", ") || "Candidate pool build",
              meta: task.request_payload?.as_of_date ?? "Awaiting next update",
              status: task.status,
            }))}
          />
        </section>
      </div>
    </main>
  );
}

function ActivityMetric({
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

function ActivityQueueSection({
  title,
  description,
  emptyLabel,
  items,
}: {
  title: string;
  description: string;
  emptyLabel: string;
  items: Array<{ href: string; label: string; meta: string; status: string }>;
}) {
  return (
    <section className="card-surface rounded-[28px] px-6 py-6">
      <div className="flex items-start justify-between gap-4">
        <div>
          <p className="text-[11px] font-semibold uppercase tracking-[0.2em] text-slate-500">
            {title}
          </p>
          <p className="mt-3 max-w-xl text-sm leading-6 text-slate-600">{description}</p>
        </div>
        <span className="rounded-full border border-[var(--border)] bg-white px-3 py-1 text-[11px] font-semibold text-slate-500">
          {items.length}
        </span>
      </div>

      {items.length === 0 ? (
        <div className="mt-5 rounded-[24px] border border-dashed border-[var(--border)] bg-[var(--surface-strong)] px-5 py-8 text-sm text-slate-500">
          {emptyLabel}
        </div>
      ) : (
        <div className="mt-5 space-y-3">
          {items.map((item) => (
            <Link
              key={`${item.href}-${item.label}`}
              href={item.href}
              className="group list-item-surface flex items-center justify-between gap-4 rounded-[24px] border border-[var(--border)] bg-white/88 px-4 py-4 hover:border-[var(--primary)]"
            >
              <div className="min-w-0">
                <p className="truncate text-base font-semibold text-slate-900">{item.label}</p>
                <p className="mt-1 truncate text-xs uppercase tracking-[0.16em] text-slate-500">
                  {item.meta}
                </p>
              </div>
              <span className="rounded-full border border-[var(--border)] bg-[var(--surface-strong)] px-3 py-1 text-[10px] font-semibold uppercase tracking-[0.16em] text-slate-600">
                {item.status}
              </span>
            </Link>
          ))}
        </div>
      )}
    </section>
  );
}
