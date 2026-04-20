"use client";

import { useParams } from "next/navigation";
import { ScreenerResultsViewer } from "@/components/ScreenerResultsViewer";

export default function ScreenerRunRoutePage() {
  const params = useParams<{ runId: string }>();
  return <ScreenerResultsViewer runId={params.runId} />;
}
