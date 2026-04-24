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
    <Card className={cn("rounded-[24px] bg-white/88", className)}>
      <CardContent className="px-4 py-4">
        <p className="text-[11px] font-semibold uppercase tracking-[0.18em] text-slate-500">
          {label}
        </p>
        <p
          className={cn(
            "mt-3 text-3xl font-semibold tracking-tight text-slate-900",
            valueClassName
          )}
        >
          {value}
        </p>
        {meta ? <p className="mt-2 text-sm text-slate-500">{meta}</p> : null}
      </CardContent>
    </Card>
  );
}
