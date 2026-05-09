import Link from "next/link";
import { ChevronDown } from "lucide-react";
import { Card, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";
import type { ReactNode } from "react";

interface PageHeaderProps {
  eyebrow: ReactNode;
  title: ReactNode;
  actions?: ReactNode;
  backHref?: string;
  backLabel?: string;
  children?: ReactNode;
  className?: string;
  contentClassName?: string;
}

export function PageHeader({
  eyebrow,
  title,
  actions,
  backHref,
  backLabel = "Back",
  children,
  className,
  contentClassName,
}: PageHeaderProps) {
  return (
    <Card className={cn("workbench-page-header card-surface", className)}>
      <CardContent className={cn("workbench-page-header-content", contentClassName)}>
        <div className="workbench-page-header-row">
          <div className="workbench-page-header-title-group">
            {backHref ? (
              <Button
                asChild
                variant="ghost"
                size="icon"
                className="workbench-page-header-back"
              >
                <Link href={backHref} aria-label={backLabel}>
                  <ChevronDown className="size-4 rotate-90" />
                </Link>
              </Button>
            ) : null}
            <div className="min-w-0">
              <p className="sr-only">{eyebrow}</p>
              <h1 className="sr-only">{title}</h1>
            </div>
          </div>
          {actions ? (
            <div className="workbench-page-header-actions">{actions}</div>
          ) : null}
        </div>
        {children ? <div className="workbench-page-header-body">{children}</div> : null}
      </CardContent>
    </Card>
  );
}
