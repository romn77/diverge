"use client";

import { useCallback } from "react";
import { useParams, useRouter } from "next/navigation";
import { TaskProgress } from "@/components/TaskProgress";
import { useWorkbench } from "@/components/WorkbenchProvider";
import { buildReportHref } from "@/lib/workbenchRoutes";

export default function TaskRoutePage() {
  const params = useParams<{ taskId: string }>();
  const router = useRouter();
  const { refreshReports, refreshTasks } = useWorkbench();
  const handleTaskComplete = useCallback(() => {
    void refreshReports();
    void refreshTasks();
  }, [refreshReports, refreshTasks]);
  const handleViewReport = useCallback(
    (reportId: string) => {
      router.push(buildReportHref(reportId));
    },
    [router]
  );

  return (
    <TaskProgress
      taskId={params.taskId}
      onTaskComplete={handleTaskComplete}
      onViewReport={handleViewReport}
    />
  );
}
