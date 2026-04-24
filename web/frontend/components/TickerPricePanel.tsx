"use client";

import { useEffect, useMemo, useState, type ReactNode } from "react";
import { usePreferences } from "@/components/PreferencesProvider";
import {
  getTickerHistory,
  type TickerHistoryPoint,
  type TickerHistorySeries,
} from "@/lib/api";

const CHART_WIDTH = 1240;
const CHART_HEIGHT = 460;
const CHART_PADDING_LEFT = 30;
const CHART_PADDING_RIGHT = 76;
const CHART_PADDING_TOP = 28;
const CHART_PADDING_BOTTOM = 54;
const SPARKLINE_WIDTH = 112;
const SPARKLINE_HEIGHT = 34;

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

interface TradingMetricCard {
  icon: "calendar" | "trend" | "high" | "low";
  label: string;
  value: string;
}

interface ChartDomain {
  min: number;
  max: number;
  step: number;
}

export function TickerPricePanel({
  symbol,
  market,
  asOfDate,
  title = "Price Trend",
  subtitle = "400-day vendor-backed history for the active ticker.",
  embedded = false,
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

  const validPoints = useMemo(
    () => filterValidPoints(history?.points ?? []),
    [history?.points]
  );
  const earliestClose = validPoints[0]?.close ?? null;
  const latestClose = validPoints[validPoints.length - 1]?.close ?? null;
  const changePercent =
    latestClose !== null && earliestClose !== null && earliestClose !== 0
      ? ((latestClose - earliestClose) / earliestClose) * 100
      : null;
  const windowHigh = validPoints.length
    ? Math.max(...validPoints.map((point) => point.high ?? point.close))
    : null;
  const windowLow = validPoints.length
    ? Math.min(...validPoints.map((point) => point.low ?? point.close))
    : null;
  const dateLabel =
    history?.start_date && history?.end_date
      ? `${formatMetricDateCompact(history.start_date, locale)} - ${formatMetricDateCompact(
          history.end_date,
          locale
        )}`
      : t("tickerHistory.windowUnavailable", "Window unavailable");

  const metricCards: TradingMetricCard[] = [
    {
      icon: "calendar",
      label: t("tickerHistory.window", "Window"),
      value: dateLabel,
    },
    {
      icon: "trend",
      label: t("tickerHistory.periodReturn", "Window Change"),
      value: formatPercent(changePercent, locale),
    },
    {
      icon: "high",
      label: t("tickerHistory.windowHigh", "Window High"),
      value: formatPrice(windowHigh, locale),
    },
    {
      icon: "low",
      label: t("tickerHistory.windowLow", "Window Low"),
      value: formatPrice(windowLow, locale),
    },
  ];

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
            <PriceLineChart points={validPoints} locale={locale} />
          </ChartShell>

          {embedded ? (
            <TradingMetricStrip metricCards={metricCards} />
          ) : (
            <div className="mt-4 grid gap-3 md:grid-cols-2 xl:grid-cols-4">
              {metricCards.map((metric) => (
                <TradingMetricTile
                  key={metric.label}
                  icon={metric.icon}
                  label={metric.label}
                  value={metric.value}
                />
              ))}
            </div>
          )}
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
    4,
    4,
    4,
    buildChartDomain(validPoints)
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

function PriceLineChart({
  points,
  locale,
}: {
  points: Array<TickerHistoryPoint & { close: number }>;
  locale: string;
}) {
  const domain = buildChartDomain(points);
  const path = buildLinePath(
    points,
    CHART_WIDTH,
    CHART_HEIGHT,
    CHART_PADDING_LEFT,
    CHART_PADDING_RIGHT,
    CHART_PADDING_TOP,
    CHART_PADDING_BOTTOM,
    domain
  );
  const yAxisTicks = buildYAxisTicks(domain, CHART_HEIGHT, CHART_PADDING_TOP, CHART_PADDING_BOTTOM);
  const monthTicks = buildMonthTicks(
    points,
    CHART_WIDTH,
    CHART_PADDING_LEFT,
    CHART_PADDING_RIGHT,
    locale
  );
  const plotLeft = CHART_PADDING_LEFT;
  const plotRight = CHART_WIDTH - CHART_PADDING_RIGHT;
  const plotBottom = CHART_HEIGHT - CHART_PADDING_BOTTOM;

  return (
    <svg
      viewBox={`0 0 ${CHART_WIDTH} ${CHART_HEIGHT}`}
      className="h-[20rem] w-full md:h-[22rem]"
      aria-hidden
    >
      <rect
        x="0"
        y="0"
        width={CHART_WIDTH}
        height={CHART_HEIGHT}
        rx="24"
        fill="var(--chart-svg-bg)"
      />

      {yAxisTicks.map((tick) => (
        <line
          key={`y-${tick.value}`}
          x1={plotLeft}
          y1={tick.y}
          x2={plotRight}
          y2={tick.y}
          stroke="var(--chart-grid)"
          strokeDasharray="10 10"
          strokeWidth="1.2"
        />
      ))}

      {monthTicks.map((tick) => (
        <line
          key={`x-${tick.label}`}
          x1={tick.x}
          y1={CHART_PADDING_TOP}
          x2={tick.x}
          y2={plotBottom}
          stroke="var(--chart-grid-soft)"
          strokeWidth="1"
        />
      ))}

      <path
        d={path}
        fill="none"
        stroke="var(--chart-line)"
        strokeWidth="4"
        strokeLinecap="round"
        strokeLinejoin="round"
      />

      <line
        x1={plotLeft}
        y1={plotBottom}
        x2={plotRight}
        y2={plotBottom}
        stroke="var(--chart-axis)"
        strokeWidth="1.2"
      />

      {yAxisTicks.map((tick) => (
        <text
          key={`y-label-${tick.value}`}
          x={CHART_WIDTH - CHART_PADDING_RIGHT + 18}
          y={tick.y + 5}
          fill="var(--chart-label)"
          fontSize="16"
          fontWeight="600"
        >
          {formatAxisPrice(tick.value, locale)}
        </text>
      ))}

      {monthTicks.map((tick) => (
        <text
          key={`x-label-${tick.label}`}
          x={tick.x}
          y={CHART_HEIGHT - 14}
          textAnchor="middle"
          fill="var(--chart-label)"
          fontSize="16"
          fontWeight="600"
        >
          {tick.label}
        </text>
      ))}
    </svg>
  );
}

function TradingMetricTile({
  icon,
  label,
  value,
}: {
  icon: TradingMetricCard["icon"];
  label: string;
  value: string;
}) {
  return (
    <div className="ticker-metric-card rounded-[20px] border px-3 py-3">
      <div className="flex items-center gap-2">
        <div className="grid h-7 w-7 shrink-0 place-items-center rounded-full bg-[var(--primary-soft)] text-[var(--primary)]">
          <MetricIcon icon={icon} />
        </div>
        <div className="min-w-0 flex-1">
          <p className="text-[9px] font-semibold uppercase tracking-[0.2em] text-slate-600">
            {label}
          </p>
          <div className="mt-1 h-px w-full bg-[var(--border)]" />
        </div>
      </div>
      <p className="mt-2 break-words text-[0.95rem] font-semibold leading-snug tracking-tight text-slate-900 md:text-[1.05rem] md:whitespace-nowrap">
        {value}
      </p>
    </div>
  );
}

function TradingMetricStrip({
  metricCards,
}: {
  metricCards: TradingMetricCard[];
}) {
  return (
    <div className="ticker-metric-strip mt-4 overflow-hidden rounded-[18px] border">
      <div className="grid md:grid-cols-2 xl:grid-cols-4">
        {metricCards.map((metric) => (
          <div
            key={metric.label}
            className="flex items-center gap-2.5 border-b border-[var(--border)] px-3 py-2.5 last:border-b-0 xl:border-b-0 xl:border-l xl:first:border-l-0"
          >
            <div className="grid h-7 w-7 shrink-0 place-items-center rounded-full bg-[var(--primary-soft)] text-[var(--primary)]">
              <MetricIcon icon={metric.icon} />
            </div>
            <div className="min-w-0">
              <p className="text-[9px] font-semibold uppercase tracking-[0.2em] text-slate-600">
                {metric.label}
              </p>
              <p className="mt-1 truncate text-[0.95rem] font-semibold leading-tight text-slate-900 md:text-[1rem]">
                {metric.value}
              </p>
            </div>
          </div>
        ))}
      </div>
    </div>
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

function MetricIcon({ icon }: { icon: TradingMetricCard["icon"] }) {
  switch (icon) {
    case "calendar":
      return (
        <svg viewBox="0 0 24 24" className="h-5 w-5" fill="none" aria-hidden>
          <rect
            x="4.5"
            y="6"
            width="15"
            height="13.5"
            rx="2.5"
            stroke="currentColor"
            strokeWidth="1.8"
          />
          <path
            d="M8 4.5v3M16 4.5v3M4.5 10h15"
            stroke="currentColor"
            strokeWidth="1.8"
            strokeLinecap="round"
          />
        </svg>
      );
    case "trend":
      return (
        <svg viewBox="0 0 24 24" className="h-5 w-5" fill="none" aria-hidden>
          <path
            d="m5 15 4-4 3 3 5-6"
            stroke="currentColor"
            strokeWidth="1.8"
            strokeLinecap="round"
            strokeLinejoin="round"
          />
          <path
            d="M17 8h2v2"
            stroke="currentColor"
            strokeWidth="1.8"
            strokeLinecap="round"
            strokeLinejoin="round"
          />
        </svg>
      );
    case "high":
      return (
        <svg viewBox="0 0 24 24" className="h-5 w-5" fill="none" aria-hidden>
          <path
            d="m6 15 6-6 6 6"
            stroke="currentColor"
            strokeWidth="1.8"
            strokeLinecap="round"
            strokeLinejoin="round"
          />
        </svg>
      );
    case "low":
      return (
        <svg viewBox="0 0 24 24" className="h-5 w-5" fill="none" aria-hidden>
          <path
            d="m6 9 6 6 6-6"
            stroke="currentColor"
            strokeWidth="1.8"
            strokeLinecap="round"
            strokeLinejoin="round"
          />
        </svg>
      );
  }
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

function buildChartDomain(points: Array<TickerHistoryPoint & { close: number }>): ChartDomain {
  if (points.length === 0) {
    return { min: 0, max: 1, step: 1 };
  }

  const lows = points.map((point) => point.low ?? point.close);
  const highs = points.map((point) => point.high ?? point.close);
  const rawMin = Math.min(...lows);
  const rawMax = Math.max(...highs);
  const range = rawMax - rawMin || Math.max(Math.abs(rawMax) * 0.12, 1);
  const paddedMin = rawMin - range * 0.08;
  const paddedMax = rawMax + range * 0.08;
  const step = getNiceStep((paddedMax - paddedMin) / 4);

  return {
    min: Math.floor(paddedMin / step) * step,
    max: Math.ceil(paddedMax / step) * step,
    step,
  };
}

function getNiceStep(roughStep: number): number {
  const safeStep = roughStep > 0 ? roughStep : 1;
  const power = 10 ** Math.floor(Math.log10(safeStep));
  const scaled = safeStep / power;

  if (scaled <= 1) {
    return power;
  }
  if (scaled <= 2) {
    return 2 * power;
  }
  if (scaled <= 5) {
    return 5 * power;
  }
  return 10 * power;
}

function buildYAxisTicks(
  domain: ChartDomain,
  height: number,
  paddingTop: number,
  paddingBottom: number
) {
  const ticks: Array<{ value: number; y: number }> = [];
  const usableHeight = height - paddingTop - paddingBottom;

  for (let value = domain.min; value <= domain.max + domain.step * 0.5; value += domain.step) {
    const ratio = (value - domain.min) / (domain.max - domain.min || 1);
    const y = height - paddingBottom - ratio * usableHeight;
    ticks.push({ value, y });
  }

  return ticks;
}

function buildMonthTicks(
  points: Array<TickerHistoryPoint & { close: number }>,
  width: number,
  paddingLeft: number,
  paddingRight: number,
  locale: string
) {
  const uniqueMonths: Array<{ index: number; date: Date }> = [];
  const seen = new Set<string>();
  const usableWidth = width - paddingLeft - paddingRight;

  points.forEach((point, index) => {
    const parsed = parseIsoDate(point.date);
    if (!parsed) {
      return;
    }
    const key = `${parsed.getUTCFullYear()}-${parsed.getUTCMonth()}`;
    if (seen.has(key)) {
      return;
    }
    seen.add(key);
    uniqueMonths.push({ index, date: parsed });
  });

  if (uniqueMonths.length === 0) {
    return [];
  }

  const maxLabels = 8;
  const interval = Math.max(1, Math.ceil(uniqueMonths.length / maxLabels));
  const sampled = uniqueMonths.filter((_, index) => index % interval === 0);
  const last = uniqueMonths[uniqueMonths.length - 1];
  if (!sampled.some((tick) => tick.index === last.index)) {
    sampled.push(last);
  }

  return sampled.map((tick) => ({
    x: paddingLeft + (usableWidth * tick.index) / Math.max(points.length - 1, 1),
    label: formatMonthTick(tick.date, locale),
  }));
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

function formatPrice(value: number | null, locale: string): string {
  if (typeof value !== "number") {
    return "—";
  }

  return new Intl.NumberFormat(locale, {
    maximumFractionDigits: 2,
  }).format(value);
}

function formatAxisPrice(value: number, locale: string): string {
  return new Intl.NumberFormat(locale, {
    maximumFractionDigits: 0,
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

function formatMonthTick(value: Date, locale: string): string {
  const formatted = new Intl.DateTimeFormat(locale, {
    month: "short",
    year: "2-digit",
    timeZone: "UTC",
  }).format(value);

  const parts = formatted.split(" ");
  if (parts.length === 2 && /^[A-Za-z]{3,}$/.test(parts[0])) {
    return `${parts[0]} '${parts[1]}`;
  }
  return formatted;
}

function parseIsoDate(value: string): Date | null {
  const parsed = new Date(`${value}T00:00:00Z`);
  return Number.isNaN(parsed.getTime()) ? null : parsed;
}
