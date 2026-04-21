"use client";

import { useParams } from "next/navigation";
import { ReportViewer } from "@/components/ReportViewer";
import { useWorkbench } from "@/components/WorkbenchProvider";

export default function ReportRoutePage() {
  const params = useParams<{ reportId: string }>();
  const { reports } = useWorkbench();
  const reportMeta = reports.find((report) => report.id === params.reportId) ?? null;

  return <ReportViewer reportId={params.reportId} reportMeta={reportMeta} />;
}
