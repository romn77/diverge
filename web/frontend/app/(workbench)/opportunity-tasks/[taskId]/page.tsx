"use client";

import { useCallback } from "react";
import { useParams, useRouter } from "next/navigation";
import { OpportunityTaskProgress } from "@/components/OpportunityTaskProgress";
import { useWorkbench } from "@/components/WorkbenchProvider";
import { buildOpportunitiesHref } from "@/lib/workbenchRoutes";

export default function OpportunityTaskRoutePage() {
  const params = useParams<{ taskId: string }>();
  const router = useRouter();
  const { refreshOpportunityTasks } = useWorkbench();

  const handleTaskComplete = useCallback(
    (runId: string | null) => {
      void refreshOpportunityTasks();
      if (runId) {
        router.push(buildOpportunitiesHref(runId));
      }
    },
    [refreshOpportunityTasks, router]
  );

  const handleViewRun = useCallback(
    (runId: string) => {
      router.push(buildOpportunitiesHref(runId));
    },
    [router]
  );

  return (
    <OpportunityTaskProgress
      taskId={params.taskId}
      onTaskComplete={handleTaskComplete}
      onViewRun={handleViewRun}
    />
  );
}
