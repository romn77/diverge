"use client";

import { useEffect, useState } from "react";
import { listReports, Report } from "@/lib/api";

interface SidebarProps {
  selectedReportId: string | null;
  onSelectReport: (reportId: string) => void;
}

const parseReportTimestamp = (report: Report): number => {
  if (report.date) {
    const isoLikeValue = `${report.date}T${report.time ?? "00:00:00"}`;
    const parsed = Date.parse(isoLikeValue);
    if (!Number.isNaN(parsed)) {
      return parsed;
    }
  }

  const fallback = Date.parse(report.id);
  return Number.isNaN(fallback) ? Number.NEGATIVE_INFINITY : fallback;
};

const findTickerForReport = (
  reports: Report[],
  reportId: string | null
): string | null => {
  if (!reportId) {
    return null;
  }
  return reports.find((report) => report.id === reportId)?.ticker ?? null;
};

const getMostRecentTicker = (reports: Report[]): string | null => {
  if (reports.length === 0) {
    return null;
  }

  const mostRecentReport = reports.reduce((best, current) =>
    parseReportTimestamp(current) > parseReportTimestamp(best) ? current : best
  );

  return mostRecentReport.ticker;
};

const toDomSafeId = (value: string): string =>
  value.toLowerCase().replace(/[^a-z0-9_-]+/g, "-");

export function Sidebar({
  selectedReportId,
  onSelectReport,
}: SidebarProps) {
  const [reports, setReports] = useState<Report[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [searchQuery, setSearchQuery] = useState("");
  const [expandedTickers, setExpandedTickers] = useState<Set<string>>(new Set());

  useEffect(() => {
    const fetchReports = async () => {
      try {
        setLoading(true);
        const data = await listReports();
        setReports(data);
        setError(null);
      } catch (err) {
        setError(
          err instanceof Error ? err.message : "Failed to load reports"
        );
        setReports([]);
      } finally {
        setLoading(false);
      }
    };

    fetchReports();
  }, []);

  const filteredReports = reports.filter((report) =>
    report.ticker.toLowerCase().includes(searchQuery.toLowerCase()) ||
    report.id.toLowerCase().includes(searchQuery.toLowerCase())
  );

  const groupedByTicker = filteredReports.reduce(
    (acc, report) => {
      const ticker = report.ticker;
      if (!acc[ticker]) {
        acc[ticker] = [];
      }
      acc[ticker].push(report);
      return acc;
    },
    {} as Record<string, Report[]>
  );

  const sortedTickers = Object.keys(groupedByTicker).sort();

  const toggleTicker = (ticker: string) => {
    const newExpanded = new Set(expandedTickers);
    if (newExpanded.has(ticker)) {
      newExpanded.delete(ticker);
    } else {
      newExpanded.add(ticker);
    }
    setExpandedTickers(newExpanded);
  };

  useEffect(() => {
    if (loading || reports.length === 0) {
      return;
    }

    const selectedTicker = findTickerForReport(reports, selectedReportId);

    setExpandedTickers((previous) => {
      if (selectedTicker) {
        if (previous.size === 0) {
          return new Set([selectedTicker]);
        }
        if (!previous.has(selectedTicker)) {
          const next = new Set(previous);
          next.add(selectedTicker);
          return next;
        }
      }

      if (previous.size > 0) {
        return previous;
      }

      const recentTicker = getMostRecentTicker(reports);
      return recentTicker ? new Set([recentTicker]) : previous;
    });
  }, [loading, reports, selectedReportId]);

  return (
    <aside className="glass-panel relative w-full shrink-0 border-b border-[var(--border)] md:h-screen md:w-[19.2rem] md:rounded-r-2xl md:border-b-0 md:border-r">
      <div className="border-b border-[var(--border)] px-4 py-4 md:px-5">
        <div className="flex items-center justify-between gap-2.5">
          <div className="flex items-center gap-2.5">
            <div className="grid size-8 place-items-center rounded-lg bg-[var(--primary)] text-white shadow-sm">
              <svg viewBox="0 0 24 24" className="size-4" fill="none" aria-hidden>
                <path
                  d="M4 16l4.2-4.2L11 14.6l8-8"
                  stroke="currentColor"
                  strokeWidth="2.2"
                  strokeLinecap="round"
                  strokeLinejoin="round"
                />
              </svg>
            </div>
            <p className="font-heading text-sm font-bold tracking-tight text-slate-900">
              Trading<span className="text-[var(--primary)]">Agent</span>
            </p>
          </div>
          <div className="rounded-full border border-[var(--border)] bg-white/75 px-2.5 py-1 text-[10px] font-semibold uppercase tracking-[0.14em] text-slate-500">
            {reports.length} total
          </div>
        </div>

        <div className="relative mt-4">
          <svg
            viewBox="0 0 24 24"
            className="pointer-events-none absolute left-2.5 top-1/2 size-4 -translate-y-1/2 text-slate-400"
            fill="none"
            aria-hidden
          >
            <path
              d="M11 5a6 6 0 104.24 10.24L19 19"
              stroke="currentColor"
              strokeWidth="1.8"
              strokeLinecap="round"
              strokeLinejoin="round"
            />
          </svg>
          <input
            type="text"
            placeholder="Search reports..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            className="focus-ring w-full rounded-xl border border-[var(--border-strong)] bg-white/82 py-2.5 pl-8 pr-16 text-sm text-slate-700 placeholder:text-slate-500"
            aria-label="Search reports"
          />
          {searchQuery && (
            <button
              type="button"
              onClick={() => setSearchQuery("")}
              className="interactive-button focus-ring absolute right-2 top-1/2 -translate-y-1/2 rounded-md border border-[var(--border)] bg-white px-2 py-1 text-[11px] font-medium text-slate-500 hover:border-[color:rgba(236,91,19,0.45)] hover:text-[var(--primary-strong)]"
              aria-label="Clear search"
            >
              Clear
            </button>
          )}
        </div>
      </div>

      <div className="max-h-[48vh] overflow-y-auto px-1 py-1 md:max-h-[calc(100vh-150px)]">
        {loading && (
          <div className="p-4 text-center text-sm text-slate-500">Loading...</div>
        )}

        {error && (
          <div className="p-4 text-center text-sm text-rose-600">{error}</div>
        )}

        {!loading && !error && filteredReports.length === 0 && (
          <div className="p-4 text-center text-sm text-slate-500">
            {searchQuery ? (
              <div>
                <div>No reports match &quot;{searchQuery}&quot;.</div>
                <div className="mt-1 text-xs text-slate-500">
                  Try a ticker symbol (for example AAPL) or part of report id.
                </div>
                <button
                  type="button"
                  onClick={() => setSearchQuery("")}
                  className="interactive-button focus-ring mt-3 rounded-md border border-[var(--border)] bg-white px-2.5 py-1 text-xs font-medium text-slate-600 hover:border-[color:rgba(236,91,19,0.45)] hover:text-[var(--primary-strong)]"
                >
                  Clear search
                </button>
              </div>
            ) : (
              "No reports found"
            )}
          </div>
        )}

        {!loading && !error && filteredReports.length > 0 && (
          <div className="space-y-4 px-3 py-4">
            <div className="flex items-center justify-between px-2">
              <div className="text-[10px] font-semibold uppercase tracking-[0.17em] text-slate-500">
                Reports
              </div>
              <div className="text-[10px] font-semibold uppercase tracking-[0.12em] text-slate-500">
                {filteredReports.length} results
              </div>
            </div>
            {sortedTickers.map((ticker) => {
              const isExpanded = expandedTickers.has(ticker);
              const panelId = `ticker-panel-${toDomSafeId(ticker)}`;

              return (
                <div key={ticker} className="rounded-xl border border-[var(--border)] bg-white/74 p-1.5">
                  <button
                    type="button"
                    onClick={() => toggleTicker(ticker)}
                    className="interactive-button focus-ring w-full rounded-lg px-2 py-2 text-left transition-colors hover:bg-slate-100"
                    aria-expanded={isExpanded}
                    aria-controls={panelId}
                  >
                    <div className="flex items-center justify-between">
                      <div className="text-sm font-semibold text-slate-700">{ticker}</div>
                      <span
                        className={`grid size-5 place-items-center rounded-full border border-[var(--border)] text-[10px] text-slate-500 transition-transform ${
                          isExpanded ? "rotate-90" : ""
                        }`}
                        aria-hidden
                      >
                        &gt;
                      </span>
                    </div>
                  </button>
                  {isExpanded && (
                    <div id={panelId} className="space-y-1 border-l border-[var(--border)] pl-2.5">
                      {groupedByTicker[ticker].map((report) => (
                        <button
                          type="button"
                          key={report.id}
                          onClick={() => onSelectReport(report.id)}
                          className={`interactive-button focus-ring w-full rounded-lg px-2.5 py-2 text-left text-sm transition-all ${
                            selectedReportId === report.id
                              ? "border border-[color:rgba(236,91,19,0.3)] bg-[var(--primary-soft)] text-[var(--primary-strong)] shadow-sm"
                              : "text-slate-600 hover:bg-slate-100"
                          }`}
                          aria-current={selectedReportId === report.id ? "true" : undefined}
                        >
                          <div className="font-medium">{report.date ?? "Unknown date"}</div>
                          <div className="mt-0.5 text-xs text-slate-500">{report.time ?? "--:--:--"}</div>
                        </button>
                      ))}
                    </div>
                  )}
                </div>
              );
            })}
          </div>
        )}
      </div>
    </aside>
  );
}
