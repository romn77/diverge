"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { getContent, getStructure, type Report, type ReportStructure } from "@/lib/api";
import { parseHighlights, type SignalConfidence, type TradeSignal } from "@/lib/highlights";
import { MarkdownContent } from "./MarkdownContent";

interface ReportViewerProps {
  reportId: string;
  reportMeta?: Report | null;
  onOpenSidebar?: () => void;
  sidebarOpen?: boolean;
}

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

function formatGeneratedLabel(reportMeta?: Report | null): string {
  if (reportMeta?.date && reportMeta.time) {
    return `${reportMeta.date} ${reportMeta.time}`;
  }

  if (reportMeta?.date) {
    return reportMeta.date;
  }

  return "Generated time unavailable";
}

function signalClass(signal: TradeSignal | null): string {
  switch (signal) {
    case "BUY":
      return "signal-buy";
    case "HOLD":
      return "signal-hold";
    case "SELL":
      return "signal-sell";
    default:
      return "";
  }
}

export function ReportViewer({
  reportId,
  reportMeta = null,
  onOpenSidebar,
  sidebarOpen = false,
}: ReportViewerProps) {
  const [structure, setStructure] = useState<ReportStructure | null>(null);
  const [selectedTab, setSelectedTab] = useState("complete");
  const [selectedFile, setSelectedFile] = useState<string | null>(null);
  const [content, setContent] = useState("");
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [finalSignal, setFinalSignal] = useState<TradeSignal | null>(null);
  const [finalConfidence, setFinalConfidence] = useState<SignalConfidence | null>(null);
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
        setSelectedTab("complete");
        setSelectedFile(null);
        setContent("");
      } catch (err) {
        if (!isActive) {
          return;
        }

        setError(err instanceof Error ? err.message : "Failed to load report");
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
  }, [reportId]);

  useEffect(() => {
    let isActive = true;

    const loadFinalSignal = async () => {
      if (!structure?.categories.portfolio?.includes("decision")) {
        setFinalSignal(null);
        setFinalConfidence(null);
        return;
      }

      try {
        const decisionMarkdown = await getContent(reportId, "5_portfolio/decision.md");
        if (!isActive) {
          return;
        }

        const parsed = parseHighlights(decisionMarkdown).highlights;
        setFinalSignal(parsed?.signal ?? null);
        setFinalConfidence(parsed?.signal_confidence ?? null);
      } catch {
        if (isActive) {
          setFinalSignal(null);
          setFinalConfidence(null);
        }
      }
    };

    loadFinalSignal();

    return () => {
      isActive = false;
    };
  }, [reportId, structure]);

  useEffect(() => {
    const loadContent = async () => {
      if (!structure) {
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

        setError(err instanceof Error ? err.message : "Failed to load content");
      } finally {
        if (thisRequest === requestIdRef.current) {
          setIsLoading(false);
        }
      }
    };

    loadContent();
  }, [reportId, selectedFile, selectedTab, structure]);

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
    () => (selectedTab !== "complete" && structure ? structure.categories[selectedTab] || [] : []),
    [selectedTab, structure]
  );

  const selectedCategoryMeta = selectedTab !== "complete" ? CATEGORY_MAP[selectedTab] : null;
  const selectedFileLabel = selectedFile ? FILE_LABELS[selectedFile] || selectedFile : null;

  const handleTabChange = useCallback(
    (tabKey: string) => {
      setSelectedTab(tabKey);

      const crossMode = (selectedTab === "complete") !== (tabKey === "complete");
      if (crossMode) {
        setContent("");
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
      <div className="flex min-w-0 flex-1 flex-col p-2 md:h-screen md:overflow-hidden md:p-3 lg:p-4">
        <div className="viewer-frame mx-auto flex min-h-0 w-full flex-1 items-center justify-center p-8 text-sm text-slate-600">
          {isLoading
            ? "Loading report..."
            : error
              ? `Error: ${error}`
              : "No report data"}
        </div>
      </div>
    );
  }

  return (
    <div className="flex min-w-0 flex-1 flex-col p-2 md:h-screen md:overflow-hidden md:p-3 lg:p-4">
      <section
        id="report-content-panel"
        className="viewer-frame mx-auto flex min-h-0 w-full flex-1 flex-col overflow-hidden"
        aria-live="polite"
      >
        <div className="h-full overflow-y-auto">
          <div className="sticky top-0 z-20 bg-transparent">
            <header className="border-b border-[color:rgba(22,34,51,0.08)] bg-[linear-gradient(180deg,rgba(255,253,248,0.98),rgba(252,245,235,0.92))] px-4 py-5 md:px-8 md:py-8">
              <div className="w-full space-y-5">
                <div className="viewer-header-grid">
                  <div className="space-y-5">
                    <div className="flex min-w-0 items-start gap-4">
                      {onOpenSidebar && (
                        <button
                          type="button"
                          onClick={onOpenSidebar}
                          aria-controls="report-navigation"
                          aria-expanded={sidebarOpen}
                          aria-haspopup="dialog"
                          className="interactive-button focus-ring grid min-h-11 min-w-11 place-items-center rounded-full border border-[color:rgba(22,34,51,0.1)] bg-white/78 text-slate-500 md:hidden"
                          aria-label="Open report navigation"
                        >
                          <svg viewBox="0 0 24 24" className="size-4" fill="none" aria-hidden>
                            <path
                              d="M4 7h16M4 12h16M4 17h16"
                              stroke="currentColor"
                              strokeWidth="1.8"
                              strokeLinecap="round"
                            />
                          </svg>
                        </button>
                      )}

                      <div className="min-w-0">
                        <p className="viewer-meta-label">
                          {selectedCategoryMeta ? selectedCategoryMeta.label : "Research workbench"}
                        </p>
                        <h2 className="mt-2 font-heading truncate text-[2.1rem] font-bold tracking-tight text-slate-900 md:text-[2.7rem]">
                          {structure.ticker}
                        </h2>
                        <div className="mt-2 flex flex-wrap items-center gap-x-3 gap-y-1 text-sm text-slate-500 md:text-base">
                          <span>{formatGeneratedLabel(reportMeta)}</span>
                          <span className="hidden text-[var(--border-strong)] sm:inline">
                            /
                          </span>
                          <span className="font-mono text-[12px] text-slate-500">
                            {reportId}
                          </span>
                        </div>
                        <div className="mt-4 flex flex-wrap items-center gap-x-6 gap-y-2 text-sm text-[var(--muted)]">
                          <span className="inline-flex items-center gap-2">
                            <span className="size-2 rounded-full bg-[var(--primary)]" aria-hidden />
                            {selectedFileLabel ??
                              (selectedCategoryMeta
                                ? `${selectedCategoryMeta.label} view`
                                : "Full report")}
                          </span>
                          {selectedTab !== "complete" && categoryFiles.length > 0 && (
                            <span>{categoryFiles.length} files in this track</span>
                          )}
                        </div>
                      </div>
                    </div>

                    <div className="scrollbar-none flex gap-5 overflow-x-auto border-b border-[color:rgba(22,34,51,0.08)] pb-1">
                      <button
                        type="button"
                        onClick={() => handleTabChange("complete")}
                        className={`focus-ring whitespace-nowrap border-b-2 px-1 pb-3 pt-1 text-sm font-semibold tracking-[0.01em] transition-colors ${
                          selectedTab === "complete"
                            ? "border-[var(--primary)] text-[var(--accent)]"
                            : "border-transparent text-[var(--muted)] hover:text-[var(--text)]"
                        }`}
                        aria-pressed={selectedTab === "complete"}
                        aria-controls="report-content-panel"
                      >
                        Complete Report
                      </button>

                      {availableCategories.map(([key, meta]) => (
                        <button
                          type="button"
                          key={key}
                          onClick={() => handleTabChange(key)}
                          className={`focus-ring whitespace-nowrap border-b-2 px-1 pb-3 pt-1 text-sm font-semibold tracking-[0.01em] transition-colors ${
                            selectedTab === key
                              ? "border-[var(--primary)] text-[var(--accent)]"
                              : "border-transparent text-[var(--muted)] hover:text-[var(--text)]"
                          }`}
                          aria-pressed={selectedTab === key}
                          aria-controls="report-content-panel"
                        >
                          {meta.label}
                        </button>
                      ))}
                    </div>
                  </div>

                  <aside className="viewer-meta-card">
                    <p className="viewer-meta-label">House View</p>
                    <div className="mt-3 flex flex-wrap items-center gap-2">
                      <span
                        className={`signal-badge viewer-signal-badge min-h-11 ${
                          finalSignal ? signalClass(finalSignal) : "border-[color:rgba(22,34,51,0.1)] bg-white/70 text-slate-600"
                        }`}
                      >
                        {finalSignal ?? "Pending"}
                      </span>
                      {finalConfidence && (
                        <span className="rounded-full border border-[color:rgba(22,34,51,0.1)] bg-white/78 px-3 py-2 text-xs font-semibold text-slate-600">
                          Confidence {finalConfidence}
                        </span>
                      )}
                    </div>

                    <p className="mt-4 text-sm leading-6 text-slate-600">
                      {selectedCategoryMeta
                        ? `Reading ${selectedFileLabel ?? selectedCategoryMeta.label}.`
                        : "Use the category rail to move between the full report and individual agent views."}
                    </p>
                  </aside>
                </div>
              </div>
            </header>

            {selectedTab !== "complete" && categoryFiles.length > 0 && (
              <div className="border-b border-[color:rgba(22,34,51,0.08)] bg-[color:rgba(255,253,248,0.8)] px-4 py-3 md:px-8">
                <div className="w-full">
                  <div className="scrollbar-none flex overflow-x-auto gap-2 rounded-[20px] border border-[color:rgba(22,34,51,0.08)] bg-white/42 p-2">
                    {categoryFiles.map((file) => (
                      <button
                        type="button"
                        key={file}
                        onClick={() => {
                          setContent("");
                          setSelectedFile(file);
                        }}
                        className="pill-tab whitespace-nowrap"
                        data-active={selectedFile === file}
                        aria-pressed={selectedFile === file}
                        aria-controls="report-content-panel"
                      >
                        {FILE_LABELS[file] || file}
                      </button>
                    ))}
                  </div>
                </div>
              </div>
            )}
          </div>

          <div className="px-4 pb-6 pt-6 md:px-8 md:pb-8 md:pt-8">
            <div className="w-full">
              {selectedTab !== "complete" && selectedCategoryMeta && (
                <div className="mb-8 flex w-full flex-col gap-3 border-b border-[color:rgba(22,34,51,0.08)] pb-5 md:flex-row md:items-end md:justify-between">
                  <div className="space-y-1">
                    <p className="viewer-meta-label">Current file</p>
                    <h3 className="font-heading text-2xl font-semibold tracking-tight text-[var(--text)] md:text-3xl">
                      {selectedFileLabel ?? selectedCategoryMeta.label}
                    </h3>
                  </div>
                  <p className="max-w-xl text-sm leading-6 text-[var(--muted)]">
                    {selectedCategoryMeta.label} captures one desk&apos;s perspective for {structure.ticker}. Read this layer on its own, then compare it against the full report.
                  </p>
                </div>
              )}

              {error ? (
                <div className="rounded-[18px] border border-rose-200 bg-rose-50 p-4 text-sm text-rose-700">
                  {error}
                </div>
              ) : selectedTab === "complete" ? (
                <MarkdownContent
                  content={content}
                  isLoading={isLoading}
                  highlightMode="off"
                />
              ) : categoryFiles.length === 0 ? (
                <div className="py-8 text-center text-sm text-slate-500">
                  No data available for this category
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
