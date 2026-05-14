"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import {
  AreaSeries,
  ColorType,
  CrosshairMode,
  createChart,
  type AreaData,
  type IChartApi,
  type ISeriesApi,
  type MouseEventHandler,
  type Time,
} from "lightweight-charts";
import { type TickerHistoryPoint } from "@/lib/api";

type ChartPoint = TickerHistoryPoint & { close: number };
export type ChartRangeKey = "1M" | "3M" | "6M" | "1Y" | "All";

interface TickerFinancialChartProps {
  points: ChartPoint[];
  locale: string;
  range: ChartRangeKey;
  onRangeChange: (range: ChartRangeKey) => void;
}

interface HoverPoint {
  date: string;
  close: number;
  changePercent: number | null;
  x: number;
}

const RANGE_OPTIONS: ChartRangeKey[] = ["1M", "3M", "6M", "1Y", "All"];
export const CHART_RANGE_DAYS: Record<Exclude<ChartRangeKey, "All">, number> = {
  "1M": 31,
  "3M": 92,
  "6M": 183,
  "1Y": 366,
};

export function TickerFinancialChart({
  points,
  locale,
  range,
  onRangeChange,
}: TickerFinancialChartProps) {
  const containerRef = useRef<HTMLDivElement | null>(null);
  const chartRef = useRef<IChartApi | null>(null);
  const seriesRef = useRef<ISeriesApi<"Area"> | null>(null);
  const pointByDate = useMemo(() => buildPointLookup(points), [points]);
  const data = useMemo<AreaData[]>(
    () =>
      points.map((point) => ({
        time: point.date,
        value: point.close,
      })),
    [points]
  );
  const [hoverPoint, setHoverPoint] = useState<HoverPoint | null>(null);
  const latestPoint = points[points.length - 1] ?? null;
  const firstClose = points[0]?.close ?? null;
  const activePoint = hoverPoint ?? (latestPoint ? buildStaticHoverPoint(latestPoint, firstClose) : null);

  useEffect(() => {
    const container = containerRef.current;
    if (!container || data.length === 0) {
      return;
    }

    const tokens = resolveChartTokens(container);
    const chart = createChart(container, {
      autoSize: true,
      height: 320,
      layout: {
        background: { type: ColorType.Solid, color: tokens.background },
        textColor: tokens.label,
        fontSize: 12,
        fontFamily: "var(--font-sans), system-ui, sans-serif",
        attributionLogo: true,
      },
      grid: {
        vertLines: { color: tokens.gridSoft },
        horzLines: { color: tokens.grid },
      },
      rightPriceScale: {
        borderColor: tokens.axis,
        scaleMargins: {
          top: 0.12,
          bottom: 0.12,
        },
      },
      timeScale: {
        borderColor: tokens.axis,
        timeVisible: false,
        secondsVisible: false,
        rightOffset: 8,
        barSpacing: 8,
      },
      crosshair: {
        mode: CrosshairMode.Normal,
        vertLine: {
          color: tokens.crosshair,
          labelBackgroundColor: tokens.line,
        },
        horzLine: {
          color: tokens.crosshair,
          labelBackgroundColor: tokens.line,
        },
      },
      handleScroll: {
        mouseWheel: true,
        pressedMouseMove: true,
        horzTouchDrag: true,
        vertTouchDrag: false,
      },
      handleScale: {
        mouseWheel: true,
        pinch: true,
        axisPressedMouseMove: true,
        axisDoubleClickReset: true,
      },
      localization: {
        priceFormatter: (price: number) => formatPrice(price, locale),
      },
    });

    const series = chart.addSeries(AreaSeries, {
      lineColor: tokens.line,
      topColor: withAlpha(tokens.line, 0.28),
      bottomColor: withAlpha(tokens.line, 0.02),
      lineWidth: 2,
      lastValueVisible: true,
      priceLineVisible: true,
      priceLineColor: withAlpha(tokens.line, 0.35),
    });

    series.setData(data);
    chart.timeScale().fitContent();
    chartRef.current = chart;
    seriesRef.current = series;

    const onCrosshairMove: MouseEventHandler<Time> = (param) => {
      if (!param.point || param.time === undefined) {
        setHoverPoint(null);
        return;
      }

      const date = String(param.time);
      const point = pointByDate.get(date);
      if (!point) {
        setHoverPoint(null);
        return;
      }

      setHoverPoint({
        date,
        close: point.close,
        changePercent: calculateChangePercent(point.close, firstClose),
        x: param.point.x,
      });
    };

    chart.subscribeCrosshairMove(onCrosshairMove);

    return () => {
      chart.unsubscribeCrosshairMove(onCrosshairMove);
      chart.remove();
      chartRef.current = null;
      seriesRef.current = null;
    };
  }, [data, firstClose, locale, pointByDate]);

  useEffect(() => {
    const chart = chartRef.current;
    if (!chart || points.length === 0) {
      return;
    }
    applyVisibleRange(chart, points, range);
  }, [points, range]);

  return (
    <div className="ticker-financial-chart">
      <div className="ticker-financial-chart__toolbar">
        <div className="ticker-financial-chart__readout">
          <span>{activePoint ? formatChartDate(activePoint.date, locale) : "--"}</span>
          <strong>{activePoint ? formatPrice(activePoint.close, locale) : "--"}</strong>
          <span className={activePoint && (activePoint.changePercent ?? 0) < 0 ? "is-negative" : "is-positive"}>
            {formatPercent(activePoint?.changePercent ?? null, locale)}
          </span>
        </div>
        <div className="ticker-financial-chart__ranges" aria-label="Chart range">
          {RANGE_OPTIONS.map((option) => (
            <button
              key={option}
              type="button"
              aria-pressed={option === range}
              data-active={option === range}
              className="ticker-financial-chart__range-button"
              onClick={() => onRangeChange(option)}
            >
              {option}
            </button>
          ))}
        </div>
      </div>
      <div className="ticker-financial-chart__canvas-wrap">
        <div ref={containerRef} className="ticker-financial-chart__canvas" />
        {hoverPoint ? (
          <div
            className="ticker-financial-chart__tooltip"
            style={{
              left: `clamp(84px, ${hoverPoint.x}px, calc(100% - 84px))`,
            }}
          >
            <span>{formatChartDate(hoverPoint.date, locale)}</span>
            <strong>{formatPrice(hoverPoint.close, locale)}</strong>
          </div>
        ) : null}
      </div>
    </div>
  );
}

function buildPointLookup(points: ChartPoint[]): Map<string, ChartPoint> {
  return new Map(points.map((point) => [point.date, point]));
}

function buildStaticHoverPoint(point: ChartPoint, firstClose: number | null): HoverPoint {
  return {
    date: point.date,
    close: point.close,
    changePercent: calculateChangePercent(point.close, firstClose),
    x: 0,
  };
}

function applyVisibleRange(chart: IChartApi, points: ChartPoint[], range: ChartRangeKey) {
  if (range === "All" || points.length < 2) {
    chart.timeScale().fitContent();
    return;
  }

  const latest = parseIsoDate(points[points.length - 1].date);
  if (!latest) {
    chart.timeScale().fitContent();
    return;
  }

  const threshold = new Date(latest);
  threshold.setUTCDate(threshold.getUTCDate() - CHART_RANGE_DAYS[range]);
  const firstVisible =
    points.find((point) => {
      const parsed = parseIsoDate(point.date);
      return parsed ? parsed >= threshold : false;
    }) ?? points[0];

  chart.timeScale().setVisibleRange({
    from: firstVisible.date,
    to: points[points.length - 1].date,
  });
}

function resolveChartTokens(container: HTMLElement) {
  const styles = window.getComputedStyle(container);
  const rootStyles = window.getComputedStyle(document.documentElement);
  const token = (name: string, fallback: string) =>
    styles.getPropertyValue(name).trim() || rootStyles.getPropertyValue(name).trim() || fallback;

  return {
    background: token("--chart-svg-bg", "rgba(255, 252, 248, 0.92)"),
    grid: token("--chart-grid", "rgba(202, 175, 143, 0.44)"),
    gridSoft: token("--chart-grid-soft", "rgba(235, 214, 190, 0.28)"),
    axis: token("--chart-axis", "rgba(214, 191, 161, 0.55)"),
    line: token("--chart-line", "rgb(17, 63, 96)"),
    label: token("--chart-label", "rgb(96, 118, 134)"),
    crosshair: withAlpha(token("--chart-label", "rgb(96, 118, 134)"), 0.38),
  };
}

function withAlpha(color: string, alpha: number): string {
  const normalized = color.trim();
  const rgbaMatch = normalized.match(/^rgba?\(([^)]+)\)$/i);
  if (rgbaMatch) {
    const rawChannels = rgbaMatch[1].trim().replace(/\s*\/\s*[^,\s]+$/, "");
    const channels = (
      rawChannels.includes(",") ? rawChannels.split(",") : rawChannels.split(/\s+/)
    )
      .map((part) => part.trim())
      .filter(Boolean)
      .slice(0, 3);
    if (channels.length === 3) {
      const [red, green, blue] = channels;
      return `rgba(${red}, ${green}, ${blue}, ${alpha})`;
    }
  }

  const hexMatch = normalized.match(
    /^#([0-9a-f]{3,4}|[0-9a-f]{6}|[0-9a-f]{8})$/i
  );
  if (hexMatch) {
    const hex = hexMatch[1];
    const expanded =
      hex.length === 3 || hex.length === 4
        ? hex
            .split("")
            .map((character) => `${character}${character}`)
            .join("")
        : hex;
    const red = Number.parseInt(expanded.slice(0, 2), 16);
    const green = Number.parseInt(expanded.slice(2, 4), 16);
    const blue = Number.parseInt(expanded.slice(4, 6), 16);
    if ([red, green, blue].every(Number.isFinite)) {
      return `rgba(${red}, ${green}, ${blue}, ${alpha})`;
    }
  }

  return color;
}

function calculateChangePercent(value: number, base: number | null): number | null {
  if (base === null || base === 0) {
    return null;
  }
  return ((value - base) / base) * 100;
}

function formatPrice(value: number, locale: string): string {
  return new Intl.NumberFormat(locale, {
    maximumFractionDigits: 2,
  }).format(value);
}

function formatPercent(value: number | null, locale: string): string {
  if (typeof value !== "number") {
    return "--";
  }

  return `${new Intl.NumberFormat(locale, {
    maximumFractionDigits: 2,
    signDisplay: "always",
  }).format(value)}%`;
}

function formatChartDate(value: string, locale: string): string {
  const parsed = new Date(`${value}T00:00:00Z`);
  if (Number.isNaN(parsed.getTime())) {
    return value;
  }

  return new Intl.DateTimeFormat(locale, {
    year: "numeric",
    month: "short",
    day: "2-digit",
    timeZone: "UTC",
  }).format(parsed);
}

function parseIsoDate(value: string): Date | null {
  const parsed = new Date(`${value}T00:00:00Z`);
  return Number.isNaN(parsed.getTime()) ? null : parsed;
}
