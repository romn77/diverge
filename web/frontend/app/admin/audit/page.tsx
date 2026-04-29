"use client";

import { useCallback, useEffect, useMemo, useState, type FormEvent } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { RefreshCw, Search, ShieldCheck } from "lucide-react";

import { useAuth } from "@/components/AuthProvider";
import { StatusPanel } from "@/components/workbench/StatusPanel";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import {
  ApiError,
  listAdminAuditEvents,
  type AdminAuditEvent,
  type AdminAuditEventsQuery,
} from "@/lib/api";

const DEFAULT_LIMIT = 100;

function createEmptyFilters() {
  return {
    actionFilter: "",
    resourceTypeFilter: "",
    actorUserIdFilter: "",
    createdFromFilter: "",
    createdToFilter: "",
    limitFilter: String(DEFAULT_LIMIT),
  };
}

function parseLimit(value: string): number {
  const parsed = Number(value);
  if (!Number.isInteger(parsed) || parsed < 1 || parsed > 500) {
    throw new Error("Limit must be a whole number between 1 and 500.");
  }
  return parsed;
}

function buildAuditQuery(filters: ReturnType<typeof createEmptyFilters>): AdminAuditEventsQuery {
  return {
    action: filters.actionFilter.trim() || undefined,
    resource_type: filters.resourceTypeFilter.trim() || undefined,
    actor_user_id: filters.actorUserIdFilter.trim() || undefined,
    created_from: filters.createdFromFilter || undefined,
    created_to: filters.createdToFilter || undefined,
    limit: parseLimit(filters.limitFilter),
  };
}

function formatDateTime(value: string | null): string {
  if (!value) {
    return "Unknown";
  }
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) {
    return value;
  }
  return new Intl.DateTimeFormat(undefined, {
    year: "numeric",
    month: "short",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  }).format(parsed);
}

function formatMetadata(metadata: Record<string, unknown>): string {
  const keys = Object.keys(metadata);
  if (!keys.length) {
    return "{}";
  }
  return JSON.stringify(metadata, null, 2);
}

function formatMetadataSummary(metadata: Record<string, unknown>): string {
  const entries = Object.entries(metadata);
  if (!entries.length) {
    return "{}";
  }
  const summary = entries
    .slice(0, 3)
    .map(([key, value]) => {
      const rendered =
        typeof value === "string" || typeof value === "number" || typeof value === "boolean"
          ? String(value)
          : JSON.stringify(value);
      return `${key}: ${rendered}`;
    })
    .join(" | ");
  return entries.length > 3 ? `${summary} | +${entries.length - 3}` : summary;
}

function compactValue(value: string | null | undefined, fallback = "-"): string {
  return value && value.trim() ? value : fallback;
}

export default function AdminAuditPage() {
  const router = useRouter();
  const { authState, authStatus, refreshSession } = useAuth();
  const [events, setEvents] = useState<AdminAuditEvent[]>([]);
  const [filters, setFilters] = useState(createEmptyFilters);
  const [loading, setLoading] = useState(true);
  const [pageError, setPageError] = useState<string | null>(null);
  const [lastLoadedAt, setLastLoadedAt] = useState<string | null>(null);

  const authEnabled = authState?.enabled ?? false;
  const shouldRedirectToLogin =
    authStatus === "ready" && authEnabled && !authState?.authenticated;
  const canLoad =
    authStatus === "ready" && authEnabled && Boolean(authState?.authenticated);
  const canInspectAudit = Boolean(authState?.permissions.includes("admin:audit"));

  const metrics = useMemo(() => {
    const actionCount = new Set(events.map((event) => event.action)).size;
    const actorCount = new Set(
      events.map((event) => event.actor_user_id).filter(Boolean)
    ).size;
    const resourceCount = new Set(events.map((event) => event.resource_type)).size;
    return { actionCount, actorCount, resourceCount };
  }, [events]);

  const handleAuthBoundary = useCallback(
    (error: unknown): boolean => {
      if (error instanceof ApiError && error.status === 401) {
        void refreshSession({ silent: true });
        return true;
      }
      if (error instanceof ApiError && error.status === 403) {
        setPageError("You do not have permission to inspect audit events.");
        return true;
      }
      return false;
    },
    [refreshSession]
  );

  const loadAuditEvents = useCallback(
    async (nextFilters: ReturnType<typeof createEmptyFilters>) => {
      setLoading(true);
      setPageError(null);
      try {
        const payload = await listAdminAuditEvents(buildAuditQuery(nextFilters));
        setEvents(payload.events);
        setLastLoadedAt(new Date().toISOString());
      } catch (error) {
        if (!handleAuthBoundary(error)) {
          setPageError(
            error instanceof Error ? error.message : "Unable to load audit events right now"
          );
        }
      } finally {
        setLoading(false);
      }
    },
    [handleAuthBoundary]
  );

  useEffect(() => {
    if (shouldRedirectToLogin) {
      router.replace("/login?next=/admin/audit");
    }
  }, [router, shouldRedirectToLogin]);

  useEffect(() => {
    if (!canLoad || !canInspectAudit) {
      setLoading(false);
      return;
    }
    void loadAuditEvents(createEmptyFilters());
  }, [canLoad, canInspectAudit, loadAuditEvents]);

  const handleFilterSubmit = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    void loadAuditEvents(filters);
  };

  const resetFilters = () => {
    const nextFilters = createEmptyFilters();
    setFilters(nextFilters);
    void loadAuditEvents(nextFilters);
  };

  if (authStatus === "loading" || loading) {
    return (
      <StatusPanel
        eyebrow="Admin Audit"
        title="Loading audit events"
        body="Checking the tenant activity trail."
      />
    );
  }

  if (!authEnabled) {
    return (
      <StatusPanel
        eyebrow="Admin Audit"
        title="Audit log is unavailable"
        body="Enable auth to inspect tenant audit events."
      />
    );
  }

  if (!canInspectAudit) {
    return (
      <StatusPanel
        eyebrow="Forbidden"
        title="This session cannot inspect audit events"
        tone="danger"
        body="You do not have permission to inspect audit events."
        action={
          <Button asChild>
            <Link href="/">Back to Workbench</Link>
          </Button>
        }
      />
    );
  }

  return (
    <main className="px-4 py-6 md:px-7 lg:px-9">
      <div className="mx-auto max-w-7xl space-y-6">
        <Card className="rounded-[30px]">
          <CardContent className="px-6 py-7 md:px-8">
            <div className="flex flex-col gap-6 lg:flex-row lg:items-end lg:justify-between">
              <div className="max-w-3xl">
                <Link
                  href="/"
                  className="text-[12px] font-semibold uppercase tracking-[0.32em] text-[var(--primary)]"
                >
                  Back to Workbench
                </Link>
                <div className="mt-4 flex flex-wrap gap-2">
                  <Button asChild type="button" size="sm" variant="secondary">
                    <Link href="/admin/task-queue">Task Queue</Link>
                  </Button>
                  <Button asChild type="button" size="sm" variant="secondary">
                    <Link href="/admin/users">User Management</Link>
                  </Button>
                  <Button asChild type="button" size="sm" variant="secondary">
                    <Link href="/admin/data-sources">Data Sources</Link>
                  </Button>
                  <Button type="button" size="sm">
                    Audit Log
                  </Button>
                </div>
                <div className="mt-4 flex flex-wrap items-center gap-3">
                  <h1 className="font-heading text-3xl font-bold tracking-tight text-slate-900 md:text-4xl">
                    Audit Log
                  </h1>
                  <Badge variant="secondary">Read-only</Badge>
                  <Badge variant="outline">{events.length} events</Badge>
                </div>
                <p className="mt-3 text-sm leading-7 text-slate-600">
                  Review tenant-scoped auth, admin, data-source, task, asset, and journal activity.
                </p>
              </div>
              <div className="flex flex-wrap items-center gap-3">
                {lastLoadedAt ? (
                  <Badge variant="secondary">Loaded {formatDateTime(lastLoadedAt)}</Badge>
                ) : null}
                <Button
                  type="button"
                  variant="secondary"
                  onClick={() => void loadAuditEvents(filters)}
                >
                  <RefreshCw className="size-4" />
                  Refresh
                </Button>
              </div>
            </div>
          </CardContent>
        </Card>

        {pageError ? (
          <div className="rounded-[24px] border border-[rgba(163,53,53,0.2)] bg-[rgba(163,53,53,0.08)] px-5 py-4 text-sm text-[var(--danger)]">
            {pageError}
          </div>
        ) : null}

        <section className="grid gap-4 md:grid-cols-4">
          <AuditMetric label="Events" value={events.length} />
          <AuditMetric label="Actions" value={metrics.actionCount} />
          <AuditMetric label="Actors" value={metrics.actorCount} />
          <AuditMetric label="Resources" value={metrics.resourceCount} />
        </section>

        <Card className="rounded-[28px]">
          <CardContent className="px-5 py-5">
            <form
              className="grid gap-4 lg:grid-cols-[1fr_1fr_1fr_1fr_1fr_auto] lg:items-end"
              onSubmit={handleFilterSubmit}
            >
              <AuditFilterField
                label="Action"
                value={filters.actionFilter}
                placeholder="auth.login.success"
                onChange={(value) =>
                  setFilters((current) => ({ ...current, actionFilter: value }))
                }
              />
              <AuditFilterField
                label="Resource Type"
                value={filters.resourceTypeFilter}
                placeholder="user"
                onChange={(value) =>
                  setFilters((current) => ({ ...current, resourceTypeFilter: value }))
                }
              />
              <AuditFilterField
                label="Actor User ID"
                value={filters.actorUserIdFilter}
                placeholder="user id"
                onChange={(value) =>
                  setFilters((current) => ({ ...current, actorUserIdFilter: value }))
                }
              />
              <AuditFilterField
                label="From"
                type="datetime-local"
                value={filters.createdFromFilter}
                onChange={(value) =>
                  setFilters((current) => ({ ...current, createdFromFilter: value }))
                }
              />
              <AuditFilterField
                label="To"
                type="datetime-local"
                value={filters.createdToFilter}
                onChange={(value) =>
                  setFilters((current) => ({ ...current, createdToFilter: value }))
                }
              />
              <div className="flex flex-wrap gap-2">
                <label className="block w-24">
                  <span className="text-[10px] font-semibold uppercase tracking-[0.24em] text-slate-500">
                    Limit
                  </span>
                  <Input
                    type="number"
                    min={1}
                    max={500}
                    step={1}
                    value={filters.limitFilter}
                    onChange={(event) =>
                      setFilters((current) => ({
                        ...current,
                        limitFilter: event.target.value,
                      }))
                    }
                    className="mt-2 bg-white"
                  />
                </label>
                <Button type="submit" className="self-end">
                  <Search className="size-4" />
                  Filter
                </Button>
                <Button type="button" variant="secondary" className="self-end" onClick={resetFilters}>
                  Reset
                </Button>
              </div>
            </form>
          </CardContent>
        </Card>

        <section>
          {events.length === 0 ? (
            <Card className="rounded-[28px] border-dashed">
              <CardContent className="px-6 py-10 text-center">
                <ShieldCheck className="mx-auto size-8 text-[var(--primary)]" />
                <h2 className="mt-4 font-heading text-2xl font-semibold text-slate-900">
                  No audit events matched
                </h2>
                <p className="mt-2 text-sm text-slate-500">
                  Adjust the filters or refresh after workspace activity occurs.
                </p>
              </CardContent>
            </Card>
          ) : (
            <AuditEventTable events={events} />
          )}
        </section>
      </div>
    </main>
  );
}

function AuditMetric({ label, value }: { label: string; value: number }) {
  return (
    <Card className="rounded-[24px] bg-white/88">
      <CardContent className="px-4 py-4">
        <p className="text-[11px] font-semibold uppercase tracking-[0.18em] text-slate-500">
          {label}
        </p>
        <p className="mt-3 text-3xl font-semibold tracking-tight text-slate-900">
          {value}
        </p>
      </CardContent>
    </Card>
  );
}

function AuditFilterField({
  label,
  value,
  onChange,
  placeholder,
  type = "text",
}: {
  label: string;
  value: string;
  onChange: (value: string) => void;
  placeholder?: string;
  type?: string;
}) {
  return (
    <label className="block">
      <span className="text-[10px] font-semibold uppercase tracking-[0.24em] text-slate-500">
        {label}
      </span>
      <Input
        type={type}
        value={value}
        placeholder={placeholder}
        onChange={(event) => onChange(event.target.value)}
        className="mt-2 bg-white"
      />
    </label>
  );
}

function AuditEventTable({ events }: { events: AdminAuditEvent[] }) {
  return (
    <Card className="overflow-hidden rounded-[18px] bg-white/95">
      <CardContent className="p-0">
        <div className="max-h-[620px] overflow-auto">
          <Table className="min-w-[1120px] text-xs [&_td]:px-3 [&_td]:py-2 [&_th]:h-9 [&_th]:px-3 [&_th]:tracking-[0.12em]">
            <TableHeader className="sticky top-0 z-10 bg-[var(--surface-strong)]">
              <TableRow className="border-b border-[var(--border)]">
                <TableHead className="w-[150px] text-left">Time</TableHead>
                <TableHead className="w-[190px] text-left">Action</TableHead>
                <TableHead className="w-[180px] text-left">Resource</TableHead>
                <TableHead className="w-[210px] text-left">Actor</TableHead>
                <TableHead className="w-[130px] text-left">IP</TableHead>
                <TableHead className="text-left">Metadata</TableHead>
                <TableHead className="w-[220px] text-left">User Agent</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {events.map((event) => {
                const metadata = formatMetadata(event.metadata);
                const metadataSummary = formatMetadataSummary(event.metadata);
                const resource = [
                  compactValue(event.resource_type),
                  event.resource_id ? `#${event.resource_id}` : null,
                ]
                  .filter(Boolean)
                  .join(" ");
                return (
                  <TableRow
                    key={event.id}
                    className="border-b border-[rgba(15,23,42,0.06)] align-top hover:bg-[rgba(47,111,78,0.06)]"
                  >
                    <TableCell className="whitespace-nowrap font-medium text-slate-800">
                      {formatDateTime(event.created_at)}
                    </TableCell>
                    <TableCell>
                      <Badge className="max-w-[170px] truncate align-middle" title={event.action}>
                        {event.action}
                      </Badge>
                    </TableCell>
                    <TableCell className="max-w-[180px] truncate text-slate-700" title={resource}>
                      {resource}
                    </TableCell>
                    <TableCell
                      className="max-w-[210px] truncate font-mono text-[11px] text-slate-600"
                      title={compactValue(event.actor_user_id, "system")}
                    >
                      {compactValue(event.actor_user_id, "system")}
                    </TableCell>
                    <TableCell
                      className="whitespace-nowrap font-mono text-[11px] text-slate-600"
                      title={compactValue(event.ip_address, "unknown")}
                    >
                      {compactValue(event.ip_address, "unknown")}
                    </TableCell>
                    <TableCell
                      className="max-w-[340px] truncate font-mono text-[11px] leading-5 text-slate-600"
                      title={metadata}
                    >
                      <span className="sr-only">Metadata</span>
                      {metadataSummary}
                    </TableCell>
                    <TableCell
                      className="max-w-[220px] truncate text-[11px] text-slate-500"
                      title={compactValue(event.user_agent, "unknown")}
                    >
                      {compactValue(event.user_agent, "unknown")}
                    </TableCell>
                  </TableRow>
                );
              })}
            </TableBody>
          </Table>
        </div>
      </CardContent>
    </Card>
  );
}
