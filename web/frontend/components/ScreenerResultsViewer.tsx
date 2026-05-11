"use client";

import { useEffect, useMemo, useState, type ReactNode } from "react";
import { usePreferences } from "@/components/PreferencesProvider";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent } from "@/components/ui/card";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { ChevronLeft, ChevronRight } from "lucide-react";
import {
  getScreenerRun,
  getTickerHistoryBatch,
  listScreenerRunCandidates,
  type ScreenerCandidateRow,
  type ScreenerRunDetail,
  type TickerHistoryPoint,
} from "@/lib/api";
import { TickerSparkline } from "./TickerPricePanel";

interface ScreenerResultsViewerProps {
  runId: string;
  embedded?: boolean;
}

type SortKey =
  | "global_rank"
  | "close"
  | "ret_20"
  | "ret_60"
  | "rsi"
  | "atr_pct"
  | "avg_amount_20d"
  | "breakout_volume_ratio";

type SortDirection = "asc" | "desc";

const BREAKOUT_FILTER_OPTIONS = [
  { value: "all" },
  { value: "platform_breakout" },
  { value: "box_breakout" },
  { value: "wedge_breakout" },
] as const;
const TREND_HISTORY_BATCH_SIZE = 50;
const PAGE_SIZE_OPTIONS = [25, 50, 100] as const;
type PageSize = (typeof PAGE_SIZE_OPTIONS)[number];

export function ScreenerResultsViewer({ runId, embedded = false }: ScreenerResultsViewerProps) {
  const { locale, t } = usePreferences();
  const [run, setRun] = useState<ScreenerRunDetail | null>(null);
  const [rows, setRows] = useState<ScreenerCandidateRow[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [loadingTrendSeries, setLoadingTrendSeries] = useState(false);
  const [trendSeriesByTicker, setTrendSeriesByTicker] = useState<
    Record<string, TickerHistoryPoint[]>
  >({});
  const [sortKey, setSortKey] = useState<SortKey>("global_rank");
  const [breakoutFilter, setBreakoutFilter] = useState<string>("all");
  const [volumeConfirmedOnly, setVolumeConfirmedOnly] = useState(false);
  const [pageSize, setPageSize] = useState<PageSize>(25);
  const [pageIndex, setPageIndex] = useState(0);

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
  }, [runId, t]);

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

  useEffect(() => {
    if (filteredRows.length === 0) {
      setTrendSeriesByTicker({});
      setLoadingTrendSeries(false);
      return;
    }

    let isActive = true;

    const loadTrendSeries = async () => {
      setLoadingTrendSeries(true);

      try {
        const uniqueTickers = Array.from(
          new Map(filteredRows.map((row) => [seriesKey(row.symbol, row.market), row])).values()
        );
        const payloads = await Promise.all(
          chunkItems(uniqueTickers, TREND_HISTORY_BATCH_SIZE).map((tickerBatch) =>
            getTickerHistoryBatch({
              tickers: tickerBatch.map((row) => ({
                symbol: row.symbol,
                market: row.market,
              })),
              as_of_date: run?.as_of_date ?? null,
            })
          )
        );
        if (!isActive) {
          return;
        }

        setTrendSeriesByTicker(
          Object.fromEntries(
            payloads
              .flatMap((payload) => payload.items)
              .map((item) => [seriesKey(item.symbol, item.market), item.points])
          )
        );
      } catch {
        if (isActive) {
          setTrendSeriesByTicker({});
        }
      } finally {
        if (isActive) {
          setLoadingTrendSeries(false);
        }
      }
    };

    void loadTrendSeries();
    return () => {
      isActive = false;
    };
  }, [filteredRows, run?.as_of_date]);

  const sortOptions = useMemo<Array<{ key: SortKey; label: string; direction?: SortDirection }>>(
    () => [
      { key: "global_rank", label: t("screenerResults.column.rank", "Rank"), direction: "asc" },
      { key: "close", label: t("screenerResults.column.close", "Close") },
      { key: "ret_20", label: t("screenerResults.column.ret20", "20D Return") },
      {
        key: "ret_60",
        label: t("screenerResults.column.ret60", "60D Return"),
      },
      { key: "rsi", label: t("screenerResults.column.rsi", "RSI") },
      { key: "atr_pct", label: t("screenerResults.column.atr", "ATR%"), direction: "asc" },
      {
        key: "avg_amount_20d",
        label: t("screenerResults.column.amount20d", "20D Amount"),
      },
      {
        key: "breakout_volume_ratio",
        label: t("screenerResults.column.volumeRatio", "Volume Ratio"),
      },
    ],
    [t]
  );
  const sortedRows = useMemo(() => {
    const sortOption = sortOptions.find((option) => option.key === sortKey);
    const direction = sortOption?.direction ?? "desc";
    return [...filteredRows].sort((a, b) => {
      if (sortKey === "global_rank") {
        return a.global_rank - b.global_rank;
      }
      const aValue = numericValue(a[sortKey]);
      const bValue = numericValue(b[sortKey]);
      if (aValue === null && bValue === null) {
        return a.global_rank - b.global_rank;
      }
      if (aValue === null) {
        return 1;
      }
      if (bValue === null) {
        return -1;
      }
      return direction === "asc" ? aValue - bValue : bValue - aValue;
    });
  }, [filteredRows, sortKey, sortOptions]);
  const pageCount = Math.max(Math.ceil(sortedRows.length / pageSize), 1);
  const safePageIndex = Math.min(pageIndex, pageCount - 1);
  const pageStart = safePageIndex * pageSize;
  const pageEnd = Math.min(pageStart + pageSize, sortedRows.length);
  const paginatedRows = useMemo(
    () => sortedRows.slice(pageStart, pageEnd),
    [pageEnd, pageStart, sortedRows]
  );

  useEffect(() => {
    setPageIndex(0);
  }, [breakoutFilter, pageSize, runId, sortKey, volumeConfirmedOnly]);

  const filteredReasons = useMemo(
    () => Object.entries(run?.filtered_count_by_reason ?? {}).filter(([, count]) => count > 0),
    [run?.filtered_count_by_reason]
  );
  const RootTag = embedded ? "section" : "main";
  const rootClassName = embedded
    ? "flex flex-col"
    : "flex min-h-dvh flex-1 flex-col p-2 md:h-dvh md:overflow-hidden md:p-3 lg:p-4";
  const cardClassName = embedded
    ? "viewer-frame fade-in"
    : "fade-in rounded-[30px] bg-white/95";
  const contentClassName = embedded ? "p-3 md:p-4" : "p-5 md:p-6";

  return (
    <RootTag className={rootClassName}>
      <div className="w-full space-y-6">
        <Card className={cardClassName}>
          <CardContent className={contentClassName}>
          <div className="flex flex-wrap items-start justify-between gap-3">
            <div>
              <p className="text-[11px] font-semibold uppercase tracking-[0.34em] text-[var(--primary)]">
                {t("screenerResults.kicker", "Screener Results")}
              </p>
              <h1 className="font-heading mt-2 text-2xl font-bold tracking-tight text-slate-900 md:text-[1.7rem]">
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

          <div className="mt-5 flex flex-wrap gap-2">
            {BREAKOUT_FILTER_OPTIONS.map((option) => (
              <SelectionChip
                key={option.value}
                pressed={breakoutFilter === option.value}
                onClick={() => setBreakoutFilter(option.value)}
              >
                {t(`screenerResults.filter.${option.value}`, option.value)}
              </SelectionChip>
            ))}
            <SelectionChip
              pressed={volumeConfirmedOnly}
              onClick={() => setVolumeConfirmedOnly((value) => !value)}
            >
              {t("screenerResults.filter.volume", "Volume Confirmed")}
            </SelectionChip>
          </div>

          <div className="mt-3 flex flex-wrap gap-2">
            {sortOptions.map((column) => (
              <SelectionChip
                key={column.key}
                pressed={sortKey === column.key}
                onClick={() => setSortKey(column.key)}
              >
                {column.label}
              </SelectionChip>
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
                <Badge
                  key={reason}
                  variant="secondary"
                  className="text-slate-600"
                >
                  {reason}: {count}
                </Badge>
              ))}
            </div>
          ) : null}

          <div className="mt-5 flex flex-wrap items-center justify-between gap-3 border-y border-[var(--border)] py-3">
            <div className="text-xs font-medium text-slate-600">
              {sortedRows.length > 0
                ? t(
                    "screenerResults.pagination.range",
                    ({ start, end, total }) => `${start}-${end} of ${total}`,
                    {
                      start: pageStart + 1,
                      end: pageEnd,
                      total: sortedRows.length,
                    }
                  )
                : t("screenerResults.pagination.empty", "0 results")}
            </div>
            <div className="flex flex-wrap items-center gap-2">
              <span className="text-[10px] font-semibold uppercase tracking-[0.14em] text-slate-500">
                {t("screenerResults.pagination.rows", "Rows")}
              </span>
              {PAGE_SIZE_OPTIONS.map((size) => (
                <SelectionChip
                  key={size}
                  pressed={pageSize === size}
                  onClick={() => setPageSize(size)}
                >
                  {size}
                </SelectionChip>
              ))}
              <div className="ml-1 flex items-center gap-1">
                <PaginationIconButton
                  label={t("screenerResults.pagination.previous", "Previous page")}
                  disabled={safePageIndex === 0}
                  onClick={() => setPageIndex((value) => Math.max(value - 1, 0))}
                >
                  <ChevronLeft className="h-4 w-4" aria-hidden />
                </PaginationIconButton>
                <span className="min-w-[4.5rem] text-center text-xs font-semibold text-slate-700">
                  {safePageIndex + 1} / {pageCount}
                </span>
                <PaginationIconButton
                  label={t("screenerResults.pagination.next", "Next page")}
                  disabled={safePageIndex >= pageCount - 1}
                  onClick={() =>
                    setPageIndex((value) => Math.min(value + 1, pageCount - 1))
                  }
                >
                  <ChevronRight className="h-4 w-4" aria-hidden />
                </PaginationIconButton>
              </div>
            </div>
          </div>

          <div className="mt-4 overflow-x-auto">
            <Table className="min-w-full text-xs [&_td]:px-3 [&_td]:py-2 [&_th]:h-9 [&_th]:px-3 [&_th]:tracking-[0.12em]">
              <TableHeader className="sticky top-0 bg-[var(--surface-strong)]">
                <TableRow>
                  <TableHead className="text-left">
                    {t("screenerResults.header.symbol", "symbol")}
                  </TableHead>
                  <TableHead className="text-left">
                    {t("screenerResults.header.trendSparkline", "trend")}
                  </TableHead>
                  <TableHead className="text-left">
                    {t("screenerResults.header.market", "market")}
                  </TableHead>
                  <TableHead className="text-right tabular-nums">
                    {t("screenerResults.header.global_rank", "global_rank")}
                  </TableHead>
                  <TableHead className="text-right tabular-nums">
                    {t("screenerResults.header.close", "close")}
                  </TableHead>
                  <TableHead className="text-right tabular-nums">
                    {t("screenerResults.header.ma20_gap", "ma20_gap")}
                  </TableHead>
                  <TableHead className="text-right tabular-nums">
                    {t("screenerResults.header.ma60_gap", "ma60_gap")}
                  </TableHead>
                  <TableHead className="text-right tabular-nums">
                    {t("screenerResults.header.ret_20", "ret_20")}
                  </TableHead>
                  <TableHead className="text-right tabular-nums">
                    {t("screenerResults.header.ret_60", "ret_60")}
                  </TableHead>
                  <TableHead className="text-right tabular-nums">
                    {t("screenerResults.header.rsi", "rsi")}
                  </TableHead>
                  <TableHead className="text-right tabular-nums">
                    {t("screenerResults.header.atr_pct", "atr_pct")}
                  </TableHead>
                  <TableHead className="text-right tabular-nums">
                    {t("screenerResults.header.avg_amount_20d", "avg_amount_20d")}
                  </TableHead>
                  <TableHead className="text-left">
                    {t("screenerResults.header.breakout_type", "breakout_type")}
                  </TableHead>
                  <TableHead className="text-right tabular-nums">
                    {t(
                      "screenerResults.header.breakout_volume_ratio",
                      "breakout_volume_ratio"
                    )}
                  </TableHead>
                  <TableHead className="text-left">
                    {t("screenerResults.header.strategy_tags", "strategy_tags")}
                  </TableHead>
                  <TableHead className="text-left">
                    {t("screenerResults.header.risk_flags", "risk_flags")}
                  </TableHead>
                  <TableHead className="text-left">
                    {t("screenerResults.header.matched_conditions", "matched_conditions")}
                  </TableHead>
                </TableRow>
              </TableHeader>
              <TableBody className="bg-white">
                {isLoading ? (
                  <TableRow>
                    <TableCell className="py-6 text-slate-500" colSpan={17}>
                      {t(
                        "screenerResults.loadingCandidates",
                        "Loading screener candidates..."
                      )}
                    </TableCell>
                  </TableRow>
                ) : sortedRows.length === 0 ? (
                  <TableRow>
                    <TableCell className="py-6 text-slate-500" colSpan={17}>
                      {t("screenerResults.empty", "No screener candidates available.")}
                    </TableCell>
                  </TableRow>
                ) : (
                  paginatedRows.map((row) => (
                    <TableRow
                      key={`${row.symbol}-${row.market}`}
                    >
                      <TableCell className="font-semibold text-slate-900">{row.symbol}</TableCell>
                      <TableCell>
                        <TickerSparkline
                          className="h-7 min-w-[96px]"
                          points={trendSeriesByTicker[seriesKey(row.symbol, row.market)] ?? []}
                          loading={
                            loadingTrendSeries &&
                            !trendSeriesByTicker[seriesKey(row.symbol, row.market)]
                          }
                        />
                      </TableCell>
                      <TableCell>{row.market}</TableCell>
                      <TableCell className="text-right tabular-nums">{row.global_rank}</TableCell>
                      <TableCell className="text-right tabular-nums">
                        {formatNumber(row.close, locale)}
                      </TableCell>
                      <TableCell className="text-right tabular-nums">
                        {formatMovingAverageGap(row, "ma20", locale)}
                      </TableCell>
                      <TableCell className="text-right tabular-nums">
                        {formatMovingAverageGap(row, "ma60", locale)}
                      </TableCell>
                      <TableCell className="text-right tabular-nums">
                        {formatPercent(row.ret_20, locale)}
                      </TableCell>
                      <TableCell className="text-right tabular-nums">
                        {formatPercent(row.ret_60, locale)}
                      </TableCell>
                      <TableCell className="text-right tabular-nums">
                        {formatNumber(row.rsi, locale)}
                      </TableCell>
                      <TableCell className="text-right tabular-nums">
                        {formatPercent(row.atr_pct, locale)}
                      </TableCell>
                      <TableCell className="text-right tabular-nums">
                        {formatCompactNumber(row.avg_amount_20d, locale)}
                      </TableCell>
                      <TableCell>
                        <TagStrip
                          label="Pattern"
                          value={formatBreakoutType(row.breakout_type, t)}
                          tone="bg-[rgba(93,116,112,0.12)] text-[var(--primary)]"
                          compact
                        />
                      </TableCell>
                      <TableCell className="text-right tabular-nums">
                        {formatRatio(row.breakout_volume_ratio, locale)}
                      </TableCell>
                      <TableCell>
                        <TagStrip
                          label="Strategy"
                          value={row.strategy_tags}
                          tone="bg-[rgba(28,56,83,0.08)] text-[var(--accent)]"
                          compact
                        />
                      </TableCell>
                      <TableCell>
                        <TagStrip
                          label="Risk"
                          value={row.risk_flags}
                          tone="bg-[rgba(163,53,53,0.08)] text-[var(--danger)]"
                          compact
                        />
                      </TableCell>
                      <TableCell>
                        <TagStrip
                          label="Matched"
                          value={row.matched_conditions}
                          tone="bg-[rgba(49,104,142,0.1)] text-sky-700"
                          compact
                        />
                      </TableCell>
                    </TableRow>
                  ))
                )}
              </TableBody>
            </Table>
          </div>
          </CardContent>
        </Card>
      </div>
    </RootTag>
  );
}

function matchesBreakoutFilter(row: ScreenerCandidateRow, breakoutFilter: string): boolean {
  if (breakoutFilter === "all") {
    return true;
  }
  return row.breakout_type === breakoutFilter;
}

function formatBreakoutType(
  breakoutType: string | null | undefined,
  t: ReturnType<typeof usePreferences>["t"]
): string {
  if (!breakoutType) {
    return t("screenerResults.breakout.none", "none");
  }
  switch (breakoutType) {
    case "platform_breakout":
      return t("screenerResults.breakout.platform_breakout", "Platform Breakout");
    case "box_breakout":
      return t("screenerResults.breakout.box_breakout", "Box Breakout");
    case "wedge_breakout":
      return t("screenerResults.breakout.wedge_breakout", "Wedge Breakout");
    default:
      return breakoutType;
  }
}

function SelectionChip({
  pressed,
  onClick,
  children,
}: {
  pressed: boolean;
  onClick: () => void;
  children: ReactNode;
}) {
  const tone = pressed
    ? "border-[var(--primary)] bg-[var(--primary)] text-[var(--primary-foreground)] shadow-[var(--button-primary-shadow)]"
    : "border-border bg-[var(--surface)] text-slate-700 shadow-[var(--button-secondary-shadow)] hover:bg-[color:var(--surface-hover)]";

  return (
    <button
      type="button"
      aria-pressed={pressed}
      className={`inline-flex h-7 items-center justify-center rounded-full border px-3 text-[10px] font-semibold uppercase tracking-[0.14em] transition focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[color:var(--ring-strong)] focus-visible:ring-offset-2 focus-visible:ring-offset-background ${tone}`}
      onClick={onClick}
    >
      {children}
    </button>
  );
}

function PaginationIconButton({
  label,
  disabled,
  onClick,
  children,
}: {
  label: string;
  disabled: boolean;
  onClick: () => void;
  children: ReactNode;
}) {
  return (
    <button
      type="button"
      aria-label={label}
      disabled={disabled}
      className="inline-flex h-8 w-8 items-center justify-center rounded-full border border-[var(--border)] bg-[var(--surface)] text-slate-700 shadow-[var(--button-secondary-shadow)] transition hover:bg-[color:var(--surface-hover)] disabled:cursor-not-allowed disabled:opacity-40"
      onClick={onClick}
    >
      {children}
    </button>
  );
}

function TagStrip({
  label,
  value,
  tone,
  compact = false,
}: {
  label: string;
  value: string | null | undefined;
  tone: string;
  compact?: boolean;
}) {
  const tokens = String(value ?? "")
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
    <div className={`flex flex-wrap ${compact ? "gap-1" : "gap-1.5 items-start"}`}>
      {tokens.map((token) => (
        <span
          key={`${label}-${token}`}
          className={`rounded-full px-2 py-0.5 text-[9px] font-semibold uppercase tracking-[0.12em] ${tone}`}
        >
          {token}
        </span>
      ))}
    </div>
  );
}

function numericValue(value: number | null | undefined): number | null {
  if (typeof value !== "number" || !Number.isFinite(value)) {
    return null;
  }
  return value;
}

function formatNumber(value: number | null | undefined, locale: string): string {
  const numeric = numericValue(value);
  if (numeric === null) {
    return "—";
  }

  return new Intl.NumberFormat(locale, {
    minimumFractionDigits: 0,
    maximumFractionDigits: 2,
  }).format(numeric);
}

function formatCompactNumber(value: number | null | undefined, locale: string): string {
  const numeric = numericValue(value);
  if (numeric === null) {
    return "—";
  }

  return new Intl.NumberFormat(locale, {
    notation: "compact",
    maximumFractionDigits: 2,
  }).format(numeric);
}

function formatPercent(value: number | null | undefined, locale: string): string {
  const numeric = numericValue(value);
  if (numeric === null) {
    return "—";
  }

  return new Intl.NumberFormat(locale, {
    style: "percent",
    minimumFractionDigits: 1,
    maximumFractionDigits: 1,
  }).format(numeric);
}

function formatMovingAverageGap(
  row: ScreenerCandidateRow,
  field: "ma20" | "ma60",
  locale: string
): string {
  const close = numericValue(row.close);
  const average = numericValue(row[field]);
  if (close === null || average === null || average === 0) {
    return "—";
  }
  return formatPercent(close / average - 1, locale);
}

function formatRatio(value: number | null | undefined, locale: string): string {
  const numeric = numericValue(value);
  if (numeric === null) {
    return "—";
  }

  return `${new Intl.NumberFormat(locale, {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  }).format(numeric)}x`;
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

function seriesKey(symbol: string, market: string) {
  return `${market}:${symbol}`;
}

function chunkItems<T>(items: T[], size: number): T[][] {
  const chunks: T[][] = [];
  for (let index = 0; index < items.length; index += size) {
    chunks.push(items.slice(index, index + size));
  }
  return chunks;
}
