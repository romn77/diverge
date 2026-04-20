"use client";

import { useParams, useRouter } from "next/navigation";
import { TaskProgress } from "@/components/TaskProgress";
import { useWorkbench } from "@/components/WorkbenchProvider";
import { buildReportHref } from "@/lib/workbenchRoutes";

export default function TaskRoutePage() {
  const params = useParams<{ taskId: string }>();
  const router = useRouter();
  const { refreshReports, refreshTasks } = useWorkbench();

  return (
    <TaskProgress
      taskId={params.taskId}
      onTaskComplete={() => {
        void refreshReports();
        void refreshTasks();
      }}
      onViewReport={(reportId) => {
        router.push(buildReportHref(reportId));
      }}
    />
  );
}
