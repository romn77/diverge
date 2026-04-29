"use client";

import { useEffect, useMemo, useState, type ReactNode } from "react";
import { usePreferences } from "@/components/PreferencesProvider";
import {
  getTickerHistory,
  type TickerHistoryPoint,
  type TickerHistorySeries,
} from "@/lib/api";
import {
  CHART_RANGE_DAYS,
  TickerFinancialChart,
  type ChartRangeKey,
} from "./TickerFinancialChart";

const SPARKLINE_WIDTH = 112;
const SPARKLINE_HEIGHT = 34;
const SPARKLINE_PADDING = 4;
const SPARKLINE_LOOKBACK_POINTS = 30;
const PRICE_PANEL_LOOKBACK_DAYS = 1000;

interface TickerPricePanelProps {
  symbol: string;
  market?: string | null;
  asOfDate?: string | null;
  title?: string;
  subtitle?: string;
  embedded?: boolean;
}

interface TickerSparklineProps {
  points: TickerHistoryPoint[];
  loading?: boolean;
  className?: string;
}

interface ChartDomain {
  min: number;
  max: number;
  step: number;
}

interface SparklineMarker {
  x: number;
  y: number;
  index: number;
}

export function TickerPricePanel({
  symbol,
  market,
  asOfDate,
  title = "Price Trend",
  subtitle = "1000-day vendor-backed history for the active ticker.",
  embedded = false,
}: TickerPricePanelProps) {
  const { locale, t } = usePreferences();
  const [history, setHistory] = useState<TickerHistorySeries | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [chartRange, setChartRange] = useState<ChartRangeKey>("1Y");

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
          days: PRICE_PANEL_LOOKBACK_DAYS,
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

  const validPoints = useMemo(
    () => filterValidPoints(history?.points ?? []),
    [history?.points]
  );
  const visiblePoints = useMemo(
    () => filterPointsForRange(validPoints, chartRange),
    [chartRange, validPoints]
  );
  const windowHigh = visiblePoints.length
    ? Math.max(...visiblePoints.map((point) => point.high ?? point.close))
    : null;
  const windowLow = visiblePoints.length
    ? Math.min(...visiblePoints.map((point) => point.low ?? point.close))
    : null;
  const dateLabel =
    visiblePoints[0]?.date && visiblePoints[visiblePoints.length - 1]?.date
      ? `${formatMetricDateCompact(visiblePoints[0].date, locale)} - ${formatMetricDateCompact(
          visiblePoints[visiblePoints.length - 1].date,
          locale
        )}`
      : t("tickerHistory.windowUnavailable", "Window unavailable");
  const rangeSummary = {
    window: dateLabel,
    high: formatPrice(windowHigh, locale),
    low: formatPrice(windowLow, locale),
  };

  return (
    <section
      className={
        embedded
          ? "bg-transparent p-0 shadow-none"
          : "ticker-price-panel rounded-[32px] border p-5 md:p-6"
      }
    >
      <div className="flex items-start gap-3">
        <div className="ticker-trend-icon grid h-12 w-12 shrink-0 place-items-center rounded-[18px] border text-[var(--primary)]">
          <TrendBadgeIcon />
        </div>
        <div className="min-w-0">
          <p className="text-[12px] font-semibold uppercase tracking-[0.26em] text-slate-700">
            {title}
          </p>
          <p className="mt-1.5 text-[13px] leading-6 text-slate-500 md:text-sm">
            {subtitle}
          </p>
        </div>
      </div>

      {error ? (
        <div className="mt-5 rounded-[24px] border border-rose-200 bg-rose-50 px-4 py-4 text-sm text-rose-700">
          {error}
        </div>
      ) : isLoading ? (
        <div className="mt-5 rounded-[26px] border border-dashed border-[var(--border)] bg-[var(--surface-strong)] px-4 py-10 text-sm text-slate-500">
          {t("tickerHistory.loading", "Loading price history...")}
        </div>
      ) : validPoints.length === 0 ? (
        <div className="mt-5 rounded-[26px] border border-dashed border-[var(--border)] bg-[var(--surface-strong)] px-4 py-10 text-sm text-slate-500">
          {t("tickerHistory.empty", "No price history is available for this ticker yet.")}
        </div>
      ) : (
        <>
          <ChartShell embedded={embedded}>
            <TickerFinancialChart
              points={validPoints}
              locale={locale}
              range={chartRange}
              onRangeChange={setChartRange}
            />
          </ChartShell>

          <TickerRangeSummaryBar
            windowLabel={t("tickerHistory.window", "")}
            highLabel={t("tickerHistory.windowHigh", "High")}
            lowLabel={t("tickerHistory.windowLow", "Low")}
            summary={rangeSummary}
          />
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
  const validPoints = filterValidPoints(points).slice(-SPARKLINE_LOOKBACK_POINTS);
  const sparklineDomain = buildSparklineDomain(validPoints);
  const sparklinePath = buildLinePath(
    validPoints,
    SPARKLINE_WIDTH,
    SPARKLINE_HEIGHT,
    SPARKLINE_PADDING,
    SPARKLINE_PADDING,
    SPARKLINE_PADDING,
    SPARKLINE_PADDING,
    sparklineDomain
  );
  const markers = buildSparklineMarkers(validPoints, sparklineDomain);
  const trendUp =
    validPoints.length >= 2 &&
    validPoints[validPoints.length - 1].close >= validPoints[0].close;
  const lineColor = trendUp ? "rgb(18 106 70)" : "rgb(161 68 68)";

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
        stroke={lineColor}
        strokeWidth="2"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
      {markers.extremes.map((marker) => (
        <circle
          key={`${marker.kind}-${marker.index}`}
          cx={marker.x}
          cy={marker.y}
          r="2"
          fill="var(--surface-strong)"
          stroke={marker.kind === "high" ? "rgb(18 106 70)" : "rgb(161 68 68)"}
          strokeWidth="1.4"
        />
      ))}
      {markers.latest ? (
        <circle
          cx={markers.latest.x}
          cy={markers.latest.y}
          r="2.8"
          fill={lineColor}
          stroke="var(--surface-strong)"
          strokeWidth="1.6"
        />
      ) : null}
    </svg>
  );
}

function ChartShell({
  children,
  embedded = false,
}: {
  children: ReactNode;
  embedded?: boolean;
}) {
  return (
    <div
      className={
        embedded
          ? "mt-4"
          : "ticker-chart-shell mt-5 rounded-[28px] border px-3 py-3 md:px-4 md:py-4"
      }
    >
      {children}
    </div>
  );
}

function TickerRangeSummaryBar({
  windowLabel,
  highLabel,
  lowLabel,
  summary,
}: {
  windowLabel: string;
  highLabel: string;
  lowLabel: string;
  summary: {
    window: string;
    high: string;
    low: string;
  };
}) {
  return (
    <div className="ticker-range-summary mt-3 rounded-[16px] border px-3 py-2.5 text-sm">
      <div className="flex min-w-0 flex-wrap items-center gap-x-4 gap-y-2">
        <TickerRangeSummaryItem label={windowLabel} value={summary.window} isPrimary />
        <TickerRangeSummaryItem label={highLabel} value={summary.high} />
        <TickerRangeSummaryItem label={lowLabel} value={summary.low} />
      </div>
    </div>
  );
}

function TickerRangeSummaryItem({
  label,
  value,
  isPrimary = false,
}: {
  label: string;
  value: string;
  isPrimary?: boolean;
}) {
  return (
    <span
      className={
        isPrimary
          ? "min-w-0 flex-[1_1_14rem] text-slate-700"
          : "inline-flex shrink-0 items-baseline gap-1.5 text-slate-700"
      }
    >
      <span className="text-[10px] font-semibold uppercase tracking-[0.18em] text-slate-500">
        {label}
      </span>
      <span className="font-semibold text-slate-900">{value}</span>
    </span>
  );
}

function TrendBadgeIcon() {
  return (
    <svg viewBox="0 0 24 24" className="h-6 w-6" fill="none" aria-hidden>
      <path
        d="M4 17h16"
        stroke="currentColor"
        strokeWidth="1.8"
        strokeLinecap="round"
      />
      <path
        d="m6 14 4-4 3 3 5-6"
        stroke="currentColor"
        strokeWidth="1.8"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
      <path
        d="M18 7h2v2"
        stroke="currentColor"
        strokeWidth="1.8"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </svg>
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

function filterPointsForRange(
  points: Array<TickerHistoryPoint & { close: number }>,
  range: ChartRangeKey
): Array<TickerHistoryPoint & { close: number }> {
  if (range === "All" || points.length < 2) {
    return points;
  }

  const latest = parseIsoDate(points[points.length - 1].date);
  if (!latest) {
    return points;
  }

  const threshold = new Date(latest);
  threshold.setUTCDate(threshold.getUTCDate() - CHART_RANGE_DAYS[range]);

  return points.filter((point) => {
    const parsed = parseIsoDate(point.date);
    return parsed ? parsed >= threshold : false;
  });
}

function buildSparklineDomain(points: Array<TickerHistoryPoint & { close: number }>): ChartDomain {
  if (points.length === 0) {
    return { min: 0, max: 1, step: 1 };
  }

  const closes = points.map((point) => point.close);
  const rawMin = Math.min(...closes);
  const rawMax = Math.max(...closes);
  const range = rawMax - rawMin || Math.max(Math.abs(rawMax) * 0.12, 1);
  const paddedMin = rawMin - range * 0.14;
  const paddedMax = rawMax + range * 0.14;

  return {
    min: paddedMin,
    max: paddedMax,
    step: (paddedMax - paddedMin) / 4,
  };
}

function buildLinePath(
  points: Array<TickerHistoryPoint & { close: number }>,
  width: number,
  height: number,
  paddingLeft: number,
  paddingRight: number,
  paddingTop: number,
  paddingBottom: number,
  domain: ChartDomain
): string {
  if (points.length === 0) {
    return "";
  }

  if (points.length === 1) {
    const midY = height / 2;
    return `M ${paddingLeft} ${midY} L ${width - paddingRight} ${midY}`;
  }

  const usableWidth = width - paddingLeft - paddingRight;
  const usableHeight = height - paddingTop - paddingBottom;

  return points
    .map((point, index) => {
      const x = paddingLeft + (usableWidth * index) / (points.length - 1);
      const y =
        height -
        paddingBottom -
        ((point.close - domain.min) / (domain.max - domain.min || 1)) * usableHeight;
      return `${index === 0 ? "M" : "L"} ${x.toFixed(2)} ${y.toFixed(2)}`;
    })
    .join(" ");
}

function buildSparklineMarkers(
  points: Array<TickerHistoryPoint & { close: number }>,
  domain: ChartDomain
): {
  latest: SparklineMarker | null;
  extremes: Array<SparklineMarker & { kind: "high" | "low" }>;
} {
  if (points.length === 0) {
    return { latest: null, extremes: [] };
  }

  const latest = toSparklineMarker(points, points.length - 1, domain);
  const lowIndex = findCloseExtremeIndex(points, "low");
  const highIndex = findCloseExtremeIndex(points, "high");
  const extremes: Array<SparklineMarker & { kind: "high" | "low" }> = [];

  if (lowIndex !== null && lowIndex !== latest.index) {
    extremes.push({ ...toSparklineMarker(points, lowIndex, domain), kind: "low" });
  }
  if (highIndex !== null && highIndex !== latest.index && highIndex !== lowIndex) {
    extremes.push({ ...toSparklineMarker(points, highIndex, domain), kind: "high" });
  }

  return { latest, extremes };
}

function findCloseExtremeIndex(
  points: Array<TickerHistoryPoint & { close: number }>,
  kind: "high" | "low"
): number | null {
  if (points.length === 0) {
    return null;
  }

  return points.reduce((selectedIndex, point, index) => {
    const selected = points[selectedIndex];
    return kind === "high"
      ? point.close > selected.close
        ? index
        : selectedIndex
      : point.close < selected.close
        ? index
        : selectedIndex;
  }, 0);
}

function toSparklineMarker(
  points: Array<TickerHistoryPoint & { close: number }>,
  index: number,
  domain: ChartDomain
): SparklineMarker {
  const point = points[index];
  const usableWidth = SPARKLINE_WIDTH - SPARKLINE_PADDING * 2;
  const usableHeight = SPARKLINE_HEIGHT - SPARKLINE_PADDING * 2;
  const x =
    points.length === 1
      ? SPARKLINE_WIDTH - SPARKLINE_PADDING
      : SPARKLINE_PADDING + (usableWidth * index) / (points.length - 1);
  const y =
    SPARKLINE_HEIGHT -
    SPARKLINE_PADDING -
    ((point.close - domain.min) / (domain.max - domain.min || 1)) * usableHeight;

  return {
    x,
    y,
    index,
  };
}

function formatPrice(value: number | null, locale: string): string {
  if (typeof value !== "number") {
    return "—";
  }

  return new Intl.NumberFormat(locale, {
    maximumFractionDigits: 2,
  }).format(value);
}

function formatMetricDateCompact(value: string, locale: string): string {
  const parsed = new Date(`${value}T00:00:00`);
  if (Number.isNaN(parsed.getTime())) {
    return value;
  }

  return new Intl.DateTimeFormat(locale, {
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
  }).format(parsed);
}

function parseIsoDate(value: string): Date | null {
  const parsed = new Date(`${value}T00:00:00`);
  return Number.isNaN(parsed.getTime()) ? null : parsed;
}
