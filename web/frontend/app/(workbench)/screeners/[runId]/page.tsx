"use client";

import { useEffect } from "react";
import { useParams, useRouter } from "next/navigation";
import { buildScreenerRunHref } from "@/lib/workbenchRoutes";

export default function ScreenerRunRoutePage() {
  const params = useParams<{ runId: string }>();
  const router = useRouter();

  useEffect(() => {
    router.replace(buildScreenerRunHref(params.runId));
  }, [params.runId, router]);

  return null;
}
