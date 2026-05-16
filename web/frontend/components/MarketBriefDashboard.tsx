"use client";

import Link from "next/link";
import { ChevronDown, Play, RefreshCw } from "lucide-react";
import { useEffect, useMemo, useState } from "react";
import { usePreferences } from "@/components/PreferencesProvider";
import { useWorkbenchChrome } from "@/components/WorkbenchShell";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
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


const MARKET_OPTIONS: Array<{ value: MarketBriefMarket; labelKey: string; fallback: string }> = [
  { value: "cn", labelKey: "marketBrief.market.cn", fallback: "A-share" },
  { value: "us", labelKey: "marketBrief.market.us", fallback: "US" },
];


function isActiveTask(task: MarketBriefTask): boolean {
  return ["pending", "queued", "waiting_for_quota", "running"].includes(task.status);
}


export function MarketBriefDashboard() {
  const { language, t } = usePreferences();
  const { setTopbarActions } = useWorkbenchChrome();
  const [briefIndex, setBriefIndex] = useState<MarketBriefIndexResponse | null>(null);
  const [tasks, setTasks] = useState<MarketBriefTask[]>([]);
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
      setError(loadError instanceof Error ? loadError.message : t("marketBrief.error.load", "Unable to load brief"));
      setLoading(false);
    });
  }, [t]);

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

  const handleRun = async (markets: MarketBriefMarket[]) => {
    setRunning(true);
    setError(null);
    try {
      const result = await createMarketBriefTask({
        markets,
        output_language: language === "zh" ? "zh-CN" : "en-US",
        report_visibility: "workspace",
      });
      const task = await getMarketBriefTask(result.task_id);
      setTasks((current) => [task, ...current.filter((item) => item.id !== task.id)]);
    } catch (runError) {
      setError(runError instanceof Error ? runError.message : t("marketBrief.error.run", "Unable to run brief"));
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
              <DropdownMenu>
                <DropdownMenuTrigger asChild>
                  <Button type="button" disabled={running}>
                    <Play className="size-4" aria-hidden />
                    <span>
                      {running
                        ? t("marketBrief.running", "Running")
                        : t("marketBrief.run", "Run brief")}
                    </span>
                    <ChevronDown className="size-4" aria-hidden />
                  </Button>
                </DropdownMenuTrigger>
                <DropdownMenuContent align="end" className="w-[13rem]">
                  <DropdownMenuLabel>
                    {t("marketBrief.chooseMarket", "Choose market")}
                  </DropdownMenuLabel>
                  {MARKET_OPTIONS.map((market) => (
                    <DropdownMenuItem
                      key={market.value}
                      disabled={running}
                      onSelect={() => void handleRun([market.value])}
                    >
                      {t(market.labelKey, market.fallback)}
                    </DropdownMenuItem>
                  ))}
                  <DropdownMenuSeparator />
                  <DropdownMenuItem
                    disabled={running}
                    onSelect={() =>
                      void handleRun(MARKET_OPTIONS.map((market) => market.value))
                    }
                  >
                    {t("marketBrief.market.all", "A-share + US")}
                  </DropdownMenuItem>
                </DropdownMenuContent>
              </DropdownMenu>
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
                            {formatMarketBriefMarket(market, t)}
                          </Badge>
                        ))}
                        <Badge variant="outline">
                          {formatQualityLevel(brief.data_quality_level, t)}
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
                        {formatMarketBriefMarkets(task.request_payload.markets, t)}
                      </p>
                      <Badge variant="outline">{t(`task.status.${task.status}`, task.status)}</Badge>
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

function formatMarketBriefMarkets(
  markets: string[] | readonly string[],
  t: ReturnType<typeof usePreferences>["t"]
): string {
  return markets.map((market) => formatMarketBriefMarket(market, t)).join(", ");
}

function formatMarketBriefMarket(
  market: string,
  t: ReturnType<typeof usePreferences>["t"]
): string {
  const normalized = market.toLowerCase();
  if (normalized === "cn") {
    return t("marketBrief.market.cn", "A-share");
  }
  if (normalized === "us") {
    return t("marketBrief.market.us", "US");
  }
  return market.toUpperCase();
}

function formatQualityLevel(
  qualityLevel: string | null,
  t: ReturnType<typeof usePreferences>["t"]
): string {
  const normalized = (qualityLevel ?? "unknown").toLowerCase();
  return t(`marketBrief.quality.${normalized}`, humanizeCode(normalized));
}

function humanizeCode(value: string): string {
  return value
    .split(/[_\s-]+/)
    .filter(Boolean)
    .map((part) => `${part.charAt(0).toUpperCase()}${part.slice(1).toLowerCase()}`)
    .join(" ");
}
