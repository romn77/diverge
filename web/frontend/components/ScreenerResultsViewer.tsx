"use client";

import { useEffect, useMemo, useState } from "react";
import { usePreferences } from "@/components/PreferencesProvider";
import {
  getScreenerRun,
  listScreenerRunCandidates,
  type ScreenerCandidateRow,
  type ScreenerRunDetail,
} from "@/lib/api";

interface ScreenerResultsViewerProps {
  runId: string;
}

type SortKey =
  | "global_rank"
  | "total_score"
  | "trend_score"
  | "momentum_score"
  | "risk_score"
  | "liquidity_score";

export function ScreenerResultsViewer({ runId }: ScreenerResultsViewerProps) {
  const { locale, t } = usePreferences();
  const [run, setRun] = useState<ScreenerRunDetail | null>(null);
  const [rows, setRows] = useState<ScreenerCandidateRow[]>([]);
  const [sortKey, setSortKey] = useState<SortKey>("global_rank");

  useEffect(() => {
    let isActive = true;

    const load = async () => {
      const [nextRun, nextRows] = await Promise.all([
        getScreenerRun(runId),
        listScreenerRunCandidates(runId),
      ]);
      if (!isActive) {
        return;
      }
      setRun(nextRun);
      setRows(nextRows);
    };

    void load();
    return () => {
      isActive = false;
    };
  }, [runId]);

  const sortedRows = useMemo(() => {
    return [...rows].sort((a, b) => {
      if (sortKey === "global_rank") {
        return a.global_rank - b.global_rank;
      }
      return (b[sortKey] ?? 0) - (a[sortKey] ?? 0);
    });
  }, [rows, sortKey]);

  const columns: Array<{ key: SortKey; label: string }> = [
    { key: "global_rank", label: t("screenerResults.column.rank", "Rank") },
    { key: "total_score", label: t("screenerResults.column.total", "Total") },
    { key: "trend_score", label: t("screenerResults.column.trend", "Trend") },
    {
      key: "momentum_score",
      label: t("screenerResults.column.momentum", "Momentum"),
    },
    { key: "risk_score", label: t("screenerResults.column.risk", "Risk") },
    {
      key: "liquidity_score",
      label: t("screenerResults.column.liquidity", "Liquidity"),
    },
  ];

  return (
    <main className="flex min-h-[100vh] flex-1 flex-col p-2 md:h-screen md:overflow-hidden md:p-3 lg:p-4">
      <div className="w-full space-y-6">
        <section className="fade-in rounded-[30px] border border-[var(--border)] bg-white/95 p-6 shadow-[0_24px_60px_rgba(18,28,41,0.08)] md:p-8">
          <div className="flex items-start justify-between gap-4">
            <div>
              <p className="text-[11px] font-semibold uppercase tracking-[0.34em] text-[var(--primary)]">
                {t("screenerResults.kicker", "Screener Results")}
              </p>
              <h1 className="font-heading mt-3 text-3xl font-bold tracking-tight text-slate-900">
                {run?.id ?? runId}
              </h1>
            </div>
            <div className="text-right text-sm text-slate-600">
              <p>{formatAsOfDate(run?.as_of_date ?? null, locale)}</p>
              <p>
                {t("screenerResults.candidates", ({ count }) => `${count} candidates`, {
                  count: run?.candidate_count ?? rows.length,
                })}
              </p>
            </div>
          </div>

          <div className="mt-6 flex flex-wrap gap-2">
            {columns.map((column) => (
              <button
                key={column.key}
                type="button"
                className="rounded-full border border-[var(--border)] bg-white px-3 py-2 text-xs font-semibold uppercase tracking-[0.18em] text-slate-700"
                onClick={() => setSortKey(column.key)}
              >
                {column.label}
              </button>
            ))}
          </div>

          <div className="mt-8 overflow-x-auto rounded-[24px] border border-[var(--border)]">
            <table className="min-w-full divide-y divide-slate-200 text-sm">
              <thead className="bg-slate-50">
                <tr>
                  <th className="px-4 py-3 text-left">
                    {t("screenerResults.header.symbol", "symbol")}
                  </th>
                  <th className="px-4 py-3 text-left">
                    {t("screenerResults.header.market", "market")}
                  </th>
                  <th className="px-4 py-3 text-left">
                    {t("screenerResults.header.global_rank", "global_rank")}
                  </th>
                  <th className="px-4 py-3 text-left">
                    {t("screenerResults.header.total_score", "total_score")}
                  </th>
                  <th className="px-4 py-3 text-left">
                    {t("screenerResults.header.trend_score", "trend_score")}
                  </th>
                  <th className="px-4 py-3 text-left">
                    {t("screenerResults.header.momentum_score", "momentum_score")}
                  </th>
                  <th className="px-4 py-3 text-left">
                    {t("screenerResults.header.risk_score", "risk_score")}
                  </th>
                  <th className="px-4 py-3 text-left">
                    {t(
                      "screenerResults.header.liquidity_score",
                      "liquidity_score"
                    )}
                  </th>
                  <th className="px-4 py-3 text-left">
                    {t("screenerResults.header.strategy_tags", "strategy_tags")}
                  </th>
                  <th className="px-4 py-3 text-left">
                    {t("screenerResults.header.risk_flags", "risk_flags")}
                  </th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100 bg-white">
                {sortedRows.length === 0 ? (
                  <tr>
                    <td className="px-4 py-6 text-slate-500" colSpan={10}>
                      {t("screenerResults.empty", "No screener candidates available.")}
                    </td>
                  </tr>
                ) : (
                  sortedRows.map((row) => (
                    <tr key={`${row.symbol}-${row.market}`}>
                      <td className="px-4 py-3">{row.symbol}</td>
                      <td className="px-4 py-3">{row.market}</td>
                      <td className="px-4 py-3">{row.global_rank}</td>
                      <td className="px-4 py-3">{row.total_score}</td>
                      <td className="px-4 py-3">{row.trend_score}</td>
                      <td className="px-4 py-3">{row.momentum_score}</td>
                      <td className="px-4 py-3">{row.risk_score}</td>
                      <td className="px-4 py-3">{row.liquidity_score}</td>
                      <td className="px-4 py-3">{row.strategy_tags}</td>
                      <td className="px-4 py-3">{row.risk_flags}</td>
                    </tr>
                  ))
                )}
              </tbody>
            </table>
          </div>
        </section>
      </div>
    </main>
  );
}

function formatAsOfDate(value: string | null, locale: string) {
  if (!value) {
    return "";
  }

  const parsed = new Date(`${value}T00:00:00`);
  if (Number.isNaN(parsed.getTime())) {
    return value;
  }

  return new Intl.DateTimeFormat(locale, {
    year: "numeric",
    month: "short",
    day: "numeric",
  }).format(parsed);
}
