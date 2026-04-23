"use client";

import Link from "next/link";
import { startTransition, useDeferredValue, useEffect, useMemo, useState } from "react";
import { useRouter } from "next/navigation";
import { useWorkbenchChrome } from "@/components/WorkbenchShell";
import { useWorkbench } from "@/components/WorkbenchProvider";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import {
  buildActivityHref,
  buildHomeHref,
  buildReportHref,
} from "@/lib/workbenchRoutes";

interface HomeDashboardProps {
  initialSearchQuery: string;
}

export function HomeDashboard({ initialSearchQuery }: HomeDashboardProps) {
  const router = useRouter();
  const { openAnalysisDialog } = useWorkbenchChrome();
  const {
    activeTasks,
    loadingReports,
    newAnalysisDisabled,
    recentReports,
    reports,
    reportsError,
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

  const trackedTickers = useMemo(() => {
    const values = new Set<string>();

    for (const report of reports) {
      values.add(report.ticker);
    }

    return Array.from(values).sort((left, right) => left.localeCompare(right));
  }, [reports]);

  const heroTitle = deferredSearchQuery
    ? `Analysis results for ${searchQuery.trim()}`
    : "Analysis workspace";

  return (
    <main className="flex min-h-[100vh] flex-1 flex-col px-4 py-6 md:px-7 lg:px-9">
      <div className="mx-auto w-full max-w-6xl space-y-6">
        <Card className="card-surface rounded-[30px]">
          <CardContent className="px-6 py-8 md:px-8">
          <div className="flex flex-col gap-6 lg:flex-row lg:items-end lg:justify-between">
            <div className="max-w-3xl">
              <p className="text-[11px] font-semibold uppercase tracking-[0.24em] text-[var(--primary)]">
                Analysis
              </p>
              <h1 className="mt-3 text-4xl font-semibold tracking-tight text-slate-900 md:text-[3.2rem]">
                {heroTitle}
              </h1>
              <p className="mt-4 max-w-2xl text-sm leading-7 text-slate-600">
                Search reports, jump back into coverage, and keep the analysis
                workspace centered on report reading instead of mixed navigation utilities.
              </p>
            </div>

            <div className="flex flex-wrap gap-3">
              <Button type="button" disabled={newAnalysisDisabled} onClick={openAnalysisDialog}>
                New Analysis
              </Button>
              <Button asChild variant="secondary">
                <Link href={buildActivityHref()}>View Activity</Link>
              </Button>
            </div>
          </div>

          <div className="mt-8 grid gap-4 md:grid-cols-3">
            <AnalysisMetric
              label="Report Library"
              value={`${reports.length}`}
              meta="Total indexed reports"
            />
            <AnalysisMetric
              label="Tracked Tickers"
              value={`${trackedTickers.length}`}
              meta="Coverage names in the library"
            />
            <AnalysisMetric
              label="Active Research"
              value={`${activeTasks.length}`}
              meta="In-flight analysis jobs"
            />
          </div>

          <div className="mt-8 rounded-[28px] border border-[var(--border)] bg-white/88 p-4 md:p-5">
            <label
              htmlFor="home-report-search"
              className="text-xs font-semibold uppercase tracking-[0.22em] text-slate-500"
            >
              Search reports
            </label>
            <Input
              id="home-report-search"
              type="search"
              value={searchQuery}
              onChange={(event) => setSearchQuery(event.target.value)}
              placeholder="Ticker or report id"
              className="mt-3 border-[var(--border-strong)] bg-[var(--surface-strong)] text-slate-900"
            />
            <p className="mt-2 text-sm text-slate-500">
              Results update in place and keep the query in the URL for deep-linking.
            </p>
          </div>
          </CardContent>
        </Card>

        <section className="grid gap-6 xl:grid-cols-[minmax(0,1.1fr)_minmax(0,0.9fr)]">
          <section className="viewer-frame px-6 py-6 md:px-8">
            <div className="flex items-center justify-between gap-4">
              <div>
                <p className="text-[11px] font-semibold uppercase tracking-[0.2em] text-slate-500">
                  {deferredSearchQuery ? "Matching Reports" : "Recent Reports"}
                </p>
                <h2 className="mt-2 text-2xl font-semibold tracking-tight text-slate-900">
                  {deferredSearchQuery
                    ? `${matchingReports.length} matching reports`
                    : "Jump back into coverage"}
                </h2>
              </div>
              {deferredSearchQuery ? (
                <Link
                  href={buildHomeHref("")}
                  className="text-xs font-semibold uppercase tracking-[0.16em] text-[var(--primary)]"
                >
                  Clear search
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
                    className="group list-item-surface flex items-center justify-between gap-4 rounded-[24px] border border-[var(--border)] bg-white/88 px-4 py-4 hover:border-[var(--primary)]"
                  >
                    <div className="min-w-0">
                      <p className="text-lg font-semibold text-slate-900">{report.ticker}</p>
                      <p className="mt-1 truncate font-mono text-[11px] text-slate-500">
                        {report.id}
                      </p>
                    </div>
                    <span className="text-xs font-semibold uppercase tracking-[0.16em] text-[var(--primary)]">
                      Open
                    </span>
                  </Link>
                ))}
              </div>
            )}
          </section>

          <div className="space-y-6">
            <Card className="card-surface rounded-[28px]">
              <CardContent className="px-6 py-6">
              <div className="flex items-center justify-between gap-4">
                <div>
                  <p className="text-[11px] font-semibold uppercase tracking-[0.2em] text-slate-500">
                    Tracked Tickers
                  </p>
                  <h2 className="mt-2 text-2xl font-semibold tracking-tight text-slate-900">
                    Coverage map
                  </h2>
                </div>
                <Badge variant="secondary" className="text-slate-500">
                  {trackedTickers.length}
                </Badge>
              </div>

              <div className="mt-4 flex flex-wrap gap-2">
                {trackedTickers.length === 0 ? (
                  <Badge variant="secondary" className="px-3 py-2 normal-case tracking-normal text-slate-500">
                    Waiting for reports
                  </Badge>
                ) : (
                  trackedTickers.slice(0, 18).map((ticker) => (
                    <Button
                      key={ticker}
                      asChild
                      variant={
                        deferredSearchQuery === ticker.toLowerCase() ? "default" : "secondary"
                      }
                      size="sm"
                      className={
                        deferredSearchQuery === ticker.toLowerCase()
                          ? "shadow-none"
                          : "text-slate-700 hover:text-[var(--primary)]"
                      }
                    >
                      <Link href={buildHomeHref(ticker)}>{ticker}</Link>
                    </Button>
                  ))
                )}
              </div>
              </CardContent>
            </Card>

            <Card className="card-surface rounded-[28px]">
              <CardContent className="px-6 py-6">
              <p className="text-[11px] font-semibold uppercase tracking-[0.2em] text-slate-500">
                Coverage Snapshot
              </p>
              <div className="mt-4 rounded-[24px] border border-[var(--border)] bg-white/88 px-4 py-4">
                <p className="text-sm font-semibold text-slate-900">
                  {deferredSearchQuery
                    ? "Search is focused on one slice of the library."
                    : "Use the analysis rail as the reports home base."}
                </p>
                <p className="mt-3 text-sm leading-6 text-slate-600">
                  {deferredSearchQuery
                    ? `The current query is filtering against ${reports.length} indexed reports across ${trackedTickers.length} tickers.`
                    : `The library currently tracks ${reports.length} reports across ${trackedTickers.length} tickers, with new research work routed through the unified sidebar action.`}
                </p>
                {recentReports[0] ? (
                  <div className="mt-4">
                    <Badge variant="secondary">
                      Latest indexed report · {recentReports[0].ticker}
                    </Badge>
                  </div>
                ) : null}
              </div>
              </CardContent>
            </Card>
          </div>
        </section>
      </div>
    </main>
  );
}

function AnalysisMetric({
  label,
  value,
  meta,
}: {
  label: string;
  value: string;
  meta: string;
}) {
  return (
    <Card className="rounded-[24px] bg-white/88">
      <CardContent className="px-4 py-4">
      <p className="text-[11px] font-semibold uppercase tracking-[0.18em] text-slate-500">
        {label}
      </p>
      <p className="mt-3 text-3xl font-semibold tracking-tight text-slate-900">{value}</p>
      <p className="mt-2 text-sm text-slate-500">{meta}</p>
      </CardContent>
    </Card>
  );
}
