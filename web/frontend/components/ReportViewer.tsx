"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { ChevronDown, ChevronUp } from "lucide-react";
import { usePreferences } from "@/components/PreferencesProvider";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Tabs, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { getContent, getStructure, type Report, type ReportStructure } from "@/lib/api";
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
  const [structure, setStructure] = useState<ReportStructure | null>(null);
  const [selectedTab, setSelectedTab] = useState(SUMMARY_TAB_KEY);
  const [selectedFile, setSelectedFile] = useState<string | null>(null);
  const [content, setContent] = useState("");
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [isOverviewCollapsed, setIsOverviewCollapsed] = useState(false);
  const requestIdRef = useRef(0);

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

      let path: string;

      if (selectedTab === "complete") {
        path = "complete_report.md";
      } else {
        const categoryInfo = CATEGORY_MAP[selectedTab];
        if (!categoryInfo || !selectedFile) {
          return;
        }

        path = `${categoryInfo.dir}/${selectedFile}.md`;
      }

      const thisRequest = ++requestIdRef.current;

      try {
        setIsLoading(true);
        setError(null);

        const data = await getContent(reportId, path);
        if (thisRequest !== requestIdRef.current) {
          return;
        }

        setContent(decorateReportContent(data));
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
  const artifactCount = structure?.artifacts.length ?? 0;

  const selectedCategoryMeta = selectedTab !== "complete" ? CATEGORY_MAP[selectedTab] : null;
  const selectedCategoryLabel =
    selectedTab === SUMMARY_TAB_KEY
      ? t("report.summary", "Summary")
      : selectedCategoryMeta
        ? t(`report.category.${selectedTab}`, selectedCategoryMeta.label)
        : null;
  const selectedFileLabel = selectedFile
    ? t(`report.file.${selectedFile}`, FILE_LABELS[selectedFile] || selectedFile)
    : null;
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

  const handleTabChange = useCallback(
    (tabKey: string) => {
      setSelectedTab(tabKey);

      const crossMode =
        (selectedTab === "complete") !== (tabKey === "complete") ||
        selectedTab === SUMMARY_TAB_KEY ||
        tabKey === SUMMARY_TAB_KEY;
      if (crossMode) {
        setContent("");
      }

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
    [selectedTab, structure]
  );

  if (!structure) {
    return (
      <div className="flex min-w-0 flex-1 flex-col p-2 md:p-3 lg:p-4">
        <div className="viewer-frame mx-auto flex w-full items-center justify-center p-8 text-sm text-slate-600">
          {isLoading
            ? t("report.loadingReport", "Loading report...")
            : error
              ? `${t("report.errorPrefix", "Error")}: ${error}`
              : t("report.noReportData", "No report data")}
        </div>
      </div>
    );
  }

  return (
    <div className="flex min-w-0 flex-1 flex-col p-2 md:p-3 lg:p-4">
      <section
        id="report-content-panel"
        className="viewer-frame mx-auto w-full"
        aria-live="polite"
      >
        <div>
          <div className="px-4 pt-6 md:px-8 md:pt-8">
            <div className="w-full">
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
                    size="sm"
                    onClick={() => setIsOverviewCollapsed((current) => !current)}
                    aria-expanded={!isOverviewCollapsed}
                    aria-controls="report-overview-panel"
                    title={overviewToggleLabel}
                    className="min-h-10 rounded-full px-3"
                  >
                    {isOverviewCollapsed ? (
                      <ChevronDown className="size-4" aria-hidden />
                    ) : (
                      <ChevronUp className="size-4" aria-hidden />
                    )}
                    <span>{overviewToggleLabel}</span>
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
                            <p className="viewer-meta-label">
                              {selectedCategoryLabel ??
                                t("report.researchWorkbench", "Research workbench")}
                            </p>
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
                            </div>
                          </div>
                        </div>

                        <div className="grid gap-3">
                          <SummaryMetric
                            label={t("report.readingOverview", "Reading Overview")}
                            value={
                              selectedCategoryLabel ??
                              t("report.completeReport", "Complete Report")
                            }
                            hint={selectedFileLabel ?? t("report.houseView", "House View")}
                          />
                          <SummaryMetric
                            label={t("report.availableTracks", "Available tracks")}
                            value={String(availableTrackCount)}
                            hint={t(
                              "report.trackCountHint",
                              ({ count }) => `${count} agent tracks available`,
                              { count: availableTrackCount }
                            )}
                          />
                          <SummaryMetric
                            label={t("report.sourceFiles", "Source files")}
                            value={String(sourceFileCount)}
                            hint={t(
                              "report.referenceArtifactsHint",
                              ({ count }) => `${count} Reference artifacts attached`,
                              { count: artifactCount }
                            )}
                          />
                        </div>
                      </div>
                    </header>
                  </div>

                  <div className="min-w-0">
                    <TickerPricePanel
                      symbol={structure.ticker}
                      asOfDate={reportMeta?.date ?? null}
                      title={t("report.priceTrend", "Price Trend")}
                      subtitle={t(
                        "report.priceTrendHint",
                        "400-day vendor-backed history aligned to this report date."
                      )}
                      embedded
                    />
                  </div>
                </div>
                )}
              </section>
            </div>
          </div>

          <div className="sticky top-0 z-20 bg-transparent">
            <div className="report-tab-rail border-b border-[var(--border)] px-4 py-3 md:px-8 md:py-4">
              <div className="w-full">
                <Tabs value={selectedTab} onValueChange={handleTabChange}>
                  <TabsList className="scrollbar-none flex w-full justify-start gap-2 overflow-x-auto rounded-none border-0 bg-transparent p-0 shadow-none">
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
                <div className="w-full">
                  <div className="scrollbar-none flex overflow-x-auto gap-2 rounded-[20px] border border-[var(--border)] bg-white/42 p-2">
                    {categoryFiles.map((file) => (
                      <Button
                        key={file}
                        onClick={() => {
                          setContent("");
                          setSelectedFile(file);
                        }}
                        variant={selectedFile === file ? "default" : "secondary"}
                        size="sm"
                        className="whitespace-nowrap"
                        aria-controls="report-content-panel"
                      >
                        {FILE_LABELS[file] || file}
                      </Button>
                    ))}
                  </div>
                </div>
              </div>
            )}
          </div>

          <div className="px-4 pb-6 pt-6 md:px-8 md:pb-8 md:pt-8">
            <div className="w-full">
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
                  <p className="max-w-xl text-sm leading-6 text-[var(--muted)]">
                    {t(
                      "report.filePerspective",
                      ({ label, ticker }) =>
                        `${label} captures one desk's perspective for ${ticker}. Read this layer on its own, then compare it against the full report.`,
                      {
                        label: selectedCategoryLabel ?? selectedCategoryMeta.label,
                        ticker: structure.ticker,
                      }
                    )}
                  </p>
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
                <MarkdownContent
                  content={content}
                  isLoading={isLoading}
                  highlightMode="off"
                />
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
  );
}

function SummaryMetric({
  label,
  value,
  hint,
}: {
  label: string;
  value: string;
  hint: string;
}) {
  return (
    <Card className="border-b-0 bg-white/80 shadow-none">
      <CardContent className="py-3">
      <p className="text-[10px] font-semibold uppercase tracking-[0.22em] text-slate-500">
        {label}
      </p>
      <p className="mt-2 text-lg font-semibold text-slate-900">{value}</p>
      <p className="mt-1 text-xs leading-5 text-slate-500">{hint}</p>
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
