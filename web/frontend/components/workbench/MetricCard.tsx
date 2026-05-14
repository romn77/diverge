import type { ReactNode } from "react";

import { Badge } from "@/components/ui/badge";
import { Card, CardContent } from "@/components/ui/card";
import { cn } from "@/lib/utils";

interface MetricCardProps {
  label: string;
  value: string;
  /** @deprecated persistent helper copy is intentionally not rendered. */
  meta?: string;
  /** @deprecated persistent helper copy is intentionally not rendered. */
  secondary?: string;
  action?: ReactNode;
  badge?: ReactNode;
  trendLabel?: string;
  trendValue?: string;
  trendDirection?: "up" | "down" | "neutral";
  className?: string;
  valueClassName?: string;
}

export function MetricCard({
  label,
  value,
  action,
  badge,
  trendLabel,
  trendValue,
  trendDirection = "neutral",
  className,
  valueClassName,
}: MetricCardProps) {
  const hasMetricDetails = Boolean(
    action || badge || trendLabel || trendValue
  );
  const trendVariant =
    trendDirection === "up"
      ? "success"
      : trendDirection === "down"
        ? "destructive"
        : "secondary";

  if (!hasMetricDetails) {
    return (
      <Card className={cn("metric-card", className)}>
        <CardContent className="relative px-4 py-3">
          <p className="text-[11px] font-semibold uppercase tracking-[0.18em] text-muted-foreground">
            {label}
          </p>
          <p
            className={cn(
              "metric-card-value mt-2 text-2xl font-semibold text-foreground",
              valueClassName
            )}
          >
            {value}
          </p>
        </CardContent>
      </Card>
    );
  }

  return (
    <Card className={cn("metric-card", className)}>
      <CardContent className="relative px-4 py-3">
        <div className="flex min-h-5 items-start justify-between gap-3">
          <p className="min-w-0 text-[11px] font-semibold uppercase tracking-[0.18em] text-muted-foreground">
            {label}
          </p>
          {badge || action ? (
            <div className="flex shrink-0 items-center gap-1.5 text-xs text-muted-foreground">
              {badge}
              {action}
            </div>
          ) : null}
        </div>
        <div className="mt-2 flex items-end justify-between gap-3">
          <p
            className={cn(
              "metric-card-value min-w-0 text-2xl font-semibold leading-none text-foreground",
              valueClassName
            )}
          >
            {value}
          </p>
          {trendValue ? (
            <Badge
              aria-label={trendLabel ? `${trendLabel}: ${trendValue}` : undefined}
              className="shrink-0 px-2 py-1 text-[10px] tracking-[0.08em]"
              variant={trendVariant}
            >
              {trendLabel ? <span className="sr-only">{trendLabel}: </span> : null}
              {trendValue}
            </Badge>
          ) : null}
        </div>
      </CardContent>
    </Card>
  );
}
