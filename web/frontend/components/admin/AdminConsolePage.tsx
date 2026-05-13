import Link from "next/link";
import type { ReactNode } from "react";

import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";

export type AdminConsoleTab =
  | "users"
  | "data-sources"
  | "search-quota"
  | "llm-models"
  | "task-queue"
  | "audit";

const ADMIN_TABS: Array<{ key: AdminConsoleTab; label: string; href: string }> = [
  { key: "users", label: "User Management", href: "/admin/users" },
  { key: "data-sources", label: "Data Sources", href: "/admin/data-sources" },
  { key: "search-quota", label: "Search Quota", href: "/admin/search-quota" },
  { key: "llm-models", label: "LLM Models", href: "/admin/llm-models" },
  { key: "task-queue", label: "Task Queue", href: "/admin/task-queue" },
  { key: "audit", label: "Audit Log", href: "/admin/audit" },
];

export function AdminConsolePage({
  activeTab,
  title,
  badges,
  actions,
  children,
}: {
  activeTab: AdminConsoleTab;
  title: string;
  badges?: ReactNode;
  actions?: ReactNode;
  children: ReactNode;
}) {
  return (
    <main className="px-3 py-4 text-[var(--foreground)] md:px-5 lg:px-6">
      <div className="mx-auto w-full max-w-7xl space-y-3">
        <Card className="rounded-[14px] border-[var(--border)] bg-white/95">
          <CardContent className="grid min-h-[8.5rem] grid-rows-[2rem_minmax(3.75rem,1fr)] gap-3 px-4 py-3 md:px-5">
            <nav className="hidden-scrollbar flex h-8 min-w-0 flex-nowrap items-center gap-3 overflow-x-auto whitespace-nowrap">
              <Link
                href="/"
                className="shrink-0 text-[10px] font-semibold uppercase tracking-[0.22em] text-[var(--primary)]"
              >
                Back to Workbench
              </Link>
              <div className="flex shrink-0 flex-nowrap gap-1.5">
                {ADMIN_TABS.map((tab) =>
                  tab.key === activeTab ? (
                    <Button
                      key={tab.key}
                      type="button"
                      size="sm"
                      className="h-8 min-w-[9.75rem] px-3 text-[11px] tracking-[0.14em]"
                    >
                      {tab.label}
                    </Button>
                  ) : (
                    <Button
                      key={tab.key}
                      asChild
                      type="button"
                      size="sm"
                      variant="secondary"
                      className="h-8 min-w-[9.75rem] px-3 text-[11px] tracking-[0.14em]"
                    >
                      <Link href={tab.href}>{tab.label}</Link>
                    </Button>
                  )
                )}
              </div>
            </nav>

            <div className="grid min-h-[3.75rem] gap-3 lg:grid-cols-[minmax(0,1fr)_minmax(18rem,28rem)] lg:items-end">
              <div className="flex min-h-[3.75rem] min-w-0 flex-col justify-end">
                <div className="flex flex-wrap items-center gap-2">
                  <h1 className="font-heading text-xl font-bold tracking-tight text-slate-900 md:text-2xl">
                    {title}
                  </h1>
                  {badges}
                </div>
              </div>
              {actions ? (
                <div className="flex min-h-[3.75rem] flex-wrap items-end justify-start gap-2 lg:justify-end">
                  {actions}
                </div>
              ) : null}
            </div>
          </CardContent>
        </Card>
        {children}
      </div>
    </main>
  );
}

export function AdminMetricGrid({ children }: { children: ReactNode }) {
  return <section className="grid gap-2 md:grid-cols-4">{children}</section>;
}

export function AdminMetricCard({
  label,
  value,
  className = "",
}: {
  label: string;
  value: string | number;
  className?: string;
}) {
  return (
    <Card className={`rounded-[12px] bg-white/90 ${className}`}>
      <CardContent className="px-3 py-2.5">
        <p className="text-[10px] font-semibold uppercase tracking-[0.16em] text-slate-500">
          {label}
        </p>
        <p className="mt-1 text-xl font-semibold tracking-tight text-slate-900">
          {value}
        </p>
      </CardContent>
    </Card>
  );
}

export function AdminPanel({
  children,
  className = "",
  contentClassName = "px-4 py-4",
}: {
  children: ReactNode;
  className?: string;
  contentClassName?: string;
}) {
  return (
    <Card className={`rounded-[14px] border-[var(--border)] bg-white/95 ${className}`}>
      <CardContent className={contentClassName}>{children}</CardContent>
    </Card>
  );
}

export function AdminNotice({
  tone = "danger",
  children,
}: {
  tone?: "danger" | "success";
  children: ReactNode;
}) {
  const toneClass =
    tone === "success"
      ? "border-[rgba(57,111,83,0.22)] bg-[rgba(57,111,83,0.08)] text-[var(--primary)]"
      : "border-[rgba(163,53,53,0.2)] bg-[rgba(163,53,53,0.08)] text-[var(--danger)]";

  return (
    <div className={`rounded-[12px] border px-3 py-2 text-xs ${toneClass}`}>
      {children}
    </div>
  );
}
