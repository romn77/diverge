"use client";

import { memo, startTransition, useCallback, useEffect, useMemo, useRef, useState } from "react";
import { ChevronDown, ChevronUp, LockKeyhole, UsersRound } from "lucide-react";
import { usePreferences } from "@/components/PreferencesProvider";
import { useWorkbench } from "@/components/WorkbenchProvider";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { Tabs, TabsList, TabsTrigger } from "@/components/ui/tabs";
import {
  getContent,
  getStructure,
  updateReportVisibility,
  type Report,
  type ReportStructure,
  type ReportVisibility,
} from "@/lib/api";
import type {
  DecisionCard as DecisionCardModel,
  DecisionDelta,
} from "@/lib/decisionCard";
import { fetchDecisionCard, fetchDecisionDelta } from "@/lib/fetchDecisionCard";
import { DecisionCard as DecisionCardView } from "./DecisionCard";
import { DecisionCardSkeleton } from "./DecisionCardSkeleton";
import { MarkdownContent } from "./MarkdownContent";
import { TickerPricePanel } from "./TickerPricePanel";

interface ReportViewerProps {
  reportId: string;
  reportMeta?: Report | null;
  onOpenSidebar?: () => void;
  sidebarOpen?: boolean;
}

const SUMMARY_TAB_KEY = "summary";

const CATEGORY_MAP: Record<string, { dir: string; label: string }> = {
  analysts: { dir: "1_analysts", label: "Analysts" },
  research: { dir: "2_research", label: "Research" },
  trading: { dir: "3_trading", label: "Trading" },
  risk: { dir: "4_risk", label: "Risk" },
  portfolio: { dir: "5_portfolio", label: "Portfolio" },
};

const FILE_LABELS: Record<string, string> = {
  market: "Market Analyst",
  sentiment: "Social Analyst",
  news: "News Analyst",
  fundamentals: "Fundamentals Analyst",
  bull: "Bull Researcher",
  bear: "Bear Researcher",
  manager: "Research Manager",
  trader: "Trader",
  aggressive: "Aggressive",
  conservative: "Conservative",
  neutral: "Neutral",
  decision: "Portfolio Decision",
};

const HIGHLIGHTS_BLOCK_RE = /```json-highlights[ \t]*\r?\n([\s\S]*?)\r?\n?```/m;

function formatDecisionCardJson(
  card: DecisionCardModel,
  delta: DecisionDelta | null
): string {
  return JSON.stringify(delta ? { decision_card: card, decision_delta: delta } : card, null, 2);
}

function localizeFileLabel(
  file: string,
  t: ReturnType<typeof usePreferences>["t"]
): string {
  return t(`report.file.${file}`, FILE_LABELS[file] || file);
}

function escapeRegExp(value: string): string {
  return value.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
}

function extractSection(markdown: string, heading: string): string | null {
  const pattern = new RegExp(
    `## ${escapeRegExp(heading)}\\s*\\n([\\s\\S]*?)(?=\\n## |\\n\`\`\`json-highlights|$)`,
    "i"
  );
  const match = markdown.match(pattern);
  return match?.[1]?.trim() ?? null;
}

function extractTableMetrics(
  markdown: string,
  heading: string,
  assessment: string
): Array<{ name: string; value: string; assessment: string }> {
  const section = extractSection(markdown, heading);
  if (!section) {
    return [];
  }

  return section
    .split(/\r?\n/)
    .map((line) => line.trim())
    .filter((line) => line.startsWith("|"))
    .filter((line) => !line.includes("---"))
    .map((line) => line.split("|").map((cell) => cell.trim()).filter(Boolean))
    .filter((cells) => cells.length >= 2 && cells[0] !== "Metric" && cells[0] !== "Multiple" && cells[0] !== "Assumption")
    .map((cells) => ({
      name: cells[0] ?? "",
      value: cells[1] ?? "",
      assessment,
    }))
    .filter((metric) => metric.name && metric.value);
}

function extractDcfApplicabilityMetrics(
  markdown: string
): Array<{ name: string; value: string; assessment: string }> {
  const section = extractSection(markdown, "DCF Applicability");
  if (!section) {
    return [];
  }

  const lines = section
    .split(/\r?\n/)
    .map((line) => line.trim())
    .filter(Boolean);

  const metrics: Array<{ name: string; value: string; assessment: string }> = [];

  for (const line of lines) {
    if (line.startsWith("Status:")) {
      metrics.push({
        name: "DCF Applicability",
        value: line.replace(/^Status:\s*/, "").trim(),
        assessment: "Valuation applicability state",
      });
    }
    if (line.startsWith("Reason:")) {
      metrics.push({
        name: "DCF Applicability Reason",
        value: line.replace(/^Reason:\s*/, "").trim(),
        assessment: "Applicability rationale",
      });
    }
  }

  return metrics;
}

function extractDcfScenarioMetrics(
  markdown: string
): Array<{ name: string; value: string; assessment: string }> {
  const section = extractSection(markdown, "DCF Scenario Summary");
  if (!section) {
    return [];
  }

  return section
    .split(/\r?\n/)
    .map((line) => line.trim())
    .filter((line) => line.startsWith("|"))
    .filter((line) => !line.includes("---"))
    .map((line) => line.split("|").map((cell) => cell.trim()).filter(Boolean))
    .filter((cells) => cells.length >= 5 && cells[0] !== "Case")
    .map((cells) => ({
      name: cells[0] ?? "",
      value: cells[4] ?? "",
      assessment: `Scenario DCF using growth ${cells[1] ?? "N/A"}, WACC ${cells[2] ?? "N/A"}, terminal growth ${cells[3] ?? "N/A"}`,
    }))
    .filter((metric) => metric.name && metric.value);
}

function injectValuationMetricsIntoHighlights(markdown: string): string {
  const match = markdown.match(HIGHLIGHTS_BLOCK_RE);
  if (!match?.[1]) {
    return markdown;
  }

  try {
    const payload = JSON.parse(match[1]) as {
      category?: string;
      metrics?: Array<{ name: string; value: string; assessment: string }>;
    };
    if (payload.category !== "fundamentals") {
      return markdown;
    }

    const valuationMetrics = [
      ...extractDcfApplicabilityMetrics(markdown),
      ...extractDcfScenarioMetrics(markdown),
      ...extractTableMetrics(markdown, "DCF Summary", "Intrinsic value output"),
      ...extractTableMetrics(markdown, "Multiples Summary", "Relative valuation output"),
      ...extractTableMetrics(markdown, "Valuation Assumptions", "DCF input assumption"),
    ];
    if (valuationMetrics.length === 0) {
      return markdown;
    }

    const existingMetrics = Array.isArray(payload.metrics) ? payload.metrics : [];
    const mergedMetrics = [...existingMetrics];

    for (const metric of valuationMetrics) {
      if (!mergedMetrics.some((existing) => existing.name === metric.name)) {
        mergedMetrics.push(metric);
      }
    }

    const nextBlock = `\`\`\`json-highlights\n${JSON.stringify(
      { ...payload, metrics: mergedMetrics },
      null,
      2
    )}\n\`\`\``;

    return markdown.replace(HIGHLIGHTS_BLOCK_RE, nextBlock);
  } catch {
    return markdown;
  }
}

function decorateReportContent(markdown: string): string {
  return injectValuationMetricsIntoHighlights(markdown);
}

function resolveReportContentPath(
  tabKey: string,
  selectedFile: string | null
): string | null {
  if (tabKey === SUMMARY_TAB_KEY) {
    return null;
  }

  if (tabKey === "complete") {
    return "complete_report.md";
  }

  const categoryInfo = CATEGORY_MAP[tabKey];
  if (!categoryInfo || !selectedFile) {
    return null;
  }

  return `${categoryInfo.dir}/${selectedFile}.md`;
}

function formatGeneratedLabel(
  reportMeta: Report | null | undefined,
  locale: string,
  fallback: string
): string {
  if (reportMeta?.date && reportMeta.time) {
    const parsed = new Date(`${reportMeta.date}T${reportMeta.time}`);
    if (!Number.isNaN(parsed.getTime())) {
      return new Intl.DateTimeFormat(locale, {
        year: "numeric",
        month: "short",
        day: "numeric",
        hour: "2-digit",
        minute: "2-digit",
      }).format(parsed);
    }

    return `${reportMeta.date} ${reportMeta.time}`;
  }

  if (reportMeta?.date) {
    const parsed = new Date(`${reportMeta.date}T00:00:00`);
    if (!Number.isNaN(parsed.getTime())) {
      return new Intl.DateTimeFormat(locale, {
        year: "numeric",
        month: "short",
        day: "numeric",
      }).format(parsed);
    }

    return reportMeta.date;
  }

  return fallback;
}

export function ReportViewer({
  reportId,
  reportMeta = null,
  onOpenSidebar,
  sidebarOpen = false,
}: ReportViewerProps) {
  const { locale, t } = usePreferences();
  const { authState, refreshReports } = useWorkbench();
  const [structure, setStructure] = useState<ReportStructure | null>(null);
  const [selectedTab, setSelectedTab] = useState(SUMMARY_TAB_KEY);
  const [selectedFile, setSelectedFile] = useState<string | null>(null);
  const [content, setContent] = useState("");
  const [decisionCard, setDecisionCard] = useState<DecisionCardModel | null>(null);
  const [decisionDelta, setDecisionDelta] = useState<DecisionDelta | null>(null);
  const [isDecisionCardLoading, setIsDecisionCardLoading] = useState(false);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [isOverviewCollapsed, setIsOverviewCollapsed] = useState(false);
  const [isUpdatingVisibility, setIsUpdatingVisibility] = useState(false);
  const requestIdRef = useRef(0);
  const contentCacheRef = useRef(new Map<string, string>());
  const decisionCardPath = useMemo(
    () =>
      structure?.artifacts.find(
        (artifact) => artifact.type.toLowerCase() === "decision_card"
      )?.path ?? null,
    [structure]
  );
  const decisionDeltaPath = useMemo(
    () =>
      structure?.artifacts.find(
        (artifact) => artifact.type.toLowerCase() === "decision_delta"
      )?.path ?? null,
    [structure]
  );

  useEffect(() => {
    let isActive = true;

    const loadStructure = async () => {
      requestIdRef.current += 1;

      try {
        setIsLoading(true);
        setError(null);

        const data = await getStructure(reportId);
        if (!isActive) {
          return;
        }

        setStructure(data);
        setSelectedTab(SUMMARY_TAB_KEY);
        setSelectedFile(null);
        setContent("");
        contentCacheRef.current.clear();
        setIsOverviewCollapsed(false);
      } catch (err) {
        if (!isActive) {
          return;
        }

        setError(
          err instanceof Error
            ? err.message
            : t("report.error.loadReport", "Failed to load report")
        );
        setStructure(null);
      } finally {
        if (isActive) {
          setIsLoading(false);
        }
      }
    };

    loadStructure();

    return () => {
      isActive = false;
    };
  }, [reportId, t]);

  useEffect(() => {
    let isActive = true;

    if (!decisionCardPath) {
      setDecisionCard(null);
      setDecisionDelta(null);
      setIsDecisionCardLoading(false);
      return () => {
        isActive = false;
      };
    }

    const loadDecisionCard = async () => {
      try {
        setIsDecisionCardLoading(true);
        const card = await fetchDecisionCard(reportId, decisionCardPath);
        if (isActive) {
          setDecisionCard(card);
        }
      } catch {
        if (isActive) {
          setDecisionCard(null);
        }
      } finally {
        if (isActive) {
          setIsDecisionCardLoading(false);
        }
      }
    };

    loadDecisionCard();

    return () => {
      isActive = false;
    };
  }, [decisionCardPath, reportId]);

  useEffect(() => {
    let isActive = true;

    if (!decisionDeltaPath) {
      setDecisionDelta(null);
      return () => {
        isActive = false;
      };
    }

    const loadDecisionDelta = async () => {
      try {
        const delta = await fetchDecisionDelta(reportId, decisionDeltaPath);
        if (isActive) {
          setDecisionDelta(delta);
        }
      } catch {
        if (isActive) {
          setDecisionDelta(null);
        }
      }
    };

    loadDecisionDelta();

    return () => {
      isActive = false;
    };
  }, [decisionDeltaPath, reportId]);

  useEffect(() => {
    const loadContent = async () => {
      if (!structure) {
        return;
      }

      if (selectedTab === SUMMARY_TAB_KEY) {
        requestIdRef.current += 1;
        setContent("");
        setError(null);
        setIsLoading(false);
        return;
      }

      const path = resolveReportContentPath(selectedTab, selectedFile);
      if (!path) {
        return;
      }

      const cachedContent = contentCacheRef.current.get(path);
      if (cachedContent !== undefined) {
        requestIdRef.current += 1;
        setError(null);
        setIsLoading(false);
        startTransition(() => {
          setContent(cachedContent);
        });
        return;
      }

      const thisRequest = ++requestIdRef.current;

      try {
        setIsLoading(true);
        setError(null);

        const data = await getContent(reportId, path);
        if (thisRequest !== requestIdRef.current) {
          return;
        }

        const decoratedContent = decorateReportContent(data);
        contentCacheRef.current.set(path, decoratedContent);
        startTransition(() => {
          setContent(decoratedContent);
        });
      } catch (err) {
        if (thisRequest !== requestIdRef.current) {
          return;
        }

        setError(
          err instanceof Error
            ? err.message
            : t("report.error.loadContent", "Failed to load content")
        );
      } finally {
        if (thisRequest === requestIdRef.current) {
          setIsLoading(false);
        }
      }
    };

    loadContent();
  }, [reportId, selectedFile, selectedTab, structure, t]);

  const availableCategories = useMemo(
    () =>
      structure
        ? Object.entries(CATEGORY_MAP).filter(
            ([key]) => structure.categories[key] && structure.categories[key].length > 0
          )
        : [],
    [structure]
  );

  const categoryFiles = useMemo(
    () =>
      selectedTab !== SUMMARY_TAB_KEY && selectedTab !== "complete" && structure
        ? structure.categories[selectedTab] || []
        : [],
    [selectedTab, structure]
  );
  const availableTrackCount = availableCategories.length;
  const sourceFileCount = useMemo(
    () =>
      structure
        ? Object.values(structure.categories).reduce((total, files) => total + files.length, 0)
        : 0,
    [structure]
  );

  const selectedCategoryMeta = selectedTab !== "complete" ? CATEGORY_MAP[selectedTab] : null;
  const selectedCategoryLabel =
    selectedTab === SUMMARY_TAB_KEY
      ? t("report.summary", "Summary")
      : selectedCategoryMeta
        ? t(`report.category.${selectedTab}`, selectedCategoryMeta.label)
        : null;
  const selectedFileLabel = selectedFile ? localizeFileLabel(selectedFile, t) : null;
  const generatedLabel = formatGeneratedLabel(
    reportMeta,
    locale,
    t("report.generatedUnavailable", "Generated time unavailable")
  );
  const overviewToggleLabel = isOverviewCollapsed
    ? t("report.expandOverview", "Expand overview")
    : t("report.collapseOverview", "Collapse overview");
  const collapsedOverviewSummary = [
    generatedLabel,
    selectedFileLabel ??
      selectedCategoryLabel ??
      t("report.completeReport", "Complete Report"),
  ].join(" / ");
  const summaryArtifact = useMemo(
    () =>
      structure?.artifacts.find(
        (artifact) => artifact.type.toLowerCase() === "summary"
      ) ?? null,
    [structure]
  );
  const summaryText = summaryArtifact?.summary?.trim() ?? "";
  const currentUserId = authState?.user?.id ?? null;
  const canUpdateVisibility =
    structure &&
    authState?.enabled &&
    authState.authenticated &&
    authState.user &&
    structure.visibility &&
    (authState.user.role === "admin" || structure.owner_user_id === currentUserId);
  const currentVisibility = structure?.visibility ?? "private";
  const isWorkspaceVisible = currentVisibility === "workspace";
  const visibilityLabel = t(
    isWorkspaceVisible ? "home.visibility.workspace" : "home.visibility.private",
    isWorkspaceVisible ? "Workspace" : "Private"
  );
  const nextVisibility = (
    isWorkspaceVisible ? "private" : "workspace"
  ) satisfies ReportVisibility;

  const handleVisibilityChange = async (visibility: ReportVisibility) => {
    if (!structure || visibility === structure.visibility) {
      return;
    }
    setIsUpdatingVisibility(true);
    try {
      const updated = await updateReportVisibility(reportId, visibility);
      setStructure((current) =>
        current
          ? {
              ...current,
              visibility: updated.visibility,
              visibility_updated_at: updated.visibility_updated_at,
              visibility_updated_by_user_id: updated.visibility_updated_by_user_id,
              visibility_admin_override: updated.visibility_admin_override,
            }
          : current
      );
      await refreshReports();
    } finally {
      setIsUpdatingVisibility(false);
    }
  };

  const handleTabChange = useCallback(
    (tabKey: string) => {
      setSelectedTab(tabKey);

      if (tabKey === SUMMARY_TAB_KEY) {
        setSelectedFile(null);
        return;
      }

      if (tabKey !== "complete" && structure) {
        const files = structure.categories[tabKey] || [];
        setSelectedFile(files[0] ?? null);
        return;
      }

      setSelectedFile(null);
    },
    [structure]
  );

  if (!structure) {
    return (
      <main className="analysis-density-page workbench-page-shell flex min-h-dvh flex-1 flex-col">
        <div className="workbench-content-frame">
          {isLoading ? (
            <div
              className="viewer-frame w-full space-y-4 p-6 md:p-8"
              role="status"
              aria-busy="true"
              aria-live="polite"
            >
              <span className="sr-only">
                {t("report.loadingReport", "Loading report...")}
              </span>
              <Skeleton className="h-7 w-2/3 rounded-[16px]" />
              <Skeleton className="h-4 w-1/3 rounded-[12px]" />
              <div className="grid gap-3 md:grid-cols-3">
                <Skeleton className="h-20 rounded-[20px]" />
                <Skeleton className="h-20 rounded-[20px]" />
                <Skeleton className="h-20 rounded-[20px]" />
              </div>
              <Skeleton className="h-40 w-full rounded-[24px]" />
              <Skeleton className="h-40 w-full rounded-[24px]" />
            </div>
          ) : (
            <div className="viewer-frame flex w-full items-center justify-center p-8 text-sm text-slate-600">
              {error
                ? `${t("report.errorPrefix", "Error")}: ${error}`
                : t("report.noReportData", "No report data")}
            </div>
          )}
        </div>
      </main>
    );
  }

  return (
    <main className="analysis-density-page workbench-page-shell flex min-h-dvh min-w-0 flex-1 flex-col overflow-x-hidden">
      <div className="workbench-content-frame">
        <section
          id="report-content-panel"
          className="viewer-frame min-w-0 w-full"
          aria-live="polite"
        >
        <div className="min-w-0 max-w-full">
          <div className="min-w-0 max-w-full px-4 pt-6 md:px-8 md:pt-8">
            <div className="min-w-0 w-full max-w-full">
              <section className="report-panel rounded-[30px] border px-4 py-4 md:px-6">
                <div className="flex flex-wrap items-center justify-between gap-3">
                  <div className="min-w-0">
                    <p className="viewer-meta-label">
                      {t("report.overviewPanel", "Report overview")}
                    </p>
                    {isOverviewCollapsed && (
                      <p className="mt-2 truncate text-sm text-slate-600 md:text-base">
                        <span className="font-heading font-semibold text-slate-900">
                          {structure.ticker}
                        </span>
                        <span className="mx-2 text-[var(--border-strong)]">/</span>
                        {collapsedOverviewSummary}
                      </p>
                    )}
                  </div>
                  <Button
                    type="button"
                    variant="secondary"
                    size="icon"
                    onClick={() => setIsOverviewCollapsed((current) => !current)}
                    aria-expanded={!isOverviewCollapsed}
                    aria-controls="report-overview-panel"
                    aria-label={overviewToggleLabel}
                    title={overviewToggleLabel}
                    className="size-10 rounded-full"
                  >
                    {isOverviewCollapsed ? (
                      <ChevronDown className="size-4" aria-hidden />
                    ) : (
                      <ChevronUp className="size-4" aria-hidden />
                    )}
                  </Button>
                </div>
                {!isOverviewCollapsed && (
                <div
                  id="report-overview-panel"
                  className="mt-4 grid gap-6 xl:grid-cols-[minmax(0,3fr)_minmax(0,7fr)] xl:items-start"
                >
                  <div className="min-w-0 space-y-5">
                    <header>
                      <div className="space-y-5">
                        <div className="flex min-w-0 items-start gap-4">
                          {onOpenSidebar && (
                            <Button
                              type="button"
                              onClick={onOpenSidebar}
                              aria-controls="report-navigation"
                              aria-expanded={sidebarOpen}
                              aria-haspopup="dialog"
                              variant="secondary"
                              size="icon"
                              className="min-h-11 min-w-11 rounded-full text-slate-500 md:hidden"
                              aria-label={t(
                                "report.openNavigation",
                                "Open report navigation"
                              )}
                            >
                              <svg viewBox="0 0 24 24" className="size-4" fill="none" aria-hidden>
                                <path
                                  d="M4 7h16M4 12h16M4 17h16"
                                  stroke="currentColor"
                                  strokeWidth="1.8"
                                  strokeLinecap="round"
                                />
                              </svg>
                            </Button>
                          )}

                          <div className="min-w-0">
                            <h2 className="mt-2 font-heading truncate text-[2.1rem] font-bold tracking-tight text-slate-900 md:text-[2.7rem]">
                              {structure.ticker}
                            </h2>
                            <div className="mt-2 flex flex-wrap items-center gap-x-3 gap-y-1 text-sm text-slate-500 md:text-base">
                              <span>{generatedLabel}</span>
                              <span className="hidden text-[var(--border-strong)] sm:inline">
                                /
                              </span>
                              <span className="font-mono text-[12px] text-slate-500">
                                {reportId}
                              </span>
                            </div>
                            <div className="mt-4 flex flex-wrap items-center gap-x-6 gap-y-2 text-sm text-[var(--muted)]">
                              <span className="inline-flex items-center gap-2">
                                <span
                                  className="size-2 rounded-full bg-[var(--primary)]"
                                  aria-hidden
                                />
                                {selectedFileLabel ??
                                  (selectedTab === SUMMARY_TAB_KEY
                                    ? t("report.summary", "Summary")
                                    : selectedCategoryMeta
                                      ? t(
                                          "report.categoryView",
                                          ({ label }) => `${label} view`,
                                          {
                                            label:
                                              selectedCategoryLabel ??
                                              selectedCategoryMeta.label,
                                          }
                                        )
                                      : t("report.completeReport", "Complete Report"))}
                              </span>
                              {selectedTab !== SUMMARY_TAB_KEY &&
                                selectedTab !== "complete" &&
                                categoryFiles.length > 0 && (
                                  <span>
                                    {t(
                                      "report.fileCount",
                                      ({ count }) => `${count} files in this track`,
                                      { count: categoryFiles.length }
                                    )}
                                  </span>
                                )}
                              {structure.visibility ? (
                                <span className="inline-flex items-center gap-2">
                                  {t(
                                    structure.visibility === "workspace"
                                      ? "home.visibility.workspace"
                                      : "home.visibility.private",
                                    structure.visibility === "workspace"
                                      ? "Workspace"
                                      : "Private"
                                  )}
                                  {structure.visibility_admin_override
                                    ? ` · ${t(
                                        "home.visibility.adminOverride",
                                        "Admin adjusted"
                                      )}`
                                    : ""}
                                </span>
                              ) : null}
                            </div>
                            {canUpdateVisibility ? (
                              <div className="mt-4">
                                <button
                                  type="button"
                                  role="switch"
                                  aria-checked={isWorkspaceVisible}
                                  aria-label={t(
                                    "home.visibility.change",
                                    "Change report visibility"
                                  )}
                                  disabled={isUpdatingVisibility}
                                  onClick={() => void handleVisibilityChange(nextVisibility)}
                                  className="report-visibility-switch"
                                  data-state={isWorkspaceVisible ? "workspace" : "private"}
                                >
                                  <span className="report-visibility-track" aria-hidden>
                                    <span className="report-visibility-thumb">
                                      {isWorkspaceVisible ? (
                                        <UsersRound className="size-3.5" />
                                      ) : (
                                        <LockKeyhole className="size-3.5" />
                                      )}
                                    </span>
                                  </span>
                                  <span className="report-visibility-copy">
                                    <span className="report-visibility-value">
                                      {visibilityLabel}
                                    </span>
                                  </span>
                                </button>
                              </div>
                            ) : null}
                          </div>
                        </div>

                        <div className="grid gap-3">
                          <SummaryMetric
                            label={t("report.readingOverview", "Reading Overview")}
                            value={
                              selectedCategoryLabel ??
                              t("report.completeReport", "Complete Report")
                            }
                          />
                          <SummaryMetric
                            label={t("report.availableTracks", "Available tracks")}
                            value={String(availableTrackCount)}
                          />
                          <SummaryMetric
                            label={t("report.sourceFiles", "Source files")}
                            value={String(sourceFileCount)}
                          />
                        </div>
                      </div>
                    </header>
                  </div>

                  <ReportOverviewCompanion
                    ticker={structure.ticker}
                    asOfDate={reportMeta?.date ?? null}
                    t={t}
                  />
                </div>
                )}
              </section>
            </div>
          </div>

          <div className="sticky top-0 z-[var(--z-overlay)] min-w-0 max-w-full bg-transparent">
            <div className="report-tab-rail border-b border-[var(--border)] px-4 py-3 md:px-8 md:py-4">
              <div className="min-w-0 w-full max-w-full">
                <Tabs value={selectedTab} onValueChange={handleTabChange}>
                  <TabsList className="scrollbar-none flex min-w-0 w-full max-w-full justify-start gap-2 overflow-x-auto rounded-none border-0 bg-transparent p-0 shadow-none">
                    <TabsTrigger value={SUMMARY_TAB_KEY}>
                      {t("report.summary", "Summary")}
                    </TabsTrigger>
                    <TabsTrigger value="complete">
                      {t("report.completeReport", "Complete Report")}
                    </TabsTrigger>
                    {availableCategories.map(([key, meta]) => (
                      <TabsTrigger key={key} value={key}>
                        {t(`report.category.${key}`, meta.label)}
                      </TabsTrigger>
                    ))}
                  </TabsList>
                </Tabs>
              </div>
            </div>

            {selectedTab !== SUMMARY_TAB_KEY &&
              selectedTab !== "complete" &&
              categoryFiles.length > 0 && (
              <div className="report-subtab-rail border-b border-[var(--border)] px-4 py-3 md:px-8">
                <div className="min-w-0 w-full max-w-full">
                  <div className="scrollbar-none flex min-w-0 max-w-full overflow-x-auto gap-2 rounded-[20px] border border-[var(--border)] bg-white/42 p-2">
                    {categoryFiles.map((file) => (
                      <Button
                        key={file}
                        onClick={() => {
                          setSelectedFile(file);
                        }}
                        variant={selectedFile === file ? "default" : "secondary"}
                        size="sm"
                        className="whitespace-nowrap"
                        aria-controls="report-content-panel"
                      >
                        {localizeFileLabel(file, t)}
                      </Button>
                    ))}
                  </div>
                </div>
              </div>
            )}
          </div>

          <div className="min-w-0 max-w-full px-4 pb-6 pt-6 md:px-8 md:pb-8 md:pt-8">
            <div className="report-reading-frame min-w-0 w-full max-w-full">
              {selectedTab !== "complete" && selectedCategoryMeta && (
                <div className="mb-8 flex w-full flex-col gap-3 border-b border-[var(--border)] pb-5 md:flex-row md:items-end md:justify-between">
                  <div className="space-y-1">
                    <p className="viewer-meta-label">
                      {t("report.currentFile", "Current file")}
                    </p>
                    <h3 className="font-heading text-2xl font-semibold tracking-tight text-[var(--text)] md:text-3xl">
                      {selectedFileLabel ?? selectedCategoryLabel ?? selectedCategoryMeta.label}
                    </h3>
                  </div>
                </div>
              )}

              {error ? (
                <div className="rounded-[18px] border border-rose-200 bg-rose-50 p-4 text-sm text-rose-700">
                  {error}
                </div>
              ) : selectedTab === SUMMARY_TAB_KEY ? (
                <SummaryPanel
                  summaryText={summaryText}
                  t={t}
                />
              ) : selectedTab === "complete" ? (
                <>
                  {isDecisionCardLoading && <DecisionCardSkeleton />}
                  {decisionCard && (
                    <>
                      <DecisionCardView card={decisionCard} delta={decisionDelta} />
                      <details className="decision-raw-details">
                        <summary>
                          <span>
                            {t(
                              "decisionCard.rawDetails",
                              "Structured decision data"
                            )}
                          </span>
                          <span className="decision-raw-meta">
                            {t(
                              "decisionCard.rawDetailsHint",
                              "JSON for audit"
                            )}
                          </span>
                        </summary>
                        <pre>
                          <code>{formatDecisionCardJson(decisionCard, decisionDelta)}</code>
                        </pre>
                      </details>
                    </>
                  )}
                  <MarkdownContent
                    content={content}
                    isLoading={isLoading}
                    highlightMode={
                      decisionCard || isDecisionCardLoading ? "off" : "single"
                    }
                  />
                </>
              ) : categoryFiles.length === 0 ? (
                <div className="py-8 text-center text-sm text-slate-500">
                  {t("report.noCategoryData", "No data available for this category")}
                </div>
              ) : (
                <MarkdownContent
                  content={content}
                  isLoading={isLoading}
                  highlightMode="single"
                />
              )}
            </div>
          </div>
        </div>
        </section>
      </div>
    </main>
  );
}

const ReportOverviewCompanion = memo(function ReportOverviewCompanion({
  asOfDate,
  ticker,
  t,
}: {
  asOfDate: string | null;
  ticker: string;
  t: ReturnType<typeof usePreferences>["t"];
}) {
  return (
    <div className="report-overview-companion min-w-0">
      <TickerPricePanel
        symbol={ticker}
        asOfDate={asOfDate}
        title={t("report.priceTrend", "Price Trend")}
        embedded
      />
    </div>
  );
});

function SummaryMetric({
  label,
  value,
}: {
  label: string;
  value: string;
}) {
  return (
    <Card className="border-b-0 bg-white/80 shadow-none">
      <CardContent className="py-3">
      <p className="text-[10px] font-semibold uppercase tracking-[0.22em] text-slate-500">
        {label}
      </p>
      <p className="mt-2 text-lg font-semibold text-slate-900">{value}</p>
      </CardContent>
    </Card>
  );
}

function SummaryPanel({
  summaryText,
  t,
}: {
  summaryText: string;
  t: ReturnType<typeof usePreferences>["t"];
}) {
  return (
    <div className="space-y-6">
      <Card className="report-summary-card rounded-[28px] border">
        <CardContent className="px-5 py-5 md:px-6">
        <p className="viewer-meta-label">{t("report.summary", "Summary")}</p>
        {summaryText ? (
          <p className="mt-4 text-sm leading-7 text-slate-700 md:text-[15px]">
            {summaryText}
          </p>
        ) : null}
        </CardContent>
      </Card>
    </div>
  );
}
