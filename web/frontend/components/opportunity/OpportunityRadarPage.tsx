"use client";

import { useCallback, useEffect, useMemo, useState, type ReactNode } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import {
  Activity,
  BarChart3,
  Eye,
  LineChart,
  ListPlus,
  Play,
  Radar,
  RefreshCw,
  Send,
  ShieldAlert,
  X,
} from "lucide-react";
import { usePreferences } from "@/components/PreferencesProvider";
import { useWorkbench } from "@/components/WorkbenchProvider";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Sheet, SheetContent, SheetHeader, SheetTitle } from "@/components/ui/sheet";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import {
  addOpportunityWatchlistItem,
  analyzeOpportunityCandidate,
  createOpportunityRun,
  deleteOpportunityWatchlistItem,
  getOpportunityCandidates,
  getOpportunityEvents,
  getOpportunityMarketPulse,
  getOpportunityThemes,
  listOpportunityRuns,
  listOpportunityWatchlist,
  type BacktestSnapshotSummary,
  type CandidatePoolResponse,
  type MarketPulse,
  type OpportunityCandidate,
  type OpportunityEvent,
  type OpportunityRunSummary,
  type ThemeRadarResponse,
  type WatchlistItem,
} from "@/lib/api";
import { buildOpportunitiesHref, buildTaskHref } from "@/lib/workbenchRoutes";

type LoadState = "idle" | "loading" | "ready" | "error";

interface RunArtifacts {
  marketPulse: MarketPulse | null;
  themes: ThemeRadarResponse | null;
  candidates: CandidatePoolResponse | null;
  events: OpportunityEvent[];
}

const EMPTY_ARTIFACTS: RunArtifacts = {
  marketPulse: null,
  themes: null,
  candidates: null,
  events: [],
};

export function OpportunityRadarPage() {
  const { t } = usePreferences();
  const { opportunityRadarEnabled } = useWorkbench();
  const router = useRouter();
  const searchParams = useSearchParams();
  const requestedRunId = searchParams.get("runId");
  const [runs, setRuns] = useState<OpportunityRunSummary[]>([]);
  const [selectedRunId, setSelectedRunId] = useState<string | null>(requestedRunId);
  const [artifacts, setArtifacts] = useState<RunArtifacts>(EMPTY_ARTIFACTS);
  const [watchlist, setWatchlist] = useState<WatchlistItem[]>([]);
  const [loadState, setLoadState] = useState<LoadState>("idle");
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [selectedCandidate, setSelectedCandidate] = useState<OpportunityCandidate | null>(null);
  const [pendingAction, setPendingAction] = useState<string | null>(null);

  const selectedRun = useMemo(
    () => runs.find((run) => run.run_id === selectedRunId) ?? null,
    [runs, selectedRunId]
  );

  const refreshRuns = useCallback(async () => {
    if (!opportunityRadarEnabled) {
      setRuns([]);
      setSelectedRunId(null);
      setArtifacts(EMPTY_ARTIFACTS);
      setWatchlist([]);
      return;
    }
    setLoadState("loading");
    setErrorMessage(null);
    try {
      const nextRuns = await listOpportunityRuns();
      setRuns(nextRuns);
      const nextRunId = requestedRunId || nextRuns[0]?.run_id || null;
      setSelectedRunId(nextRunId);
      if (nextRunId && nextRunId !== requestedRunId) {
        router.replace(buildOpportunitiesHref(nextRunId));
      }
    } catch (error) {
      setLoadState("error");
      setErrorMessage(error instanceof Error ? error.message : t("opportunity.error.loadRuns", "Unable to load opportunity runs"));
    }
  }, [opportunityRadarEnabled, requestedRunId, router, t]);

  const refreshWatchlist = useCallback(async () => {
    if (!opportunityRadarEnabled) {
      return;
    }
    try {
      setWatchlist(await listOpportunityWatchlist());
    } catch {
      setWatchlist([]);
    }
  }, [opportunityRadarEnabled]);

  useEffect(() => {
    void refreshRuns();
    void refreshWatchlist();
  }, [refreshRuns, refreshWatchlist]);

  useEffect(() => {
    if (!selectedRunId || !opportunityRadarEnabled) {
      setArtifacts(EMPTY_ARTIFACTS);
      return;
    }

    let isActive = true;
    const loadArtifacts = async () => {
      setLoadState("loading");
      setErrorMessage(null);
      try {
        const [marketPulse, themes, candidates, events] = await Promise.all([
          getOpportunityMarketPulse(selectedRunId),
          getOpportunityThemes(selectedRunId),
          getOpportunityCandidates(selectedRunId),
          getOpportunityEvents(selectedRunId),
        ]);
        if (!isActive) {
          return;
        }
        setArtifacts({ marketPulse, themes, candidates, events });
        setLoadState("ready");
      } catch (error) {
        if (!isActive) {
          return;
        }
        setArtifacts(EMPTY_ARTIFACTS);
        setLoadState("error");
        setErrorMessage(error instanceof Error ? error.message : t("opportunity.error.loadArtifacts", "Unable to load opportunity artifacts"));
      }
    };

    void loadArtifacts();
    return () => {
      isActive = false;
    };
  }, [opportunityRadarEnabled, selectedRunId, t]);

  const runRadar = async () => {
    setPendingAction("run");
    setErrorMessage(null);
    try {
      const result = await createOpportunityRun({ market: "cn" });
      if (result.run_id) {
        router.push(buildOpportunitiesHref(result.run_id));
      }
      await refreshRuns();
    } catch (error) {
      setErrorMessage(error instanceof Error ? error.message : t("opportunity.error.run", "Unable to start Opportunity Radar"));
    } finally {
      setPendingAction(null);
    }
  };

  const addToWatchlist = async (candidate: OpportunityCandidate) => {
    setPendingAction(`watch:${candidate.symbol}`);
    try {
      await addOpportunityWatchlistItem({
        symbol: candidate.symbol,
        market: candidate.market ?? "cn",
        name: candidate.name,
        theme_id: candidate.theme_id,
        status: "NEW",
        reason: candidate.reason,
        source_run_id: selectedRunId,
        metadata: {
          candidate_type: candidate.candidate_type,
          score: candidate.stock_score,
        },
      });
      await refreshWatchlist();
    } catch (error) {
      setErrorMessage(error instanceof Error ? error.message : t("opportunity.error.watchlist", "Unable to update watchlist"));
    } finally {
      setPendingAction(null);
    }
  };

  const removeFromWatchlist = async (symbol: string) => {
    setPendingAction(`remove:${symbol}`);
    try {
      await deleteOpportunityWatchlistItem(symbol);
      await refreshWatchlist();
    } catch (error) {
      setErrorMessage(error instanceof Error ? error.message : t("opportunity.error.watchlist", "Unable to update watchlist"));
    } finally {
      setPendingAction(null);
    }
  };

  const triggerAnalysis = async (candidate: OpportunityCandidate) => {
    setPendingAction(`analyze:${candidate.symbol}`);
    try {
      const result = await analyzeOpportunityCandidate(candidate.symbol, {
        run_id: selectedRunId,
        opportunity_context: buildOpportunityContext(candidate, selectedRunId),
      });
      if (result.task_id) {
        router.push(buildTaskHref(result.task_id));
      }
    } catch (error) {
      setErrorMessage(error instanceof Error ? error.message : t("opportunity.error.analyze", "Unable to trigger analysis"));
    } finally {
      setPendingAction(null);
    }
  };

  const candidates = artifacts.candidates?.candidates ?? [];
  const themes = artifacts.themes?.themes ?? [];
  const watchSymbols = useMemo(
    () => new Set(watchlist.map((item) => item.symbol)),
    [watchlist]
  );

  if (!opportunityRadarEnabled) {
    return (
      <main className="flex min-h-dvh flex-1 flex-col p-2 md:p-4">
        <Card className="viewer-frame fade-in">
          <CardContent className="p-5 md:p-6">
            <div className="flex items-center gap-3">
              <Radar className="h-5 w-5 text-[var(--primary)]" aria-hidden />
              <div>
                <h1 className="font-heading text-xl font-bold text-foreground">
                  {t("opportunity.disabled.title", "Opportunity Radar is disabled")}
                </h1>
                <p className="mt-1 text-sm text-muted-foreground">
                  {t("opportunity.disabled.body", "Enable OPPORTUNITY_RADAR_ENABLED to use this workspace.")}
                </p>
              </div>
            </div>
          </CardContent>
        </Card>
      </main>
    );
  }

  return (
    <main className="flex min-h-dvh flex-1 flex-col p-2 md:h-dvh md:overflow-hidden md:p-3 lg:p-4">
      <div className="flex min-h-0 flex-1 flex-col gap-4 overflow-hidden">
        <Card className="viewer-frame fade-in shrink-0">
          <CardContent className="p-4 md:p-5">
            <div className="flex flex-wrap items-start justify-between gap-3">
              <div className="min-w-0">
                <p className="text-[11px] font-semibold uppercase tracking-[0.24em] text-[var(--primary)]">
                  {t("opportunity.kicker", "Opportunity Radar")}
                </p>
                <h1 className="font-heading mt-2 text-2xl font-bold tracking-tight text-foreground md:text-[1.75rem]">
                  {selectedRun?.trade_date ?? t("opportunity.latest", "Latest run")}
                </h1>
                <p className="mt-1 text-sm text-muted-foreground">
                  {artifacts.marketPulse?.summary ?? t("opportunity.summary.empty", "No run has been loaded yet.")}
                </p>
              </div>
              <div className="flex flex-wrap items-center gap-2">
                <Button type="button" variant="secondary" size="sm" onClick={() => void refreshRuns()}>
                  <RefreshCw className="h-4 w-4" aria-hidden />
                  {t("common.refresh", "Refresh")}
                </Button>
                <Button type="button" size="sm" disabled={pendingAction === "run"} onClick={() => void runRadar()}>
                  <Play className="h-4 w-4" aria-hidden />
                  {t("opportunity.run", "Run Radar")}
                </Button>
              </div>
            </div>

            <div className="mt-4 flex flex-wrap gap-2">
              {runs.slice(0, 8).map((run) => (
                <button
                  key={run.run_id}
                  type="button"
                  data-active={run.run_id === selectedRunId}
                  className="choice-pill choice-pill-sm inline-flex items-center justify-center border uppercase leading-none align-middle transition focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[color:var(--ring-strong)] focus-visible:ring-offset-2 focus-visible:ring-offset-background"
                  onClick={() => {
                    setSelectedRunId(run.run_id);
                    router.push(buildOpportunitiesHref(run.run_id));
                  }}
                >
                  {run.trade_date} · {run.candidate_count}
                </button>
              ))}
            </div>

            {errorMessage ? (
              <div className="mt-4 rounded-md border border-[var(--danger-border)] bg-[var(--danger-soft)] px-4 py-3 text-sm text-[var(--danger)]">
                {errorMessage}
              </div>
            ) : null}
          </CardContent>
        </Card>

        <div className="grid min-h-0 flex-1 grid-cols-1 gap-4 overflow-y-auto lg:grid-cols-[minmax(0,1.35fr)_minmax(22rem,0.65fr)]">
          <section className="space-y-4">
            <MarketPulsePanel pulse={artifacts.marketPulse} loading={loadState === "loading"} />
            <ThemeRadarTable themes={themes} loading={loadState === "loading"} />
            <CandidatePoolTable
              candidates={candidates}
              loading={loadState === "loading"}
              watchSymbols={watchSymbols}
              pendingAction={pendingAction}
              onAddWatchlist={addToWatchlist}
              onAnalyze={triggerAnalysis}
              onSelect={setSelectedCandidate}
            />
          </section>

          <aside className="space-y-4">
            <BacktestSnapshotCard summary={themes[0]?.backtest_summary ?? candidates[0]?.backtest_summary ?? null} />
            <WatchlistMonitor
              items={watchlist}
              pendingAction={pendingAction}
              onRemove={removeFromWatchlist}
            />
            <OpportunityEventTimeline events={artifacts.events} loading={loadState === "loading"} />
          </aside>
        </div>
      </div>

      <CandidateDetailSheet
        candidate={selectedCandidate}
        runId={selectedRunId}
        inWatchlist={selectedCandidate ? watchSymbols.has(selectedCandidate.symbol) : false}
        pendingAction={pendingAction}
        onClose={() => setSelectedCandidate(null)}
        onAddWatchlist={addToWatchlist}
        onAnalyze={triggerAnalysis}
      />
    </main>
  );
}

function MarketPulsePanel({ pulse, loading }: { pulse: MarketPulse | null; loading: boolean }) {
  const { t } = usePreferences();
  return (
    <Card className="viewer-frame">
      <CardContent className="p-4">
        <PanelTitle icon={<Activity className="h-4 w-4" aria-hidden />} title={t("opportunity.marketPulse", "Market Pulse")} />
        {loading ? <PanelEmpty label={t("common.loading", "Loading")} /> : null}
        {!loading && pulse ? (
          <div className="mt-3 grid gap-3 md:grid-cols-3">
            <Metric label={t("opportunity.regime", "Regime")} value={pulse.market_regime} />
            <Metric label={t("opportunity.topThemes", "Top Themes")} value={pulse.top_themes.slice(0, 3).join(" / ") || "—"} />
            <Metric label={t("opportunity.riskNotes", "Risk Notes")} value={String(pulse.risk_notes.length)} />
          </div>
        ) : null}
        {!loading && pulse ? <p className="mt-3 text-sm text-muted-foreground">{pulse.summary}</p> : null}
        {!loading && !pulse ? <PanelEmpty label={t("opportunity.empty.market", "No market pulse artifact.")} /> : null}
      </CardContent>
    </Card>
  );
}

function ThemeRadarTable({ themes, loading }: { themes: ThemeRadarResponse["themes"]; loading: boolean }) {
  const { t } = usePreferences();
  return (
    <Card className="viewer-frame">
      <CardContent className="p-4">
        <PanelTitle icon={<Radar className="h-4 w-4" aria-hidden />} title={t("opportunity.themeRadar", "Theme Radar")} />
        <div className="mt-3 overflow-x-auto">
          <Table className="min-w-full text-xs [&_td]:px-3 [&_td]:py-2 [&_th]:h-9 [&_th]:px-3">
            <TableHeader className="sticky top-0 bg-[var(--surface-strong)]">
              <TableRow>
                <TableHead>{t("opportunity.theme", "Theme")}</TableHead>
                <TableHead className="text-right tabular-nums">{t("opportunity.hot", "Hot")}</TableHead>
                <TableHead className="text-right tabular-nums">{t("opportunity.capital", "Capital")}</TableHead>
                <TableHead>{t("opportunity.stage", "Stage")}</TableHead>
                <TableHead>{t("opportunity.leaders", "Leaders")}</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody className="bg-[var(--surface)]">
              {loading ? <EmptyRow colSpan={5} label={t("common.loading", "Loading")} /> : null}
              {!loading && themes.length === 0 ? <EmptyRow colSpan={5} label={t("opportunity.empty.themes", "No themes detected.")} /> : null}
              {!loading && themes.map((theme) => (
                <TableRow key={theme.theme_id}>
                  <TableCell className="font-semibold text-foreground">{theme.theme_name}</TableCell>
                  <TableCell className="text-right tabular-nums">{formatNumber(theme.hot_score)}</TableCell>
                  <TableCell className="text-right tabular-nums">{formatNumber(theme.capital_score)}</TableCell>
                  <TableCell><Badge variant="secondary">{theme.stage}</Badge></TableCell>
                  <TableCell>{theme.leaders.join(" / ") || "—"}</TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </div>
      </CardContent>
    </Card>
  );
}

function CandidatePoolTable({
  candidates,
  loading,
  watchSymbols,
  pendingAction,
  onAddWatchlist,
  onAnalyze,
  onSelect,
}: {
  candidates: OpportunityCandidate[];
  loading: boolean;
  watchSymbols: Set<string>;
  pendingAction: string | null;
  onAddWatchlist: (candidate: OpportunityCandidate) => Promise<void>;
  onAnalyze: (candidate: OpportunityCandidate) => Promise<void>;
  onSelect: (candidate: OpportunityCandidate) => void;
}) {
  const { t } = usePreferences();
  return (
    <Card className="viewer-frame">
      <CardContent className="p-4">
        <PanelTitle icon={<LineChart className="h-4 w-4" aria-hidden />} title={t("opportunity.candidates", "Candidate Pool")} />
        <div className="mt-3 overflow-x-auto">
          <Table className="min-w-full text-xs [&_td]:px-3 [&_td]:py-2 [&_th]:h-9 [&_th]:px-3">
            <TableHeader className="sticky top-0 bg-[var(--surface-strong)]">
              <TableRow>
                <TableHead>{t("opportunity.symbol", "Symbol")}</TableHead>
                <TableHead>{t("opportunity.type", "Type")}</TableHead>
                <TableHead className="text-right tabular-nums">{t("opportunity.score", "Score")}</TableHead>
                <TableHead>{t("opportunity.theme", "Theme")}</TableHead>
                <TableHead>{t("opportunity.nextStep", "Next")}</TableHead>
                <TableHead className="text-right">{t("opportunity.actions", "Actions")}</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody className="bg-[var(--surface)]">
              {loading ? <EmptyRow colSpan={6} label={t("common.loading", "Loading")} /> : null}
              {!loading && candidates.length === 0 ? <EmptyRow colSpan={6} label={t("opportunity.empty.candidates", "No candidates available.")} /> : null}
              {!loading && candidates.map((candidate) => {
                const watched = watchSymbols.has(candidate.symbol);
                return (
                  <TableRow key={`${candidate.market}-${candidate.symbol}`}>
                    <TableCell>
                      <button type="button" className="font-semibold text-[var(--primary)] hover:text-[var(--primary-strong)]" onClick={() => onSelect(candidate)}>
                        {candidate.symbol}
                      </button>
                      {candidate.name ? <div className="text-[10px] text-muted-foreground">{candidate.name}</div> : null}
                    </TableCell>
                    <TableCell><Badge variant="secondary">{candidate.candidate_type}</Badge></TableCell>
                    <TableCell className="text-right tabular-nums">{formatNumber(candidate.stock_score)}</TableCell>
                    <TableCell>{candidate.theme_name ?? candidate.theme_id ?? "—"}</TableCell>
                    <TableCell>{candidate.recommended_next_step ?? "WATCH"}</TableCell>
                    <TableCell>
                      <div className="flex justify-end gap-1">
                        <IconButton label={t("opportunity.view", "View candidate")} onClick={() => onSelect(candidate)}>
                          <Eye className="h-4 w-4" aria-hidden />
                        </IconButton>
                        <IconButton label={t("opportunity.addWatchlist", "Add to watchlist")} disabled={watched || pendingAction === `watch:${candidate.symbol}`} onClick={() => void onAddWatchlist(candidate)}>
                          <ListPlus className="h-4 w-4" aria-hidden />
                        </IconButton>
                        <IconButton label={t("opportunity.analyze", "Analyze")} disabled={pendingAction === `analyze:${candidate.symbol}`} onClick={() => void onAnalyze(candidate)}>
                          <Send className="h-4 w-4" aria-hidden />
                        </IconButton>
                      </div>
                    </TableCell>
                  </TableRow>
                );
              })}
            </TableBody>
          </Table>
        </div>
      </CardContent>
    </Card>
  );
}

function BacktestSnapshotCard({ summary }: { summary: BacktestSnapshotSummary | null | undefined }) {
  const { t } = usePreferences();
  const periods = summary?.holding_periods ?? {};
  const fiveDay = periods["5d"];
  return (
    <Card className="viewer-frame">
      <CardContent className="p-4">
        <PanelTitle icon={<BarChart3 className="h-4 w-4" aria-hidden />} title={t("opportunity.backtest", "Backtest Snapshot")} />
        <div className="mt-3 grid grid-cols-3 gap-2">
          <Metric label={t("opportunity.sample", "Sample")} value={String(summary?.sample_size ?? 0)} />
          <Metric label={t("opportunity.winRate5d", "5D Win") } value={formatPercent(fiveDay?.win_rate)} />
          <Metric label={t("opportunity.avgReturn5d", "5D Avg") } value={formatPercent(fiveDay?.avg_return)} />
        </div>
        {(!summary || !summary.sample_size) ? (
          <p className="mt-3 text-xs text-muted-foreground">
            {t("opportunity.backtest.unavailable", "Historical validation is unavailable or sample size is insufficient.")}
          </p>
        ) : null}
      </CardContent>
    </Card>
  );
}

function WatchlistMonitor({
  items,
  pendingAction,
  onRemove,
}: {
  items: WatchlistItem[];
  pendingAction: string | null;
  onRemove: (symbol: string) => Promise<void>;
}) {
  const { t } = usePreferences();
  return (
    <Card className="viewer-frame">
      <CardContent className="p-4">
        <PanelTitle icon={<ShieldAlert className="h-4 w-4" aria-hidden />} title={t("opportunity.watchlist", "Watchlist Monitor")} />
        <div className="mt-3 space-y-2">
          {items.length === 0 ? <PanelEmpty label={t("opportunity.empty.watchlist", "No watchlist items.")} /> : null}
          {items.slice(0, 8).map((item) => (
            <div key={item.id ?? item.symbol} className="flex items-center justify-between gap-2 rounded-md border border-[var(--border)] bg-[var(--surface)] px-3 py-2">
              <div className="min-w-0">
                <div className="truncate text-sm font-semibold text-foreground">{item.symbol}</div>
                <div className="truncate text-xs text-muted-foreground">{item.status} · {item.theme_id ?? "—"}</div>
              </div>
              <IconButton label={t("common.delete", "Delete")} disabled={pendingAction === `remove:${item.symbol}`} onClick={() => void onRemove(item.symbol)}>
                <X className="h-4 w-4" aria-hidden />
              </IconButton>
            </div>
          ))}
        </div>
      </CardContent>
    </Card>
  );
}

function OpportunityEventTimeline({ events, loading }: { events: OpportunityEvent[]; loading: boolean }) {
  const { t } = usePreferences();
  return (
    <Card className="viewer-frame">
      <CardContent className="p-4">
        <PanelTitle icon={<Activity className="h-4 w-4" aria-hidden />} title={t("opportunity.events", "Event Timeline")} />
        <div className="mt-3 space-y-2">
          {loading ? <PanelEmpty label={t("common.loading", "Loading")} /> : null}
          {!loading && events.length === 0 ? <PanelEmpty label={t("opportunity.empty.events", "No events available.")} /> : null}
          {!loading && events.slice(0, 10).map((event) => (
            <div key={event.event_id} className="rounded-md border border-[var(--border)] bg-[var(--surface)] px-3 py-2">
              <div className="flex items-center justify-between gap-2">
                <span className="text-xs font-semibold text-foreground">{event.event_type}</span>
                <span className="text-[10px] text-muted-foreground">{event.trade_date}</span>
              </div>
              <p className="mt-1 text-xs text-muted-foreground">{event.evidence?.[0] ?? event.symbol ?? event.theme_id ?? "—"}</p>
            </div>
          ))}
        </div>
      </CardContent>
    </Card>
  );
}

function CandidateDetailSheet({
  candidate,
  runId,
  inWatchlist,
  pendingAction,
  onClose,
  onAddWatchlist,
  onAnalyze,
}: {
  candidate: OpportunityCandidate | null;
  runId: string | null;
  inWatchlist: boolean;
  pendingAction: string | null;
  onClose: () => void;
  onAddWatchlist: (candidate: OpportunityCandidate) => Promise<void>;
  onAnalyze: (candidate: OpportunityCandidate) => Promise<void>;
}) {
  const { t } = usePreferences();
  return (
    <Sheet open={Boolean(candidate)} onOpenChange={(open) => !open && onClose()}>
      <SheetContent side="right" className="w-full max-w-xl overflow-y-auto border-l border-[var(--border)] bg-[var(--background)] px-5 py-5">
        <SheetHeader>
          <SheetTitle>{candidate?.symbol ?? t("opportunity.candidate", "Candidate")}</SheetTitle>
        </SheetHeader>
        {candidate ? (
          <div className="mt-5 space-y-4">
            <div className="grid grid-cols-2 gap-3">
              <Metric label={t("opportunity.score", "Score")} value={formatNumber(candidate.stock_score)} />
              <Metric label={t("opportunity.type", "Type")} value={candidate.candidate_type} />
              <Metric label={t("opportunity.theme", "Theme")} value={candidate.theme_name ?? candidate.theme_id ?? "—"} />
              <Metric label={t("opportunity.runId", "Run")} value={runId ?? "—"} />
            </div>
            <section className="rounded-md border border-[var(--border)] bg-[var(--surface)] p-3">
              <h3 className="text-sm font-semibold text-foreground">{t("opportunity.reason", "Reason")}</h3>
              <p className="mt-2 text-sm text-muted-foreground">{candidate.reason}</p>
            </section>
            <section className="rounded-md border border-[var(--border)] bg-[var(--surface)] p-3">
              <h3 className="text-sm font-semibold text-foreground">{t("opportunity.riskFlags", "Risk Flags")}</h3>
              <div className="mt-2 flex flex-wrap gap-2">
                {candidate.risk_flags.length === 0 ? <span className="text-sm text-muted-foreground">—</span> : null}
                {candidate.risk_flags.map((flag) => <Badge key={flag} variant="secondary">{flag}</Badge>)}
              </div>
            </section>
            <div className="flex flex-wrap gap-2">
              <Button type="button" variant="secondary" disabled={inWatchlist || pendingAction === `watch:${candidate.symbol}`} onClick={() => void onAddWatchlist(candidate)}>
                <ListPlus className="h-4 w-4" aria-hidden />
                {t("opportunity.addWatchlist", "Add to watchlist")}
              </Button>
              <Button type="button" disabled={pendingAction === `analyze:${candidate.symbol}`} onClick={() => void onAnalyze(candidate)}>
                <Send className="h-4 w-4" aria-hidden />
                {t("opportunity.analyze", "Analyze")}
              </Button>
            </div>
          </div>
        ) : null}
      </SheetContent>
    </Sheet>
  );
}

function PanelTitle({ icon, title }: { icon: ReactNode; title: string }) {
  return (
    <div className="flex items-center gap-2 text-sm font-bold text-foreground">
      <span className="inline-flex h-7 w-7 items-center justify-center rounded-md border border-[var(--border)] bg-[var(--surface-translucent)] text-[var(--primary)]">
        {icon}
      </span>
      {title}
    </div>
  );
}

function Metric({ label, value }: { label: string; value: string }) {
  return (
    <div className="metric-card min-w-0 rounded-md border border-[var(--border)] bg-[var(--surface)] px-3 py-2">
      <div className="truncate text-[10px] font-semibold uppercase tracking-[0.14em] text-muted-foreground">{label}</div>
      <div className="mt-1 truncate text-sm font-bold text-foreground">{value}</div>
    </div>
  );
}

function PanelEmpty({ label }: { label: string }) {
  return <p className="mt-3 text-sm text-muted-foreground">{label}</p>;
}

function EmptyRow({ colSpan, label }: { colSpan: number; label: string }) {
  return (
    <TableRow>
      <TableCell colSpan={colSpan} className="py-6 text-muted-foreground">
        {label}
      </TableCell>
    </TableRow>
  );
}

function IconButton({
  label,
  disabled = false,
  onClick,
  children,
}: {
  label: string;
  disabled?: boolean;
  onClick: () => void;
  children: ReactNode;
}) {
  return (
    <button
      type="button"
      aria-label={label}
      title={label}
      disabled={disabled}
      className="inline-flex h-8 w-8 items-center justify-center rounded-md border border-[var(--border)] bg-[var(--surface)] text-muted-foreground transition hover:border-[var(--border-strong)] hover:bg-[color:var(--surface-hover)] hover:text-[var(--primary)] disabled:cursor-not-allowed disabled:opacity-40"
      onClick={onClick}
    >
      {children}
    </button>
  );
}

function formatNumber(value: number | null | undefined): string {
  return typeof value === "number" && Number.isFinite(value) ? value.toFixed(2) : "—";
}

function formatPercent(value: number | null | undefined): string {
  return typeof value === "number" && Number.isFinite(value) ? `${(value * 100).toFixed(1)}%` : "—";
}

function buildOpportunityContext(candidate: OpportunityCandidate, runId: string | null) {
  return {
    symbol: candidate.symbol,
    trigger: candidate.reason,
    theme_id: candidate.theme_id,
    theme_name: candidate.theme_name,
    candidate_type: candidate.candidate_type,
    backtest_summary: candidate.backtest_summary ?? null,
    risk_flags: candidate.risk_flags,
    source_run_id: runId,
  };
}
