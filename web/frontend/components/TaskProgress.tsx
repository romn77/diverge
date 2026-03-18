"use client";

import { useEffect, useMemo, useState } from "react";
import {
  getTask,
  subscribeToTask,
  type ProgressEvent,
  type StageStatus,
  type Task,
} from "@/lib/api";

interface TaskProgressProps {
  taskId: string;
  onViewReport: (reportId: string) => void;
  onTaskComplete: (reportId: string | null) => void;
}

const STAGES = ["Analysts", "Research", "Trading", "Risk", "Portfolio"] as const;

export function TaskProgress({
  taskId,
  onViewReport,
  onTaskComplete,
}: TaskProgressProps) {
  const [task, setTask] = useState<Task | null>(null);
  const [events, setEvents] = useState<ProgressEvent[]>([]);
  const [loading, setLoading] = useState(true);
  const [streamError, setStreamError] = useState<string | null>(null);

  useEffect(() => {
    let isActive = true;

    const syncTask = async () => {
      const nextTask = await getTask(taskId);
      if (!isActive) {
        return;
      }
      setTask(nextTask);
      setLoading(false);
      if (nextTask.status === "completed") {
        onTaskComplete(nextTask.report_id);
      }
    };

    const ingestEvent = (event: ProgressEvent) => {
      if (!isActive) {
        return;
      }

      setEvents((current) => {
        const key = buildEventKey(event);
        if (current.some((item) => buildEventKey(item) === key)) {
          return current;
        }
        return [...current, event];
      });
      setTask((current) =>
        current
          ? { ...current, status: event.status, latest_progress: event }
          : {
              id: taskId,
              ticker: "Task",
              analysis_date: "",
              analysts: [],
              status: event.status,
              latest_progress: event,
              report_id: null,
              error: null,
            }
      );

      if (event.status === "completed" || event.status === "failed") {
        void syncTask();
      }
    };

    void syncTask().catch((error) => {
      if (isActive) {
        setStreamError(
          error instanceof Error ? error.message : "Unable to load task"
        );
        setLoading(false);
      }
    });

    const unsubscribe = subscribeToTask(
      taskId,
      ingestEvent,
      (error) => setStreamError(error.message)
    );

    return () => {
      isActive = false;
      unsubscribe();
    };
  }, [onTaskComplete, taskId]);

  const stageStatus = task?.latest_progress?.stage_status ?? {};
  const eventLog = useMemo(
    () =>
      events
        .filter((event) => event.message)
        .slice()
        .reverse()
        .slice(0, 12),
    [events]
  );

  if (loading) {
    return (
      <main className="flex min-h-[100vh] flex-1 flex-col p-2 md:h-screen md:overflow-hidden md:p-3 lg:p-4">
        <div className="w-full">
          <div className="fade-in rounded-[30px] border border-[var(--border)] bg-white/92 p-8 shadow-[0_24px_60px_rgba(18,28,41,0.08)]">
            Loading task progress...
          </div>
        </div>
      </main>
    );
  }

  return (
    <main className="flex min-h-[100vh] flex-1 flex-col p-2 md:h-screen md:overflow-hidden md:p-3 lg:p-4">
      <div className="w-full space-y-6">
        <section className="fade-in rounded-[30px] border border-[var(--border)] bg-white/95 p-6 shadow-[0_24px_60px_rgba(18,28,41,0.08)] md:p-8">
          <div className="flex flex-wrap items-start justify-between gap-4">
            <div>
              <p className="text-[11px] font-semibold uppercase tracking-[0.34em] text-[var(--primary)]">
                Background Task
              </p>
              <h1 className="font-heading mt-3 text-3xl font-bold tracking-tight text-slate-900">
                {task?.ticker ?? "New Analysis"}
              </h1>
              <p className="mt-2 text-sm leading-6 text-slate-600">
                {task?.analysis_date
                  ? `Tracking ${task.analysis_date} research flow across analyst, debate, trading, and portfolio stages.`
                  : "Tracking the live research pipeline."}
              </p>
            </div>

            <div className="flex flex-wrap items-center gap-3">
              <TaskStatusBadge status={task?.status ?? "pending"} />
              {task?.report_id ? (
                <button
                  type="button"
                  className="interactive-button focus-ring rounded-full border border-[var(--accent)] bg-[var(--accent)] px-5 py-3 text-xs font-semibold uppercase tracking-[0.2em] text-white"
                  onClick={() => onViewReport(task.report_id!)}
                >
                  View Report
                </button>
              ) : null}
            </div>
          </div>

          <div className="mt-8 grid gap-3 md:grid-cols-5">
            {STAGES.map((stage) => {
              const state = stageStatus[stage] ?? "not_started";
              return (
                <div
                  key={stage}
                  data-state={state}
                  className={`stage-card rounded-[24px] border p-4 ${
                    state === "completed"
                      ? "border-[rgba(46,118,83,0.2)] bg-[rgba(46,118,83,0.08)]"
                      : state === "processing"
                        ? "border-[rgba(28,56,83,0.18)] bg-[rgba(28,56,83,0.08)]"
                        : "border-[var(--border)] bg-[var(--surface-strong)]"
                  }`}
                >
                  <p className="text-xs font-semibold uppercase tracking-[0.24em] text-slate-500">
                    {stage}
                  </p>
                  <div className="mt-3 flex items-center gap-2">
                    <span
                      className={`inline-flex h-2.5 w-2.5 rounded-full ${
                        state === "completed"
                          ? "bg-[var(--success)]"
                          : state === "processing"
                            ? "progress-slide bg-[var(--accent)]"
                            : "bg-slate-300"
                      }`}
                    />
                    <span className="text-sm font-semibold text-slate-800">
                      {formatStageLabel(state)}
                    </span>
                  </div>
                </div>
              );
            })}
          </div>

          {task?.latest_progress?.current_agent ? (
            <p className="mt-6 text-sm text-slate-600">
              Current agent:{" "}
              <span className="font-semibold text-slate-900">
                {task.latest_progress.current_agent}
              </span>
            </p>
          ) : null}

          {task?.status === "failed" ? (
            <div className="mt-6 rounded-2xl border border-[rgba(163,53,53,0.2)] bg-[rgba(163,53,53,0.08)] px-4 py-3 text-sm text-[var(--danger)]">
              {task.error ?? "The analysis task failed."}
            </div>
          ) : null}

          {streamError && task?.status !== "failed" ? (
            <div className="mt-6 rounded-2xl border border-[rgba(28,56,83,0.14)] bg-[rgba(28,56,83,0.08)] px-4 py-3 text-sm text-slate-700">
              {streamError}
            </div>
          ) : null}
        </section>

        <section className="rounded-[30px] border border-[var(--border)] bg-white/95 p-6 shadow-[0_24px_60px_rgba(18,28,41,0.08)] md:p-8">
          <div className="flex items-center justify-between gap-3">
            <div>
              <p className="text-[11px] font-semibold uppercase tracking-[0.34em] text-[var(--primary)]">
                Event Log
              </p>
              <h2 className="font-heading mt-3 text-2xl font-bold tracking-tight text-slate-900">
                Live progress feed
              </h2>
            </div>
            <span className="rounded-full border border-[var(--border)] bg-[var(--surface-strong)] px-3 py-1 text-[11px] font-semibold uppercase tracking-[0.24em] text-slate-500">
              {eventLog.length} updates
            </span>
          </div>

          <div className="mt-6 space-y-3">
            {eventLog.length === 0 ? (
              <div className="rounded-[24px] border border-dashed border-[var(--border)] bg-[var(--surface-strong)] px-4 py-6 text-sm text-slate-600">
                Waiting for the first streamed update...
              </div>
            ) : (
              eventLog.map((event) => (
                <div
                  key={buildEventKey(event)}
                  className="rounded-[24px] border border-[var(--border)] bg-[var(--surface-strong)] px-4 py-4"
                >
                  <div className="flex flex-wrap items-center gap-3 text-[11px] font-semibold uppercase tracking-[0.24em] text-slate-500">
                    <span>{event.timestamp}</span>
                    {event.current_agent ? <span>{event.current_agent}</span> : null}
                  </div>
                  <p className="mt-2 text-sm leading-6 text-slate-700">
                    {event.message}
                  </p>
                </div>
              ))
            )}
          </div>
        </section>
      </div>
    </main>
  );
}

function buildEventKey(event: ProgressEvent): string {
  return `${event.timestamp}|${event.status}|${event.current_agent ?? ""}|${event.message ?? ""}`;
}

function formatStageLabel(state: StageStatus): string {
  if (state === "not_started") {
    return "Not started";
  }
  if (state === "processing") {
    return "Processing";
  }
  return "Completed";
}

function TaskStatusBadge({ status }: { status: Task["status"] }) {
  const classes =
    status === "completed"
      ? "border-[rgba(46,118,83,0.2)] bg-[rgba(46,118,83,0.1)] text-[var(--success)]"
      : status === "failed"
        ? "border-[rgba(163,53,53,0.2)] bg-[rgba(163,53,53,0.08)] text-[var(--danger)]"
        : "border-[rgba(28,56,83,0.16)] bg-[rgba(28,56,83,0.08)] text-[var(--accent)]";

  return (
    <span
      className={`inline-flex items-center rounded-full border px-4 py-2 text-xs font-semibold uppercase tracking-[0.2em] ${classes}`}
    >
      {status}
    </span>
  );
}
