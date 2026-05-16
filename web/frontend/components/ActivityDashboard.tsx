"use client";

import Link from "next/link";
import { useState } from "react";
import { Trash2, XCircle } from "lucide-react";
import { usePreferences } from "@/components/PreferencesProvider";
import { useWorkbench } from "@/components/WorkbenchProvider";
import { MetricCard } from "@/components/workbench/MetricCard";
import { PageHeader } from "@/components/workbench/PageHeader";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import {
  cancelOpportunityTask,
  cancelScreenerTask,
  cancelTask,
  deleteScreenerTask,
  deleteTask,
  type JournalReviewTask,
  type OpportunityTask,
  type ScreenerTask,
  type Task,
} from "@/lib/api";
import {
  buildHomeHref,
  buildOpportunityTaskHref,
  buildScreenerHref,
  buildScreenerTaskHref,
  buildTaskHref,
} from "@/lib/workbenchRoutes";

type TaskActionTarget = {
  action: "cancel" | "delete";
  kind: "analysis" | "screener" | "opportunity";
  taskId: string;
  label: string;
  meta: string;
};

export function ActivityDashboard() {
  const { t } = usePreferences();
  const [taskActionTarget, setTaskActionTarget] = useState<TaskActionTarget | null>(
    null
  );
  const [isSubmittingTaskAction, setIsSubmittingTaskAction] = useState(false);
  const {
    activeJournalReviewTasks,
    activeOpportunityTasks,
    activeScreenerTasks,
    activeTasks,
    journalReviewTasks,
    refreshOpportunityTasks,
    refreshScreenerTasks,
    refreshTasks,
    screenerTasks,
    tasks,
  } = useWorkbench();
  const totalActive =
    activeTasks.length +
    activeScreenerTasks.length +
    activeOpportunityTasks.length +
    activeJournalReviewTasks.length;
  const failedTasks = tasks.filter((task) => task.status === "failed" || task.status === "canceled");
  const failedScreenerTasks = screenerTasks.filter(
    (task) => task.status === "failed" || task.status === "canceled"
  );

  const requestDeleteTask = (task: Task) => {
    setTaskActionTarget({
      action: "delete",
      kind: "analysis",
      taskId: task.id,
      label: task.ticker,
      meta: task.error ?? task.analysis_date,
    });
  };

  const requestDeleteScreenerTask = (task: ScreenerTask) => {
    setTaskActionTarget({
      action: "delete",
      kind: "screener",
      taskId: task.id,
      label:
        task.request_payload?.markets.join(", ") ||
        t("activity.candidatePoolBuild", "Candidate pool build"),
      meta:
        task.error ??
        task.request_payload?.as_of_date ??
        t("activity.awaitingUpdate", "Awaiting next update"),
    });
  };

  const requestCancelTask = (task: Task) => {
    setTaskActionTarget({
      action: "cancel",
      kind: "analysis",
      taskId: task.id,
      label: task.ticker,
      meta: formatAnalysisTaskMeta(task, t),
    });
  };

  const requestCancelScreenerTask = (task: ScreenerTask) => {
    setTaskActionTarget({
      action: "cancel",
      kind: "screener",
      taskId: task.id,
      label:
        task.request_payload?.markets.join(", ") ||
        t("activity.candidatePoolBuild", "Candidate pool build"),
      meta: formatScreenerTaskMeta(task, t),
    });
  };

  const requestCancelOpportunityTask = (task: OpportunityTask) => {
    setTaskActionTarget({
      action: "cancel",
      kind: "opportunity",
      taskId: task.id,
      label:
        task.request_payload?.trade_date ||
        task.result?.run_id ||
        t("activity.opportunityRadarRun", "Opportunity radar run"),
      meta: formatOpportunityTaskMeta(task, t),
    });
  };

  const handleConfirmTaskAction = async () => {
    if (!taskActionTarget) {
      return;
    }
    setIsSubmittingTaskAction(true);
    try {
      if (taskActionTarget.action === "delete") {
        if (taskActionTarget.kind === "analysis") {
          await deleteTask(taskActionTarget.taskId);
          await refreshTasks();
        } else if (taskActionTarget.kind === "screener") {
          await deleteScreenerTask(taskActionTarget.taskId);
          await refreshScreenerTasks();
        }
      } else if (taskActionTarget.kind === "analysis") {
        await cancelTask(taskActionTarget.taskId);
        await refreshTasks();
      } else if (taskActionTarget.kind === "screener") {
        await cancelScreenerTask(taskActionTarget.taskId);
        await refreshScreenerTasks();
      } else {
        await cancelOpportunityTask(taskActionTarget.taskId);
        await refreshOpportunityTasks();
      }
      setTaskActionTarget(null);
    } finally {
      setIsSubmittingTaskAction(false);
    }
  };

  const dialogIsDelete = taskActionTarget?.action === "delete";
  const dialogTitle = dialogIsDelete
    ? t("activity.deleteTaskDialogTitle", "Delete task record")
    : t("activity.cancelTaskDialogTitle", "Cancel task");
  const dialogDescription = dialogIsDelete
    ? t(
        "activity.deleteTaskDialogDescription",
        "This removes only the task record. Reports, caches, and other jobs are kept."
      )
    : t(
        "activity.cancelTaskDialogDescription",
        "Running work will stop at the next safe step."
      );
  const dialogCancelLabel = dialogIsDelete
    ? t("activity.keepTaskRecord", "Keep record")
    : t("activity.keepTaskRunning", "Keep running");
  const dialogConfirmLabel = dialogIsDelete
    ? t("activity.confirmDeleteTask", "Delete record")
    : t("activity.confirmCancelTask", "Cancel task");

  return (
    <main className="workbench-page-shell flex min-h-dvh flex-1 flex-col">
      <div className="workbench-content-frame space-y-6">
        <PageHeader
          eyebrow={t("sidebar.nav.activity", "Activity")}
          title={t("activity.title", "Background work")}
          actions={
            <>
              <Button asChild variant="secondary">
                <Link href={buildHomeHref()}>{t("sidebar.nav.analysis", "Analysis")}</Link>
              </Button>
              <Button asChild variant="secondary">
                <Link href={buildScreenerHref()}>{t("sidebar.nav.screener", "Screener")}</Link>
              </Button>
            </>
          }
        >
          <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-5">
            <ActivityMetric
              label={t("activity.metric.total", "Total Active")}
              value={`${totalActive}`}
              meta={t("activity.metric.totalMeta", "Combined background jobs")}
            />
            <ActivityMetric
              label={t("activity.metric.analysis", "Analysis Jobs")}
              value={`${activeTasks.length}`}
              meta={t("activity.metric.analysisMeta", "Research tasks in flight")}
            />
            <ActivityMetric
              label={t("activity.metric.screener", "Screener Jobs")}
              value={`${activeScreenerTasks.length}`}
              meta={t("activity.metric.screenerMeta", "Candidate builds in flight")}
            />
            <ActivityMetric
              label={t("activity.metric.opportunity", "Radar Jobs")}
              value={`${activeOpportunityTasks.length}`}
              meta={t("activity.metric.opportunityMeta", "Opportunity radar runs")}
            />
            <ActivityMetric
              label={t("activity.metric.journal", "Journal AI Reviews")}
              value={`${activeJournalReviewTasks.length}`}
              meta={t("activity.metric.journalMeta", "Trade review generation")}
            />
          </div>
        </PageHeader>

        <section className="grid gap-6 xl:grid-cols-2">
          <ActivityQueueSection
            title={t("activity.analysisTasks", "Analysis tasks")}
            emptyLabel={t("activity.noAnalysisJobs", "No active analysis jobs.")}
            items={activeTasks.map((task) => ({
              href: buildTaskHref(task.id),
              label: task.ticker,
              meta: formatAnalysisTaskMeta(task, t),
              status: t(`task.status.${task.status}`, task.status),
              cancelLabel: canCancelTask(task)
                ? t("activity.cancelTask", "Cancel task")
                : undefined,
              onCancel: canCancelTask(task)
                ? () => requestCancelTask(task)
                : undefined,
            }))}
          />
          <ActivityQueueSection
            title={t("activity.failedAnalysisTasks", "Failed analysis tasks")}
            emptyLabel={t("activity.noFailedAnalysisJobs", "No failed analysis jobs.")}
            items={failedTasks.map((task) => ({
              href: buildTaskHref(task.id),
              label: task.ticker,
              meta: task.error ?? task.analysis_date,
              status: t(`task.status.${task.status}`, task.status),
              deleteLabel:
                task.status === "failed"
                  ? t("activity.deleteFailedTask", "Delete failed task")
                  : undefined,
              onDelete:
                task.status === "failed"
                  ? () => requestDeleteTask(task)
                  : undefined,
            }))}
          />
          <ActivityQueueSection
            title={t("activity.screenerTasks", "Screener tasks")}
            emptyLabel={t("activity.noScreenerJobs", "No active screener jobs.")}
            items={activeScreenerTasks.map((task) => ({
              href: buildScreenerTaskHref(task.id),
              label:
                task.request_payload?.markets.join(", ") ||
                t("activity.candidatePoolBuild", "Candidate pool build"),
              meta:
                formatScreenerTaskMeta(task, t),
              status: t(`task.status.${task.status}`, task.status),
              cancelLabel: canCancelTask(task)
                ? t("activity.cancelTask", "Cancel task")
                : undefined,
              onCancel: canCancelTask(task)
                ? () => requestCancelScreenerTask(task)
                : undefined,
            }))}
          />
          <ActivityQueueSection
            title={t("activity.opportunityTasks", "Opportunity radar tasks")}
            emptyLabel={t(
              "activity.noOpportunityJobs",
              "No active opportunity radar jobs."
            )}
            items={activeOpportunityTasks.map((task) => ({
              href: buildOpportunityTaskHref(task.id),
              label:
                task.request_payload?.trade_date ||
                task.result?.run_id ||
                t("activity.opportunityRadarRun", "Opportunity radar run"),
              meta: formatOpportunityTaskMeta(task, t),
              status: t(`task.status.${task.status}`, task.status),
              cancelLabel: canCancelTask(task)
                ? t("activity.cancelTask", "Cancel task")
                : undefined,
              onCancel: canCancelTask(task)
                ? () => requestCancelOpportunityTask(task)
                : undefined,
            }))}
          />
          <ActivityQueueSection
            title={t("activity.journalReviewTasks", "Journal AI reviews")}
            emptyLabel={t(
              "activity.noJournalReviewJobs",
              "No journal AI review activity yet."
            )}
            items={journalReviewTasks.slice(0, 8).map((task) => ({
              href: "/journal",
              label:
                task.request_payload?.ticker ||
                t("activity.tradeReviewGeneration", "Trade review generation"),
              meta: formatJournalReviewTaskMeta(task, t),
              status: t(`task.status.${task.status}`, task.status),
            }))}
          />
          <ActivityQueueSection
            title={t("activity.failedScreenerTasks", "Failed screener tasks")}
            emptyLabel={t("activity.noFailedScreenerJobs", "No failed screener jobs.")}
            items={failedScreenerTasks.map((task) => ({
              href: buildScreenerTaskHref(task.id),
              label:
                task.request_payload?.markets.join(", ") ||
                t("activity.candidatePoolBuild", "Candidate pool build"),
              meta:
                task.error ??
                task.request_payload?.as_of_date ??
                t("activity.awaitingUpdate", "Awaiting next update"),
              status: t(`task.status.${task.status}`, task.status),
              deleteLabel:
                task.status === "failed"
                  ? t("activity.deleteFailedTask", "Delete failed task")
                  : undefined,
              onDelete:
                task.status === "failed"
                  ? () => requestDeleteScreenerTask(task)
                  : undefined,
            }))}
          />
        </section>
      </div>
      <Dialog
        open={taskActionTarget !== null}
        onOpenChange={(open) => {
          if (!open && !isSubmittingTaskAction) {
            setTaskActionTarget(null);
          }
        }}
      >
        <DialogContent className="w-[calc(100vw-2rem)] max-w-none sm:w-[34rem]">
          <DialogHeader className="pr-12">
            <DialogTitle className="text-2xl">{dialogTitle}</DialogTitle>
            <DialogDescription>{dialogDescription}</DialogDescription>
          </DialogHeader>
          {taskActionTarget ? (
            <div className="min-w-0 rounded-[22px] border border-[var(--border)] bg-[var(--surface)] px-4 py-3">
              <p className="truncate text-sm font-semibold text-slate-900">
                {taskActionTarget.label}
              </p>
              <p className="mt-1 truncate text-xs uppercase tracking-[0.14em] text-slate-500">
                {taskActionTarget.meta}
              </p>
            </div>
          ) : null}
          <DialogFooter>
            <Button
              type="button"
              variant="secondary"
              disabled={isSubmittingTaskAction}
              onClick={() => setTaskActionTarget(null)}
            >
              {dialogCancelLabel}
            </Button>
            <Button
              type="button"
              variant="destructive"
              disabled={isSubmittingTaskAction}
              onClick={() => void handleConfirmTaskAction()}
            >
              {dialogConfirmLabel}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </main>
  );
}

function ActivityMetric({
  label,
  value,
  meta,
}: {
  label: string;
  value: string;
  meta: string;
}) {
  return <MetricCard label={label} value={value} meta={meta} />;
}

function ActivityQueueSection({
  title,
  emptyLabel,
  items,
}: {
  title: string;
  emptyLabel: string;
  items: Array<{
    href: string;
    label: string;
    meta: string;
    status: string;
    deleteLabel?: string;
    onDelete?: () => void;
    cancelLabel?: string;
    onCancel?: () => void;
  }>;
}) {
  return (
    <Card className="card-surface rounded-[28px]">
      <CardContent className="px-6 py-6">
      <div className="flex items-start justify-between gap-4">
        <div>
          <p className="text-[11px] font-semibold uppercase tracking-[0.2em] text-slate-500">
            {title}
          </p>
        </div>
        <Badge variant="secondary" className="text-slate-500">
          {items.length}
        </Badge>
      </div>

      {items.length === 0 ? (
        <div className="mt-5 rounded-[24px] border border-dashed border-[var(--border)] bg-[var(--surface-strong)] px-5 py-8 text-sm text-slate-500">
          {emptyLabel}
        </div>
      ) : (
        <div className="mt-5 space-y-3">
          {items.map((item) => (
            <div
              key={`${item.href}-${item.label}`}
              className="group list-item-surface flex items-center justify-between gap-4 rounded-[24px] border border-[var(--border)] bg-white/88 px-4 py-4 hover:border-[var(--primary)]"
            >
              <Link href={item.href} className="min-w-0 flex-1">
                <p className="truncate text-base font-semibold text-slate-900">{item.label}</p>
                <p className="mt-1 truncate text-xs uppercase tracking-[0.16em] text-slate-500">
                  {item.meta}
                </p>
              </Link>
              <div className="flex shrink-0 items-center gap-2">
                <Badge variant="secondary">
                  {item.status}
                </Badge>
                {item.onDelete ? (
                  <Button
                    type="button"
                    variant="ghost"
                    size="icon"
                    aria-label={item.deleteLabel}
                    title={item.deleteLabel}
                    className="size-8 text-[var(--danger)] hover:bg-[rgba(163,53,53,0.08)] hover:text-[var(--danger)]"
                    onClick={(event) => {
                      event.preventDefault();
                      event.stopPropagation();
                      item.onDelete?.();
                    }}
                  >
                    <Trash2 className="size-4" />
                  </Button>
                ) : null}
                {item.onCancel ? (
                  <Button
                    type="button"
                    variant="ghost"
                    size="icon"
                    aria-label={item.cancelLabel}
                    title={item.cancelLabel}
                    className="size-8 text-slate-500 hover:bg-[rgba(28,56,83,0.08)] hover:text-[var(--accent)]"
                    onClick={(event) => {
                      event.preventDefault();
                      event.stopPropagation();
                      item.onCancel?.();
                    }}
                  >
                    <XCircle className="size-4" />
                  </Button>
                ) : null}
              </div>
            </div>
          ))}
        </div>
      )}
      </CardContent>
    </Card>
  );
}

function canCancelTask(task: Task | ScreenerTask | OpportunityTask): boolean {
  if (task.cancel_requested_at) {
    return false;
  }
  return (
    task.status === "pending" ||
    task.status === "queued" ||
    task.status === "waiting_for_quota" ||
    task.status === "running"
  );
}

function formatAnalysisTaskMeta(
  task: Task,
  t: ReturnType<typeof usePreferences>["t"]
): string {
  if (task.status === "queued" || task.status === "pending") {
    return formatQueueMeta(task.queue_position, t);
  }
  if (task.status === "waiting_for_quota") {
    return formatQuotaMeta(task.blocked_vendor, task.blocked_until, t);
  }
  return task.latest_progress?.current_agent ?? task.analysis_date;
}

function formatScreenerTaskMeta(
  task: ScreenerTask,
  t: ReturnType<typeof usePreferences>["t"]
): string {
  if (task.status === "queued" || task.status === "pending") {
    return formatQueueMeta(task.queue_position, t);
  }
  if (task.status === "waiting_for_quota") {
    return formatQuotaMeta(task.blocked_vendor, task.blocked_until, t);
  }
  return (
    task.request_payload?.as_of_date ??
    t("activity.awaitingUpdate", "Awaiting next update")
  );
}

function formatOpportunityTaskMeta(
  task: OpportunityTask,
  t: ReturnType<typeof usePreferences>["t"]
): string {
  if (task.status === "queued" || task.status === "pending") {
    return formatQueueMeta(task.queue_position, t);
  }
  return (
    task.latest_progress?.message ??
    task.request_payload?.market ??
    t("activity.awaitingUpdate", "Awaiting next update")
  );
}

function formatJournalReviewTaskMeta(
  task: JournalReviewTask,
  t: ReturnType<typeof usePreferences>["t"]
): string {
  const reviewTypes = task.request_payload?.review_types ?? [];
  const reviewLabel =
    reviewTypes.length > 0
      ? reviewTypes
          .map((type) =>
            type === "entry_review"
              ? t("journal.entryReview", "Entry Review")
              : t("journal.exitReview", "Exit Review")
          )
          .join(", ")
      : t("activity.tradeReviewGeneration", "Trade review generation");
  if (task.status === "completed") {
    const generatedCount = task.result?.generated_count ?? 0;
    return task.result?.skipped
      ? t("activity.journalReviewSkipped", ({ reason }) => `Skipped: ${reason}`, {
          reason: task.result.reason ?? "not enabled",
        })
      : t(
          "activity.journalReviewCompleted",
          ({ count, reviews }) => `${count} generated · ${reviews}`,
          { count: generatedCount, reviews: reviewLabel }
        );
  }
  return task.latest_progress?.message ?? reviewLabel;
}

function formatQueueMeta(
  queuePosition: number | null | undefined,
  t: ReturnType<typeof usePreferences>["t"]
): string {
  return typeof queuePosition === "number"
    ? t("task.queuePosition", ({ position }) => `Queue position ${position}`, {
        position: queuePosition,
      })
    : t("activity.awaitingWorker", "Awaiting worker slot");
}

function formatQuotaMeta(
  vendor: string | null | undefined,
  blockedUntil: string | null | undefined,
  t: ReturnType<typeof usePreferences>["t"]
): string {
  return t(
    "activity.waitingForQuota",
    ({ vendor: vendorName, until }) =>
      `Waiting for ${vendorName ?? "data source"} quota${until ? ` until ${until}` : ""}`,
    {
      vendor: vendor ?? undefined,
      until: formatDateTimeLabel(blockedUntil),
    }
  );
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
