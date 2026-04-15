"use client";

import { useEffect, useMemo, useState } from "react";
import { usePreferences } from "@/components/PreferencesProvider";
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

    const syncTask = async () => {
      const nextTask = await getScreenerTask(taskId);
      if (!isActive) {
        return;
      }
      setTask(nextTask);
      if (nextTask.status === "completed") {
        onTaskComplete(nextTask.run_id);
      }
    };

    const unsubscribe = subscribeToScreenerTask(taskId, (event) => {
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
              run_id: null,
              error: null,
            }
      );
      if (event.status === "completed" || event.status === "failed") {
        void syncTask();
      }
    });

    void syncTask();
    return () => {
      isActive = false;
      unsubscribe();
    };
  }, [onTaskComplete, taskId]);

  const eventLog = useMemo(
    () => events.filter((event) => event.message).slice().reverse().slice(0, 10),
    [events]
  );

  return (
    <main className="flex min-h-[100vh] flex-1 flex-col p-2 md:h-screen md:overflow-hidden md:p-3 lg:p-4">
      <div className="w-full space-y-6">
        <section className="fade-in rounded-[30px] border border-[var(--border)] bg-white/95 p-6 shadow-[0_24px_60px_rgba(18,28,41,0.08)] md:p-8">
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
              <button
                type="button"
                className="interactive-button focus-ring rounded-full border border-[var(--accent)] bg-[var(--accent)] px-5 py-3 text-xs font-semibold uppercase tracking-[0.2em] text-white"
                onClick={() => onViewRun(task.run_id!)}
              >
                {t("screenerTask.viewResults", "View Results")}
              </button>
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
                  <p className="mt-2 text-sm font-semibold text-slate-800">
                    {t(`task.stage.${state}`, state)}
                  </p>
                </div>
              );
            })}
          </div>

          <div className="mt-8 rounded-[24px] border border-[var(--border)] bg-[var(--surface-strong)] p-4">
            <h2 className="text-xs font-semibold uppercase tracking-[0.3em] text-slate-500">
              {t("screenerTask.progressLog", "Progress Log")}
            </h2>
            <div className="mt-3 space-y-2 text-sm text-slate-600">
              {eventLog.length === 0 ? (
                <p>{t("screenerTask.noUpdates", "No progress updates yet.")}</p>
              ) : (
                eventLog.map((event, index) => (
                  <p key={`${event.timestamp}-${index}`}>{event.message}</p>
                ))
              )}
            </div>
          </div>
        </section>
      </div>
    </main>
  );
}
