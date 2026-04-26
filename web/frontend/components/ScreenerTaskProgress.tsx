"use client";

import { useEffect, useMemo, useState } from "react";
import { usePreferences } from "@/components/PreferencesProvider";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { ScrollArea } from "@/components/ui/scroll-area";
import {
  getScreenerTask,
  subscribeToScreenerTask,
  type ProgressEvent,
  type ScreenerTask,
} from "@/lib/api";

interface ScreenerTaskProgressProps {
  taskId: string;
  onViewRun: (runId: string) => void;
  onTaskComplete: (runId: string | null) => void;
}

const STAGES = ["Universe", "History", "Features", "Filters", "Ranking", "Export"] as const;

export function ScreenerTaskProgress({
  taskId,
  onViewRun,
  onTaskComplete,
}: ScreenerTaskProgressProps) {
  const { t } = usePreferences();
  const [task, setTask] = useState<ScreenerTask | null>(null);
  const [events, setEvents] = useState<ProgressEvent[]>([]);

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
      if (!snapshot || snapshot.nextTask.status === "completed" || snapshot.nextTask.status === "failed") {
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
          if (event.status === "completed" || event.status === "failed") {
            unsubscribe?.();
            unsubscribe = undefined;
            void syncTask();
          }
        },
        undefined,
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

  return (
    <main className="flex min-h-[100vh] flex-1 flex-col p-2 md:h-screen md:overflow-hidden md:p-3 lg:p-4">
      <div className="w-full space-y-6">
        <Card className="fade-in rounded-[30px] bg-white/95">
          <CardContent className="p-6 md:p-8">
            <div className="flex items-start justify-between gap-4">
              <div>
                <p className="text-[11px] font-semibold uppercase tracking-[0.34em] text-[var(--primary)]">
                  {t("screenerTask.kicker", "Background Screener")}
                </p>
                <h1 className="font-heading mt-3 text-3xl font-bold tracking-tight text-slate-900">
                  {t("screenerTask.title", "Candidate Pool Build")}
                </h1>
              </div>
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

            <div className="mt-8 grid gap-3 md:grid-cols-6">
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
