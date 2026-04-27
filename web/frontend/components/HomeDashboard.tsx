"use client";

import Link from "next/link";
import { startTransition, useDeferredValue, useEffect, useMemo, useState } from "react";
import { useRouter } from "next/navigation";
import { usePreferences } from "@/components/PreferencesProvider";
import { useWorkbenchChrome } from "@/components/WorkbenchShell";
import { useWorkbench } from "@/components/WorkbenchProvider";
import { MetricCard } from "@/components/workbench/MetricCard";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import {
  buildActivityHref,
  buildHomeHref,
  buildReportHref,
} from "@/lib/workbenchRoutes";
import type { Report } from "@/lib/api";

interface HomeDashboardProps {
  initialSearchQuery: string;
}

type ReportScopeFilter = "all" | "mine" | "workspace";

const REPORT_SCOPE_FILTERS: ReportScopeFilter[] = ["all", "mine", "workspace"];
const REPORT_SCOPE_LABEL_KEYS: Record<ReportScopeFilter, string> = {
  all: "home.scope.all",
  mine: "home.scope.mine",
  workspace: "home.scope.workspace",
};

function isOwnedReport(
  report: Report,
  currentUserId: string | null | undefined
): boolean {
  if (!report.owner_user_id || !currentUserId) {
    return true;
  }
  return report.owner_user_id === currentUserId;
}

function matchesReportScope(
  report: Report,
  scope: ReportScopeFilter,
  currentUserId: string | null | undefined
): boolean {
  if (scope === "workspace") {
    return report.visibility === "workspace";
  }

  if (scope === "mine") {
    return isOwnedReport(report, currentUserId);
  }

  return true;
}

function matchesReportQuery(report: Report, normalizedQuery: string): boolean {
  if (!normalizedQuery) {
    return true;
  }

  return (
    report.ticker.toLowerCase().includes(normalizedQuery) ||
    report.id.toLowerCase().includes(normalizedQuery)
  );
}

export function HomeDashboard({ initialSearchQuery }: HomeDashboardProps) {
  const router = useRouter();
  const { t } = usePreferences();
  const { openAnalysisDialog } = useWorkbenchChrome();
  const {
    activeTasks,
    authState,
    loadingReports,
    newAnalysisDisabled,
    reports,
    reportsError,
  } = useWorkbench();
  const [searchQuery, setSearchQuery] = useState(initialSearchQuery);
  const [scopeFilter, setScopeFilter] = useState<ReportScopeFilter>("all");
  const deferredSearchQuery = useDeferredValue(searchQuery.trim().toLowerCase());
  const currentUserId = authState?.user?.id ?? null;

  const searchMatchedReports = useMemo(() => {
    return reports.filter((report) => matchesReportQuery(report, deferredSearchQuery));
  }, [deferredSearchQuery, reports]);

  const reportScopeCounts = useMemo(() => {
    return {
      all: searchMatchedReports.length,
      mine: searchMatchedReports.filter((report) =>
        matchesReportScope(report, "mine", currentUserId)
      ).length,
      workspace: searchMatchedReports.filter((report) =>
        matchesReportScope(report, "workspace", currentUserId)
      ).length,
    };
  }, [currentUserId, searchMatchedReports]);

  const scopedReports = useMemo(() => {
    return searchMatchedReports.filter((report) =>
      matchesReportScope(report, scopeFilter, currentUserId)
    );
  }, [currentUserId, scopeFilter, searchMatchedReports]);
  const latestScopedReport = scopedReports[0] ?? null;

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

  const matchingReports = scopedReports;

  const trackedTickers = useMemo(() => {
    const values = new Set<string>();

    for (const report of scopedReports) {
      values.add(report.ticker);
    }

    return Array.from(values).sort((left, right) => left.localeCompare(right));
  }, [scopedReports]);

  return (
    <main className="flex min-h-[100vh] flex-1 flex-col px-4 py-6 md:px-7 lg:px-9">
      <div className="workbench-content-frame space-y-6">
        <Card className="card-surface rounded-[30px]">
          <CardContent className="px-6 py-8 md:px-8">
          <div className="flex flex-col gap-6 lg:flex-row lg:items-end lg:justify-between">
            <div className="max-w-3xl">
              <p className="text-[11px] font-semibold uppercase tracking-[0.24em] text-[var(--primary)]">
                {t("sidebar.nav.analysis", "Analysis")}
              </p>
              <h1 className="workbench-page-title mt-3">
                {t("home.analysisWorkspace", "Analysis workspace")}
              </h1>
              <p className="mt-4 max-w-2xl text-sm leading-7 text-slate-600">
                {t(
                  "home.workspaceDescription",
                  "Search reports and continue existing coverage."
                )}
              </p>
            </div>

            <div className="flex flex-wrap gap-3">
              <Button type="button" disabled={newAnalysisDisabled} onClick={openAnalysisDialog}>
                {t("home.launchAnalysis", "New Analysis")}
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
              label={t("home.metric.reportLibrary", "Report Library")}
              value={`${scopedReports.length}`}
              meta={
                scopeFilter === "all"
                  ? t("home.metric.reportLibraryMeta", "Total indexed reports")
                  : t("home.metric.scopedReportLibraryMeta", "Reports in current scope")
              }
            />
            <MetricCard
              label={t("home.recentTickers", "Tracked Tickers")}
              value={`${trackedTickers.length}`}
              meta={t("home.metric.trackedTickersMeta", "Coverage names in the library")}
            />
            <MetricCard
              label={t("home.metric.activeResearch", "Active Research")}
              value={`${activeTasks.length}`}
              meta={t("home.metric.activeResearchMeta", "In-flight analysis jobs")}
            />
          </div>

          <div className="mt-8 rounded-[28px] border border-[var(--border)] bg-white/88 p-4 md:p-5">
            <label
              htmlFor="home-report-search"
              className="text-xs font-semibold uppercase tracking-[0.22em] text-slate-500"
            >
              {t("home.searchLabel", "Search reports")}
            </label>
            <Input
              id="home-report-search"
              type="search"
              value={searchQuery}
              onChange={(event) => setSearchQuery(event.target.value)}
              placeholder={t("home.searchPlaceholderShort", "Ticker or report id")}
              className="mt-3 border-[var(--border-strong)] bg-[var(--surface-strong)] text-slate-900"
            />
            <p className="mt-2 text-sm text-slate-500">
              {t(
                "home.searchDeepLinkHint",
                "Results update in place and keep the query in the URL for deep-linking."
              )}
            </p>
          </div>
          </CardContent>
        </Card>

        <section className="grid gap-6 xl:grid-cols-[minmax(0,1.1fr)_minmax(0,0.9fr)]">
          <section className="viewer-frame px-6 py-6 md:px-8">
            <div className="flex items-center justify-between gap-4">
              <div>
                <p className="text-[11px] font-semibold uppercase tracking-[0.2em] text-slate-500">
                  {deferredSearchQuery
                    ? t("home.matchingReports", "Matching Reports")
                    : t("home.recentReports", "Recent Reports")}
                </p>
                <h2 className="workbench-section-title mt-2 text-2xl">
                  {deferredSearchQuery
                    ? t("home.matchingReportCount", ({ count }) => `${count} matching reports`, {
                        count: matchingReports.length,
                      })
                    : t("home.jumpBack", "Jump back into coverage")}
                </h2>
              </div>
              {deferredSearchQuery ? (
                <Link
                  href={buildHomeHref("")}
                  className="text-xs font-semibold uppercase tracking-[0.16em] text-[var(--primary)]"
                >
                  {t("common.clear", "Clear search")}
                </Link>
              ) : null}
            </div>

            <div
              className="mt-5 flex flex-wrap gap-2"
              role="group"
              aria-label={t("home.scope.label", "Report scope")}
            >
              {REPORT_SCOPE_FILTERS.map((scope) => (
                <Button
                  key={scope}
                  type="button"
                  variant={scopeFilter === scope ? "default" : "secondary"}
                  size="sm"
                  onClick={() => setScopeFilter(scope)}
                  className={scopeFilter === scope ? "shadow-none" : "text-slate-700"}
                >
                  {t(REPORT_SCOPE_LABEL_KEYS[scope], scope)}
                  <span className="ml-2 rounded-full bg-white/55 px-2 py-0.5 text-[10px]">
                    {reportScopeCounts[scope]}
                  </span>
                </Button>
              ))}
            </div>

            {reportsError ? (
              <div className="mt-5 rounded-[24px] border border-[rgba(163,53,53,0.2)] bg-[rgba(163,53,53,0.08)] px-4 py-4 text-sm text-[var(--danger)]">
                {reportsError}
              </div>
            ) : loadingReports ? (
              <div className="mt-5 rounded-[24px] border border-dashed border-[var(--border)] bg-[var(--surface-strong)] px-5 py-8 text-sm text-slate-500">
                {t("home.loadingReportIndex", "Loading report index...")}
              </div>
            ) : matchingReports.length === 0 ? (
              <div className="mt-5 rounded-[24px] border border-dashed border-[var(--border)] bg-[var(--surface-strong)] px-5 py-8 text-sm text-slate-500">
                {t("home.noReportMatches", "No reports match this search yet.")}
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
                      <div className="flex flex-wrap items-center gap-2">
                        <p className="text-lg font-semibold text-slate-900">{report.ticker}</p>
                        <Badge
                          variant={report.visibility === "workspace" ? "success" : "secondary"}
                          className="px-2 py-1 text-[10px]"
                        >
                          {report.visibility === "workspace"
                            ? t("home.visibility.workspace", "Workspace")
                            : t("home.visibility.private", "Private")}
                        </Badge>
                      </div>
                      <p className="mt-1 truncate font-mono text-[11px] text-slate-500">
                        {report.id}
                      </p>
                    </div>
                    <span className="text-xs font-semibold uppercase tracking-[0.16em] text-[var(--primary)]">
                      {t("common.open", "Open")}
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
                    {t("home.recentTickers", "Tracked Tickers")}
                  </p>
                  <h2 className="workbench-section-title mt-2 text-2xl">
                    {t("home.coverageMap", "Coverage map")}
                  </h2>
                </div>
                <Badge variant="secondary" className="text-slate-500">
                  {trackedTickers.length}
                </Badge>
              </div>

              <div className="mt-4 flex flex-wrap gap-2">
                {trackedTickers.length === 0 ? (
                  <Badge variant="secondary" className="px-3 py-2 normal-case tracking-normal text-slate-500">
                    {t("home.waitingForReports", "Waiting for reports")}
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
                {t("home.coverageSnapshot", "Coverage Snapshot")}
              </p>
              <div className="mt-4 rounded-[24px] border border-[var(--border)] bg-white/88 px-4 py-4">
                <p className="text-sm font-semibold text-slate-900">
                  {deferredSearchQuery
                    ? t("home.snapshotSearchFocus", "Search is focused on one slice of the library.")
                    : t("home.snapshotHomeBase", "Use the analysis rail as the reports home base.")}
                </p>
                <p className="mt-3 text-sm leading-6 text-slate-600">
                  {deferredSearchQuery
                    ? t(
                        "home.snapshotSearchBody",
                        ({ reports: reportCount, tickers }) =>
                          `The current query is filtering against ${reportCount} indexed reports across ${tickers} tickers.`,
                        { reports: scopedReports.length, tickers: trackedTickers.length }
                      )
                    : t(
                        "home.snapshotLibraryBody",
                        ({ reports: reportCount, tickers }) =>
                          `The library currently tracks ${reportCount} reports across ${tickers} tickers, with new research work routed through the unified sidebar action.`,
                        { reports: scopedReports.length, tickers: trackedTickers.length }
                      )}
                </p>
                {latestScopedReport ? (
                  <div className="mt-4">
                    <Badge variant="secondary">
                      {t(
                        "home.latestIndexedReport",
                        ({ ticker }) => `Latest indexed report · ${ticker}`,
                        { ticker: latestScopedReport.ticker }
                      )}
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
