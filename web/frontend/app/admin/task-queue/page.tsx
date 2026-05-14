"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { ExternalLink, RefreshCw, Trash2, XCircle } from "lucide-react";

import { useAuth } from "@/components/AuthProvider";
import {
  AdminConsolePage,
  AdminMetricCard,
  AdminMetricGrid,
  AdminNotice,
} from "@/components/admin/AdminConsolePage";
import { StatusPanel } from "@/components/workbench/StatusPanel";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { ConfirmDialog } from "@/components/ui/confirm-dialog";
import {
  ApiError,
  cancelDataSyncJob,
  createOhlcvSyncTask,
  deleteAdminTaskQueueItem,
  getDataSyncJob,
  listAdminTaskQueue,
  type AdminTaskQueueItem,
  type AdminTaskQueueResponse,
  type DataSyncTask,
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

const ACTIVE_DATA_SYNC_STATUSES = new Set<TaskStatus>([
  "pending",
  "queued",
  "waiting_for_quota",
  "running",
]);
const DATA_SYNC_REFRESH_INTERVAL_MS = 3000;
const DEFAULT_SYNC_DATE = new Date().toISOString().slice(0, 10);

type AdminQueueConfirmTarget =
  | {
      action: "cancel-data-sync";
      taskId: string;
      label: string;
    }
  | {
      action: "remove-stale";
      kind: AdminTaskQueueItem["kind"];
      taskId: string;
      label: string;
    };

export default function AdminTaskQueuePage() {
  const router = useRouter();
  const { authState, authStatus, refreshSession } = useAuth();
  const [snapshot, setSnapshot] = useState<AdminTaskQueueResponse | null>(null);
  const [selectedDataSyncJob, setSelectedDataSyncJob] = useState<DataSyncTask | null>(null);
  const [loadingDataSyncJob, setLoadingDataSyncJob] = useState<string | null>(null);
  const [syncMarket, setSyncMarket] = useState<"cn" | "us">("cn");
  const [syncAsOfDate, setSyncAsOfDate] = useState(DEFAULT_SYNC_DATE);
  const [syncSource, setSyncSource] = useState("tushare");
  const [creatingSync, setCreatingSync] = useState(false);
  const [confirmTarget, setConfirmTarget] = useState<AdminQueueConfirmTarget | null>(
    null
  );
  const [cancelingDataSyncJob, setCancelingDataSyncJob] = useState<string | null>(null);
  const [removingQueueItemId, setRemovingQueueItemId] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [pageError, setPageError] = useState<string | null>(null);

  const authEnabled = authState?.enabled ?? false;
  const shouldRedirectToLogin =
    authStatus === "ready" && authEnabled && !authState?.authenticated;
  const canLoad =
    authStatus === "ready" && authEnabled && Boolean(authState?.authenticated);
  const canManage = Boolean(authState?.permissions.includes("admin:settings"));

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

  const refreshSelectedDataSyncJob = useCallback(
    async (taskId: string, options: { silent?: boolean } = {}) => {
      if (!options.silent) {
        setLoadingDataSyncJob(taskId);
      }
      setPageError(null);
      try {
        setSelectedDataSyncJob(await getDataSyncJob(taskId));
      } catch (error) {
        if (!handleAuthBoundary(error)) {
          setPageError(
            error instanceof Error ? error.message : "Unable to load data sync job"
          );
        }
      } finally {
        if (!options.silent) {
          setLoadingDataSyncJob(null);
        }
      }
    },
    [handleAuthBoundary]
  );

  const inspectDataSyncJob = async (taskId: string) => {
    await refreshSelectedDataSyncJob(taskId);
  };

  const handleRefreshAll = async () => {
    await loadTaskQueue();
    if (selectedDataSyncJob) {
      await refreshSelectedDataSyncJob(selectedDataSyncJob.id, { silent: true });
    }
  };

  const handleCreateOhlcvSync = async () => {
    setCreatingSync(true);
    setPageError(null);
    try {
      const payload =
        syncMarket === "cn"
          ? {
              markets: ["cn"],
              as_of_date: syncAsOfDate,
              cn_data_source: syncSource,
              cn_data_source_fallbacks: [],
            }
          : {
              markets: ["us"],
              as_of_date: syncAsOfDate,
              us_data_source: syncSource,
              us_data_source_fallbacks: [],
            };
      const response = await createOhlcvSyncTask(payload);
      await loadTaskQueue();
      await refreshSelectedDataSyncJob(response.task_id, { silent: true });
    } catch (error) {
      if (!handleAuthBoundary(error)) {
        setPageError(error instanceof Error ? error.message : "Unable to start data sync");
      }
    } finally {
      setCreatingSync(false);
    }
  };

  const handleCancelDataSyncJob = (job: DataSyncTask) => {
    setConfirmTarget({
      action: "cancel-data-sync",
      taskId: job.id,
      label: `${job.sync_type} sync`,
    });
  };

  const handleRemoveStaleQueueItem = (
    kind: AdminTaskQueueItem["kind"],
    taskId: string,
    label: string
  ) => {
    setConfirmTarget({
      action: "remove-stale",
      kind,
      taskId,
      label,
    });
  };

  const handleConfirmQueueAction = async () => {
    if (!confirmTarget) {
      return;
    }

    setPageError(null);

    if (confirmTarget.action === "cancel-data-sync") {
      setCancelingDataSyncJob(confirmTarget.taskId);
      try {
        await cancelDataSyncJob(confirmTarget.taskId);
        await loadTaskQueue();
        await refreshSelectedDataSyncJob(confirmTarget.taskId, { silent: true });
        setConfirmTarget(null);
      } catch (error) {
        if (!handleAuthBoundary(error)) {
          setPageError(error instanceof Error ? error.message : "Unable to cancel data sync");
        }
      } finally {
        setCancelingDataSyncJob(null);
      }
      return;
    }

    const itemKey = `${confirmTarget.kind}:${confirmTarget.taskId}`;
    setRemovingQueueItemId(itemKey);
    try {
      await deleteAdminTaskQueueItem(confirmTarget.kind, confirmTarget.taskId);
      if (selectedDataSyncJob?.id === confirmTarget.taskId) {
        setSelectedDataSyncJob(null);
      }
      await loadTaskQueue();
      setConfirmTarget(null);
    } catch (error) {
      if (!handleAuthBoundary(error)) {
        setPageError(error instanceof Error ? error.message : "Unable to remove stale task");
      }
    } finally {
      setRemovingQueueItemId(null);
    }
  };

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

  useEffect(() => {
    if (!selectedDataSyncJob || !ACTIVE_DATA_SYNC_STATUSES.has(selectedDataSyncJob.status)) {
      return;
    }
    const intervalId = window.setInterval(() => {
      void refreshSelectedDataSyncJob(selectedDataSyncJob.id, { silent: true });
    }, DATA_SYNC_REFRESH_INTERVAL_MS);
    return () => window.clearInterval(intervalId);
  }, [refreshSelectedDataSyncJob, selectedDataSyncJob]);

  const isConfirmingQueueAction = Boolean(cancelingDataSyncJob || removingQueueItemId);
  const confirmIsRemoveStale = confirmTarget?.action === "remove-stale";

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
    <AdminConsolePage
      activeTab="task-queue"
      title="Task Queue"
      badges={<Badge variant="secondary">Operations</Badge>}
      actions={
        <>
          <Badge variant="secondary">Backend: {snapshot?.task_backend ?? "unknown"}</Badge>
          <Button
            type="button"
            variant="secondary"
            size="sm"
            onClick={() => void handleRefreshAll()}
          >
            <RefreshCw className="size-4" />
            Refresh
          </Button>
        </>
      }
    >

        {pageError ? (
          <AdminNotice>{pageError}</AdminNotice>
        ) : null}

        <section className="rounded-[14px] border border-[var(--border)] bg-white/90 px-4 py-3">
          <div className="flex flex-col gap-3 lg:flex-row lg:items-end lg:justify-between">
            <div>
              <h2 className="text-[10px] font-semibold uppercase tracking-[0.16em] text-slate-500">
                Manual data sync
              </h2>
              <p className="mt-1 text-xs text-slate-600">
                Start OHLCV sync from the admin queue.
              </p>
            </div>
            <div className="grid gap-3 sm:grid-cols-4 lg:min-w-[620px]">
              <label className="grid gap-1 text-xs font-semibold uppercase tracking-[0.16em] text-slate-500">
                Market
                <select
                  value={syncMarket}
                  onChange={(event) => {
                    const nextMarket = event.target.value as "cn" | "us";
                    setSyncMarket(nextMarket);
                    setSyncSource(nextMarket === "cn" ? "tushare" : "massive");
                  }}
                  className="h-10 rounded-[10px] border border-[var(--border)] bg-white px-3 text-sm normal-case tracking-normal text-slate-900"
                >
                  <option value="cn">CN</option>
                  <option value="us">US</option>
                </select>
              </label>
              <label className="grid gap-1 text-xs font-semibold uppercase tracking-[0.16em] text-slate-500">
                Source
                <select
                  value={syncSource}
                  onChange={(event) => setSyncSource(event.target.value)}
                  className="h-10 rounded-[10px] border border-[var(--border)] bg-white px-3 text-sm normal-case tracking-normal text-slate-900"
                >
                  {syncMarket === "cn" ? (
                    <>
                      <option value="tushare">Tushare</option>
                      <option value="akshare">AkShare</option>
                    </>
                  ) : (
                    <>
                      <option value="massive">Massive</option>
                      <option value="yfinance">Yahoo Finance</option>
                    </>
                  )}
                </select>
              </label>
              <label className="grid gap-1 text-xs font-semibold uppercase tracking-[0.16em] text-slate-500">
                As of
                <input
                  type="date"
                  value={syncAsOfDate}
                  onChange={(event) => setSyncAsOfDate(event.target.value)}
                  className="h-10 rounded-[10px] border border-[var(--border)] bg-white px-3 text-sm normal-case tracking-normal text-slate-900"
                />
              </label>
              <Button
                type="button"
                className="self-end"
                disabled={creatingSync || !syncAsOfDate}
                onClick={() => void handleCreateOhlcvSync()}
              >
                {creatingSync ? "Starting..." : "Start OHLCV sync"}
              </Button>
            </div>
          </div>
        </section>

        <AdminMetricGrid>
          <AdminMetricCard label="Active" value={snapshot?.totals.active ?? 0} />
          <AdminMetricCard label="Running" value={snapshot?.totals.running ?? 0} />
          <AdminMetricCard label="Queued" value={snapshot?.totals.queued ?? 0} />
          <AdminMetricCard
            label="Waiting for quota"
            value={snapshot?.totals.waiting_for_quota ?? 0}
          />
        </AdminMetricGrid>

        <section className="grid gap-3 xl:grid-cols-3">
          {QUEUE_SECTIONS.map((section) => (
            <QueueSection
              key={section.key}
              title={section.title}
              emptyLabel={section.emptyLabel}
              tasks={groupedTasks[section.key]}
              selectedDataSyncTaskId={selectedDataSyncJob?.id ?? null}
              loadingDataSyncTaskId={loadingDataSyncJob}
              removingQueueItemId={removingQueueItemId}
              onInspectDataSync={inspectDataSyncJob}
              onRemoveStale={handleRemoveStaleQueueItem}
            />
          ))}
        </section>

        <DataSyncDetails
          job={selectedDataSyncJob}
          loadingTaskId={loadingDataSyncJob}
          cancelingTaskId={cancelingDataSyncJob}
          onCancel={handleCancelDataSyncJob}
        />

        <ConfirmDialog
          open={confirmTarget !== null}
          title={confirmIsRemoveStale ? "Remove stale queue record" : "Cancel data sync task"}
          description={
            confirmIsRemoveStale
              ? "Remove this stale queue record? This only clears an orphaned admin queue row. It does not delete reports or task artifacts."
              : "Running work stops at the next safe step."
          }
          details={confirmTarget ? `${confirmTarget.label} - ${confirmTarget.taskId}` : null}
          confirmLabel={confirmIsRemoveStale ? "Remove record" : "Cancel task"}
          confirmingLabel={confirmIsRemoveStale ? "Removing" : "Canceling"}
          cancelLabel={confirmIsRemoveStale ? "Keep record" : "Keep running"}
          isConfirming={isConfirmingQueueAction}
          onConfirm={() => void handleConfirmQueueAction()}
          onOpenChange={(open) => {
            if (!open && !isConfirmingQueueAction) {
              setConfirmTarget(null);
            }
          }}
        />
    </AdminConsolePage>
  );
}

function QueueSection({
  title,
  emptyLabel,
  tasks,
  selectedDataSyncTaskId,
  loadingDataSyncTaskId,
  removingQueueItemId,
  onInspectDataSync,
  onRemoveStale,
}: {
  title: string;
  emptyLabel: string;
  tasks: AdminTaskQueueItem[];
  selectedDataSyncTaskId: string | null;
  loadingDataSyncTaskId: string | null;
  removingQueueItemId: string | null;
  onInspectDataSync: (taskId: string) => void;
  onRemoveStale: (
    kind: AdminTaskQueueItem["kind"],
    taskId: string,
    label: string
  ) => void;
}) {
  return (
    <Card className="rounded-[14px]">
      <CardContent className="px-3 py-3">
        <div className="flex items-center justify-between gap-3">
          <h2 className="text-[10px] font-semibold uppercase tracking-[0.16em] text-slate-500">
            {title}
          </h2>
          <Badge variant="secondary">{tasks.length}</Badge>
        </div>
        {tasks.length === 0 ? (
          <div className="mt-2 rounded-[12px] border border-dashed border-[var(--border)] bg-[var(--surface-strong)] px-3 py-4 text-xs text-slate-500">
            {emptyLabel}
          </div>
        ) : (
          <div className="mt-2 space-y-1.5">
            {tasks.map((task) => (
              <div
                key={`${task.kind}:${task.task_id}`}
                className={`rounded-[12px] border px-3 py-2 ${
                  task.kind === "data_sync" && selectedDataSyncTaskId === task.task_id
                    ? "border-[rgba(47,111,78,0.28)] bg-[rgba(47,111,78,0.08)]"
                    : "border-[var(--border)] bg-[var(--surface-strong)]"
                }`}
              >
                <div className="grid gap-2 xl:grid-cols-[minmax(0,1.1fr)_auto]">
                  <div className="min-w-0">
                    <p className="truncate text-sm font-semibold text-slate-900">
                      {task.label}
                    </p>
                    <div className="mt-1 flex flex-wrap items-center gap-1.5">
                      <span className="text-[10px] uppercase tracking-[0.14em] text-slate-500">
                        {task.kind}
                      </span>
                      <Badge variant="secondary">{STATUS_LABELS[task.status]}</Badge>
                      {task.stale ? <Badge variant="destructive">Stale</Badge> : null}
                    </div>
                  </div>
                  <div className="flex flex-wrap items-start gap-1.5 xl:justify-end">
                    {task.stale ? (
                      <Button
                        type="button"
                        size="sm"
                        variant="secondary"
                        className="h-8 px-3 text-[10px]"
                        disabled={removingQueueItemId === `${task.kind}:${task.task_id}`}
                        onClick={() => onRemoveStale(task.kind, task.task_id, task.label)}
                      >
                        <Trash2 className="size-3.5" />
                        {removingQueueItemId === `${task.kind}:${task.task_id}`
                          ? "Removing"
                          : "Remove"}
                      </Button>
                    ) : task.kind === "data_sync" ? (
                      <Button
                        type="button"
                        size="sm"
                        variant="secondary"
                        className="h-8 px-3 text-[10px]"
                        onClick={() => onInspectDataSync(task.task_id)}
                      >
                        {loadingDataSyncTaskId === task.task_id ? "Loading" : "Inspect"}
                      </Button>
                    ) : (
                      <Button
                        asChild
                        type="button"
                        size="sm"
                        variant="secondary"
                        className="h-8 px-3 text-[10px]"
                      >
                        <Link href={task.detail_path}>
                          <ExternalLink className="size-3.5" />
                          Open
                        </Link>
                      </Button>
                    )}
                  </div>
                </div>
                <div className="mt-2 grid gap-x-3 gap-y-1 text-xs text-slate-600 sm:grid-cols-2">
                  <QueueDetail label="Owner" value={formatOwner(task)} />
                  <QueueDetail label="Queue" value={formatQueuePosition(task)} />
                  <QueueDetail label="Started" value={formatDateTime(task.started_at)} />
                  <QueueDetail
                    label="Quota"
                    value={formatQuotaBlock(task.blocked_vendor, task.blocked_until)}
                  />
                </div>
              </div>
            ))}
          </div>
        )}
      </CardContent>
    </Card>
  );
}

function DataSyncDetails({
  job,
  loadingTaskId,
  cancelingTaskId,
  onCancel,
}: {
  job: DataSyncTask | null;
  loadingTaskId: string | null;
  cancelingTaskId: string | null;
  onCancel: (job: DataSyncTask) => void;
}) {
  const canCancel =
    job &&
    !job.cancel_requested_at &&
    (job.status === "pending" ||
      job.status === "queued" ||
      job.status === "waiting_for_quota" ||
      job.status === "running");
  return (
    <Card className="rounded-[18px]">
      <CardContent className="grid gap-4 px-4 py-4">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div>
            <h2 className="text-[11px] font-semibold uppercase tracking-[0.22em] text-slate-500">
              Data Sync Details
            </h2>
            <p className="mt-1 text-sm text-slate-600">
              Detail endpoint payload for data_sync tasks: latest_progress, progress_events, result, and error.
            </p>
          </div>
          <div className="flex items-center gap-2">
            {job ? <Badge variant={dataSyncStatusVariant(job.status)}>{job.status}</Badge> : null}
            {canCancel ? (
              <Button
                type="button"
                size="sm"
                variant="secondary"
                disabled={cancelingTaskId === job.id}
                onClick={() => onCancel(job)}
              >
                <XCircle className="size-4" />
                {cancelingTaskId === job.id
                  ? "Canceling..."
                  : job.status === "running"
                    ? "Terminate"
                    : "Cancel"}
              </Button>
            ) : null}
          </div>
        </div>

        {job ? (
          <div className="grid gap-4">
            <div className="grid gap-2 rounded-[14px] border border-[var(--border)] bg-[var(--surface-strong)] px-3 py-3 text-xs text-slate-600 md:grid-cols-4">
              <QueueDetail label="Task" value={job.id} />
              <QueueDetail label="Type" value={job.sync_type} />
              <QueueDetail label="Started" value={formatDateTime(job.started_at ?? null)} />
              <QueueDetail label="Events" value={`${job.progress_events.length}`} />
            </div>
            <div className="grid gap-3 lg:grid-cols-2">
              <PayloadBlock label="latest_progress" value={job.latest_progress} />
              <PayloadBlock label="progress_events" value={job.progress_events.slice(-8)} />
              <PayloadBlock label="result" value={job.result} />
              <PayloadBlock label="error" value={job.error} />
            </div>
          </div>
        ) : (
          <div className="rounded-[14px] border border-dashed border-[var(--border)] bg-[var(--surface-strong)] px-4 py-6 text-sm text-slate-500">
            {loadingTaskId
              ? "Loading data sync details..."
              : "Select a data_sync task from the queue to inspect progress, result, or failure details."}
          </div>
        )}
      </CardContent>
    </Card>
  );
}

function PayloadBlock({ label, value }: { label: string; value: unknown }) {
  return (
    <div>
      <p className="text-[11px] font-semibold uppercase tracking-[0.18em] text-slate-500">
        {label}
      </p>
      <pre className="mt-2 max-h-44 overflow-auto rounded-[12px] border border-[var(--border)] bg-white p-3 text-[11px] leading-5 text-slate-700">
        {formatJsonPayload(value)}
      </pre>
    </div>
  );
}

function formatJsonPayload(value: unknown): string {
  if (value === null || value === undefined) {
    return "-";
  }
  return JSON.stringify(value, null, 2);
}

function dataSyncStatusVariant(
  status: string
): "secondary" | "success" | "destructive" | "outline" {
  if (status === "completed") {
    return "success";
  }
  if (status === "failed" || status === "canceled") {
    return "destructive";
  }
  if (status === "running" || status === "queued" || status === "pending") {
    return "secondary";
  }
  return "outline";
}

function QueueDetail({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex min-w-0 items-center justify-between gap-2">
      <span className="text-[10px] uppercase tracking-[0.12em] text-slate-500">
        {label}
      </span>
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
