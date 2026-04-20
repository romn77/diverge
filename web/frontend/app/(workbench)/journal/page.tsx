"use client";

import { TradeJournal } from "@/components/TradeJournal";
import { useWorkbench } from "@/components/WorkbenchProvider";

export default function JournalRoutePage() {
  const { reports } = useWorkbench();
  return <TradeJournal reports={reports} />;
}
