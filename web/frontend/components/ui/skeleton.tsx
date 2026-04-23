import { cn } from "@/lib/utils";

function Skeleton({ className, ...props }: React.ComponentProps<"div">) {
  return (
    <div
      className={cn("animate-pulse rounded-[18px] bg-[color:var(--surface-strong)]", className)}
      {...props}
    />
  );
}

export { Skeleton };
