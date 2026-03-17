"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import type { Report } from "@/lib/api";

interface SidebarProps {
  selectedReportId: string | null;
  onSelectReport: (reportId: string) => void;
  reports: Report[];
  loading: boolean;
  error: string | null;
  searchQuery: string;
  onSearchQueryChange: (value: string) => void;
  isOpen: boolean;
  onClose: () => void;
}

export function Sidebar({
  selectedReportId,
  onSelectReport,
  reports,
  loading,
  error,
  searchQuery,
  onSearchQueryChange,
  isOpen,
  onClose,
}: SidebarProps) {
  const [expandedTickers, setExpandedTickers] = useState<Set<string>>(() => new Set());
  const [isRecentReportsOpen, setIsRecentReportsOpen] = useState(true);
  const [isAllTickersOpen, setIsAllTickersOpen] = useState(false);
  const [isMobileViewport, setIsMobileViewport] = useState(false);
  const searchInputRef = useRef<HTMLInputElement>(null);

  const sortedReports = useMemo(() => {
    return [...reports].sort((a, b) => parseReportTimestamp(b) - parseReportTimestamp(a));
  }, [reports]);

  const filteredReports = useMemo(() => {
    if (!searchQuery.trim()) {
      return sortedReports;
    }
    const normalized = searchQuery.toLowerCase();
    return sortedReports.filter(
      (report) =>
        report.ticker.toLowerCase().includes(normalized) ||
        report.id.toLowerCase().includes(normalized)
    );
  }, [searchQuery, sortedReports]);

  const groupedByTicker = useMemo(() => {
    return filteredReports.reduce<Record<string, Report[]>>((acc, report) => {
      const ticker = report.ticker;
      if (!acc[ticker]) {
        acc[ticker] = [];
      }
      acc[ticker].push(report);
      return acc;
    }, {});
  }, [filteredReports]);

  const tickerOrder = useMemo(() => {
    return Object.entries(groupedByTicker)
      .sort(
        ([aTicker, reportsA], [bTicker, reportsB]) =>
          Math.max(...reportsB.map(parseReportTimestamp)) -
          Math.max(...reportsA.map(parseReportTimestamp))
      )
      .map(([ticker]) => ticker);
  }, [groupedByTicker]);

  const recentReports = useMemo(() => sortedReports.slice(0, 3), [sortedReports]);
  const isMobileDrawerOpen = isMobileViewport && isOpen;

  useEffect(() => {
    const mediaQuery = window.matchMedia("(max-width: 767px)");
    const syncViewport = (event?: MediaQueryListEvent) => {
      setIsMobileViewport(event ? event.matches : mediaQuery.matches);
    };

    syncViewport();
    mediaQuery.addEventListener("change", syncViewport);

    return () => {
      mediaQuery.removeEventListener("change", syncViewport);
    };
  }, []);

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

  useEffect(() => {
    if (!isMobileDrawerOpen) {
      document.body.style.overflow = "";
      return;
    }

    document.body.style.overflow = "hidden";
    return () => {
      document.body.style.overflow = "";
    };
  }, [isMobileDrawerOpen]);

  useEffect(() => {
    if (!isMobileDrawerOpen) {
      return;
    }

    const handleKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape") {
        onClose();
      }
    };

    window.addEventListener("keydown", handleKeyDown);
    return () => {
      window.removeEventListener("keydown", handleKeyDown);
    };
  }, [isMobileDrawerOpen, onClose]);

  useEffect(() => {
    if (isMobileDrawerOpen) {
      searchInputRef.current?.focus();
    }
  }, [isMobileDrawerOpen]);

  const toggleTicker = (ticker: string) => {
    setExpandedTickers((current) => {
      const next = new Set(current);
      if (next.has(ticker)) {
        next.delete(ticker);
      } else {
        next.add(ticker);
      }
      return next;
    });
  };

  const drawerClasses = [
    "fixed inset-y-0 left-0 z-50 w-full max-w-xs flex-col overflow-y-auto border-r border-[var(--border)] bg-white px-4 py-5 shadow-lg transition-transform duration-300",
    "hidden md:flex -translate-x-full md:translate-x-0",
    isMobileDrawerOpen ? "flex translate-x-0" : "",
    "md:relative md:w-[19.2rem] md:shadow-none md:border-r-0",
  ].join(" ");

  return (
    <>
      {isMobileDrawerOpen && (
        <div
          className="fixed inset-0 z-40 bg-black/30 md:hidden"
          onClick={onClose}
          aria-hidden="true"
        />
      )}

      <aside
        id="report-navigation"
        className={drawerClasses}
        role={isMobileDrawerOpen ? "dialog" : undefined}
        aria-modal={isMobileDrawerOpen ? true : undefined}
        aria-label="Report navigation"
      >
      <div className="flex items-center justify-between gap-2 border-b border-[var(--border)] pb-4">
        <div className="flex items-center gap-2">
          <div className="grid h-9 w-9 place-items-center rounded-2xl bg-[var(--primary)] text-white shadow-sm">
            <svg viewBox="0 0 24 24" className="h-4 w-4" fill="none" aria-hidden>
              <path
                d="M4 16l4.2-4.2L11 14.6l8-8"
                stroke="currentColor"
                strokeWidth="2.2"
                strokeLinecap="round"
                strokeLinejoin="round"
              />
            </svg>
          </div>
          <div>
            <p className="text-sm font-semibold text-slate-900">TradingAgent</p>
            <p className="text-xs uppercase tracking-[0.3em] text-slate-500">Research</p>
          </div>
        </div>
        <button
          type="button"
          className="md:hidden rounded-2xl border border-[var(--border)] px-3 py-2 text-xs font-semibold text-slate-600 transition hover:border-[var(--primary)] hover:text-[var(--primary)]"
          onClick={onClose}
          aria-label="Close sidebar"
        >
          Close
        </button>
      </div>

      <div className="mt-4">
        <label
          className="text-xs font-semibold uppercase tracking-[0.25em] text-slate-500"
          htmlFor="sidebar-search"
        >
          Filter reports
        </label>
        <div className="relative mt-2">
          <span className="pointer-events-none absolute inset-y-0 left-3 flex items-center text-slate-400">
            <svg
              className="h-4 w-4"
              viewBox="0 0 20 20"
              fill="currentColor"
              aria-hidden
            >
              <path
                fillRule="evenodd"
                clipRule="evenodd"
                d="M8 3a5 5 0 013.872 8.064l3.283 3.283a1 1 0 01-1.415 1.415l-3.283-3.283A5 5 0 118 3zm0 2a3 3 0 100 6 3 3 0 000-6z"
              />
            </svg>
          </span>
          <input
            ref={searchInputRef}
            id="sidebar-search"
            type="text"
            value={searchQuery}
            onChange={(event) => onSearchQueryChange(event.target.value)}
            placeholder="Ticker or report id"
            className="focus-ring w-full rounded-2xl border border-[var(--border-strong)] bg-slate-50 py-3 pl-10 pr-12 text-sm font-medium text-slate-800 transition focus:border-[var(--primary)]"
          />
          {searchQuery && (
            <button
              type="button"
              className="absolute right-3 top-1/2 -translate-y-1/2 rounded-full border border-[var(--border)] bg-white px-2 py-1 text-[10px] font-semibold text-slate-500 transition hover:text-[var(--primary)]"
              onClick={() => onSearchQueryChange("")}
            >
              Clear
            </button>
          )}
        </div>
        <p className="mt-1 text-xs text-slate-500">Filter by ticker or report ID.</p>
      </div>

      <div className="mt-6 space-y-4">
        <section>
          <button
            type="button"
            className="flex w-full items-center justify-between text-left"
            onClick={() => setIsRecentReportsOpen((current) => !current)}
            aria-expanded={isRecentReportsOpen}
            aria-controls="recent-reports-panel"
          >
            <h3 className="text-xs font-semibold uppercase tracking-[0.4em] text-slate-500">
              Recent Reports
            </h3>
            <div className="flex items-center gap-2">
              <span className="text-[10px] font-semibold uppercase tracking-[0.3em] text-slate-400">
                {recentReports.length} shown
              </span>
              <svg
                className={`h-4 w-4 text-slate-400 transition-transform ${
                  isRecentReportsOpen ? "rotate-90" : ""
                }`}
                viewBox="0 0 20 20"
                fill="none"
                stroke="currentColor"
                aria-hidden
              >
                <path
                  d="M7 6l5 4-5 4"
                  strokeWidth="1.8"
                  strokeLinecap="round"
                  strokeLinejoin="round"
                />
              </svg>
            </div>
          </button>
          {isRecentReportsOpen && (
            <div
              id="recent-reports-panel"
              className="mt-3 space-y-2 rounded-2xl border border-slate-100 bg-slate-50 p-2 text-sm"
            >
              {loading ? (
                <p className="px-3 py-4 text-xs font-semibold text-slate-500">
                  Loading reports…
                </p>
              ) : recentReports.length === 0 ? (
                <p className="px-3 py-4 text-xs font-semibold text-slate-500">
                  No reports yet.
                </p>
              ) : (
                recentReports.map((report) => (
                  <button
                    key={report.id}
                    type="button"
                    className="flex w-full items-center justify-between rounded-2xl px-3 py-3 text-left transition hover:bg-white hover:text-[var(--primary)]"
                    onClick={() => onSelectReport(report.id)}
                  >
                    <div>
                      <p className="text-sm font-semibold text-slate-900">
                        {report.ticker}
                      </p>
                      <p className="text-xs uppercase tracking-[0.3em] text-slate-500">
                        {formatReportDate(report)}
                      </p>
                    </div>
                    <svg
                      className="h-4 w-4 text-slate-400"
                      viewBox="0 0 20 20"
                      fill="none"
                      stroke="currentColor"
                      aria-hidden
                    >
                      <path
                        d="M7 6l5 4-5 4"
                        strokeWidth="1.8"
                        strokeLinecap="round"
                        strokeLinejoin="round"
                      />
                    </svg>
                  </button>
                ))
              )}
            </div>
          )}
        </section>

        <section>
          <button
            type="button"
            className="flex w-full items-center justify-between text-left"
            onClick={() => setIsAllTickersOpen((current) => !current)}
            aria-expanded={isAllTickersOpen}
            aria-controls="all-tickers-panel"
          >
            <h3 className="text-xs font-semibold uppercase tracking-[0.35em] text-slate-500">
              All tickers
            </h3>
            <svg
              className={`h-4 w-4 text-slate-400 transition-transform ${
                isAllTickersOpen ? "rotate-90" : ""
              }`}
              viewBox="0 0 20 20"
              fill="none"
              stroke="currentColor"
              aria-hidden
            >
              <path
                d="M7 6l5 4-5 4"
                strokeWidth="1.8"
                strokeLinecap="round"
                strokeLinejoin="round"
              />
            </svg>
          </button>
          {isAllTickersOpen && (
            <div id="all-tickers-panel" className="mt-3 space-y-3">
              {tickerOrder.length === 0 ? (
                <p className="text-xs font-semibold text-slate-500">
                  No tickers match the current filter.
                </p>
              ) : (
                tickerOrder.map((ticker) => {
                  const isExpanded = expandedTickers.has(ticker);
                  const panelId = `ticker-panel-${ticker}`;

                  return (
                    <div
                      key={ticker}
                      className="rounded-2xl border border-[var(--border)] bg-white/80"
                    >
                      <button
                        type="button"
                        onClick={() => toggleTicker(ticker)}
                        className="flex h-[44px] w-full items-center justify-between px-3 py-2 text-sm font-semibold text-slate-800 transition hover:bg-slate-50"
                        aria-expanded={isExpanded}
                        aria-controls={panelId}
                      >
                        <span>{ticker}</span>
                        <svg
                          className={`h-4 w-4 text-slate-500 transition-transform ${
                            isExpanded ? "rotate-90" : ""
                          }`}
                          viewBox="0 0 20 20"
                          fill="none"
                          stroke="currentColor"
                          aria-hidden
                        >
                          <path
                            d="M7 6l5 4-5 4"
                            strokeWidth="1.8"
                            strokeLinecap="round"
                            strokeLinejoin="round"
                          />
                        </svg>
                      </button>
                      {isExpanded && (
                        <div
                          id={panelId}
                          className="flex flex-col gap-1 border-t border-[var(--border)] px-1.5 py-2"
                        >
                          {groupedByTicker[ticker].map((report) => (
                            <button
                              key={report.id}
                              type="button"
                              className={`flex min-h-[44px] w-full items-center justify-between rounded-xl px-3 text-sm transition hover:bg-slate-100 ${
                                selectedReportId === report.id
                                  ? "text-[var(--primary)]"
                                  : "text-slate-600"
                              }`}
                              onClick={() => onSelectReport(report.id)}
                              aria-current={selectedReportId === report.id ? "true" : undefined}
                            >
                              <div>
                                <p className="font-medium">{report.date ?? "Unknown date"}</p>
                                <p className="text-[11px] text-slate-500">
                                  {report.time ?? "--:--:--"}
                                </p>
                              </div>
                              <span className="text-[10px] font-semibold uppercase tracking-[0.3em]">
                                {selectedReportId === report.id ? "Active" : "View"}
                              </span>
                            </button>
                          ))}
                        </div>
                      )}
                    </div>
                  );
                })
              )}
            </div>
          )}
        </section>
        {error && (
          <div className="text-xs font-semibold text-rose-600">{error}</div>
        )}
      </div>
      </aside>
    </>
  );
}

function parseReportTimestamp(report: Report): number {
  if (report.date) {
    const isoLike = `${report.date}T${report.time ?? "00:00:00"}`;
    const parsed = Date.parse(isoLike);
    if (!Number.isNaN(parsed)) {
      return parsed;
    }
  }

  const fallback = Date.parse(report.id);
  if (!Number.isNaN(fallback)) {
    return fallback;
  }

  return Number.NEGATIVE_INFINITY;
}

function getMostRecentTicker(reports: Report[]): string | null {
  if (reports.length === 0) {
    return null;
  }

  const recent = reports.reduce((best, current) =>
    parseReportTimestamp(current) > parseReportTimestamp(best) ? current : best
  );
  return recent.ticker;
}

function findTickerForReport(reports: Report[], reportId: string | null): string | null {
  if (!reportId) {
    return null;
  }
  return reports.find((report) => report.id === reportId)?.ticker ?? null;
}

function formatReportDate(report: Report) {
  if (report.date && report.time) {
    return `${report.date} · ${report.time}`;
  }
  if (report.date) {
    return report.date;
  }
  return "Unknown date";
}
