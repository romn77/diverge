"use client";

import { useEffect, useMemo, useState } from "react";
import { usePreferences } from "@/components/PreferencesProvider";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { ScrollArea } from "@/components/ui/scroll-area";
import {
  cancelOpportunityTask,
  getOpportunityTask,
  subscribeToOpportunityTask,
  type OpportunityTask,
  type ProgressEvent,
  type TaskStatus,
} from "@/lib/api";

interface OpportunityTaskProgressProps {
  taskId: string;
  onViewRun: (runId: string) => void;
  onTaskComplete: (runId: string | null) => void;
}

const STAGES = ["Radar"] as const;

export function OpportunityTaskProgress({
  taskId,
  onViewRun,
  onTaskComplete,
}: OpportunityTaskProgressProps) {
  const { t } = usePreferences();
  const [task, setTask] = useState<OpportunityTask | null>(null);
  const [events, setEvents] = useState<ProgressEvent[]>([]);
  const [canceling, setCanceling] = useState(false);
  const [streamError, setStreamError] = useState<string | null>(null);

  useEffect(() => {
    let isActive = true;
    let unsubscribe: (() => void) | undefined;

    const syncTask = async (replaceEvents = false) => {
      const nextTask = await getOpportunityTask(taskId);
      if (!isActive) {
        return null;
      }
      const existingEvents = nextTask.progress_events ?? [];
      setTask(nextTask);
      if (replaceEvents) {
        setEvents(existingEvents);
      }
      if (nextTask.status === "completed") {
        onTaskComplete(getOpportunityRunId(nextTask));
      }
      return { nextTask, existingEvents };
    };

    const syncAndSubscribe = async () => {
      const snapshot = await syncTask(true);
      if (!snapshot || isTerminalTaskStatus(snapshot.nextTask.status)) {
        return;
      }

      unsubscribe = subscribeToOpportunityTask(
        taskId,
        (event) => {
          if (!isActive) {
            return;
          }
          setEvents((current) => [...current, event]);
          setTask((current) =>
            current
              ? { ...current, status: event.status, latest_progress: event }
              : {
                  id: taskId,
                  request_payload: null,
                  status: event.status,
                  latest_progress: event,
                  progress_events: [event],
                  result: null,
                  error: null,
                }
          );
          if (isTerminalTaskStatus(event.status)) {
            unsubscribe?.();
            unsubscribe = undefined;
            void syncTask();
          }
        },
        (error) => setStreamError(error.message),
        snapshot.existingEvents.length
      );
    };

    void syncAndSubscribe();
    return () => {
      isActive = false;
      unsubscribe?.();
    };
  }, [onTaskComplete, taskId]);

  const eventLog = useMemo(
    () => events.filter((event) => event.message).slice().reverse().slice(0, 10),
    [events]
  );
  const runId = task ? getOpportunityRunId(task) : null;
  const canCancelTask = task
    ? canCancelTaskStatus(task.status) && !task.cancel_requested_at
    : false;

  const handleCancelTask = async () => {
    if (!task || !canCancelTask) {
      return;
    }
    setCanceling(true);
    setStreamError(null);
    try {
      await cancelOpportunityTask(task.id);
      const nextTask = await getOpportunityTask(task.id);
      setTask(nextTask);
      if (isTerminalTaskStatus(nextTask.status)) {
        onTaskComplete(getOpportunityRunId(nextTask));
      }
    } catch (error) {
      setStreamError(
        error instanceof Error
          ? error.message
          : t("opportunityTask.error.cancel", "Unable to cancel opportunity task")
      );
    } finally {
      setCanceling(false);
    }
  };

  return (
    <main className="flex min-h-dvh flex-1 flex-col p-2 md:h-dvh md:overflow-hidden md:p-3 lg:p-4">
      <div className="w-full space-y-6">
        <Card className="viewer-frame fade-in">
          <CardContent className="p-6 md:p-8">
            <div className="flex flex-wrap items-start justify-between gap-4">
              <div>
                <p className="text-[11px] font-semibold uppercase tracking-[0.34em] text-[var(--primary)]">
                  {t("opportunityTask.kicker", "Background Radar")}
                </p>
                <h1 className="font-heading mt-3 text-3xl font-bold tracking-tight text-foreground">
                  {t("opportunityTask.title", "Opportunity Radar Run")}
                </h1>
                <p className="mt-2 text-sm text-muted-foreground">
                  {task ? formatTaskMeta(task, t) : t("common.loading", "Loading")}
                </p>
              </div>
              <div className="flex flex-wrap items-center gap-3">
                {task ? <TaskStatusBadge status={task.status} /> : null}
                {canCancelTask ? (
                  <Button
                    type="button"
                    variant="secondary"
                    disabled={canceling}
                    onClick={() => void handleCancelTask()}
                  >
                    {canceling
                      ? t("opportunityTask.canceling", "Canceling...")
                      : task?.status === "running"
                        ? t("opportunityTask.terminate", "Terminate task")
                        : t("opportunityTask.cancel", "Cancel task")}
                  </Button>
                ) : null}
                {runId ? (
                  <Button type="button" onClick={() => onViewRun(runId)}>
                    {t("opportunityTask.viewResults", "View Results")}
                  </Button>
                ) : null}
              </div>
            </div>

            {task ? <OpportunityQueueNotice task={task} /> : null}

            <div className="mt-8 grid gap-3 md:grid-cols-3">
              {STAGES.map((stage) => {
                const state = normalizeStageState(task?.latest_progress?.stage_status?.[stage]);
                return (
                  <div key={stage} className={`rounded-md border p-4 ${stageStatusClass(state)}`}>
                    <p className="text-xs font-semibold uppercase tracking-[0.24em] text-muted-foreground">
                      {t(`opportunityTask.stage.${stage}`, stage)}
                    </p>
                    <div className="mt-3">
                      <Badge variant="secondary">{t(`task.stage.${state}`, state)}</Badge>
                    </div>
                  </div>
                );
              })}
              <div className="rounded-md border border-[var(--border)] bg-[var(--surface)] p-4">
                <p className="text-xs font-semibold uppercase tracking-[0.24em] text-muted-foreground">
                  {t("opportunityTask.candidates", "Candidates")}
                </p>
                <p className="mt-3 text-xl font-bold text-foreground">
                  {String(task?.result?.candidate_count ?? 0)}
                </p>
              </div>
              <div className="rounded-md border border-[var(--border)] bg-[var(--surface)] p-4">
                <p className="text-xs font-semibold uppercase tracking-[0.24em] text-muted-foreground">
                  {t("opportunityTask.runId", "Run")}
                </p>
                <p className="mt-3 truncate text-sm font-semibold text-foreground">
                  {runId ?? "—"}
                </p>
              </div>
            </div>

            {streamError ? (
              <div className="mt-6 rounded-md border border-[var(--danger-border)] bg-[var(--danger-soft)] px-4 py-3 text-sm text-[var(--danger)]">
                {streamError}
              </div>
            ) : null}

            <div className="mt-8 rounded-md border border-[var(--border)] bg-[var(--surface-strong)] p-4">
              <div className="flex items-center justify-between gap-3">
                <h2 className="text-xs font-semibold uppercase tracking-[0.3em] text-muted-foreground">
                  {t("opportunityTask.progressLog", "Progress Log")}
                </h2>
                <Badge variant="secondary">{eventLog.length}</Badge>
              </div>
              <ScrollArea className="mt-3 max-h-[20rem] pr-3">
                <div className="space-y-2 text-sm text-muted-foreground">
                  {eventLog.length === 0 ? (
                    <p>{t("opportunityTask.noUpdates", "No progress updates yet.")}</p>
                  ) : (
                    eventLog.map((event, index) => (
                      <p key={`${event.timestamp}-${index}`}>{event.message}</p>
                    ))
                  )}
                </div>
              </ScrollArea>
            </div>
          </CardContent>
        </Card>
      </div>
    </main>
  );
}

function getOpportunityRunId(task: OpportunityTask): string | null {
  return task.result?.run_id ?? null;
}

function isTerminalTaskStatus(status: TaskStatus): boolean {
  return status === "completed" || status === "failed" || status === "canceled";
}

function canCancelTaskStatus(status: TaskStatus): boolean {
  return (
    status === "pending" ||
    status === "queued" ||
    status === "waiting_for_quota" ||
    status === "running"
  );
}

function normalizeStageState(value: unknown): "not_started" | "processing" | "completed" {
  if (value === "completed") {
    return "completed";
  }
  if (value === "processing" || value === "running" || value === "queued" || value === "pending") {
    return "processing";
  }
  return "not_started";
}

function stageStatusClass(state: "not_started" | "processing" | "completed"): string {
  if (state === "completed") {
    return "border-[rgba(46,118,83,0.2)] bg-[rgba(46,118,83,0.08)]";
  }
  if (state === "processing") {
    return "border-[rgba(28,56,83,0.18)] bg-[rgba(28,56,83,0.08)]";
  }
  return "border-[var(--border)] bg-[var(--surface)]";
}

function TaskStatusBadge({ status }: { status: TaskStatus }) {
  const { t } = usePreferences();
  const classes =
    status === "completed"
      ? "border-[rgba(46,118,83,0.2)] bg-[rgba(46,118,83,0.1)] text-[var(--success)]"
      : status === "failed"
        ? "border-[rgba(163,53,53,0.2)] bg-[rgba(163,53,53,0.08)] text-[var(--danger)]"
        : status === "canceled"
          ? "border-[rgba(100,116,139,0.22)] bg-[rgba(100,116,139,0.1)] text-muted-foreground"
          : "border-[rgba(28,56,83,0.16)] bg-[rgba(28,56,83,0.08)] text-[var(--accent)]";

  return <Badge className={classes}>{t(`task.status.${status}`, status)}</Badge>;
}

function OpportunityQueueNotice({ task }: { task: OpportunityTask }) {
  const { t } = usePreferences();
  if (task.status === "running" && task.cancel_requested_at) {
    return (
      <div className="mt-6 rounded-md border border-[rgba(181,121,34,0.24)] bg-[rgba(181,121,34,0.08)] px-4 py-3 text-sm text-foreground">
        {t(
          "opportunityTask.cancelRequested",
          "Termination requested. Running work will stop at the next safe step."
        )}
      </div>
    );
  }

  if (task.status === "queued" || task.status === "pending") {
    const position =
      typeof task.queue_position === "number"
        ? t("task.queuePosition", ({ position }) => `Queue position ${position}`, {
            position: task.queue_position,
          })
        : t("task.queuedWaiting", "Waiting for a worker slot.");
    return (
      <div className="mt-6 rounded-md border border-[rgba(28,56,83,0.14)] bg-[rgba(28,56,83,0.07)] px-4 py-3 text-sm text-foreground">
        {position}
      </div>
    );
  }

  if (task.status === "canceled") {
    return (
      <div className="mt-6 rounded-md border border-[rgba(28,56,83,0.14)] bg-[rgba(28,56,83,0.08)] px-4 py-3 text-sm text-foreground">
        {t("opportunityTask.canceledFallback", "This opportunity radar task was canceled.")}
      </div>
    );
  }

  return null;
}

function formatTaskMeta(
  task: OpportunityTask,
  t: ReturnType<typeof usePreferences>["t"]
): string {
  if (task.error) {
    return task.error;
  }
  if (task.latest_progress?.message) {
    return task.latest_progress.message;
  }
  const market = task.request_payload?.market ?? "cn";
  const tradeDate = task.request_payload?.trade_date ?? "latest";
  return t(
    "opportunityTask.meta",
    ({ market: marketLabel, tradeDate: dateLabel }) => `${marketLabel} · ${dateLabel}`,
    { market: market, tradeDate }
  );
}
