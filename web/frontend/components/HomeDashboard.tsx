"use client";

import Link from "next/link";
import {
  CalendarDays,
  ChevronDown,
  ChevronRight,
  MoreHorizontal,
  Search,
  Tags,
} from "lucide-react";
import { startTransition, useDeferredValue, useEffect, useMemo, useState } from "react";
import { useRouter } from "next/navigation";
import { usePreferences } from "@/components/PreferencesProvider";
import { useWorkbench } from "@/components/WorkbenchProvider";
import { MetricCard } from "@/components/workbench/MetricCard";
import { PageHeader } from "@/components/workbench/PageHeader";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { ConfirmDialog } from "@/components/ui/confirm-dialog";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuGroup,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import {
  InputGroup,
  InputGroupAddon,
  InputGroupInput,
} from "@/components/ui/input-group";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Skeleton } from "@/components/ui/skeleton";
import {
  buildHomeHref,
  buildReportHref,
} from "@/lib/workbenchRoutes";
import { deleteReport, type Report } from "@/lib/api";

interface HomeDashboardProps {
  initialSearchQuery: string;
}

type ReportScopeFilter = "all" | "mine" | "workspace";
type ReportDisplayMode = "ticker" | "calendar";
type ReportSortMode = "latest" | "ticker" | "count";
type ReportVisibilityBucket = "private" | "workspace" | "mixed";

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
const REPORT_DISPLAY_MODES: ReportDisplayMode[] = ["ticker", "calendar"];
const REPORT_DISPLAY_MODE_LABEL_KEYS: Record<ReportDisplayMode, string> = {
  ticker: "home.display.ticker",
  calendar: "home.display.calendar",
};
const REPORT_SORT_MODES: ReportSortMode[] = ["latest", "ticker", "count"];
const REPORT_SORT_LABEL_KEYS: Record<ReportSortMode, string> = {
  latest: "home.sort.latest",
  ticker: "home.sort.ticker",
  count: "home.sort.count",
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

function compareReportsByCalendar(left: Report, right: Report): number {
  const leftValue = `${left.date || ""} ${left.time || ""} ${left.id || ""}`;
  const rightValue = `${right.date || ""} ${right.time || ""} ${right.id || ""}`;
  return (
    rightValue.localeCompare(leftValue) || left.ticker.localeCompare(right.ticker)
  );
}

function compareReportsByTicker(left: Report, right: Report): number {
  return (
    left.ticker.localeCompare(right.ticker) || compareReportsByCalendar(left, right)
  );
}

function compareReportsBySort(
  left: Report,
  right: Report,
  sortMode: ReportSortMode,
  tickerReportCounts: Map<string, number>
): number {
  if (sortMode === "ticker") {
    return compareReportsByTicker(left, right);
  }

  if (sortMode === "count") {
    return (
      (tickerReportCounts.get(right.ticker) ?? 0) -
        (tickerReportCounts.get(left.ticker) ?? 0) ||
      compareReportsByCalendar(left, right)
    );
  }

  return compareReportsByCalendar(left, right);
}

function compareReportTickerGroups(
  left: ReportTickerGroup,
  right: ReportTickerGroup,
  sortMode: ReportSortMode
): number {
  if (sortMode === "ticker") {
    return left.ticker.localeCompare(right.ticker);
  }

  if (sortMode === "count") {
    return (
      right.reports.length - left.reports.length ||
      compareReportsByCalendar(left.latestReport, right.latestReport)
    );
  }

  return compareReportsByCalendar(left.latestReport, right.latestReport);
}

function getReportVisibilityBucket(report: Report): Exclude<ReportVisibilityBucket, "mixed"> {
  return report.visibility === "workspace" ? "workspace" : "private";
}

function getGroupVisibilityBucket(reports: Report[]): ReportVisibilityBucket {
  const values = new Set(reports.map(getReportVisibilityBucket));

  if (values.size > 1) {
    return "mixed";
  }

  return values.has("workspace") ? "workspace" : "private";
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

function ReportRowActions({
  href,
  menuLabel,
  openLabel,
  deleteLabel,
  canDelete,
  onDelete,
}: {
  href: string;
  menuLabel: string;
  openLabel: string;
  deleteLabel: string;
  canDelete: boolean;
  onDelete: () => void;
}) {
  return (
    <DropdownMenu>
      <DropdownMenuTrigger asChild>
        <Button
          type="button"
          variant="ghost"
          size="icon"
          className="analysis-report-row-menu"
          aria-label={menuLabel}
        >
          <MoreHorizontal aria-hidden="true" />
        </Button>
      </DropdownMenuTrigger>
      <DropdownMenuContent align="end" className="min-w-32">
        <DropdownMenuGroup>
          <DropdownMenuItem asChild>
            <Link href={href}>{openLabel}</Link>
          </DropdownMenuItem>
          {canDelete ? (
            <>
              <DropdownMenuSeparator />
              <DropdownMenuItem
                className="text-[var(--danger)] focus:text-[var(--danger)]"
                onSelect={(event) => {
                  event.preventDefault();
                  onDelete();
                }}
              >
                {deleteLabel}
              </DropdownMenuItem>
            </>
          ) : null}
        </DropdownMenuGroup>
      </DropdownMenuContent>
    </DropdownMenu>
  );
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
    refreshReports,
  } = useWorkbench();
  const [searchQuery, setSearchQuery] = useState(initialSearchQuery);
  const [scopeFilter, setScopeFilter] = useState<ReportScopeFilter>("all");
  const [reportDisplayMode, setReportDisplayMode] =
    useState<ReportDisplayMode>("ticker");
  const [reportSortMode, setReportSortMode] = useState<ReportSortMode>("latest");
  const [expandedTickerGroups, setExpandedTickerGroups] = useState<Record<string, boolean>>({});
  const [deleteTarget, setDeleteTarget] = useState<Report | null>(null);
  const [isDeletingReport, setIsDeletingReport] = useState(false);
  const [deleteError, setDeleteError] = useState<string | null>(null);
  const deferredSearchQuery = useDeferredValue(searchQuery.trim().toLowerCase());
  const currentUserId = authState?.user?.id ?? null;
  const canDeleteGeneratedReports = authState?.user?.role === "admin";

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
  const tickerReportCounts = useMemo(() => {
    const counts = new Map<string, number>();

    for (const report of matchingReports) {
      counts.set(report.ticker, (counts.get(report.ticker) ?? 0) + 1);
    }

    return counts;
  }, [matchingReports]);
  const calendarSortedReports = useMemo(
    () =>
      [...matchingReports]
        .sort((left, right) =>
          compareReportsBySort(left, right, reportSortMode, tickerReportCounts)
        )
        .slice(0, 8),
    [matchingReports, reportSortMode, tickerReportCounts]
  );
  const reportTickerGroups = useMemo(
    () =>
      groupReportsByTicker(matchingReports)
        .sort((left, right) => compareReportTickerGroups(left, right, reportSortMode))
        .slice(0, 8),
    [matchingReports, reportSortMode]
  );
  const visibilityLabels: Record<ReportVisibilityBucket, string> = {
    private: t("home.visibility.private", "Private"),
    workspace: t("home.visibility.workspace", "Workspace"),
    mixed: t("home.visibility.mixed", "Mixed"),
  };

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

  const handleConfirmDeleteReport = async () => {
    if (!deleteTarget) {
      return;
    }
    setIsDeletingReport(true);
    setDeleteError(null);
    try {
      await deleteReport(deleteTarget.id);
      setDeleteTarget(null);
      await refreshReports();
    } catch (error) {
      setDeleteError(
        error instanceof Error
          ? error.message
          : t("home.deleteReportError", "Unable to delete report")
      );
    } finally {
      setIsDeletingReport(false);
    }
  };

  return (
    <main className="analysis-density-page workbench-page-shell flex min-h-dvh flex-1 flex-col">
      <div className="workbench-content-frame space-y-5">
        <PageHeader
          eyebrow={t("sidebar.nav.analysis", "Analysis")}
          title={t("home.analysisWorkspace", "Analysis workspace")}
        >
          <div className="grid h-full items-stretch gap-3 sm:grid-cols-[minmax(0,1.4fr)_minmax(0,1fr)_minmax(0,1fr)]">
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
        </PageHeader>

        <section className="analysis-report-section viewer-frame px-6 py-6 md:px-8">
            <div>
              <h2 className="analysis-reports-title workbench-section-title text-2xl">
                {deferredSearchQuery
                  ? t("home.matchingReportCount", ({ count }) => `${count} matching reports`, {
                      count: matchingReports.length,
                    })
                  : t("home.jumpBack", "Jump back into coverage")}
              </h2>
            </div>

            <div className="analysis-report-toolbar">
              <div className="analysis-report-toolbar-search">
                <label htmlFor="home-report-search" className="sr-only">
                  {t("home.searchLabel", "Search reports")}
                </label>
                <InputGroup className="border-[var(--border-strong)]">
                  <InputGroupAddon>
                    <Search aria-hidden="true" />
                  </InputGroupAddon>
                  <InputGroupInput
                    id="home-report-search"
                    type="search"
                    value={searchQuery}
                    onChange={(event) => setSearchQuery(event.target.value)}
                    placeholder={t("home.searchPlaceholderShort", "Ticker or report id")}
                    className="font-medium"
                  />
                </InputGroup>
              </div>

              <div className="analysis-report-toolbar-controls">
                <label htmlFor="home-report-scope" className="sr-only">
                  {t("home.scope.label", "Report scope")}
                </label>
                <Select
                  value={scopeFilter}
                  onValueChange={(value) => setScopeFilter(value as ReportScopeFilter)}
                >
                  <SelectTrigger
                    id="home-report-scope"
                    className="analysis-report-toolbar-select"
                    aria-label={t("home.scope.label", "Report scope")}
                  >
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    {REPORT_SCOPE_FILTERS.map((scope) => (
                      <SelectItem key={scope} value={scope}>
                        {t(REPORT_SCOPE_LABEL_KEYS[scope], scope)} ({reportScopeCounts[scope]})
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>

                <label htmlFor="home-report-sort" className="sr-only">
                  {t("home.sort.label", "Report sort")}
                </label>
                <Select
                  value={reportSortMode}
                  onValueChange={(value) => setReportSortMode(value as ReportSortMode)}
                >
                  <SelectTrigger
                    id="home-report-sort"
                    className="analysis-report-toolbar-select analysis-report-sort-select"
                    aria-label={t("home.sort.label", "Report sort")}
                  >
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    {REPORT_SORT_MODES.map((sortMode) => (
                      <SelectItem key={sortMode} value={sortMode}>
                        {t(REPORT_SORT_LABEL_KEYS[sortMode], sortMode)}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>

                <div
                  className="analysis-report-view-toggle"
                  role="group"
                  aria-label={t("home.display.label", "Report display")}
                >
                  {REPORT_DISPLAY_MODES.map((mode) => {
                    const isSelected = reportDisplayMode === mode;
                    const Icon = mode === "ticker" ? Tags : CalendarDays;
                    return (
                      <Button
                        key={mode}
                        type="button"
                        variant="ghost"
                        size="icon"
                        data-active={isSelected}
                        aria-label={t(REPORT_DISPLAY_MODE_LABEL_KEYS[mode], mode)}
                        aria-pressed={isSelected}
                        onClick={() => setReportDisplayMode(mode)}
                        className="analysis-view-button"
                      >
                        <Icon aria-hidden="true" />
                      </Button>
                    );
                  })}
                </div>

                {deferredSearchQuery ? (
                  <Link href={buildHomeHref("")} className="analysis-report-clear-link">
                    {t("common.clear", "Clear")}
                  </Link>
                ) : null}
              </div>
            </div>

            {reportsError || deleteError ? (
              <div className="mt-5 rounded-[24px] border border-[var(--danger-border)] bg-[var(--danger-soft)] px-4 py-4 text-sm text-[var(--danger)]">
                {reportsError || deleteError}
              </div>
            ) : loadingReports ? (
              <div
                className="mt-5 space-y-3"
                role="status"
                aria-busy="true"
                aria-live="polite"
              >
                <span className="sr-only">
                  {t("home.loadingReportIndex", "Loading report index...")}
                </span>
                {Array.from({ length: 3 }).map((_, index) => (
                  <Skeleton key={index} className="h-[68px] w-full rounded-[24px]" />
                ))}
              </div>
            ) : matchingReports.length === 0 ? (
              <div className="mt-5 rounded-[24px] border border-dashed border-[var(--border)] bg-[var(--surface-strong)] px-5 py-8 text-sm text-muted-foreground">
                {t("home.noReportMatches", "No reports match this search yet.")}
              </div>
            ) : reportDisplayMode === "calendar" ? (
              <div className="analysis-report-list mt-5" data-view="calendar">
                <div className="analysis-report-list-head analysis-report-grid">
                  <span>{t("home.reportColumnReport", "Report")}</span>
                  <span>{t("home.reportColumnTicker", "Ticker")}</span>
                  <span>{t("home.reportColumnLatest", "Latest")}</span>
                  <span>{t("home.reportColumnScope", "Scope")}</span>
                  <span className="text-right">{t("home.reportColumnAction", "Action")}</span>
                </div>
                {calendarSortedReports.map((report) => {
                  const visibilityBucket = getReportVisibilityBucket(report);
                  return (
                    <div
                      key={report.id}
                      className="analysis-report-row analysis-report-grid"
                    >
                      <Link
                        href={buildReportHref(report.id)}
                        className="analysis-report-primary-cell"
                      >
                        <span className="analysis-report-id">{report.id}</span>
                        <span className="analysis-report-mobile-meta">
                          {report.ticker} · {formatReportTimestamp(report)}
                        </span>
                      </Link>
                      <span className="analysis-report-muted-cell">{report.ticker}</span>
                      <span className="analysis-report-date-cell">
                        {formatReportTimestamp(report)}
                      </span>
                      <span className="analysis-report-scope-cell">
                        <Badge
                          variant={visibilityBucket === "workspace" ? "success" : "secondary"}
                          className="analysis-report-status-badge"
                        >
                          {visibilityLabels[visibilityBucket]}
                        </Badge>
                        {report.visibility_admin_override ? (
                          <Badge variant="secondary" className="analysis-report-status-badge">
                            {t("home.visibility.adminOverride", "Admin adjusted")}
                          </Badge>
                        ) : null}
                      </span>
                      <span className="analysis-report-action-cell">
                        <ReportRowActions
                          href={buildReportHref(report.id)}
                          menuLabel={t("home.reportActions", "Report actions")}
                          openLabel={t("common.open", "Open")}
                          deleteLabel={t("home.deleteReport", "Delete report")}
                          canDelete={canDeleteGeneratedReports}
                          onDelete={() => setDeleteTarget(report)}
                        />
                      </span>
                    </div>
                  );
                })}
              </div>
            ) : (
              <div className="analysis-report-list mt-5" data-view="ticker">
                <div className="analysis-report-list-head analysis-report-grid">
                  <span>{t("home.reportColumnTicker", "Ticker")}</span>
                  <span>{t("home.reportColumnReports", "Reports")}</span>
                  <span>{t("home.reportColumnLatest", "Latest")}</span>
                  <span>{t("home.reportColumnScope", "Scope")}</span>
                  <span className="text-right">{t("home.reportColumnAction", "Action")}</span>
                </div>
                {reportTickerGroups.map((group) => {
                  const isExpanded = expandedTickerGroups[group.ticker] ?? false;
                  const panelId = buildTickerGroupPanelId(group.ticker);
                  const latestTimestamp = formatReportTimestamp(group.latestReport);
                  const groupVisibilityBucket = getGroupVisibilityBucket(group.reports);

                  return (
                    <div key={group.ticker} className="analysis-report-group">
                      <button
                        type="button"
                        className="analysis-report-group-header analysis-report-grid"
                        aria-expanded={isExpanded}
                        aria-controls={panelId}
                        onClick={() =>
                          setExpandedTickerGroups((current) => ({
                            ...current,
                            [group.ticker]: !(current[group.ticker] ?? false),
                          }))
                        }
                      >
                        <span className="analysis-report-primary-cell">
                          <span className="analysis-report-disclosure-icon" aria-hidden="true">
                            {isExpanded ? <ChevronDown size={16} /> : <ChevronRight size={16} />}
                          </span>
                          <span className="min-w-0">
                            <span className="analysis-report-ticker">{group.ticker}</span>
                            <span className="analysis-report-mobile-meta">
                              {t(
                                "home.reportGroupCount",
                                ({ count }) => `${count} reports`,
                                {
                                  count: group.reports.length,
                                }
                              )} · {latestTimestamp}
                            </span>
                          </span>
                        </span>
                        <span className="analysis-report-muted-cell">
                          {t(
                            "home.reportGroupCount",
                            ({ count }) => `${count} reports`,
                            {
                              count: group.reports.length,
                            }
                          )}
                        </span>
                        <span className="analysis-report-date-cell">{latestTimestamp}</span>
                        <span className="analysis-report-scope-cell">
                          <Badge
                            variant={
                              groupVisibilityBucket === "workspace" ? "success" : "secondary"
                            }
                            className="analysis-report-status-badge"
                          >
                            {visibilityLabels[groupVisibilityBucket]}
                          </Badge>
                        </span>
                        <span className="analysis-report-action-cell" aria-hidden="true" />
                      </button>

                      {isExpanded ? (
                        <div id={panelId} className="analysis-report-children">
                          {group.reports.map((report) => {
                            const visibilityBucket = getReportVisibilityBucket(report);
                            return (
                              <div
                                key={report.id}
                                className="analysis-report-row analysis-report-grid analysis-report-child-row"
                              >
                                <Link
                                  href={buildReportHref(report.id)}
                                  className="analysis-report-primary-cell analysis-report-child-primary"
                                >
                                  <span className="analysis-report-id">{report.id}</span>
                                  <span className="analysis-report-mobile-meta">
                                    {formatReportTimestamp(report)}
                                  </span>
                                </Link>
                                <span className="analysis-report-muted-cell">
                                  {t("home.reportRowType", "Report")}
                                </span>
                                <span className="analysis-report-date-cell">
                                  {formatReportTimestamp(report)}
                                </span>
                                <span className="analysis-report-scope-cell">
                                  <Badge
                                    variant={
                                      visibilityBucket === "workspace"
                                        ? "success"
                                        : "secondary"
                                    }
                                    className="analysis-report-status-badge"
                                  >
                                    {visibilityLabels[visibilityBucket]}
                                  </Badge>
                                  {report.visibility_admin_override ? (
                                    <Badge
                                      variant="secondary"
                                      className="analysis-report-status-badge"
                                    >
                                      {t("home.visibility.adminOverride", "Admin adjusted")}
                                    </Badge>
                                  ) : null}
                                </span>
                                <span className="analysis-report-action-cell">
                                  <ReportRowActions
                                    href={buildReportHref(report.id)}
                                    menuLabel={t("home.reportActions", "Report actions")}
                                    openLabel={t("common.open", "Open")}
                                    deleteLabel={t("home.deleteReport", "Delete report")}
                                    canDelete={canDeleteGeneratedReports}
                                    onDelete={() => setDeleteTarget(report)}
                                  />
                                </span>
                              </div>
                            );
                          })}
                        </div>
                      ) : null}
                    </div>
                  );
                })}
              </div>
            )}
        </section>
      </div>
      <ConfirmDialog
        open={deleteTarget !== null}
        title={t("home.deleteReportDialogTitle", "Delete report")}
        description={t(
          "home.deleteReportDialogDescription",
          "This removes the generated report files and report index entry. It does not delete task history, usage, trades, or user data."
        )}
        details={deleteTarget ? deleteTarget.id : null}
        confirmLabel={t("home.deleteReportConfirm", "Delete report")}
        confirmingLabel={t("home.deleteReportDeleting", "Deleting...")}
        isConfirming={isDeletingReport}
        onConfirm={() => void handleConfirmDeleteReport()}
        onOpenChange={(open) => {
          if (!open && !isDeletingReport) {
            setDeleteTarget(null);
          }
        }}
      />
    </main>
  );
}
