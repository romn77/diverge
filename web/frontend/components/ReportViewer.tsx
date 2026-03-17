"use client";

import { useState, useEffect, useCallback, useRef } from "react";
import { getStructure, getContent, ReportStructure } from "@/lib/api";
import { MarkdownContent } from "./MarkdownContent";

interface ReportViewerProps {
  reportId: string;
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

export function ReportViewer({ reportId }: ReportViewerProps) {
  const [structure, setStructure] = useState<ReportStructure | null>(null);
  const [selectedTab, setSelectedTab] = useState<string>("complete");
  const [selectedFile, setSelectedFile] = useState<string | null>(null);
  const [content, setContent] = useState<string>("");
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const requestIdRef = useRef(0);

  useEffect(() => {
    const loadStructure = async () => {
      requestIdRef.current++;
      try {
        setIsLoading(true);
        setError(null);
        const data = await getStructure(reportId);
        setStructure(data);
        setSelectedTab("complete");
        setSelectedFile(null);
        setContent("");
      } catch (err) {
        setError(err instanceof Error ? err.message : "Failed to load report");
        setStructure(null);
      } finally {
        setIsLoading(false);
      }
    };

    loadStructure();
  }, [reportId]);

  useEffect(() => {
    const loadContent = async () => {
      if (!structure) return;

      let path: string;

      if (selectedTab === "complete") {
        path = "complete_report.md";
      } else {
        const categoryKey = selectedTab;
        const categoryInfo = CATEGORY_MAP[categoryKey];
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
        if (thisRequest !== requestIdRef.current) return;
        setContent(data);
      } catch (err) {
        if (thisRequest !== requestIdRef.current) return;
        setError(err instanceof Error ? err.message : "Failed to load content");
      } finally {
        if (thisRequest === requestIdRef.current) {
          setIsLoading(false);
        }
      }
    };

    loadContent();
  }, [reportId, selectedTab, selectedFile, structure]);

   const handleTabChange = useCallback(
      (tabKey: string) => {
        setSelectedTab(tabKey);
        // Force skeleton load when switching between complete and category modes (cross-mode policy)
        const crossMode = (selectedTab === "complete") !== (tabKey === "complete");
        if (crossMode) {
          setContent("");
        }
        if (tabKey !== "complete" && structure) {
          const categoryKey = tabKey;
          const files = structure.categories[categoryKey] || [];
          if (files.length > 0) {
            setSelectedFile(files[0]);
          } else {
            setSelectedFile(null);
          }
        } else {
          setSelectedFile(null);
        }
      },
      [selectedTab, structure]
    );

  if (!structure) {
    return (
      <div className="flex-1 min-w-0 p-4 md:p-7 lg:p-9">
        <div className="glass-panel fade-in rounded-2xl p-8 text-sm text-slate-600">
          {isLoading
            ? "Loading report..."
            : error
              ? `Error: ${error}`
              : "No report data"}
        </div>
      </div>
    );
  }

  const availableCategories = Object.entries(CATEGORY_MAP).filter(
    ([key]) => structure.categories[key] && structure.categories[key].length > 0
  );

  const categoryFiles =
    selectedTab !== "complete"
      ? structure.categories[selectedTab] || []
      : [];

  return (
    <div className="flex min-w-0 flex-1 flex-col gap-3 p-3 md:h-screen md:gap-4 md:p-5 lg:p-7">
      <header className="glass-panel fade-in shrink-0 rounded-2xl p-4 md:p-5">
        <div className="flex flex-col gap-4">
          <div className="grid grid-cols-[1fr_auto_1fr] items-center gap-3">
            <p className="justify-self-start rounded-full border border-[color:rgba(236,91,19,0.35)] bg-[var(--primary-soft)] px-2.5 py-1 text-[10px] font-semibold uppercase tracking-[0.16em] text-[var(--primary-strong)]">
              Trading Report
            </p>
            <h2 className="justify-self-center text-center font-heading text-2xl font-extrabold tracking-tight text-slate-900 md:text-3xl">
              {structure.ticker}
            </h2>
            <p className="justify-self-end rounded-full border border-[var(--border)] bg-white/78 px-2.5 py-1 text-[10px] font-semibold uppercase tracking-[0.15em] text-slate-500">
              {reportId}
            </p>
          </div>

          <div
            className="flex flex-wrap gap-2 pb-1"
            role="tablist"
            aria-label="Report stages"
          >
            <button
              id="report-tab-complete"
              type="button"
              onClick={() => handleTabChange("complete")}
              className={`interactive-button focus-ring whitespace-nowrap rounded-full border px-4 py-2 text-sm font-semibold transition-all ${
                selectedTab === "complete"
                  ? "border-[color:rgba(236,91,19,0.82)] bg-[linear-gradient(135deg,#ec5b13_0%,#d74f0d_100%)] text-white shadow-[0_10px_20px_rgba(236,91,19,0.24)]"
                  : "border-[var(--border)] bg-white/90 text-slate-600 hover:border-[color:rgba(236,91,19,0.45)] hover:text-[var(--primary-strong)]"
              }`}
              role="tab"
              aria-selected={selectedTab === "complete"}
              aria-controls="report-content-panel"
            >
              Complete Report
            </button>

            {availableCategories.map(([key, meta]) => (
              <button
                id={`report-tab-${key}`}
                type="button"
                key={key}
                onClick={() => handleTabChange(key)}
                className={`interactive-button focus-ring whitespace-nowrap rounded-full border px-4 py-2 text-sm font-semibold transition-all ${
                  selectedTab === key
                    ? "border-[color:rgba(236,91,19,0.82)] bg-[linear-gradient(135deg,#ec5b13_0%,#d74f0d_100%)] text-white shadow-[0_10px_20px_rgba(236,91,19,0.24)]"
                    : "border-[var(--border)] bg-white/90 text-slate-600 hover:border-[color:rgba(236,91,19,0.45)] hover:text-[var(--primary-strong)]"
                }`}
                role="tab"
                aria-selected={selectedTab === key}
                aria-controls="report-content-panel"
              >
                {meta.label}
              </button>
            ))}
          </div>

          {selectedTab !== "complete" && categoryFiles.length > 0 && (
            <div
              className="flex flex-wrap gap-2 border-t border-[var(--border)] pt-3"
              role="tablist"
              aria-label="Stage files"
            >
              {categoryFiles.map((file) => (
                <button
                   id={`report-file-${file}`}
                   type="button"
                   key={file}
                   onClick={() => {
                     setContent("");
                     setSelectedFile(file);
                   }}
                   className={`interactive-button focus-ring rounded-full px-3.5 py-1.5 text-sm font-medium whitespace-nowrap transition-all ${
                    selectedFile === file
                      ? "border border-[color:rgba(236,91,19,0.42)] bg-[var(--primary-soft)] text-[var(--primary-strong)] shadow-[0_6px_16px_rgba(236,91,19,0.14)]"
                      : "border border-[var(--border)] bg-white/86 text-slate-500 hover:border-[color:rgba(21,55,96,0.28)] hover:text-[var(--accent)]"
                  }`}
                  role="tab"
                  aria-selected={selectedFile === file}
                  aria-controls="report-content-panel"
                >
                  {FILE_LABELS[file] || file}
                </button>
              ))}
            </div>
          )}
        </div>
      </header>

      <section
        id="report-content-panel"
        className="card-surface flex-1 min-h-0 overflow-hidden rounded-2xl"
        role="tabpanel"
        aria-live="polite"
      >
        <div className="h-full overflow-y-auto p-5 md:p-8">
          {selectedTab === "complete" ? (
            <MarkdownContent content={content} isLoading={isLoading} highlightMode="off" />
          ) : categoryFiles.length === 0 ? (
            <div className="py-8 text-center text-sm text-slate-500">
              No data available for this category
            </div>
          ) : (
            <MarkdownContent content={content} isLoading={isLoading} highlightMode="single" />
          )}
        </div>
      </section>
    </div>
  );
}
