"use client";

import { useCallback } from "react";
import { useParams, useRouter } from "next/navigation";
import { ScreenerTaskProgress } from "@/components/ScreenerTaskProgress";
import { useWorkbench } from "@/components/WorkbenchProvider";
import { buildScreenerRunHref } from "@/lib/workbenchRoutes";

export default function ScreenerTaskRoutePage() {
  const params = useParams<{ taskId: string }>();
  const router = useRouter();
  const { refreshScreenerRuns, refreshScreenerTasks } = useWorkbench();

  const handleTaskComplete = useCallback(
    (runId: string | null) => {
      void refreshScreenerRuns();
      void refreshScreenerTasks();
      if (runId) {
        router.push(buildScreenerRunHref(runId));
      }
    },
    [refreshScreenerRuns, refreshScreenerTasks, router]
  );

  const handleViewRun = useCallback(
    (runId: string) => {
      router.push(buildScreenerRunHref(runId));
    },
    [router]
  );

  return (
    <ScreenerTaskProgress
      taskId={params.taskId}
      onTaskComplete={handleTaskComplete}
      onViewRun={handleViewRun}
    />
  );
}
