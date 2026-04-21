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
  | "breakout_bonus"
  | "trend_score"
  | "momentum_score"
  | "risk_score"
  | "liquidity_score";

const BREAKOUT_FILTER_OPTIONS = [
  { value: "all", label: "All Results" },
  { value: "platform_breakout", label: "Platform Breakout" },
  { value: "box_breakout", label: "Box Breakout" },
  { value: "wedge_breakout", label: "Wedge Breakout" },
] as const;

export function ScreenerResultsViewer({ runId }: ScreenerResultsViewerProps) {
  const { locale, t } = usePreferences();
  const [run, setRun] = useState<ScreenerRunDetail | null>(null);
  const [rows, setRows] = useState<ScreenerCandidateRow[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [sortKey, setSortKey] = useState<SortKey>("global_rank");
  const [breakoutFilter, setBreakoutFilter] = useState<string>("all");
  const [volumeConfirmedOnly, setVolumeConfirmedOnly] = useState(false);

  useEffect(() => {
    let isActive = true;

    const load = async () => {
      setIsLoading(true);
      setLoadError(null);

      try {
        const [nextRun, nextRows] = await Promise.all([
          getScreenerRun(runId),
          listScreenerRunCandidates(runId),
        ]);
        if (!isActive) {
          return;
        }
        setRun(nextRun);
        setRows(nextRows);
      } catch (error) {
        if (!isActive) {
          return;
        }
        setLoadError(
          error instanceof Error
            ? error.message
            : t("screenerResults.error", "Unable to load screener results")
        );
      } finally {
        if (isActive) {
          setIsLoading(false);
        }
      }
    };

    void load();
    return () => {
      isActive = false;
    };
  }, [runId]);

  const filteredRows = useMemo(() => {
    return rows.filter((row) => {
      if (!matchesBreakoutFilter(row, breakoutFilter)) {
        return false;
      }
      if (volumeConfirmedOnly && row.breakout_with_volume !== true) {
        return false;
      }
      return true;
    });
  }, [rows, breakoutFilter, volumeConfirmedOnly]);

  const sortedRows = useMemo(() => {
    return [...filteredRows].sort((a, b) => {
      if (sortKey === "global_rank") {
        return a.global_rank - b.global_rank;
      }
      return (b[sortKey] ?? 0) - (a[sortKey] ?? 0);
    });
  }, [filteredRows, sortKey]);

  const columns: Array<{ key: SortKey; label: string }> = [
    { key: "global_rank", label: t("screenerResults.column.rank", "Rank") },
    { key: "total_score", label: t("screenerResults.column.total", "Total") },
    { key: "breakout_bonus", label: t("screenerResults.column.breakout", "Breakout") },
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
  const highlightedRows = useMemo(() => sortedRows.slice(0, 3), [sortedRows]);
  const marketCount = useMemo(
    () => new Set(filteredRows.map((row) => row.market)).size,
    [filteredRows]
  );
  const strongestSignal = highlightedRows[0] ?? null;
  const filteredReasons = useMemo(
    () => Object.entries(run?.filtered_count_by_reason ?? {}).filter(([, count]) => count > 0),
    [run?.filtered_count_by_reason]
  );

  return (
    <main className="flex min-h-[100vh] flex-1 flex-col p-2 md:h-screen md:overflow-hidden md:p-3 lg:p-4">
      <div className="w-full space-y-6">
        <section className="fade-in rounded-[30px] border border-[var(--border)] bg-white/95 p-6 shadow-[0_24px_60px_rgba(18,28,41,0.08)] md:p-8">
          <div className="flex flex-wrap items-start justify-between gap-4">
            <div>
              <p className="text-[11px] font-semibold uppercase tracking-[0.34em] text-[var(--primary)]">
                {t("screenerResults.kicker", "Screener Results")}
              </p>
              <h1 className="font-heading mt-3 text-3xl font-bold tracking-tight text-slate-900">
                {run?.id ?? runId}
              </h1>
              <p className="mt-3 max-w-2xl text-sm leading-6 text-slate-600">
                Compare the ranked pool, inspect the strongest candidates first, and
                use the score mix to decide which symbols deserve deeper research.
              </p>
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

          <div className="mt-8 grid gap-4 lg:grid-cols-[minmax(0,1.4fr)_minmax(0,0.6fr)]">
            <div className="grid gap-4 md:grid-cols-3">
              <SummaryCard
                label={t("screenerResults.summary.topPick", "Top pick")}
                value={strongestSignal?.symbol ?? "—"}
                hint={
                  strongestSignal
                    ? `${strongestSignal.market} · total ${formatScore(strongestSignal.total_score, locale)}`
                    : "Waiting for screener candidates"
                }
              />
              <SummaryCard
                label={t("screenerResults.summary.coverage", "Markets")}
                value={String(marketCount || 0)}
                hint="Distinct markets represented in this run"
              />
              <SummaryCard
                label={t("screenerResults.summary.filtered", "Filtered Out")}
                value={String(
                  filteredReasons.reduce((sum, [, count]) => sum + count, 0)
                )}
                hint="Candidates removed before the final export"
              />
            </div>

            <div className="rounded-[24px] border border-[var(--border)] bg-[var(--surface-strong)] p-4">
              <p className="text-[10px] font-semibold uppercase tracking-[0.24em] text-slate-500">
                {t("screenerResults.summary.artifacts", "Artifacts")}
              </p>
              <div className="mt-3 space-y-2">
                {Object.entries(run?.artifact_paths ?? {}).length === 0 ? (
                  <p className="text-sm text-slate-500">No artifact paths exposed yet.</p>
                ) : (
                  Object.entries(run?.artifact_paths ?? {}).map(([label, artifactPath]) => (
                    <div
                      key={label}
                      className="rounded-[18px] border border-[var(--border)] bg-white/88 px-3 py-3"
                    >
                      <p className="text-[10px] font-semibold uppercase tracking-[0.2em] text-slate-500">
                        {label}
                      </p>
                      <p className="mt-1 break-all font-mono text-[11px] text-slate-700">
                        {artifactPath}
                      </p>
                    </div>
                  ))
                )}
              </div>
            </div>
          </div>

          <div className="mt-8 flex flex-wrap gap-2">
            {BREAKOUT_FILTER_OPTIONS.map((option) => (
              <button
                key={option.value}
                type="button"
                aria-pressed={breakoutFilter === option.value}
                className={`rounded-full border px-3 py-2 text-xs font-semibold uppercase tracking-[0.18em] transition ${
                  breakoutFilter === option.value
                    ? "border-[var(--primary)] bg-[var(--primary)] text-white shadow-[0_10px_24px_rgba(181,89,38,0.22)]"
                    : "border-[var(--border)] bg-white text-slate-700 hover:border-[rgba(181,89,38,0.22)] hover:bg-[rgba(181,89,38,0.06)] hover:text-[var(--primary)]"
                }`}
                onClick={() => setBreakoutFilter(option.value)}
              >
                {option.label}
              </button>
            ))}
            <button
              type="button"
              aria-pressed={volumeConfirmedOnly}
              className={`rounded-full border px-3 py-2 text-xs font-semibold uppercase tracking-[0.18em] transition ${
                volumeConfirmedOnly
                  ? "border-[var(--primary)] bg-[var(--primary)] text-white shadow-[0_10px_24px_rgba(181,89,38,0.22)]"
                  : "border-[var(--border)] bg-white text-slate-700 hover:border-[rgba(181,89,38,0.22)] hover:bg-[rgba(181,89,38,0.06)] hover:text-[var(--primary)]"
              }`}
              onClick={() => setVolumeConfirmedOnly((value) => !value)}
            >
              {t("screenerResults.filter.volume", "Volume Confirmed")}
            </button>
          </div>

          <div className="mt-4 flex flex-wrap gap-2">
            {columns.map((column) => (
              <button
                key={column.key}
                type="button"
                aria-pressed={sortKey === column.key}
                className={`rounded-full border px-3 py-2 text-xs font-semibold uppercase tracking-[0.18em] transition ${
                  sortKey === column.key
                    ? "border-[var(--primary)] bg-[var(--primary)] text-white shadow-[0_10px_24px_rgba(181,89,38,0.22)]"
                    : "border-[var(--border)] bg-white text-slate-700 hover:border-[rgba(181,89,38,0.22)] hover:bg-[rgba(181,89,38,0.06)] hover:text-[var(--primary)]"
                }`}
                onClick={() => setSortKey(column.key)}
              >
                {column.label}
              </button>
            ))}
          </div>

          {loadError ? (
            <div className="mt-8 rounded-[24px] border border-[rgba(163,53,53,0.2)] bg-[rgba(163,53,53,0.08)] px-4 py-4 text-sm text-[var(--danger)]">
              {loadError}
            </div>
          ) : null}

          {filteredReasons.length > 0 ? (
            <div className="mt-6 flex flex-wrap gap-2">
              {filteredReasons.map(([reason, count]) => (
                <span
                  key={reason}
                  className="rounded-full border border-[var(--border)] bg-white px-3 py-1 text-[10px] font-semibold uppercase tracking-[0.18em] text-slate-600"
                >
                  {reason}: {count}
                </span>
              ))}
            </div>
          ) : null}

          {highlightedRows.length > 0 ? (
            <div className="mt-8 grid gap-4 lg:grid-cols-3">
              {highlightedRows.map((row) => (
                <article
                  key={`${row.symbol}-${row.market}-hero`}
                  className="rounded-[26px] border border-[var(--border)] bg-[var(--surface-strong)]/92 p-5"
                >
                  <div className="flex items-start justify-between gap-3">
                    <div>
                      <p className="text-[10px] font-semibold uppercase tracking-[0.22em] text-[var(--primary)]">
                        Rank #{row.global_rank}
                      </p>
                      <h2 className="mt-2 text-2xl font-semibold text-slate-900">
                        {row.symbol}
                      </h2>
                      <p className="mt-1 text-sm text-slate-500">{row.market}</p>
                    </div>
                    <span className="rounded-full bg-white px-3 py-1 text-xs font-semibold text-slate-700">
                      {formatScore(row.total_score, locale)}
                    </span>
                  </div>

                  <dl className="mt-4 grid grid-cols-2 gap-3">
                    <Metric label="Trend" value={formatScore(row.trend_score, locale)} />
                    <Metric
                      label="Breakout"
                      value={formatScore(row.breakout_bonus ?? 0, locale)}
                    />
                    <Metric
                      label="Momentum"
                      value={formatScore(row.momentum_score, locale)}
                    />
                    <Metric label="Risk" value={formatScore(row.risk_score, locale)} />
                    <Metric
                      label="Liquidity"
                      value={formatScore(row.liquidity_score, locale)}
                    />
                  </dl>

                  <div className="mt-4 space-y-2">
                    <TagStrip
                      label="Pattern"
                      value={formatBreakoutType(row.breakout_type)}
                      tone="bg-[rgba(181,89,38,0.08)] text-[var(--primary)]"
                    />
                    <TagStrip
                      label="Volume"
                      value={formatVolumeFlag(row.breakout_with_volume)}
                      tone="bg-[rgba(22,101,52,0.08)] text-emerald-700"
                    />
                    <TagStrip
                      label="Strategy"
                      value={row.strategy_tags}
                      tone="bg-[rgba(28,56,83,0.08)] text-[var(--accent)]"
                    />
                    <TagStrip
                      label="Risk"
                      value={row.risk_flags}
                      tone="bg-[rgba(163,53,53,0.08)] text-[var(--danger)]"
                    />
                  </div>
                </article>
              ))}
            </div>
          ) : null}

          <div className="mt-8 overflow-x-auto rounded-[24px] border border-[var(--border)]">
            <table className="min-w-full divide-y divide-slate-200 text-sm">
              <thead className="sticky top-0 bg-slate-50">
                <tr>
                  <th className="px-4 py-3 text-left">
                    {t("screenerResults.header.symbol", "symbol")}
                  </th>
                  <th className="px-4 py-3 text-left">
                    {t("screenerResults.header.market", "market")}
                  </th>
                  <th className="px-4 py-3 text-right tabular-nums">
                    {t("screenerResults.header.global_rank", "global_rank")}
                  </th>
                  <th className="px-4 py-3 text-right tabular-nums">
                    {t("screenerResults.header.total_score", "total_score")}
                  </th>
                  <th className="px-4 py-3 text-left">
                    {t("screenerResults.header.breakout_type", "breakout_type")}
                  </th>
                  <th className="px-4 py-3 text-left">
                    {t(
                      "screenerResults.header.breakout_with_volume",
                      "breakout_with_volume"
                    )}
                  </th>
                  <th className="px-4 py-3 text-right tabular-nums">
                    {t("screenerResults.header.breakout_bonus", "breakout_bonus")}
                  </th>
                  <th className="px-4 py-3 text-right tabular-nums">
                    {t("screenerResults.header.trend_score", "trend_score")}
                  </th>
                  <th className="px-4 py-3 text-right tabular-nums">
                    {t("screenerResults.header.momentum_score", "momentum_score")}
                  </th>
                  <th className="px-4 py-3 text-right tabular-nums">
                    {t("screenerResults.header.risk_score", "risk_score")}
                  </th>
                  <th className="px-4 py-3 text-right tabular-nums">
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
                {isLoading ? (
                  <tr>
                    <td className="px-4 py-6 text-slate-500" colSpan={13}>
                      Loading screener candidates...
                    </td>
                  </tr>
                ) : sortedRows.length === 0 ? (
                  <tr>
                    <td className="px-4 py-6 text-slate-500" colSpan={13}>
                      {t("screenerResults.empty", "No screener candidates available.")}
                    </td>
                  </tr>
                ) : (
                  sortedRows.map((row) => (
                    <tr
                      key={`${row.symbol}-${row.market}`}
                      className={row.global_rank <= 3 ? "bg-[rgba(245,222,209,0.18)]" : ""}
                    >
                      <td className="px-4 py-3 font-semibold text-slate-900">{row.symbol}</td>
                      <td className="px-4 py-3">{row.market}</td>
                      <td className="px-4 py-3 text-right tabular-nums">{row.global_rank}</td>
                      <td className="px-4 py-3 text-right tabular-nums">
                        {formatScore(row.total_score, locale)}
                      </td>
                      <td className="px-4 py-3">
                        <TagStrip
                          label="Pattern"
                          value={formatBreakoutType(row.breakout_type)}
                          tone="bg-[rgba(181,89,38,0.08)] text-[var(--primary)]"
                          compact
                        />
                      </td>
                      <td className="px-4 py-3">
                        <TagStrip
                          label="Volume"
                          value={formatVolumeFlag(row.breakout_with_volume)}
                          tone="bg-[rgba(22,101,52,0.08)] text-emerald-700"
                          compact
                        />
                      </td>
                      <td className="px-4 py-3 text-right tabular-nums">
                        {formatScore(row.breakout_bonus ?? 0, locale)}
                      </td>
                      <td className="px-4 py-3 text-right tabular-nums">
                        {formatScore(row.trend_score, locale)}
                      </td>
                      <td className="px-4 py-3 text-right tabular-nums">
                        {formatScore(row.momentum_score, locale)}
                      </td>
                      <td className="px-4 py-3 text-right tabular-nums">
                        {formatScore(row.risk_score, locale)}
                      </td>
                      <td className="px-4 py-3 text-right tabular-nums">
                        {formatScore(row.liquidity_score, locale)}
                      </td>
                      <td className="px-4 py-3">
                        <TagStrip
                          label="Strategy"
                          value={row.strategy_tags}
                          tone="bg-[rgba(28,56,83,0.08)] text-[var(--accent)]"
                          compact
                        />
                      </td>
                      <td className="px-4 py-3">
                        <TagStrip
                          label="Risk"
                          value={row.risk_flags}
                          tone="bg-[rgba(163,53,53,0.08)] text-[var(--danger)]"
                          compact
                        />
                      </td>
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

function matchesBreakoutFilter(row: ScreenerCandidateRow, breakoutFilter: string): boolean {
  if (breakoutFilter === "all") {
    return true;
  }
  return row.breakout_type === breakoutFilter;
}

function formatBreakoutType(breakoutType: string | null | undefined): string {
  if (!breakoutType) {
    return "none";
  }
  switch (breakoutType) {
    case "platform_breakout":
      return "Platform Breakout";
    case "box_breakout":
      return "Box Breakout";
    case "wedge_breakout":
      return "Wedge Breakout";
    default:
      return breakoutType;
  }
}

function formatVolumeFlag(value: boolean | undefined): string {
  return value ? "confirmed" : "standard";
}

function SummaryCard({
  label,
  value,
  hint,
}: {
  label: string;
  value: string;
  hint: string;
}) {
  return (
    <div className="rounded-[24px] border border-[var(--border)] bg-[var(--surface-strong)] p-5">
      <p className="text-[10px] font-semibold uppercase tracking-[0.22em] text-slate-500">
        {label}
      </p>
      <p className="mt-3 text-3xl font-semibold tracking-tight text-slate-900">{value}</p>
      <p className="mt-2 text-sm leading-6 text-slate-600">{hint}</p>
    </div>
  );
}

function Metric({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-[18px] border border-[var(--border)] bg-white/88 px-3 py-3">
      <p className="text-[10px] font-semibold uppercase tracking-[0.2em] text-slate-500">
        {label}
      </p>
      <p className="mt-2 text-lg font-semibold tabular-nums text-slate-900">{value}</p>
    </div>
  );
}

function TagStrip({
  label,
  value,
  tone,
  compact = false,
}: {
  label: string;
  value: string;
  tone: string;
  compact?: boolean;
}) {
  const tokens = value
    .split(/[;,]/)
    .map((token) => token.trim())
    .filter(Boolean);

  if (tokens.length === 0) {
    return (
      <span className="text-xs text-slate-400">
        {compact ? "—" : `${label}: none`}
      </span>
    );
  }

  return (
    <div className={`flex flex-wrap gap-2 ${compact ? "" : "items-start"}`}>
      {tokens.map((token) => (
        <span
          key={`${label}-${token}`}
          className={`rounded-full px-2.5 py-1 text-[10px] font-semibold uppercase tracking-[0.16em] ${tone}`}
        >
          {token}
        </span>
      ))}
    </div>
  );
}

function formatScore(value: number, locale: string): string {
  return new Intl.NumberFormat(locale, {
    minimumFractionDigits: 1,
    maximumFractionDigits: 1,
  }).format(value);
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
