import { Card, CardContent } from "@/components/ui/card";
import { cn } from "@/lib/utils";

interface MetricCardProps {
  label: string;
  value: string;
  meta?: string;
  className?: string;
  valueClassName?: string;
}

export function MetricCard({
  label,
  value,
  meta,
  className,
  valueClassName,
}: MetricCardProps) {
  return (
    <Card className={cn("metric-card", className)}>
      <CardContent className="relative px-4 py-3">
        <p className="text-[11px] font-semibold uppercase tracking-[0.18em] text-slate-500">
          {label}
        </p>
        <p
          className={cn(
            "metric-card-value mt-2 text-2xl font-semibold text-slate-900",
            valueClassName
          )}
        >
          {value}
        </p>
        {meta ? <p className="metric-card-meta mt-1 text-xs">{meta}</p> : null}
      </CardContent>
    </Card>
  );
}
