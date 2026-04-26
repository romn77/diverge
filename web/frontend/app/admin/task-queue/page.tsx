"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { RefreshCw } from "lucide-react";

import { useAuth } from "@/components/AuthProvider";
import { StatusPanel } from "@/components/workbench/StatusPanel";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import {
  ApiError,
  listAdminTaskQueue,
  type AdminTaskQueueItem,
  type AdminTaskQueueResponse,
  type TaskStatus,
} from "@/lib/api";

const STATUS_LABELS: Record<TaskStatus, string> = {
  pending: "Pending",
  queued: "Queued",
  waiting_for_quota: "Waiting for quota",
  running: "Running",
  completed: "Completed",
  failed: "Failed",
  canceled: "Canceled",
};

const QUEUE_SECTIONS = [
  {
    key: "running",
    title: "Running",
    emptyLabel: "No running tasks.",
  },
  {
    key: "queued",
    title: "Queued",
    emptyLabel: "No queued tasks.",
  },
  {
    key: "waiting_for_quota",
    title: "Waiting for quota",
    emptyLabel: "No tasks waiting for quota.",
  },
] as const;

export default function AdminTaskQueuePage() {
  const router = useRouter();
  const { authState, authStatus, refreshSession } = useAuth();
  const [snapshot, setSnapshot] = useState<AdminTaskQueueResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [pageError, setPageError] = useState<string | null>(null);

  const authEnabled = authState?.enabled ?? false;
  const shouldRedirectToLogin =
    authStatus === "ready" && authEnabled && !authState?.authenticated;
  const canLoad =
    authStatus === "ready" && authEnabled && Boolean(authState?.authenticated);
  const canManage = authState?.user?.role === "admin";

  const groupedTasks = useMemo(() => {
    const groups: Record<(typeof QUEUE_SECTIONS)[number]["key"], AdminTaskQueueItem[]> = {
      running: [],
      queued: [],
      waiting_for_quota: [],
    };
    for (const task of snapshot?.tasks ?? []) {
      if (task.status === "pending") {
        groups.queued.push(task);
      } else if (task.status in groups) {
        groups[task.status as keyof typeof groups].push(task);
      }
    }
    return groups;
  }, [snapshot]);

  const handleAuthBoundary = useCallback(
    (error: unknown): boolean => {
      if (error instanceof ApiError && error.status === 401) {
        void refreshSession({ silent: true });
        return true;
      }
      if (error instanceof ApiError && error.status === 403) {
        setPageError("You do not have permission to inspect the task queue.");
        return true;
      }
      return false;
    },
    [refreshSession]
  );

  const loadTaskQueue = useCallback(async () => {
    setLoading(true);
    setPageError(null);
    try {
      setSnapshot(await listAdminTaskQueue());
    } catch (error) {
      if (!handleAuthBoundary(error)) {
        setPageError(
          error instanceof Error
            ? error.message
            : "Unable to load the task queue right now"
        );
      }
    } finally {
      setLoading(false);
    }
  }, [handleAuthBoundary]);

  useEffect(() => {
    if (shouldRedirectToLogin) {
      router.replace("/login?next=/admin/task-queue");
    }
  }, [router, shouldRedirectToLogin]);

  useEffect(() => {
    if (!canLoad || !canManage) {
      setLoading(false);
      return;
    }
    void loadTaskQueue();
  }, [canLoad, canManage, loadTaskQueue]);

  if (authStatus === "loading" || loading) {
    return (
      <StatusPanel
        eyebrow="Admin Console"
        title="Loading task queue"
        body="Checking active background work."
      />
    );
  }

  if (!authEnabled) {
    return (
      <StatusPanel
        eyebrow="Admin Console"
        title="Task queue dashboard is unavailable"
        body="Enable auth to inspect workspace operations."
      />
    );
  }

  if (!canManage) {
    return (
      <StatusPanel
        eyebrow="Forbidden"
        title="This session cannot inspect the task queue"
        tone="danger"
        body="You do not have permission to inspect admin operations."
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
                  <Button type="button" size="sm">
                    Task Queue
                  </Button>
                  <Button asChild type="button" size="sm" variant="secondary">
                    <Link href="/admin/users">User Management</Link>
                  </Button>
                  <Button asChild type="button" size="sm" variant="secondary">
                    <Link href="/admin/data-sources">Data Sources</Link>
                  </Button>
                </div>
                <div className="mt-4 flex flex-wrap items-center gap-3">
                  <h1 className="font-heading text-3xl font-bold tracking-tight text-slate-900 md:text-4xl">
                    Task Queue
                  </h1>
                  <Badge variant="secondary">Read-only</Badge>
                </div>
                <p className="mt-3 text-sm leading-7 text-slate-600">
                  Inspect active background jobs by status, owner, queue position, and quota block.
                </p>
              </div>
              <div className="flex flex-wrap items-center gap-3">
                <Badge variant="secondary">
                  Backend: {snapshot?.task_backend ?? "unknown"}
                </Badge>
                <Button type="button" variant="secondary" onClick={() => void loadTaskQueue()}>
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
          <QueueMetric label="Active" value={snapshot?.totals.active ?? 0} />
          <QueueMetric label="Running" value={snapshot?.totals.running ?? 0} />
          <QueueMetric label="Queued" value={snapshot?.totals.queued ?? 0} />
          <QueueMetric
            label="Waiting for quota"
            value={snapshot?.totals.waiting_for_quota ?? 0}
          />
        </section>

        <section className="grid gap-5 xl:grid-cols-3">
          {QUEUE_SECTIONS.map((section) => (
            <QueueSection
              key={section.key}
              title={section.title}
              emptyLabel={section.emptyLabel}
              tasks={groupedTasks[section.key]}
            />
          ))}
        </section>
      </div>
    </main>
  );
}

function QueueMetric({ label, value }: { label: string; value: number }) {
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

function QueueSection({
  title,
  emptyLabel,
  tasks,
}: {
  title: string;
  emptyLabel: string;
  tasks: AdminTaskQueueItem[];
}) {
  return (
    <Card className="rounded-[28px]">
      <CardContent className="px-5 py-5">
        <div className="flex items-center justify-between gap-3">
          <h2 className="text-[11px] font-semibold uppercase tracking-[0.22em] text-slate-500">
            {title}
          </h2>
          <Badge variant="secondary">{tasks.length}</Badge>
        </div>
        {tasks.length === 0 ? (
          <div className="mt-4 rounded-[20px] border border-dashed border-[var(--border)] bg-[var(--surface-strong)] px-4 py-6 text-sm text-slate-500">
            {emptyLabel}
          </div>
        ) : (
          <div className="mt-4 space-y-3">
            {tasks.map((task) => (
              <div
                key={`${task.kind}:${task.task_id}`}
                className="rounded-[20px] border border-[var(--border)] bg-[var(--surface-strong)] px-4 py-4"
              >
                <div className="flex items-start justify-between gap-3">
                  <div className="min-w-0">
                    <p className="truncate text-base font-semibold text-slate-900">
                      {task.label}
                    </p>
                    <p className="mt-1 text-xs uppercase tracking-[0.16em] text-slate-500">
                      {task.kind}
                    </p>
                  </div>
                  <Badge variant="secondary">{STATUS_LABELS[task.status]}</Badge>
                </div>
                <div className="mt-3 grid gap-2 text-sm text-slate-600">
                  <QueueDetail label="Owner" value={formatOwner(task)} />
                  <QueueDetail label="Queue" value={formatQueuePosition(task)} />
                  <QueueDetail label="Started" value={formatDateTime(task.started_at)} />
                  <QueueDetail
                    label="Quota"
                    value={formatQuotaBlock(task.blocked_vendor, task.blocked_until)}
                  />
                </div>
                <Button asChild type="button" size="sm" variant="secondary" className="mt-4">
                  <Link href={task.detail_path}>View task</Link>
                </Button>
              </div>
            ))}
          </div>
        )}
      </CardContent>
    </Card>
  );
}

function QueueDetail({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex items-center justify-between gap-3">
      <span className="text-xs uppercase tracking-[0.14em] text-slate-500">{label}</span>
      <span className="min-w-0 truncate text-right font-medium text-slate-800">{value}</span>
    </div>
  );
}

function formatOwner(task: AdminTaskQueueItem): string {
  if (!task.owner) {
    return task.owner_user_id ?? "Unowned";
  }
  return `${task.owner.display_name || task.owner.email} · ${task.owner.role}`;
}

function formatQueuePosition(task: AdminTaskQueueItem): string {
  return typeof task.queue_position === "number" ? `#${task.queue_position}` : "-";
}

function formatQuotaBlock(
  blocked_vendor: string | null,
  blockedUntil: string | null
): string {
  if (!blocked_vendor) {
    return "-";
  }
  const until = formatDateTime(blockedUntil);
  return until === "-" ? blocked_vendor : `${blocked_vendor} until ${until}`;
}

function formatDateTime(value: string | null): string {
  if (!value) {
    return "-";
  }
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) {
    return value;
  }
  return parsed.toLocaleString();
}
