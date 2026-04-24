import * as React from "react";
import { Slot } from "@radix-ui/react-slot";
import { cva, type VariantProps } from "class-variance-authority";
import { cn } from "@/lib/utils";

const buttonVariants = cva(
  "inline-flex items-center justify-center gap-2 whitespace-nowrap rounded-full text-sm font-semibold tracking-[0.04em] transition focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[color:var(--ring-strong)] focus-visible:ring-offset-2 focus-visible:ring-offset-background disabled:pointer-events-none disabled:opacity-60 [&_svg]:pointer-events-none [&_svg]:shrink-0",
  {
    variants: {
      variant: {
        default:
          "border border-primary bg-primary text-primary-foreground shadow-[var(--button-primary-shadow)] hover:brightness-[0.985] active:brightness-[0.96]",
        secondary:
          "border border-border bg-white text-foreground shadow-[var(--button-secondary-shadow)] hover:bg-[color:var(--surface-hover)]",
        outline:
          "border border-border bg-transparent text-foreground hover:bg-[color:var(--surface-hover)]",
        ghost: "border border-transparent bg-transparent text-muted-foreground hover:bg-accent hover:text-accent-foreground",
        destructive:
          "border border-destructive bg-destructive text-destructive-foreground shadow-[0_14px_28px_rgba(163,53,53,0.14)] hover:brightness-[0.98]",
      },
      size: {
        default: "h-11 px-5 py-3",
        sm: "h-9 px-4 py-2 text-xs uppercase tracking-[0.18em]",
        lg: "h-12 px-6 py-3.5",
        icon: "size-10 p-0",
      },
    },
    defaultVariants: {
      variant: "default",
      size: "default",
    },
  }
);

const Button = React.forwardRef<
  HTMLButtonElement,
  React.ComponentProps<"button"> &
    VariantProps<typeof buttonVariants> & {
      asChild?: boolean;
    }
>(({ className, variant, size, asChild = false, ...props }, ref) => {
  const Comp = asChild ? Slot : "button";

  return (
    <Comp
      ref={ref}
      className={cn(buttonVariants({ variant, size, className }))}
      {...props}
    />
  );
});
Button.displayName = "Button";

export { Button, buttonVariants };
