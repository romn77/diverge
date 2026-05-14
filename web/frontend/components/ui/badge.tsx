import * as React from "react";
import { cva, type VariantProps } from "class-variance-authority";
import { cn } from "@/lib/utils";

const badgeVariants = cva(
  "inline-flex items-center rounded-full border px-3 py-1 text-[11px] font-semibold uppercase tracking-[0.16em] transition-colors",
  {
    variants: {
      variant: {
        default: "border-primary/25 bg-primary-soft text-[color:var(--primary-strong)]",
        secondary: "border-border bg-[var(--surface)] text-muted-foreground",
        outline: "border-border bg-transparent text-foreground",
        destructive: "border-[var(--danger-border)] bg-[var(--danger-soft)] text-destructive",
        success: "border-[var(--success-border)] bg-[var(--success-soft)] text-success",
      },
    },
    defaultVariants: {
      variant: "default",
    },
  }
);

function Badge({
  className,
  variant,
  ...props
}: React.ComponentProps<"span"> & VariantProps<typeof badgeVariants>) {
  return <span className={cn(badgeVariants({ variant, className }))} {...props} />;
}

export { Badge, badgeVariants };
