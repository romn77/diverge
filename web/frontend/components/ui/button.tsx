import * as React from "react";
import { Slot } from "@radix-ui/react-slot";
import { cva, type VariantProps } from "class-variance-authority";
import { cn } from "@/lib/utils";

const buttonVariants = cva(
  "inline-flex items-center justify-center gap-2 whitespace-nowrap rounded-[10px] text-sm font-semibold leading-none tracking-normal align-middle transition active:translate-y-px motion-reduce:active:translate-y-0 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[color:var(--ring-strong)] focus-visible:ring-offset-2 focus-visible:ring-offset-background disabled:pointer-events-none disabled:opacity-60 [&_svg]:pointer-events-none [&_svg]:size-4 [&_svg]:shrink-0",
  {
    variants: {
      variant: {
        default:
          "button-primary border",
        secondary:
          "border border-border bg-[var(--surface)] text-foreground shadow-[var(--button-secondary-shadow)] hover:bg-[color:var(--surface-hover)]",
        outline:
          "border border-border bg-transparent text-foreground hover:bg-[color:var(--surface-hover)]",
        ghost: "border border-transparent bg-transparent text-muted-foreground hover:bg-accent hover:text-accent-foreground",
        destructive:
          "border border-destructive bg-destructive text-destructive-foreground shadow-[var(--button-danger-shadow)] hover:brightness-[0.98]",
      },
      size: {
        default: "h-10 px-4 py-2.5",
        sm: "h-8 px-3 py-1.5 text-xs",
        lg: "h-11 px-5 py-3",
        icon: "size-9 p-0",
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
