import * as React from "react";
import { cva, type VariantProps } from "class-variance-authority";
import { cn } from "@/lib/utils";

const badgeVariants = cva(
  "inline-flex items-center rounded-full border px-3 py-1 text-[11px] font-semibold uppercase tracking-[0.16em] transition-colors",
  {
    variants: {
      variant: {
        default: "border-primary/25 bg-primary-soft text-[color:var(--primary-strong)]",
        secondary: "border-border bg-white text-muted-foreground",
        outline: "border-border bg-transparent text-foreground",
        destructive: "border-destructive/20 bg-[rgba(163,53,53,0.08)] text-destructive",
        success: "border-[rgba(46,118,83,0.2)] bg-[rgba(46,118,83,0.08)] text-success",
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
