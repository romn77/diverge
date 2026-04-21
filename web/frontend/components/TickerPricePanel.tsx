"use client";

import { useEffect, useMemo, useState } from "react";
import { usePreferences } from "@/components/PreferencesProvider";
import {
  getTickerHistory,
  type TickerHistoryPoint,
  type TickerHistorySeries,
} from "@/lib/api";

const CHART_WIDTH = 720;
const CHART_HEIGHT = 220;
const CHART_PADDING_X = 18;
const CHART_PADDING_Y = 16;
const SPARKLINE_WIDTH = 112;
const SPARKLINE_HEIGHT = 34;

interface TickerPricePanelProps {
  symbol: string;
  market?: string | null;
  asOfDate?: string | null;
  title?: string;
  subtitle?: string;
}

interface TickerSparklineProps {
  points: TickerHistoryPoint[];
  loading?: boolean;
  className?: string;
}

export function TickerPricePanel({
  symbol,
  market,
  asOfDate,
  title = "Price Trend",
  subtitle = "400-day vendor-backed history for the active ticker.",
}: TickerPricePanelProps) {
  const { locale, t } = usePreferences();
  const [history, setHistory] = useState<TickerHistorySeries | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let isActive = true;

    const load = async () => {
      setIsLoading(true);
      setError(null);

      try {
        const nextHistory = await getTickerHistory({
          symbol,
          market,
          asOfDate,
        });
        if (!isActive) {
          return;
        }
        setHistory(nextHistory);
      } catch (nextError) {
        if (!isActive) {
          return;
        }
        setHistory(null);
        setError(
          nextError instanceof Error
            ? nextError.message
            : t("tickerHistory.error", "Unable to load price history")
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
  }, [asOfDate, market, symbol, t]);

  const validPoints = useMemo(() => filterValidPoints(history?.points ?? []), [history?.points]);
  const latestClose = validPoints[validPoints.length - 1]?.close ?? null;
  const earliestClose = validPoints[0]?.close ?? null;
  const changePercent =
    latestClose !== null && earliestClose !== null && earliestClose !== 0
      ? ((latestClose - earliestClose) / earliestClose) * 100
      : null;
  const dateLabel = history?.start_date && history?.end_date
    ? `${formatShortDate(history.start_date, locale)} - ${formatShortDate(
        history.end_date,
        locale
      )}`
    : t("tickerHistory.windowUnavailable", "Window unavailable");

  return (
    <section className="rounded-[28px] border border-[var(--border)] bg-white/90 p-5 shadow-[0_18px_36px_rgba(18,28,41,0.05)]">
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <p className="text-xs font-semibold uppercase tracking-[0.26em] text-slate-500">
            {title}
          </p>
          <h3 className="mt-2 text-xl font-semibold text-slate-900">
            {symbol}
            {history?.market ? ` · ${history.market.toUpperCase()}` : ""}
          </h3>
          <p className="mt-2 text-sm leading-6 text-slate-500">{subtitle}</p>
        </div>

        <div className="rounded-[22px] border border-[var(--border)] bg-[var(--surface-strong)] px-4 py-3 text-right">
          <p className="text-[10px] font-semibold uppercase tracking-[0.22em] text-slate-500">
            {t("tickerHistory.window", "Window")}
          </p>
          <p className="mt-2 text-sm font-semibold text-slate-800">{dateLabel}</p>
        </div>
      </div>

      {error ? (
        <div className="mt-5 rounded-[22px] border border-rose-200 bg-rose-50 px-4 py-4 text-sm text-rose-700">
          {error}
        </div>
      ) : isLoading ? (
        <div className="mt-5 rounded-[22px] border border-dashed border-[var(--border)] bg-[var(--surface-strong)] px-4 py-8 text-sm text-slate-500">
          {t("tickerHistory.loading", "Loading price history...")}
        </div>
      ) : validPoints.length === 0 ? (
        <div className="mt-5 rounded-[22px] border border-dashed border-[var(--border)] bg-[var(--surface-strong)] px-4 py-8 text-sm text-slate-500">
          {t("tickerHistory.empty", "No price history is available for this ticker yet.")}
        </div>
      ) : (
        <>
          <div className="mt-5 grid gap-3 md:grid-cols-3">
            <HistoryMetric
              label={t("tickerHistory.lastClose", "Last Close")}
              value={formatPrice(latestClose, locale)}
            />
            <HistoryMetric
              label={t("tickerHistory.periodReturn", "Window Change")}
              value={formatPercent(changePercent, locale)}
            />
            <HistoryMetric
              label={t("tickerHistory.points", "Data Points")}
              value={String(validPoints.length)}
            />
          </div>

          <div className="mt-5 rounded-[24px] border border-[var(--border)] bg-[var(--surface-strong)] px-3 py-3">
            <PriceLineChart points={validPoints} />
          </div>
        </>
      )}
    </section>
  );
}

export function TickerSparkline({
  points,
  loading = false,
  className = "",
}: TickerSparklineProps) {
  const validPoints = filterValidPoints(points);
  const sparklinePath = buildLinePath(
    validPoints,
    SPARKLINE_WIDTH,
    SPARKLINE_HEIGHT,
    4,
    4
  );
  const trendUp =
    validPoints.length >= 2 &&
    validPoints[validPoints.length - 1].close >= validPoints[0].close;

  if (loading) {
    return (
      <div
        className={`h-[34px] min-w-[112px] rounded-[14px] border border-[var(--border)] bg-[var(--surface-strong)]/80 ${className}`}
      />
    );
  }

  if (validPoints.length === 0 || !sparklinePath) {
    return (
      <div
        className={`flex h-[34px] min-w-[112px] items-center justify-center rounded-[14px] border border-[var(--border)] bg-[var(--surface-strong)]/80 text-[11px] text-slate-400 ${className}`}
      >
        —
      </div>
    );
  }

  return (
    <svg
      viewBox={`0 0 ${SPARKLINE_WIDTH} ${SPARKLINE_HEIGHT}`}
      className={`h-[34px] min-w-[112px] rounded-[14px] border border-[var(--border)] bg-[var(--surface-strong)]/80 px-1 py-1 ${className}`}
      aria-hidden
    >
      <path
        d={sparklinePath}
        fill="none"
        stroke={trendUp ? "rgb(18 106 70)" : "rgb(161 68 68)"}
        strokeWidth="2"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </svg>
  );
}

function PriceLineChart({ points }: { points: TickerHistoryPoint[] }) {
  const path = buildLinePath(
    points,
    CHART_WIDTH,
    CHART_HEIGHT,
    CHART_PADDING_X,
    CHART_PADDING_Y
  );

  return (
    <svg
      viewBox={`0 0 ${CHART_WIDTH} ${CHART_HEIGHT}`}
      className="h-56 w-full"
      aria-hidden
    >
      <rect
        x="0"
        y="0"
        width={CHART_WIDTH}
        height={CHART_HEIGHT}
        rx="18"
        fill="rgba(255,255,255,0.72)"
      />
      <path
        d={path}
        fill="none"
        stroke="rgb(28 56 83)"
        strokeWidth="3"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </svg>
  );
}

function HistoryMetric({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-[20px] border border-[var(--border)] bg-[var(--surface-strong)] px-4 py-4">
      <p className="text-[10px] font-semibold uppercase tracking-[0.22em] text-slate-500">
        {label}
      </p>
      <p className="mt-2 text-lg font-semibold text-slate-900">{value}</p>
    </div>
  );
}

function filterValidPoints(
  points: TickerHistoryPoint[]
): Array<TickerHistoryPoint & { close: number }> {
  return points.filter(hasNumericClose);
}

function hasNumericClose(
  point: TickerHistoryPoint
): point is TickerHistoryPoint & { close: number } {
  return typeof point.close === "number";
}

function buildLinePath(
  points: TickerHistoryPoint[],
  width: number,
  height: number,
  paddingX: number,
  paddingY: number
): string {
  if (points.length === 0) {
    return "";
  }

  if (points.length === 1) {
    const midY = height / 2;
    return `M ${paddingX} ${midY} L ${width - paddingX} ${midY}`;
  }

  const closes = points.map((point) => Number(point.close));
  const minClose = Math.min(...closes);
  const maxClose = Math.max(...closes);
  const range = maxClose - minClose || 1;
  const usableWidth = width - paddingX * 2;
  const usableHeight = height - paddingY * 2;

  return points
    .map((point, index) => {
      const x = paddingX + (usableWidth * index) / (points.length - 1);
      const close = Number(point.close);
      const y =
        height - paddingY - ((close - minClose) / range) * usableHeight;
      return `${index === 0 ? "M" : "L"} ${x.toFixed(2)} ${y.toFixed(2)}`;
    })
    .join(" ");
}

function formatPrice(value: number | null, locale: string): string {
  if (typeof value !== "number") {
    return "—";
  }

  return new Intl.NumberFormat(locale, {
    maximumFractionDigits: 2,
  }).format(value);
}

function formatPercent(value: number | null, locale: string): string {
  if (typeof value !== "number") {
    return "—";
  }

  return `${new Intl.NumberFormat(locale, {
    maximumFractionDigits: 2,
    signDisplay: "always",
  }).format(value)}%`;
}

function formatShortDate(value: string, locale: string): string {
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
