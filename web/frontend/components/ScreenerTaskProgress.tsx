"use client";

import { useEffect, useMemo, useState } from "react";
import { usePreferences } from "@/components/PreferencesProvider";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { ScrollArea } from "@/components/ui/scroll-area";
import {
  cancelScreenerTask,
  getScreenerTask,
  subscribeToScreenerTask,
  type ProgressEvent,
  type ScreenerTask,
  type TaskStatus,
} from "@/lib/api";

interface ScreenerTaskProgressProps {
  taskId: string;
  onViewRun: (runId: string) => void;
  onTaskComplete: (runId: string | null) => void;
}

const STAGES = ["Features", "Filters", "Ranking", "Export"] as const;

export function ScreenerTaskProgress({
  taskId,
  onViewRun,
  onTaskComplete,
}: ScreenerTaskProgressProps) {
  const { t } = usePreferences();
  const [task, setTask] = useState<ScreenerTask | null>(null);
  const [events, setEvents] = useState<ProgressEvent[]>([]);
  const [canceling, setCanceling] = useState(false);
  const [streamError, setStreamError] = useState<string | null>(null);

  useEffect(() => {
    let isActive = true;
    let unsubscribe: (() => void) | undefined;

    const syncTask = async (replaceEvents = false) => {
      const nextTask = await getScreenerTask(taskId);
      if (!isActive) {
        return null;
      }
      const existingEvents = nextTask.progress_events ?? [];
      setTask(nextTask);
      if (replaceEvents) {
        setEvents(existingEvents);
      }
      if (nextTask.status === "completed") {
        onTaskComplete(nextTask.run_id);
      }
      return { nextTask, existingEvents };
    };

    const syncAndSubscribe = async () => {
      const snapshot = await syncTask(true);
      if (!snapshot || isTerminalTaskStatus(snapshot.nextTask.status)) {
        return;
      }

      unsubscribe = subscribeToScreenerTask(
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
                  run_id: null,
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
      await cancelScreenerTask(task.id);
      const nextTask = await getScreenerTask(task.id);
      setTask(nextTask);
      if (isTerminalTaskStatus(nextTask.status)) {
        onTaskComplete(nextTask.run_id);
      }
    } catch (error) {
      setStreamError(
        error instanceof Error
          ? error.message
          : t("screenerTask.error.cancel", "Unable to cancel screener task")
      );
    } finally {
      setCanceling(false);
    }
  };

  return (
    <main className="flex min-h-dvh flex-1 flex-col p-2 md:h-dvh md:overflow-hidden md:p-3 lg:p-4">
      <div className="w-full space-y-6">
        <Card className="fade-in rounded-[30px] bg-white/95">
          <CardContent className="p-6 md:p-8">
            <div className="flex flex-wrap items-start justify-between gap-4">
              <div>
                <p className="text-[11px] font-semibold uppercase tracking-[0.34em] text-[var(--primary)]">
                  {t("screenerTask.kicker", "Background Screener")}
                </p>
                <h1 className="font-heading mt-3 text-3xl font-bold tracking-tight text-slate-900">
                  {t("screenerTask.title", "Candidate Pool Build")}
                </h1>
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
                      ? t("screenerTask.canceling", "Canceling...")
                      : task?.status === "running"
                        ? t("screenerTask.terminate", "Terminate task")
                        : t("screenerTask.cancel", "Cancel task")}
                  </Button>
                ) : null}
                {task?.run_id ? (
                  <Button
                    type="button"
                    className="bg-[var(--accent)] hover:bg-[var(--accent)] hover:brightness-105"
                    onClick={() => onViewRun(task.run_id!)}
                  >
                    {t("screenerTask.viewResults", "View Results")}
                  </Button>
                ) : null}
              </div>
            </div>

            {task ? <ScreenerQueueNotice task={task} /> : null}

            <div className="mt-8 grid gap-3 md:grid-cols-4">
              {STAGES.map((stage) => {
                const state = task?.latest_progress?.stage_status?.[stage] ?? "not_started";
                return (
                  <div
                    key={stage}
                    className={`rounded-[24px] border p-4 ${
                      state === "completed"
                        ? "border-[rgba(46,118,83,0.2)] bg-[rgba(46,118,83,0.08)]"
                        : state === "processing"
                          ? "border-[rgba(28,56,83,0.18)] bg-[rgba(28,56,83,0.08)]"
                          : "border-[var(--border)] bg-[var(--surface-strong)]"
                    }`}
                  >
                    <p className="text-xs font-semibold uppercase tracking-[0.24em] text-slate-500">
                      {t(`screenerTask.stage.${stage}`, stage)}
                    </p>
                    <div className="mt-3">
                      <Badge variant="secondary">{t(`task.stage.${state}`, state)}</Badge>
                    </div>
                  </div>
                );
              })}
            </div>

            {streamError ? (
              <div className="mt-6 rounded-2xl border border-[rgba(28,56,83,0.14)] bg-[rgba(28,56,83,0.08)] px-4 py-3 text-sm text-slate-700">
                {streamError}
              </div>
            ) : null}

            <div className="mt-8 rounded-[24px] border border-[var(--border)] bg-[var(--surface-strong)] p-4">
              <div className="flex items-center justify-between gap-3">
                <h2 className="text-xs font-semibold uppercase tracking-[0.3em] text-slate-500">
                  {t("screenerTask.progressLog", "Progress Log")}
                </h2>
                <Badge variant="secondary">{eventLog.length}</Badge>
              </div>
              <ScrollArea className="mt-3 max-h-[20rem] pr-3">
                <div className="space-y-2 text-sm text-slate-600">
                  {eventLog.length === 0 ? (
                    <p>{t("screenerTask.noUpdates", "No progress updates yet.")}</p>
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

function TaskStatusBadge({ status }: { status: TaskStatus }) {
  const { t } = usePreferences();
  const classes =
    status === "completed"
      ? "border-[rgba(46,118,83,0.2)] bg-[rgba(46,118,83,0.1)] text-[var(--success)]"
      : status === "failed"
        ? "border-[rgba(163,53,53,0.2)] bg-[rgba(163,53,53,0.08)] text-[var(--danger)]"
        : status === "canceled"
          ? "border-[rgba(100,116,139,0.22)] bg-[rgba(100,116,139,0.1)] text-slate-600"
          : status === "waiting_for_quota"
            ? "border-[rgba(181,121,34,0.24)] bg-[rgba(181,121,34,0.1)] text-[rgb(146,91,22)]"
            : "border-[rgba(28,56,83,0.16)] bg-[rgba(28,56,83,0.08)] text-[var(--accent)]";

  return <Badge className={classes}>{t(`task.status.${status}`, status)}</Badge>;
}

function ScreenerQueueNotice({ task }: { task: ScreenerTask }) {
  const { t } = usePreferences();
  if (task.status === "running" && task.cancel_requested_at) {
    return (
      <div className="mt-6 rounded-2xl border border-[rgba(181,121,34,0.24)] bg-[rgba(181,121,34,0.08)] px-4 py-3 text-sm text-slate-700">
        {t(
          "screenerTask.cancelRequested",
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
      <div className="mt-6 rounded-2xl border border-[rgba(28,56,83,0.14)] bg-[rgba(28,56,83,0.07)] px-4 py-3 text-sm text-slate-700">
        {position}
      </div>
    );
  }

  if (task.status === "waiting_for_quota") {
    return (
      <div className="mt-6 rounded-2xl border border-[rgba(181,121,34,0.24)] bg-[rgba(181,121,34,0.08)] px-4 py-3 text-sm text-slate-700">
        {t(
          "task.waitingForQuota",
          ({ vendor, until }) =>
            `Waiting for ${vendor ?? "data source"} quota to recover${until ? ` around ${until}` : ""}.`,
          {
            vendor: task.blocked_vendor ?? undefined,
            until: formatDateTimeLabel(task.blocked_until),
          }
        )}
      </div>
    );
  }

  if (task.status === "canceled") {
    return (
      <div className="mt-6 rounded-2xl border border-[rgba(28,56,83,0.14)] bg-[rgba(28,56,83,0.08)] px-4 py-3 text-sm text-slate-700">
        {t("screenerTask.canceledFallback", "This screener task was canceled.")}
      </div>
    );
  }

  return null;
}

function formatDateTimeLabel(value: string | null | undefined): string | undefined {
  if (!value) {
    return undefined;
  }
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) {
    return value;
  }
  return parsed.toLocaleString();
}
