"use client";

import Link from "next/link";
import { Trash2 } from "lucide-react";
import { usePreferences } from "@/components/PreferencesProvider";
import { useWorkbench } from "@/components/WorkbenchProvider";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { deleteScreenerTask, deleteTask } from "@/lib/api";
import {
  buildHomeHref,
  buildScreenerHref,
  buildScreenerTaskHref,
  buildTaskHref,
} from "@/lib/workbenchRoutes";

export function ActivityDashboard() {
  const { t } = usePreferences();
  const {
    activeScreenerTasks,
    activeTasks,
    refreshScreenerTasks,
    refreshTasks,
    screenerTasks,
    tasks,
  } = useWorkbench();
  const totalActive = activeTasks.length + activeScreenerTasks.length;
  const failedTasks = tasks.filter((task) => task.status === "failed");
  const failedScreenerTasks = screenerTasks.filter((task) => task.status === "failed");

  const confirmDeleteFailedTask = () =>
    window.confirm(
      t(
        "activity.deleteFailedTaskConfirm",
        "Delete this failed task record? This removes only the task record."
      )
    );

  const handleDeleteTask = async (taskId: string) => {
    if (!confirmDeleteFailedTask()) {
      return;
    }
    await deleteTask(taskId);
    await refreshTasks();
  };

  const handleDeleteScreenerTask = async (taskId: string) => {
    if (!confirmDeleteFailedTask()) {
      return;
    }
    await deleteScreenerTask(taskId);
    await refreshScreenerTasks();
  };

  return (
    <main className="flex min-h-[100vh] flex-1 flex-col px-4 py-6 md:px-7 lg:px-9">
      <div className="mx-auto w-full max-w-6xl space-y-6">
        <Card className="card-surface rounded-[30px]">
          <CardContent className="px-6 py-8 md:px-8">
          <div className="flex flex-col gap-6 lg:flex-row lg:items-end lg:justify-between">
            <div className="max-w-3xl">
              <p className="text-[11px] font-semibold uppercase tracking-[0.24em] text-[var(--primary)]">
                {t("sidebar.nav.activity", "Activity")}
              </p>
              <h1 className="mt-3 text-4xl font-semibold tracking-tight text-slate-900 md:text-[3.2rem]">
                {t("activity.title", "Background work")}
              </h1>
              <p className="mt-4 max-w-2xl text-sm leading-7 text-slate-600">
                {t(
                  "activity.description",
                  "Monitor analysis and screener jobs in one place."
                )}
              </p>
            </div>

            <div className="flex flex-wrap gap-3">
              <Button asChild variant="secondary">
                <Link href={buildHomeHref()}>{t("sidebar.nav.analysis", "Analysis")}</Link>
              </Button>
              <Button asChild variant="secondary">
                <Link href={buildScreenerHref()}>{t("sidebar.nav.screener", "Screener")}</Link>
              </Button>
            </div>
          </div>

          <div className="mt-8 grid gap-4 md:grid-cols-3">
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
          </div>
          </CardContent>
        </Card>

        <section className="grid gap-6 xl:grid-cols-2">
          <ActivityQueueSection
            title={t("activity.analysisTasks", "Analysis tasks")}
            description={t("activity.analysisDescription", "Research jobs waiting or running.")}
            emptyLabel={t("activity.noAnalysisJobs", "No active analysis jobs.")}
            items={activeTasks.map((task) => ({
              href: buildTaskHref(task.id),
              label: task.ticker,
              meta: task.latest_progress?.current_agent ?? task.analysis_date,
              status: t(`task.status.${task.status}`, task.status),
            }))}
          />
          <ActivityQueueSection
            title={t("activity.failedAnalysisTasks", "Failed analysis tasks")}
            description={t("activity.failedAnalysisDescription", "Failed research records that can be removed.")}
            emptyLabel={t("activity.noFailedAnalysisJobs", "No failed analysis jobs.")}
            items={failedTasks.map((task) => ({
              href: buildTaskHref(task.id),
              label: task.ticker,
              meta: task.error ?? task.analysis_date,
              status: t(`task.status.${task.status}`, task.status),
              deleteLabel: t("activity.deleteFailedTask", "Delete failed task"),
              onDelete: () => void handleDeleteTask(task.id),
            }))}
          />
          <ActivityQueueSection
            title={t("activity.screenerTasks", "Screener tasks")}
            description={t(
              "activity.screenerDescription",
              "Candidate-pool builds currently in motion."
            )}
            emptyLabel={t("activity.noScreenerJobs", "No active screener jobs.")}
            items={activeScreenerTasks.map((task) => ({
              href: buildScreenerTaskHref(task.id),
              label:
                task.request_payload?.markets.join(", ") ||
                t("activity.candidatePoolBuild", "Candidate pool build"),
              meta:
                task.request_payload?.as_of_date ??
                t("activity.awaitingUpdate", "Awaiting next update"),
              status: t(`task.status.${task.status}`, task.status),
            }))}
          />
          <ActivityQueueSection
            title={t("activity.failedScreenerTasks", "Failed screener tasks")}
            description={t("activity.failedScreenerDescription", "Failed candidate-pool records that can be removed.")}
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
              deleteLabel: t("activity.deleteFailedTask", "Delete failed task"),
              onDelete: () => void handleDeleteScreenerTask(task.id),
            }))}
          />
        </section>
      </div>
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
  return (
    <Card className="rounded-[24px] bg-white/88">
      <CardContent className="px-4 py-4">
      <p className="text-[11px] font-semibold uppercase tracking-[0.18em] text-slate-500">
        {label}
      </p>
      <p className="mt-3 text-3xl font-semibold tracking-tight text-slate-900">{value}</p>
      <p className="mt-2 text-sm text-slate-500">{meta}</p>
      </CardContent>
    </Card>
  );
}

function ActivityQueueSection({
  title,
  description,
  emptyLabel,
  items,
}: {
  title: string;
  description: string;
  emptyLabel: string;
  items: Array<{
    href: string;
    label: string;
    meta: string;
    status: string;
    deleteLabel?: string;
    onDelete?: () => void;
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
          <p className="mt-3 max-w-xl text-sm leading-6 text-slate-600">{description}</p>
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
              </div>
            </div>
          ))}
        </div>
      )}
      </CardContent>
    </Card>
  );
}
