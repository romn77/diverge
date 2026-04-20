"use client";

import { useParams, useRouter } from "next/navigation";
import { ScreenerTaskProgress } from "@/components/ScreenerTaskProgress";
import { useWorkbench } from "@/components/WorkbenchProvider";
import { buildScreenerRunHref } from "@/lib/workbenchRoutes";

export default function ScreenerTaskRoutePage() {
  const params = useParams<{ taskId: string }>();
  const router = useRouter();
  const { refreshScreenerRuns, refreshScreenerTasks } = useWorkbench();

  return (
    <ScreenerTaskProgress
      taskId={params.taskId}
      onTaskComplete={(runId) => {
        void refreshScreenerRuns();
        void refreshScreenerTasks();
        if (runId) {
          router.push(buildScreenerRunHref(runId));
        }
      }}
      onViewRun={(runId) => {
        router.push(buildScreenerRunHref(runId));
      }}
    />
  );
}
