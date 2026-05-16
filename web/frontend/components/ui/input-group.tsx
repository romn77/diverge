"use client";

import * as React from "react";
import { cva, type VariantProps } from "class-variance-authority";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { cn } from "@/lib/utils";

function InputGroup({ className, ...props }: React.ComponentProps<"div">) {
  return (
    <div
      data-slot="input-group"
      role="group"
      className={cn(
        "group/input-group relative flex h-10 w-full min-w-0 items-center rounded-[10px] border border-input bg-[color:var(--surface-strong)] text-foreground shadow-[var(--field-shadow)] transition has-[>textarea]:h-auto has-[>textarea]:items-stretch focus-within:border-[var(--accent-border)] focus-within:outline-none focus-within:ring-2 focus-within:ring-[color:var(--ring-strong)] focus-within:ring-offset-2 focus-within:ring-offset-background data-[disabled=true]:cursor-not-allowed data-[disabled=true]:opacity-60",
        className
      )}
      {...props}
    />
  );
}

const inputGroupAddonVariants = cva(
  "flex cursor-text select-none items-center justify-center text-muted-foreground [&_svg]:pointer-events-none [&_svg]:size-4 [&_svg]:shrink-0",
  {
    variants: {
      align: {
        "inline-start": "order-first h-full pl-3 pr-1",
        "inline-end": "order-last h-full pl-1 pr-3",
        "block-start":
          "order-first w-full justify-start border-b border-[var(--border)] px-3 py-2",
        "block-end":
          "order-last w-full justify-start border-t border-[var(--border)] px-3 py-2",
      },
    },
    defaultVariants: {
      align: "inline-start",
    },
  }
);

function InputGroupAddon({
  className,
  align = "inline-start",
  ...props
}: React.ComponentProps<"div"> & VariantProps<typeof inputGroupAddonVariants>) {
  return (
    <div
      role="group"
      data-slot="input-group-addon"
      data-align={align}
      className={cn(inputGroupAddonVariants({ align }), className)}
      onClick={(event) => {
        if ((event.target as HTMLElement).closest("button")) {
          return;
        }
        const control = event.currentTarget.parentElement?.querySelector(
          "input, textarea"
        ) as HTMLElement | null;
        control?.focus();
      }}
      {...props}
    />
  );
}

const inputGroupButtonVariants = cva(
  "h-7 rounded-[8px] px-2 text-xs tracking-normal shadow-none",
  {
    variants: {
      size: {
        xs: "h-7 px-2",
        sm: "h-8 px-2.5",
        "icon-xs": "size-7 p-0",
        "icon-sm": "size-8 p-0",
      },
    },
    defaultVariants: {
      size: "xs",
    },
  }
);

function InputGroupButton({
  className,
  type = "button",
  variant = "ghost",
  size = "xs",
  ...props
}: Omit<React.ComponentProps<typeof Button>, "size"> &
  VariantProps<typeof inputGroupButtonVariants>) {
  return (
    <Button
      type={type}
      data-size={size}
      variant={variant}
      className={cn(inputGroupButtonVariants({ size }), className)}
      {...props}
    />
  );
}

function InputGroupText({ className, ...props }: React.ComponentProps<"span">) {
  return (
    <span
      data-slot="input-group-text"
      className={cn("flex items-center gap-1 text-xs font-medium", className)}
      {...props}
    />
  );
}

function InputGroupInput({
  className,
  ...props
}: React.ComponentProps<"input">) {
  return (
    <Input
      data-slot="input-group-control"
      className={cn(
        "h-full flex-1 rounded-none border-0 bg-transparent px-3 py-2 shadow-none focus-visible:ring-0 focus-visible:ring-offset-0",
        className
      )}
      {...props}
    />
  );
}

function InputGroupTextarea({
  className,
  ...props
}: React.ComponentProps<"textarea">) {
  return (
    <Textarea
      data-slot="input-group-control"
      className={cn(
        "min-h-[96px] flex-1 resize-none rounded-none border-0 bg-transparent px-3 py-2 shadow-none focus-visible:ring-0 focus-visible:ring-offset-0",
        className
      )}
      {...props}
    />
  );
}

export {
  InputGroup,
  InputGroupAddon,
  InputGroupButton,
  InputGroupInput,
  InputGroupText,
  InputGroupTextarea,
};
