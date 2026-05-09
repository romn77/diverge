"use client";

import Link from "next/link";
import { ChevronDown, ChevronRight } from "lucide-react";
import { startTransition, useDeferredValue, useEffect, useMemo, useState } from "react";
import { useRouter } from "next/navigation";
import { usePreferences } from "@/components/PreferencesProvider";
import { useWorkbench } from "@/components/WorkbenchProvider";
import { MetricCard } from "@/components/workbench/MetricCard";
import { PageHeader } from "@/components/workbench/PageHeader";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import {
  buildHomeHref,
  buildReportHref,
} from "@/lib/workbenchRoutes";
import type { Report } from "@/lib/api";

interface HomeDashboardProps {
  initialSearchQuery: string;
}

type ReportScopeFilter = "all" | "mine" | "workspace";

interface ReportTickerGroup {
  ticker: string;
  reports: Report[];
  latestReport: Report;
}

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

function groupReportsByTicker(reports: Report[]): ReportTickerGroup[] {
  const grouped = reports.reduce<Map<string, Report[]>>((acc, report) => {
    const existing = acc.get(report.ticker) ?? [];
    existing.push(report);
    acc.set(report.ticker, existing);
    return acc;
  }, new Map());

  return Array.from(grouped.entries()).map(([ticker, tickerReports]) => ({
    ticker,
    reports: tickerReports,
    latestReport: tickerReports[0],
  }));
}

function formatReportTimestamp(report: Report): string {
  if (report.date && report.time) {
    return `${report.date} ${report.time}`;
  }

  return report.date || report.time || report.id;
}

function buildTickerGroupPanelId(ticker: string): string {
  return `report-ticker-group-${ticker.replace(/[^a-zA-Z0-9_-]/g, "-")}`;
}

export function HomeDashboard({ initialSearchQuery }: HomeDashboardProps) {
  const router = useRouter();
  const { t } = usePreferences();
  const {
    activeTasks,
    authState,
    loadingReports,
    reports,
    reportsError,
  } = useWorkbench();
  const [searchQuery, setSearchQuery] = useState(initialSearchQuery);
  const [scopeFilter, setScopeFilter] = useState<ReportScopeFilter>("all");
  const [expandedTickerGroups, setExpandedTickerGroups] = useState<Record<string, boolean>>({});
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
  const visibleReports = useMemo(() => matchingReports.slice(0, 8), [matchingReports]);
  const reportTickerGroups = useMemo(
    () => groupReportsByTicker(visibleReports),
    [visibleReports]
  );

  const trackedTickers = useMemo(() => {
    const values = new Set<string>();

    for (const report of scopedReports) {
      values.add(report.ticker);
    }

    return Array.from(values).sort((left, right) => left.localeCompare(right));
  }, [scopedReports]);

  useEffect(() => {
    setExpandedTickerGroups((current) => {
      const nextState: Record<string, boolean> = {};

      for (const [index, group] of reportTickerGroups.entries()) {
        nextState[group.ticker] = current[group.ticker] ?? index === 0;
      }

      return nextState;
    });
  }, [reportTickerGroups]);

  return (
    <main className="analysis-density-page workbench-page-shell flex min-h-[100vh] flex-1 flex-col">
      <div className="workbench-content-frame space-y-5">
        <PageHeader
          eyebrow={t("sidebar.nav.analysis", "Analysis")}
          title={t("home.analysisWorkspace", "Analysis workspace")}
        >
          <div className="grid gap-4 md:grid-cols-3">
            <MetricCard
              className="analysis-overview-metric"
              label={t("home.metric.reportLibrary", "Report Library")}
              value={`${scopedReports.length}`}
              trendLabel={t("home.metric.reportLibraryScope", "Scope")}
              trendValue={t(REPORT_SCOPE_LABEL_KEYS[scopeFilter], scopeFilter)}
            />
            <MetricCard
              className="analysis-overview-metric"
              label={t("home.recentTickers", "Tracked Tickers")}
              value={`${trackedTickers.length}`}
              trendLabel={t("home.metric.groupedReports", "Grouped reports")}
              trendValue={`${reportTickerGroups.length}`}
            />
            <MetricCard
              className="analysis-overview-metric"
              label={t("home.metric.activeResearch", "Active Research")}
              value={`${activeTasks.length}`}
              trendLabel={t("activity.title", "Background work")}
              trendValue={
                activeTasks.length > 0
                  ? t("home.metric.activeResearchLive", "Live")
                  : t("home.metric.activeResearchIdle", "Idle")
              }
              trendDirection={activeTasks.length > 0 ? "up" : "neutral"}
            />
          </div>

          <div className="analysis-overview-search mt-5 rounded-[28px] border border-[var(--border)] bg-white/88 p-4 md:p-5">
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
          </div>
        </PageHeader>

        <section className="analysis-report-section viewer-frame px-6 py-6 md:px-8">
            <div className="flex items-center justify-between gap-4">
              <div>
                <h2 className="analysis-reports-title workbench-section-title text-2xl">
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
              <div className="analysis-report-list mt-5">
                {reportTickerGroups.map((group) => {
                  const isExpanded = expandedTickerGroups[group.ticker] ?? false;
                  const panelId = buildTickerGroupPanelId(group.ticker);
                  const latestTimestamp = formatReportTimestamp(group.latestReport);

                  return (
                    <div key={group.ticker} className="analysis-report-group">
                      <button
                        type="button"
                        className="analysis-report-group-header"
                        aria-expanded={isExpanded}
                        aria-controls={panelId}
                        onClick={() =>
                          setExpandedTickerGroups((current) => ({
                            ...current,
                            [group.ticker]: !(current[group.ticker] ?? false),
                          }))
                        }
                      >
                        <span className="analysis-report-group-main">
                          <span className="analysis-report-disclosure-icon" aria-hidden="true">
                            {isExpanded ? <ChevronDown size={16} /> : <ChevronRight size={16} />}
                          </span>
                          <span className="min-w-0">
                            <span className="flex flex-wrap items-center gap-2">
                              <span className="analysis-report-ticker text-lg font-semibold text-slate-900">
                                {group.ticker}
                              </span>
                              <Badge variant="secondary" className="px-2 py-1 text-[10px]">
                                {t(
                                  "home.reportGroupCount",
                                  ({ count }) => `${count} reports`,
                                  {
                                    count: group.reports.length,
                                  }
                                )}
                              </Badge>
                            </span>
                            <span className="analysis-report-group-latest">
                              {t("home.reportGroupLatest", ({ value }) => `Latest ${value}`, {
                                value: latestTimestamp,
                              })}
                            </span>
                          </span>
                        </span>
                        <span className="analysis-report-group-action">
                          {isExpanded
                            ? t("home.reportGroupCollapse", "Collapse")
                            : t("home.reportGroupExpand", "Expand")}
                        </span>
                      </button>

                      {isExpanded ? (
                        <div id={panelId} className="analysis-report-children">
                          {group.reports.map((report) => (
                            <Link
                              key={report.id}
                              href={buildReportHref(report.id)}
                              className="analysis-report-row group flex items-center justify-between gap-4"
                            >
                              <div className="min-w-0">
                                <div className="flex flex-wrap items-center gap-2">
                                  <p className="font-mono text-xs font-semibold text-slate-700">
                                    {formatReportTimestamp(report)}
                                  </p>
                                  <Badge
                                    variant={
                                      report.visibility === "workspace" ? "success" : "secondary"
                                    }
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
                      ) : null}
                    </div>
                  );
                })}
              </div>
            )}
        </section>
      </div>
    </main>
  );
}
