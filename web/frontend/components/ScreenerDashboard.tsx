"use client";

import Link from "next/link";
import { useMemo } from "react";
import { usePreferences } from "@/components/PreferencesProvider";
import { useWorkbenchChrome } from "@/components/WorkbenchShell";
import { useWorkbench } from "@/components/WorkbenchProvider";
import { MetricCard } from "@/components/workbench/MetricCard";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import type { ScreenerRunSummary } from "@/lib/api";
import {
  buildActivityHref,
  buildScreenerRunHref,
  buildScreenerTaskHref,
} from "@/lib/workbenchRoutes";

function buildScreenerRunListKey(run: ScreenerRunSummary, index: number): string {
  return [
    run.id,
    run.snapshot_slot ?? "archive",
    run.snapshot_available ? "snapshot" : "metadata",
    run.generated_at,
    index,
  ].join(":");
}

function getScreenerRunScopeLabel(
  run: ScreenerRunSummary,
  currentUserId: string | null | undefined,
  t: ReturnType<typeof usePreferences>["t"]
): string {
  if (!run.owner_user_id || run.owner_user_id === currentUserId) {
    return t("screenerDashboard.scope.mine", "Mine");
  }

  return t("screenerDashboard.scope.team", "Team");
}

export function ScreenerDashboard() {
  const { locale, t } = usePreferences();
  const { openScreenerDialog } = useWorkbenchChrome();
  const { activeScreenerTasks, authState, newScreenerDisabled, screenerRuns } =
    useWorkbench();
  const recentRuns = screenerRuns.slice(0, 8);
  const firstActiveScreenerTask = activeScreenerTasks[0];
  const currentUserId = authState?.user?.id ?? null;
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
      <div className="workbench-content-frame space-y-6">
        <Card className="card-surface rounded-[30px]">
          <CardContent className="px-6 py-8 md:px-8">
          <div className="flex flex-col gap-6 lg:flex-row lg:items-end lg:justify-between">
            <div className="max-w-3xl">
              <p className="text-[11px] font-semibold uppercase tracking-[0.24em] text-[var(--accent)]">
                {t("sidebar.nav.screener", "Screener")}
              </p>
              <h1 className="workbench-page-title mt-3">
                {t("screenerDashboard.title", "Candidate workspace")}
              </h1>
              <p className="mt-4 max-w-2xl text-sm leading-7 text-slate-600">
                {t(
                  "screenerDashboard.description",
                  "Launch screens and review candidate pools."
                )}
              </p>
            </div>

            <div className="flex flex-wrap gap-3">
              <Button
                type="button"
                disabled={newScreenerDisabled}
                onClick={openScreenerDialog}
                className="bg-[var(--accent)] hover:bg-[var(--accent)] hover:brightness-105"
              >
                {t("screenerDashboard.newScreener", "New Screener")}
              </Button>
              <Button asChild variant="secondary">
                <Link href={buildActivityHref()}>
                  {t("home.viewActivity", "View Activity")}
                </Link>
              </Button>
            </div>
          </div>

          <div className="mt-8 grid gap-4 md:grid-cols-3">
            <MetricCard
              label={t("screenerDashboard.recentRuns", "Recent Runs")}
              value={`${screenerRuns.length}`}
              meta={t("screenerDashboard.recentRunsMeta", "Saved candidate pools")}
            />
            <MetricCard
              label={t("screenerDashboard.activeBuilds", "Active Builds")}
              value={`${activeScreenerTasks.length}`}
              meta={t("screenerDashboard.activeBuildsMeta", "Background screener jobs")}
            />
            <MetricCard
              label={t("screenerDashboard.markets", "Markets")}
              value={`${recentMarkets.length}`}
              meta={t("screenerDashboard.marketsMeta", "Recent market coverage")}
            />
          </div>
          </CardContent>
        </Card>

        <section className="grid gap-6 xl:grid-cols-[minmax(0,1.1fr)_minmax(0,0.9fr)]">
          <section className="viewer-frame px-6 py-6 md:px-8">
            <div className="flex items-center justify-between gap-4">
              <div>
                <p className="text-[11px] font-semibold uppercase tracking-[0.2em] text-slate-500">
                  {t("screenerDashboard.recentRuns", "Recent Runs")}
                </p>
                <h2 className="workbench-section-title mt-2 text-2xl">
                  {t("screenerDashboard.rankedPools", "Ranked candidate pools")}
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
                  {t("screenerDashboard.activeBuild", "Active build")}
                </Link>
              ) : null}
            </div>

            {recentRuns.length === 0 ? (
              <div className="mt-5 rounded-[24px] border border-dashed border-[var(--border)] bg-[var(--surface-strong)] px-5 py-8 text-sm text-slate-500">
                {t(
                  "screenerDashboard.emptyRuns",
                  "No screener runs yet. Launch a new screener to generate the first ranked pool."
                )}
              </div>
            ) : (
              <div className="mt-5 space-y-3">
                {recentRuns.map((run, index) => (
                  run.snapshot_available ? (
                    <Link
                      key={buildScreenerRunListKey(run, index)}
                      href={buildScreenerRunHref(run.id)}
                      className="group list-item-surface flex items-center justify-between gap-4 rounded-[24px] border border-[var(--border)] bg-white/88 px-4 py-4 hover:border-[var(--accent)]"
                    >
                      <div className="min-w-0">
                        <p className="truncate text-base font-semibold text-slate-900">{run.id}</p>
                        <p className="mt-1 truncate text-xs uppercase tracking-[0.16em] text-slate-500">
                          {t(
                            "screenerDashboard.runMeta",
                            ({ markets, count }) => `${markets} · ${count} candidates`,
                            { markets: run.markets.join(", "), count: run.candidate_count }
                          )}
                        </p>
                        <Badge variant="secondary" className="mt-2 px-2 py-1 text-[10px]">
                          {getScreenerRunScopeLabel(run, currentUserId, t)}
                        </Badge>
                      </div>
                      <div className="text-right">
                        <p className="text-xs font-semibold uppercase tracking-[0.16em] text-[var(--accent)]">
                          {formatRunDate(run.as_of_date, locale)}
                        </p>
                        <p className="mt-1 text-[10px] font-semibold uppercase tracking-[0.18em] text-slate-500">
                          {run.snapshot_slot === "previous"
                            ? t("screenerDashboard.previous", "Previous")
                            : t("screenerDashboard.current", "Current")}
                        </p>
                      </div>
                    </Link>
                  ) : (
                    <div
                      key={buildScreenerRunListKey(run, index)}
                      className="list-item-surface flex items-center justify-between gap-4 rounded-[24px] border border-[var(--border)] bg-white/72 px-4 py-4"
                    >
                      <div className="min-w-0">
                        <p className="truncate text-base font-semibold text-slate-900">{run.id}</p>
                        <p className="mt-1 truncate text-xs uppercase tracking-[0.16em] text-slate-500">
                          {t(
                            "screenerDashboard.runMeta",
                            ({ markets, count }) => `${markets} · ${count} candidates`,
                            { markets: run.markets.join(", "), count: run.candidate_count }
                          )}
                        </p>
                        <Badge variant="secondary" className="mt-2 px-2 py-1 text-[10px]">
                          {getScreenerRunScopeLabel(run, currentUserId, t)}
                        </Badge>
                      </div>
                      <div className="text-right">
                        <p className="text-xs font-semibold uppercase tracking-[0.16em] text-slate-500">
                          {formatRunDate(run.as_of_date, locale)}
                        </p>
                        <p className="mt-1 text-[10px] font-semibold uppercase tracking-[0.18em] text-slate-400">
                          {t("screenerDashboard.metadataOnly", "Metadata only")}
                        </p>
                      </div>
                    </div>
                  )
                ))}
              </div>
            )}
          </section>

          <div className="space-y-6">
            <Card className="card-surface rounded-[28px]">
              <CardContent className="px-6 py-6">
              <p className="text-[11px] font-semibold uppercase tracking-[0.2em] text-slate-500">
                {t("screenerDashboard.marketCoverage", "Market Coverage")}
              </p>
              <div className="mt-4 flex flex-wrap gap-2">
                {recentMarkets.length === 0 ? (
                  <Badge variant="secondary" className="px-3 py-2 normal-case tracking-normal text-slate-500">
                    {t("screenerDashboard.waitingHistory", "Waiting for screener history")}
                  </Badge>
                ) : (
                  recentMarkets.map((market) => (
                    <Badge
                      key={market}
                      variant="secondary"
                      className="px-3 py-2 normal-case tracking-normal text-slate-700"
                    >
                      {market}
                    </Badge>
                  ))
                )}
              </div>
              </CardContent>
            </Card>

            <Card className="card-surface rounded-[28px]">
              <CardContent className="px-6 py-6">
              <p className="text-[11px] font-semibold uppercase tracking-[0.2em] text-slate-500">
                {t("screenerDashboard.queueSnapshot", "Queue Snapshot")}
              </p>
              <div className="mt-4 rounded-[24px] border border-[var(--border)] bg-white/88 px-4 py-4">
                <p className="metric-card-value text-3xl font-semibold text-slate-900">
                  {activeScreenerTasks.length}
                </p>
                <p className="mt-2 text-sm leading-6 text-slate-600">
                  {t(
                    "screenerDashboard.queueHint",
                    "Screener builds currently in motion. Use Activity for task-by-task monitoring."
                  )}
                </p>
                <div className="mt-4">
                  <Button asChild variant="secondary" size="sm">
                    <Link href={buildActivityHref()}>
                      {t("screenerDashboard.openActivity", "Open Activity")}
                    </Link>
                  </Button>
                </div>
              </div>
              </CardContent>
            </Card>
          </div>
        </section>
      </div>
    </main>
  );
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
