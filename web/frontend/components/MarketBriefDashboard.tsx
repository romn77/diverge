"use client";

import Link from "next/link";
import { Play, RefreshCw } from "lucide-react";
import { useEffect, useMemo, useState } from "react";
import { usePreferences } from "@/components/PreferencesProvider";
import { useWorkbenchChrome } from "@/components/WorkbenchShell";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import {
  createMarketBriefTask,
  getMarketBriefTask,
  listMarketBriefs,
  listMarketBriefTasks,
  type MarketBriefIndexResponse,
  type MarketBriefMarket,
  type MarketBriefTask,
} from "@/lib/api";
import { buildReportHref } from "@/lib/workbenchRoutes";


const MARKET_OPTIONS: Array<{ value: MarketBriefMarket; label: string }> = [
  { value: "cn", label: "A-share" },
  { value: "us", label: "US" },
];


function isActiveTask(task: MarketBriefTask): boolean {
  return ["pending", "queued", "waiting_for_quota", "running"].includes(task.status);
}


export function MarketBriefDashboard() {
  const { t } = usePreferences();
  const { setTopbarActions } = useWorkbenchChrome();
  const [briefIndex, setBriefIndex] = useState<MarketBriefIndexResponse | null>(null);
  const [tasks, setTasks] = useState<MarketBriefTask[]>([]);
  const [selectedMarkets, setSelectedMarkets] = useState<MarketBriefMarket[]>([
    "cn",
    "us",
  ]);
  const [loading, setLoading] = useState(true);
  const [running, setRunning] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const activeTasks = useMemo(() => tasks.filter(isActiveTask), [tasks]);

  const refresh = async () => {
    setError(null);
    const [nextBriefs, nextTasks] = await Promise.all([
      listMarketBriefs(),
      listMarketBriefTasks(),
    ]);
    setBriefIndex(nextBriefs);
    setTasks(nextTasks);
    setLoading(false);
  };

  useEffect(() => {
    void refresh().catch((loadError) => {
      setError(loadError instanceof Error ? loadError.message : "Unable to load brief");
      setLoading(false);
    });
  }, []);

  useEffect(() => {
    setTopbarActions(
      <Button
        type="button"
        variant="secondary"
        size="sm"
        onClick={() => void refresh()}
        disabled={loading}
      >
        <RefreshCw className="size-4" aria-hidden />
        <span>{t("marketBrief.refresh", "Refresh")}</span>
      </Button>
    );
    return () => setTopbarActions(null);
  }, [loading, setTopbarActions, t]);

  useEffect(() => {
    if (!activeTasks.length) {
      return;
    }
    const timer = window.setInterval(() => {
      void Promise.all(activeTasks.map((task) => getMarketBriefTask(task.id)))
        .then((nextTasks) => {
          setTasks((current) => {
            const byId = new Map(current.map((task) => [task.id, task]));
            for (const task of nextTasks) {
              byId.set(task.id, task);
            }
            return Array.from(byId.values()).sort((a, b) =>
              String(b.created_at ?? "").localeCompare(String(a.created_at ?? ""))
            );
          });
          if (nextTasks.some((task) => task.status === "completed")) {
            void refresh();
          }
        })
        .catch(() => undefined);
    }, 2500);
    return () => window.clearInterval(timer);
  }, [activeTasks]);

  const toggleMarket = (market: MarketBriefMarket) => {
    setSelectedMarkets((current) => {
      if (current.includes(market)) {
        return current.length === 1 ? current : current.filter((item) => item !== market);
      }
      return [...current, market];
    });
  };

  const handleRun = async () => {
    setRunning(true);
    setError(null);
    try {
      const result = await createMarketBriefTask({
        markets: selectedMarkets,
        output_language: "zh-CN",
        report_visibility: "workspace",
      });
      const task = await getMarketBriefTask(result.task_id);
      setTasks((current) => [task, ...current.filter((item) => item.id !== task.id)]);
    } catch (runError) {
      setError(runError instanceof Error ? runError.message : "Unable to run brief");
    } finally {
      setRunning(false);
    }
  };

  return (
    <main className="flex min-h-dvh flex-1 flex-col px-4 py-6 md:px-7 lg:px-9">
      <div className="workbench-content-frame space-y-5">
        <Card className="card-surface rounded-[24px]">
          <CardContent className="space-y-5 p-5 md:p-6">
            <div className="flex flex-wrap items-start justify-between gap-4">
              <div className="min-w-0">
                <p className="text-[11px] font-semibold uppercase tracking-[0.22em] text-muted-foreground">
                  {t("marketBrief.kicker", "Daily Brief")}
                </p>
                <h2 className="mt-2 text-xl font-bold tracking-tight text-[var(--text)]">
                  {t("marketBrief.title", "Premarket brief")}
                </h2>
              </div>
              <Button type="button" onClick={() => void handleRun()} disabled={running}>
                <Play className="size-4" aria-hidden />
                <span>
                  {running
                    ? t("marketBrief.running", "Running")
                    : t("marketBrief.run", "Run brief")}
                </span>
              </Button>
            </div>

            <div className="flex flex-wrap gap-2" aria-label={t("marketBrief.markets", "Markets")}>
              {MARKET_OPTIONS.map((market) => {
                const selected = selectedMarkets.includes(market.value);
                return (
                  <button
                    key={market.value}
                    type="button"
                    aria-pressed={selected}
                    onClick={() => toggleMarket(market.value)}
                    className={`focus-ring rounded-md border px-3 py-2 text-xs font-semibold transition ${
                      selected
                        ? "border-[var(--border-strong)] bg-[var(--primary)] text-[var(--primary-foreground)]"
                        : "border-[var(--border)] bg-[var(--surface)] text-[var(--text)] hover:bg-[color:var(--surface-hover)]"
                    }`}
                  >
                    {market.label}
                  </button>
                );
              })}
            </div>

            {error ? (
              <div className="rounded-[14px] border border-[var(--border)] bg-[var(--surface-strong)] px-4 py-3 text-sm text-[var(--danger)]">
                {error}
              </div>
            ) : null}
          </CardContent>
        </Card>

        <section className="grid gap-4 lg:grid-cols-[minmax(0,1fr)_minmax(18rem,0.5fr)]">
          <Card className="card-surface rounded-[24px]">
            <CardContent className="p-5 md:p-6">
              <div className="flex items-center justify-between gap-3">
                <h2 className="text-base font-bold text-[var(--text)]">
                  {t("marketBrief.history", "Last 7 days")}
                </h2>
                <Badge variant="secondary">
                  {briefIndex?.briefs.length ?? 0}
                </Badge>
              </div>

              <div className="mt-4 space-y-3">
                {loading ? (
                  <p className="text-sm text-muted-foreground">
                    {t("marketBrief.loading", "Loading briefs...")}
                  </p>
                ) : briefIndex?.briefs.length ? (
                  briefIndex.briefs.map((brief) => (
                    <Link
                      key={brief.brief_id}
                      href={brief.report_id ? buildReportHref(brief.report_id) : "#"}
                      className="block rounded-[14px] border border-[var(--border)] bg-[var(--surface)] px-4 py-3 transition hover:border-[var(--border-strong)] hover:bg-[color:var(--surface-hover)]"
                    >
                      <div className="flex flex-wrap items-center justify-between gap-2">
                        <p className="font-semibold text-[var(--text)]">{brief.title}</p>
                        <span className="text-xs text-muted-foreground">
                          {brief.date} {brief.time}
                        </span>
                      </div>
                      {brief.summary ? (
                        <p className="mt-2 text-sm leading-6 text-muted-foreground">
                          {brief.summary}
                        </p>
                      ) : null}
                      <div className="mt-3 flex flex-wrap gap-2">
                        {brief.markets.map((market) => (
                          <Badge key={market} variant="secondary">
                            {market.toUpperCase()}
                          </Badge>
                        ))}
                        <Badge variant="outline">
                          {brief.data_quality_level ?? "unknown"}
                        </Badge>
                      </div>
                    </Link>
                  ))
                ) : (
                  <p className="rounded-[14px] border border-dashed border-[var(--border)] bg-[var(--surface-strong)] px-4 py-6 text-sm text-muted-foreground">
                    {t("marketBrief.empty", "No market briefs found in the 7-day window.")}
                  </p>
                )}
              </div>
            </CardContent>
          </Card>

          <Card className="card-surface rounded-[24px]">
            <CardContent className="p-5 md:p-6">
              <div className="flex items-center justify-between gap-3">
                <h2 className="text-base font-bold text-[var(--text)]">
                  {t("marketBrief.tasks", "Generation tasks")}
                </h2>
                <Badge variant="secondary">{activeTasks.length}</Badge>
              </div>
              <div className="mt-4 space-y-3">
                {tasks.slice(0, 6).map((task) => (
                  <div
                    key={task.id}
                    className="rounded-[14px] border border-[var(--border)] bg-[var(--surface)] px-4 py-3"
                  >
                    <div className="flex items-center justify-between gap-3">
                      <p className="truncate text-sm font-semibold text-[var(--text)]">
                        {task.request_payload.markets.join(", ").toUpperCase()}
                      </p>
                      <Badge variant="outline">{task.status}</Badge>
                    </div>
                    <p className="mt-2 text-xs leading-5 text-muted-foreground">
                      {task.latest_progress?.message ?? task.created_at ?? task.id}
                    </p>
                    {task.report_id ? (
                      <Link
                        href={buildReportHref(task.report_id)}
                        className="mt-3 inline-flex text-xs font-semibold text-[var(--primary)] underline-offset-4 hover:underline"
                      >
                        {t("marketBrief.openReport", "Open report")}
                      </Link>
                    ) : null}
                  </div>
                ))}
                {!tasks.length ? (
                  <p className="rounded-[14px] border border-dashed border-[var(--border)] bg-[var(--surface-strong)] px-4 py-6 text-sm text-muted-foreground">
                    {t("marketBrief.noTasks", "No brief tasks yet.")}
                  </p>
                ) : null}
              </div>
            </CardContent>
          </Card>
        </section>
      </div>
    </main>
  );
}
