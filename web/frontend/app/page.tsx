"use client";

import { useState } from "react";
import { Sidebar } from "@/components/Sidebar";
import { ReportViewer } from "@/components/ReportViewer";

export default function Home() {
  const [selectedReportId, setSelectedReportId] = useState<string | null>(null);

  return (
    <div className="app-shell relative flex min-h-screen flex-col md:flex-row">
      <Sidebar
        selectedReportId={selectedReportId}
        onSelectReport={setSelectedReportId}
      />

      {selectedReportId ? (
        <ReportViewer reportId={selectedReportId} />
      ) : (
        <main className="flex-1 min-w-0 p-4 md:p-7 lg:p-9">
          <div className="glass-panel fade-in mx-auto mt-5 max-w-3xl rounded-3xl px-7 py-10 text-center md:px-12 md:py-14">
            <p className="text-[11px] font-semibold uppercase tracking-[0.2em] text-[var(--primary)]">
              TradingAgents Report Center
            </p>
            <h1 className="font-heading mt-3 text-3xl font-bold tracking-tight text-slate-900 md:text-5xl">
              Select a report to start analysis review
            </h1>
            <p className="mx-auto mt-5 max-w-xl text-base leading-7 text-slate-600">
              Use the left panel to search by ticker and date. Once selected,
              you will get stage-by-stage tabs and a fully formatted markdown
              report.
            </p>
            <div className="mx-auto mt-7 grid max-w-xl grid-cols-1 gap-3 text-left text-sm text-slate-600 md:grid-cols-3">
              <div className="rounded-xl border border-[var(--border)] bg-white/75 px-3.5 py-3">
                <p className="font-semibold text-[var(--accent)]">Search</p>
                <p className="mt-1 text-xs leading-5">Filter by ticker or report id</p>
              </div>
              <div className="rounded-xl border border-[var(--border)] bg-white/75 px-3.5 py-3">
                <p className="font-semibold text-[var(--accent)]">Navigate</p>
                <p className="mt-1 text-xs leading-5">Jump between analyst stages</p>
              </div>
              <div className="rounded-xl border border-[var(--border)] bg-white/75 px-3.5 py-3">
                <p className="font-semibold text-[var(--accent)]">Review</p>
                <p className="mt-1 text-xs leading-5">Read full markdown output cleanly</p>
              </div>
            </div>
          </div>
        </main>
      )}
    </div>
  );
}
