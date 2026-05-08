"use client";

import { type CSSProperties, useEffect, useMemo, useRef, useState } from "react";
import {
  ChevronDown,
  ChevronRight,
  PanelLeftClose,
  PanelLeftOpen,
} from "lucide-react";
import { usePreferences } from "@/components/PreferencesProvider";
import { useWorkbenchChrome } from "@/components/WorkbenchShell";
import { PageHeader } from "@/components/workbench/PageHeader";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Tabs, TabsList, TabsTrigger } from "@/components/ui/tabs";
import {
  generateTradeReview,
  getTickerTradeFeedback,
  getTrade,
  listTrades,
  type Report,
  type TradeDetail,
  type TradeFeedbackPayload,
  type TradeRecord,
  type TradeReview,
  type TradeReviewGenerateRequest,
  type TradeReviewType,
} from "@/lib/api";
import { cn } from "@/lib/utils";
import { TickerPricePanel } from "./TickerPricePanel";
import { CloseTradeForm } from "./CloseTradeForm";
import { TradeRecordForm } from "./TradeRecordForm";
import { TradeReviewForm } from "./TradeReviewForm";

interface TradeJournalProps {
  reports: Report[];
  onOpenSidebar?: () => void;
  sidebarOpen?: boolean;
}

type TimeWindow = "all" | "30d" | "90d" | "365d";

interface PendingReviewGeneration {
  tradeId: string;
  reviewType: TradeReviewType;
  startedAt: string;
}

interface ReviewGenerationError {
  tradeId: string;
  reviewType: TradeReviewType;
  message: string;
}

interface TradeTickerGroup {
  ticker: string;
  displaySymbol: string;
  trades: TradeRecord[];
  latestTrade: TradeRecord;
}

export function TradeJournal({
  reports,
  onOpenSidebar,
  sidebarOpen = false,
}: TradeJournalProps) {
  const { locale, t } = usePreferences();
  const { setTopbarActions } = useWorkbenchChrome();
  const [trades, setTrades] = useState<TradeRecord[]>([]);
  const [selectedTradeId, setSelectedTradeId] = useState<string | null>(null);
  const [tradeDetail, setTradeDetail] = useState<TradeDetail | null>(null);
  const [feedback, setFeedback] = useState<TradeFeedbackPayload | null>(null);
  const [tickerFilter, setTickerFilter] = useState("");
  const [statusFilter, setStatusFilter] = useState("all");
  const [timeWindow, setTimeWindow] = useState<TimeWindow>("all");
  const [reviewTab, setReviewTab] = useState<TradeReviewType>("entry_review");
  const [expandedTickerGroups, setExpandedTickerGroups] = useState<Record<string, boolean>>(
    {}
  );
  const [isHistoryCollapsed, setIsHistoryCollapsed] = useState(false);
  const [historyPaneWidth, setHistoryPaneWidth] = useState(420);
  const [isResizingHistory, setIsResizingHistory] = useState(false);
  const [loadingTrades, setLoadingTrades] = useState(true);
  const [loadingDetail, setLoadingDetail] = useState(false);
  const [tradesError, setTradesError] = useState<string | null>(null);
  const [detailError, setDetailError] = useState<string | null>(null);
  const [showCreateTrade, setShowCreateTrade] = useState(false);
  const [showEditTrade, setShowEditTrade] = useState(false);
  const [showCloseTrade, setShowCloseTrade] = useState(false);
  const [editingReviewType, setEditingReviewType] = useState<TradeReviewType | null>(
    null
  );
  const [pendingReviewGeneration, setPendingReviewGeneration] =
    useState<PendingReviewGeneration | null>(null);
  const [reviewGenerationError, setReviewGenerationError] =
    useState<ReviewGenerationError | null>(null);
  const historyGridRef = useRef<HTMLElement | null>(null);

  useEffect(() => {
    let isActive = true;

    const loadTrades = async () => {
      setLoadingTrades(true);
      setTradesError(null);

      try {
        const data = await listTrades();
        if (!isActive) {
          return;
        }

        setTrades(data);
        setSelectedTradeId((current) => {
          if (current && data.some((trade) => trade.trade_id === current)) {
            return current;
          }
          return data[0]?.trade_id ?? null;
        });
      } catch (error) {
        if (!isActive) {
          return;
        }

        setTrades([]);
        setSelectedTradeId(null);
        setTradesError(
          error instanceof Error
            ? error.message
            : t("journal.error.loadHistory", "Unable to load trade history")
        );
      } finally {
        if (isActive) {
          setLoadingTrades(false);
        }
      }
    };

    void loadTrades();
    return () => {
      isActive = false;
    };
  }, [t]);

  useEffect(() => {
    if (!selectedTradeId) {
      setTradeDetail(null);
      setDetailError(null);
      return;
    }

    let isActive = true;

    const loadTradeDetail = async () => {
      setLoadingDetail(true);
      setDetailError(null);

      try {
        const data = await getTrade(selectedTradeId);
        if (!isActive) {
          return;
        }
        setTradeDetail(data);
      } catch (error) {
        if (!isActive) {
          return;
        }

        setTradeDetail(null);
        setDetailError(
          error instanceof Error
            ? error.message
            : t("journal.error.loadDetail", "Unable to load trade details")
        );
      } finally {
        if (isActive) {
          setLoadingDetail(false);
        }
      }
    };

    void loadTradeDetail();
    return () => {
      isActive = false;
    };
  }, [selectedTradeId, t]);

  useEffect(() => {
    if (!tradeDetail?.record.ticker) {
      setFeedback(null);
      return;
    }

    let isActive = true;

    const loadFeedback = async () => {
      try {
        const data = await getTickerTradeFeedback(tradeDetail.record.ticker, {
          limit: 3,
        });
        if (!isActive) {
          return;
        }
        setFeedback(data);
      } catch {
        if (!isActive) {
          return;
        }

        setFeedback(null);
      }
    };

    void loadFeedback();
    return () => {
      isActive = false;
    };
  }, [tradeDetail?.record.ticker]);

  const refreshTrades = async (preferredTradeId?: string) => {
    setLoadingTrades(true);
    setTradesError(null);

    try {
      const data = await listTrades();
      setTrades(data);
      setSelectedTradeId((current) => {
        if (preferredTradeId && data.some((trade) => trade.trade_id === preferredTradeId)) {
          return preferredTradeId;
        }
        if (current && data.some((trade) => trade.trade_id === current)) {
          return current;
        }
        return data[0]?.trade_id ?? null;
      });
    } catch (error) {
      setTradesError(
        error instanceof Error
          ? error.message
          : t("journal.error.loadHistory", "Unable to load trade history")
      );
    } finally {
      setLoadingTrades(false);
    }
  };

  const refreshTradeDetail = async (tradeId: string) => {
    setLoadingDetail(true);
    setDetailError(null);

    try {
      const data = await getTrade(tradeId);
      setTradeDetail(data);
    } catch (error) {
      setDetailError(
        error instanceof Error
          ? error.message
          : t("journal.error.loadDetail", "Unable to load trade details")
      );
    } finally {
      setLoadingDetail(false);
    }
  };

  const refreshFeedback = async (ticker: string) => {
    try {
      const data = await getTickerTradeFeedback(ticker, { limit: 3 });
      setFeedback(data);
    } catch {
      setFeedback(null);
    }
  };

  const filteredTrades = useMemo(() => {
    return trades
      .filter((trade) => {
        const normalizedFilter = tickerFilter.trim().toUpperCase();
        const matchesTicker =
          !normalizedFilter ||
          trade.ticker.includes(normalizedFilter) ||
          trade.trade_id.toUpperCase().includes(normalizedFilter);
        const matchesStatus =
          statusFilter === "all" || trade.status.toLowerCase() === statusFilter;
        const matchesTimeWindow = withinTimeWindow(trade, timeWindow);
        return matchesTicker && matchesStatus && matchesTimeWindow;
      })
      .sort((left, right) => compareTradesNewestFirst(left, right));
  }, [statusFilter, tickerFilter, timeWindow, trades]);

  const tradeTickerGroups = useMemo<TradeTickerGroup[]>(() => {
    const grouped = new Map<string, TradeRecord[]>();

    for (const trade of filteredTrades) {
      const current = grouped.get(trade.ticker) ?? [];
      current.push(trade);
      grouped.set(trade.ticker, current);
    }

    return Array.from(grouped.entries())
      .map(([ticker, tickerTrades]) => {
        const sortedTrades = [...tickerTrades].sort((left, right) =>
          compareTradesNewestFirst(left, right)
        );
        const latestTrade = sortedTrades[0];
        return {
          ticker,
          displaySymbol: latestTrade.display_symbol ?? ticker,
          trades: sortedTrades,
          latestTrade,
        };
      })
      .sort((left, right) => compareTradesNewestFirst(left.latestTrade, right.latestTrade));
  }, [filteredTrades]);

  useEffect(() => {
    if (filteredTrades.length === 0 || !selectedTradeId) {
      return;
    }

    if (!filteredTrades.some((trade) => trade.trade_id === selectedTradeId)) {
      setSelectedTradeId(filteredTrades[0].trade_id);
    }
  }, [filteredTrades, selectedTradeId]);

  useEffect(() => {
    setExpandedTickerGroups((current) => {
      let changed = false;
      const next = { ...current };

      tradeTickerGroups.forEach((group, index) => {
        if (typeof next[group.ticker] !== "boolean") {
          next[group.ticker] = index === 0;
          changed = true;
        }
      });

      return changed ? next : current;
    });
  }, [tradeTickerGroups]);

  useEffect(() => {
    if (!selectedTradeId) {
      return;
    }

    const selectedTrade = trades.find((trade) => trade.trade_id === selectedTradeId);
    if (!selectedTrade) {
      return;
    }

    setExpandedTickerGroups((current) =>
      current[selectedTrade.ticker] ? current : { ...current, [selectedTrade.ticker]: true }
    );
  }, [selectedTradeId, trades]);

  useEffect(() => {
    if (!isResizingHistory) {
      return;
    }

    const handlePointerMove = (event: PointerEvent) => {
      const left = historyGridRef.current?.getBoundingClientRect().left ?? 0;
      setHistoryPaneWidth(Math.min(620, Math.max(300, event.clientX - left)));
      setIsHistoryCollapsed(false);
    };
    const handlePointerUp = () => setIsResizingHistory(false);

    window.addEventListener("pointermove", handlePointerMove);
    window.addEventListener("pointerup", handlePointerUp);
    return () => {
      window.removeEventListener("pointermove", handlePointerMove);
      window.removeEventListener("pointerup", handlePointerUp);
    };
  }, [isResizingHistory]);

  const statusOptions = useMemo(() => {
    const values = Array.from(
      new Set(
        trades
          .map((trade) => trade.status.trim().toLowerCase())
          .filter((status) => status.length > 0)
      )
    ).sort();

    return ["all", ...values];
  }, [trades]);

  const selectedReview =
    tradeDetail?.reviews.find((review) => review.review_type === reviewTab) ?? null;
  const activeReviewGeneration =
    pendingReviewGeneration &&
    tradeDetail?.record.trade_id === pendingReviewGeneration.tradeId &&
    reviewTab === pendingReviewGeneration.reviewType
      ? pendingReviewGeneration
      : null;
  const activeReviewGenerationError =
    reviewGenerationError &&
    tradeDetail?.record.trade_id === reviewGenerationError.tradeId &&
    reviewTab === reviewGenerationError.reviewType
      ? reviewGenerationError
      : null;
  const openTrades = trades.filter((trade) => trade.status.toLowerCase() === "open");
  const reviewCoverageLabel = tradeDetail
    ? `${tradeDetail.reviews.length}/2 reviews`
    : "0/2 reviews";
  const sameTickerFeedbackReviews = feedback?.reviews ?? [];
  const currentTradeFeedbackReviews =
    tradeDetail
      ? sameTickerFeedbackReviews.filter(
          (review) => review.trade_id === tradeDetail.record.trade_id
        )
      : [];
  const selectionSummaryCards = useMemo(() => {
    if (!tradeDetail) {
      return [];
    }

    return [
      {
        label: "Trade Health",
        value: localizeTradeValue(tradeDetail.record.status, t),
        hint: `${localizeTradeValue(tradeDetail.record.side, t)} · ${tradeDetail.record.market.toUpperCase()}`,
      },
      {
        label: "Review Coverage",
        value: reviewCoverageLabel,
        hint: `${tradeDetail.record.analysis_references.length} linked snapshots`,
      },
      {
        label: "Feedback Loop",
        value:
          sameTickerFeedbackReviews.length > 0
            ? t("journal.feedbackReady", "Ready")
            : t("journal.feedbackBuilding", "Building"),
        hint:
          sameTickerFeedbackReviews.length > 0
            ? `${sameTickerFeedbackReviews.length} same-ticker saved examples; ${currentTradeFeedbackReviews.length} on this trade`
            : "Save at least one review to seed future context",
      },
    ];
  }, [
    currentTradeFeedbackReviews.length,
    reviewCoverageLabel,
    sameTickerFeedbackReviews.length,
    t,
    tradeDetail,
  ]);

  const handleTradeSaved = (record: TradeRecord) => {
    setShowCreateTrade(false);
    setShowEditTrade(false);
    setShowCloseTrade(false);
    setSelectedTradeId(record.trade_id);
    void refreshTrades(record.trade_id);
    void refreshTradeDetail(record.trade_id);
    void refreshFeedback(record.ticker);
  };

  const handleReviewSaved = (review: TradeReview) => {
    setEditingReviewType(null);
    setReviewTab(review.review_type);
    setPendingReviewGeneration((current) =>
      current?.tradeId === review.trade_id && current.reviewType === review.review_type
        ? null
        : current
    );
    setReviewGenerationError(null);
    void refreshTrades(review.trade_id);
    void refreshTradeDetail(review.trade_id);
    void refreshFeedback(review.ticker);
  };

  const handleGenerateReviewRequested = (
    record: TradeRecord,
    reviewType: TradeReviewType,
    payload: TradeReviewGenerateRequest
  ) => {
    setEditingReviewType(null);
    setReviewTab(reviewType);
    setSelectedTradeId(record.trade_id);
    setReviewGenerationError(null);
    setPendingReviewGeneration({
      tradeId: record.trade_id,
      reviewType,
      startedAt: new Date().toISOString(),
    });

    void generateTradeReview(record.trade_id, reviewType, payload)
      .then((review) => {
        handleReviewSaved(review);
      })
      .catch((error) => {
        setPendingReviewGeneration((current) =>
          current?.tradeId === record.trade_id && current.reviewType === reviewType
            ? null
            : current
        );
        setReviewGenerationError({
          tradeId: record.trade_id,
          reviewType,
          message:
            error instanceof Error
              ? error.message
              : t("tradeReview.error.generate", "Unable to generate the AI review"),
        });
      });
  };

  const topbarActions = useMemo(
    () => (
      <Button
        type="button"
        className="workbench-topbar-new"
        onClick={() => setShowCreateTrade(true)}
      >
        {t("journal.recordTrade", "Record Trade")}
      </Button>
    ),
    [t]
  );

  useEffect(() => {
    setTopbarActions(topbarActions);
    return () => setTopbarActions(null);
  }, [setTopbarActions, topbarActions]);

  return (
    <>
      <main className="workbench-page-shell flex min-h-[100vh] flex-1 flex-col">
        <div className="workbench-content-frame flex flex-col gap-6">
          <PageHeader
            eyebrow={t("sidebar.tradeJournal", "Trade Journal")}
            title={t(
              "journal.title",
              "Record trades, separate entry and exit reviews, and preview future same-ticker feedback"
            )}
            actions={
              onOpenSidebar ? (
                  <Button
                    type="button"
                    variant={sidebarOpen ? "default" : "secondary"}
                    className={`md:hidden ${
                      sidebarOpen
                        ? "bg-[var(--primary-soft)] text-[var(--primary-strong)] shadow-none"
                        : "text-slate-600"
                    }`}
                    onClick={onOpenSidebar}
                  >
                    {t("common.menu", "Menu")}
                  </Button>
              ) : null
            }
          >
            <div className="grid gap-4 xl:grid-cols-[minmax(0,1fr)_180px_180px]">
              <label className="field-shell block rounded-3xl border border-[var(--border)] bg-white/90 p-4">
                <span className="text-xs font-semibold uppercase tracking-[0.24em] text-slate-500">
                  {t("journal.filterLabel", "Filter by Ticker or Trade ID")}
                </span>
                <Input
                  type="text"
                  value={tickerFilter}
                  onChange={(event) => setTickerFilter(event.target.value)}
                  placeholder={t("journal.filterPlaceholder", "MSFT or trade_id")}
                  className="mt-3 border-[var(--border)] bg-[var(--surface-strong)] text-slate-800"
                />
              </label>

              <label className="field-shell block rounded-3xl border border-[var(--border)] bg-white/90 p-4">
                <span className="text-xs font-semibold uppercase tracking-[0.24em] text-slate-500">
                  {t("journal.status", "Status")}
                </span>
                <Select value={statusFilter} onValueChange={setStatusFilter}>
                  <SelectTrigger className="mt-3 border-[var(--border)] bg-[var(--surface-strong)] text-slate-800">
                    <SelectValue placeholder={t("journal.status", "Status")} />
                  </SelectTrigger>
                  <SelectContent>
                  {statusOptions.map((status) => (
                    <SelectItem key={status} value={status}>
                      {localizeTradeValue(status, t)}
                    </SelectItem>
                  ))}
                  </SelectContent>
                </Select>
              </label>

              <label className="field-shell block rounded-3xl border border-[var(--border)] bg-white/90 p-4">
                <span className="text-xs font-semibold uppercase tracking-[0.24em] text-slate-500">
                  {t("journal.timeWindow", "Time Window")}
                </span>
                <Select value={timeWindow} onValueChange={(value) => setTimeWindow(value as TimeWindow)}>
                  <SelectTrigger className="mt-3 border-[var(--border)] bg-[var(--surface-strong)] text-slate-800">
                    <SelectValue placeholder={t("journal.timeWindow", "Time Window")} />
                  </SelectTrigger>
                  <SelectContent>
                  <SelectItem value="all">{t("journal.timeWindow.all", "all")}</SelectItem>
                  <SelectItem value="30d">
                    {t("journal.timeWindow.30d", "last 30 days")}
                  </SelectItem>
                  <SelectItem value="90d">
                    {t("journal.timeWindow.90d", "last 90 days")}
                  </SelectItem>
                  <SelectItem value="365d">
                    {t("journal.timeWindow.365d", "last 12 months")}
                  </SelectItem>
                  </SelectContent>
                </Select>
              </label>
            </div>

            <div className="mt-6 grid gap-4 md:grid-cols-3">
              <SummaryCard
                label={t("journal.summary.totalRecords", "Total Records")}
                value={String(trades.length)}
                hint={t(
                  "journal.summary.totalHint",
                  "Hand-entered trades saved against the backend schema"
                )}
              />
              <SummaryCard
                label={t("journal.summary.openStatus", "Open Status")}
                value={String(openTrades.length)}
                hint={t(
                  "journal.summary.openHint",
                  "Trades still marked open in the manual journal"
                )}
              />
              <SummaryCard
                label={t("journal.summary.visible", "Visible in Filter")}
                value={String(filteredTrades.length)}
                hint={t(
                  "journal.summary.visibleHint",
                  "History filtered by ticker, status, and activity window"
                )}
              />
            </div>
          </PageHeader>

          <section
            ref={historyGridRef}
            style={
              {
                "--journal-history-width": isHistoryCollapsed
                  ? "5.5rem"
                  : `${historyPaneWidth}px`,
              } as CSSProperties
            }
            className="grid gap-6 transition-[grid-template-columns] duration-300 xl:[grid-template-columns:minmax(5.5rem,var(--journal-history-width))_minmax(0,1fr)]"
          >
            <Card className={cn("card-surface relative p-4 md:p-5", isHistoryCollapsed && "p-3 md:p-3")}>
              {!isHistoryCollapsed ? (
                <div
                  role="separator"
                  aria-label={t("journal.resizeHistory", "Resize trade history")}
                  aria-orientation="vertical"
                  className="absolute -right-3 top-8 hidden h-[calc(100%-4rem)] w-6 cursor-col-resize items-center justify-center xl:flex"
                  onPointerDown={(event) => {
                    event.preventDefault();
                    setIsResizingHistory(true);
                  }}
                >
                  <span className="h-16 w-1 rounded-full bg-[var(--border)] shadow-[0_0_0_3px_rgba(255,255,255,0.75)]" />
                </div>
              ) : null}
              <CardContent className="p-0">
              <div
                className={cn(
                  "flex items-center justify-between gap-4",
                  isHistoryCollapsed && "justify-center"
                )}
              >
                <div className={cn(isHistoryCollapsed && "sr-only")}>
                  <p className="text-xs font-semibold uppercase tracking-[0.3em] text-slate-500">
                    {t("journal.history", "History")}
                  </p>
                  <h2 className="mt-2 text-xl font-semibold text-slate-900">
                    {t("journal.tradeRecords", "Trade records")}
                  </h2>
                </div>
                <div className="flex items-center gap-2">
                  {!isHistoryCollapsed ? (
                    <Badge variant="secondary" className="text-slate-500">
                      {t("sidebar.shownCount", ({ count }) => `${count} shown`, {
                        count: filteredTrades.length,
                      })}
                    </Badge>
                  ) : null}
                  <Button
                    type="button"
                    variant="secondary"
                    size="icon"
                    aria-label={
                      isHistoryCollapsed
                        ? t("journal.expandHistory", "Expand trade history")
                        : t("journal.collapseHistory", "Collapse trade history")
                    }
                    onClick={() => setIsHistoryCollapsed((current) => !current)}
                    title={
                      isHistoryCollapsed
                        ? t("journal.expandHistory", "Expand trade history")
                        : t("journal.collapseHistory", "Collapse trade history")
                    }
                  >
                    {isHistoryCollapsed ? (
                      <PanelLeftOpen className="size-4" aria-hidden />
                    ) : (
                      <PanelLeftClose className="size-4" aria-hidden />
                    )}
                  </Button>
                </div>
              </div>

              {tradesError ? (
                <div className="mt-4 rounded-3xl border border-rose-200 bg-rose-50 px-4 py-4 text-sm text-rose-700">
                  {tradesError}
                </div>
              ) : loadingTrades ? (
                <div className="mt-4 rounded-3xl border border-dashed border-[var(--border)] bg-[var(--surface-strong)] px-4 py-8 text-sm text-slate-500">
                  {t("journal.loadingHistory", "Loading manual trade history...")}
                </div>
              ) : filteredTrades.length === 0 ? (
                <div className="mt-4 rounded-3xl border border-dashed border-[var(--border)] bg-[var(--surface-strong)] px-5 py-8 text-sm text-slate-500">
                  <p>
                    {t(
                      "journal.noTradeMatch",
                      "No trade records match the current filters."
                    )}
                  </p>
                  <Button type="button" className="mt-4" onClick={() => setShowCreateTrade(true)}>
                    {t("journal.recordFirstTrade", "Record First Trade")}
                  </Button>
                </div>
              ) : (
                <div className={cn("mt-4 space-y-3", isHistoryCollapsed && "space-y-2")}>
                  {tradeTickerGroups.map((group) => {
                    const isExpanded = expandedTickerGroups[group.ticker] ?? false;
                    const selectedWithinGroup = group.trades.some(
                      (trade) => trade.trade_id === selectedTradeId
                    );
                    const latestTimestamp = formatDateTime(
                      activityDateValue(group.latestTrade),
                      locale,
                      t("common.notSet", "Not set")
                    );

                    if (isHistoryCollapsed) {
                      return (
                        <Button
                          key={group.ticker}
                          type="button"
                          data-active={selectedWithinGroup}
                          variant="secondary"
                          className={cn(
                            "h-auto w-full flex-col gap-1 rounded-2xl px-2 py-3 text-center",
                            selectedWithinGroup
                              ? "border-[var(--primary)] bg-[var(--primary-soft)]/80 text-slate-900"
                              : "bg-white/85 text-slate-700 hover:bg-white"
                          )}
                          title={`${group.displaySymbol} · ${group.trades.length}`}
                          onClick={() => {
                            setSelectedTradeId(group.latestTrade.trade_id);
                            setExpandedTickerGroups((current) => ({
                              ...current,
                              [group.ticker]: true,
                            }));
                          }}
                        >
                          <span className="max-w-full truncate font-mono text-[11px] font-semibold">
                            {compactTickerLabel(group.displaySymbol)}
                          </span>
                          <span className="rounded-full border border-[var(--border)] bg-white px-2 py-0.5 text-[10px] text-slate-500">
                            {group.trades.length}
                          </span>
                        </Button>
                      );
                    }

                    return (
                      <div
                        key={group.ticker}
                        className={cn(
                          "rounded-[28px] border bg-white/70 p-3",
                          selectedWithinGroup
                            ? "border-[var(--primary)] shadow-[0_18px_36px_rgba(28,36,48,0.1)]"
                            : "border-[var(--border)]"
                        )}
                      >
                        <Button
                          type="button"
                          variant="secondary"
                          className="h-auto w-full items-start justify-between rounded-[22px] bg-white/80 px-4 py-3 text-left hover:bg-white"
                          aria-expanded={isExpanded}
                          onClick={() =>
                            setExpandedTickerGroups((current) => ({
                              ...current,
                              [group.ticker]: !(current[group.ticker] ?? false),
                            }))
                          }
                        >
                          <span className="flex min-w-0 items-start gap-3">
                            <span className="mt-1 grid size-6 shrink-0 place-items-center rounded-full border border-[var(--border)] bg-[var(--surface-strong)] text-slate-600">
                              {isExpanded ? (
                                <ChevronDown className="size-4" aria-hidden />
                              ) : (
                                <ChevronRight className="size-4" aria-hidden />
                              )}
                            </span>
                            <span className="min-w-0">
                              <span className="block truncate text-lg font-semibold text-slate-900">
                                {group.displaySymbol}
                              </span>
                              <span className="mt-1 block text-xs text-slate-500">
                                {t(
                                  "journal.tickerGroupLatest",
                                  ({ value }) => `Latest ${value}`,
                                  { value: latestTimestamp }
                                )}
                              </span>
                            </span>
                          </span>
                          <Badge variant="secondary" className="shrink-0 text-slate-500">
                            {t("journal.tradeCount", ({ count }) => `${count} logs`, {
                              count: group.trades.length,
                            })}
                          </Badge>
                        </Button>

                        {isExpanded ? (
                          <div className="mt-3 space-y-3">
                            {group.trades.map((trade) => {
                              const isSelected = selectedTradeId === trade.trade_id;
                              return (
                                <Button
                                  key={trade.trade_id}
                                  type="button"
                                  data-active={isSelected}
                                  variant="secondary"
                                  className={cn(
                                    "h-auto w-full flex-col items-stretch justify-start overflow-hidden rounded-[24px] p-4 text-left whitespace-normal",
                                    isSelected
                                      ? "border-[var(--primary)] bg-[var(--primary-soft)]/75 text-slate-900 shadow-[0_14px_28px_rgba(28,36,48,0.1)] hover:bg-[var(--primary-soft)]/75"
                                      : "bg-white/85 text-slate-900 hover:bg-white"
                                  )}
                                  onClick={() => setSelectedTradeId(trade.trade_id)}
                                >
                                  <div className="flex items-start justify-between gap-4">
                                    <div className="min-w-0">
                                      <p className="font-mono text-[11px] text-slate-500">
                                        {formatDateTime(
                                          activityDateValue(trade),
                                          locale,
                                          t("common.notSet", "Not set")
                                        )}
                                      </p>
                                      <p className="mt-1 truncate font-mono text-[11px] text-slate-500">
                                        {trade.trade_id}
                                      </p>
                                    </div>
                                    <div className="flex flex-wrap justify-end gap-2">
                                      <StatusBadge label={trade.side} tone="accent" />
                                      <StatusBadge label={trade.status} tone="primary" />
                                    </div>
                                  </div>
                                  <div className="mt-4 grid w-full gap-3 sm:grid-cols-2">
                                    <MetaItem
                                      label={t("journal.entry", "Entry")}
                                      value={formatDateTime(
                                        trade.entry_timestamp,
                                        locale,
                                        t("common.notSet", "Not set")
                                      )}
                                    />
                                    <MetaItem
                                      label={t("journal.exit", "Exit")}
                                      value={formatDateTime(
                                        trade.exit_timestamp,
                                        locale,
                                        t("common.notSet", "Not set")
                                      )}
                                    />
                                    <MetaItem
                                      label={t("journal.entryPrice", "Entry Px")}
                                      value={formatNumber(
                                        trade.entry_price,
                                        locale,
                                        t("common.notSet", "Not set")
                                      )}
                                    />
                                    <MetaItem
                                      label={t("journal.exitPrice", "Exit Px")}
                                      value={formatNumber(
                                        trade.exit_price,
                                        locale,
                                        t("common.notSet", "Not set")
                                      )}
                                    />
                                  </div>
                                </Button>
                              );
                            })}
                          </div>
                        ) : null}
                      </div>
                    );
                  })}
                </div>
              )}
              </CardContent>
            </Card>

            <div className="space-y-6">
              <section className="viewer-frame px-6 py-6 md:px-8">
                {detailError ? (
                  <div className="rounded-3xl border border-rose-200 bg-rose-50 px-5 py-5 text-sm text-rose-700">
                    {detailError}
                  </div>
                ) : loadingDetail ? (
                  <div className="rounded-3xl border border-dashed border-[var(--border)] bg-[var(--surface-strong)] px-5 py-10 text-sm text-slate-500">
                    {t(
                      "journal.loadingDetail",
                      "Loading trade record and review details..."
                    )}
                  </div>
                ) : !tradeDetail ? (
                  <div className="rounded-3xl border border-dashed border-[var(--border)] bg-[var(--surface-strong)] px-5 py-10 text-sm text-slate-500">
                    {t(
                      "journal.selectTrade",
                      "Select a trade record to inspect its fields, snapshot references, and review history."
                    )}
                  </div>
                ) : (
                  <div className="space-y-6">
                    <div className="flex flex-wrap items-start justify-between gap-4">
                      <div>
                        <p className="text-xs font-semibold uppercase tracking-[0.32em] text-[var(--primary)]">
                          {t("journal.stableTradeId", "Stable trade_id")}
                        </p>
                        <h2 className="mt-2 text-3xl font-semibold text-slate-900">
                          {tradeDetail.record.display_symbol ?? tradeDetail.record.ticker}
                        </h2>
                        <p className="mt-2 font-mono text-[12px] text-slate-500">
                          {tradeDetail.record.trade_id}
                        </p>
                      </div>

                      <div className="flex flex-wrap items-center gap-3">
                        <StatusBadge label={tradeDetail.record.side} tone="accent" />
                        <StatusBadge label={tradeDetail.record.status} tone="primary" />
                        {tradeDetail.record.status.toLowerCase() === "open" ? (
                          <Button type="button" size="sm" onClick={() => setShowCloseTrade(true)}>
                            {t("journal.closeTrade", "Close Trade")}
                          </Button>
                        ) : null}
                        <Button type="button" variant="secondary" size="sm" onClick={() => setShowEditTrade(true)}>
                          {t("journal.editTrade", "Edit Trade")}
                        </Button>
                      </div>
                    </div>

                    <div className="grid gap-4 md:grid-cols-3">
                      {selectionSummaryCards.map((card) => (
                        <DetailMetric
                          key={card.label}
                          label={card.label}
                          value={card.value}
                          hint={card.hint}
                        />
                      ))}
                    </div>

                    <TickerPricePanel
                      symbol={tradeDetail.record.canonical_symbol ?? tradeDetail.record.ticker}
                      market={tradeDetail.record.market}
                      title={t("journal.priceTrend", "Price Trend")}
                      subtitle={t(
                        "journal.priceTrendHint",
                        "1000-day vendor-backed history for the selected trade ticker."
                      )}
                    />

                    <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
                      <MetaCard
                        label={t("journal.marketExchange", "Market / Exchange")}
                        value={`${tradeDetail.record.market.toUpperCase()}${tradeDetail.record.exchange ? ` · ${tradeDetail.record.exchange}` : ""}`}
                      />
                      <MetaCard
                        label={t("journal.strategyTags", "Strategy Tags")}
                        value={tradeDetail.record.strategy_tags.join(", ")}
                      />
                      <MetaCard
                        label={t("journal.plannedHorizon", "Planned Horizon")}
                        value={tradeDetail.record.planned_horizon}
                      />
                      <MetaCard
                        label={t("journal.size", "Size")}
                        value={formatNumber(
                          tradeDetail.record.size,
                          locale,
                          t("common.notSet", "Not set")
                        )}
                      />
                      <MetaCard
                        label={t("journal.lastUpdated", "Last Updated")}
                        value={formatDateTime(
                          tradeDetail.record.updated_at,
                          locale,
                          t("common.notSet", "Not set")
                        )}
                      />
                      <MetaCard
                        label={t("journal.realizedReturn", "Realized Return")}
                        value={formatPercent(
                          tradeDetail.record.derived_metrics?.realized_return_pct ?? null,
                          locale,
                          t("common.notSet", "Not set")
                        )}
                      />
                      <MetaCard
                        label={t("journal.rMultiple", "R Multiple")}
                        value={formatNumber(
                          tradeDetail.record.derived_metrics?.r_multiple ?? null,
                          locale,
                          t("common.notSet", "Not set")
                        )}
                      />
                      <MetaCard
                        label={t("journal.entry", "Entry")}
                        value={formatDateTime(
                          tradeDetail.record.entry_timestamp,
                          locale,
                          t("common.notSet", "Not set")
                        )}
                      />
                      <MetaCard
                        label={t("journal.exit", "Exit")}
                        value={formatDateTime(
                          tradeDetail.record.exit_timestamp,
                          locale,
                          t("common.notSet", "Not set")
                        )}
                      />
                      <MetaCard
                        label={t("journal.stopLoss", "Stop Loss")}
                        value={formatNumber(
                          tradeDetail.record.stop_loss,
                          locale,
                          t("common.notSet", "Not set")
                        )}
                      />
                      <MetaCard
                        label={t("journal.takeProfit", "Take Profit")}
                        value={formatNumber(
                          tradeDetail.record.take_profit,
                          locale,
                          t("common.notSet", "Not set")
                        )}
                      />
                    </div>

                    <div className="grid gap-4 xl:grid-cols-[minmax(0,1.25fr)_minmax(0,0.75fr)]">
                      <section className="rounded-[28px] border border-[var(--border)] bg-white/90 p-5">
                        <p className="text-xs font-semibold uppercase tracking-[0.26em] text-slate-500">
                          {t("journal.entryReason", "Entry Reason")}
                        </p>
                        <p className="mt-3 whitespace-pre-wrap text-sm leading-7 text-slate-700">
                          {tradeDetail.record.entry_reason}
                        </p>
                      </section>

                      <section className="rounded-[28px] border border-[var(--border)] bg-white/90 p-5">
                        <p className="text-xs font-semibold uppercase tracking-[0.26em] text-slate-500">
                          {t("journal.invalidationCondition", "Invalidation Condition")}
                        </p>
                        <p className="mt-3 whitespace-pre-wrap text-sm leading-7 text-slate-700">
                          {tradeDetail.record.invalidation_condition}
                        </p>
                      </section>
                    </div>

                    <div className="grid gap-4 xl:grid-cols-2">
                      <section className="rounded-[28px] border border-[var(--border)] bg-white/90 p-5">
                        <p className="text-xs font-semibold uppercase tracking-[0.26em] text-slate-500">
                          {t("journal.exitReason", "Exit Reason")}
                        </p>
                        <p className="mt-3 whitespace-pre-wrap text-sm leading-7 text-slate-700">
                          {tradeDetail.record.exit_reason ||
                            t("journal.noExitReason", "No exit reason saved.")}
                        </p>
                      </section>
                      <section className="rounded-[28px] border border-[var(--border)] bg-white/90 p-5">
                        <p className="text-xs font-semibold uppercase tracking-[0.26em] text-slate-500">
                          {t("journal.planExecution", "Plan Execution")}
                        </p>
                        <p className="mt-3 text-sm leading-7 text-slate-700">
                          {tradeDetail.record.plan_execution.replaceAll("_", " ")}
                        </p>
                      </section>
                    </div>

                    <section className="rounded-[28px] border border-[var(--border)] bg-white/90 p-5">
                      <div className="flex flex-wrap items-center justify-between gap-4">
                        <div>
                          <p className="text-xs font-semibold uppercase tracking-[0.26em] text-slate-500">
                            {t(
                              "journal.snapshotReferences",
                              "Linked Snapshot References"
                            )}
                          </p>
                          <h3 className="mt-2 text-xl font-semibold text-slate-900">
                            {t(
                              "journal.snapshotOnly",
                              "Snapshot references only, not copied report content"
                            )}
                          </h3>
                        </div>
                        <Badge variant="secondary" className="text-slate-500">
                          {t("journal.linkedCount", ({ count }) => `${count} linked`, {
                            count: tradeDetail.record.analysis_references.length,
                          })}
                        </Badge>
                      </div>

                      {tradeDetail.record.analysis_references.length === 0 ? (
                        <div className="mt-4 rounded-3xl border border-dashed border-[var(--border)] bg-[var(--surface-strong)] px-5 py-6 text-sm text-slate-500">
                          {t(
                            "journal.noSnapshots",
                            "No analysis snapshots are attached yet. Add them on the trade record before saving manual reviews."
                          )}
                        </div>
                      ) : (
                        <div className="mt-4 space-y-3">
                          {tradeDetail.record.analysis_references.map((reference) => (
                            <div
                              key={`${reference.report_path}-${reference.full_state_log_path}-${reference.analysis_date}`}
                              className="rounded-3xl border border-[var(--border)] bg-[var(--surface-strong)]/85 p-4"
                            >
                              <p className="text-xs font-semibold uppercase tracking-[0.22em] text-slate-500">
                                {reference.analysis_date}
                              </p>
                              <p className="mt-2 break-all text-sm font-medium text-slate-800">
                                {reference.report_path}
                              </p>
                              <p className="mt-1 break-all text-xs text-slate-500">
                                {reference.full_state_log_path}
                              </p>
                            </div>
                          ))}
                        </div>
                      )}
                    </section>

                    <section className="rounded-[28px] border border-[var(--border)] bg-white/90 p-5">
                      <div className="flex flex-wrap items-center justify-between gap-4">
                        <div>
                          <p className="text-xs font-semibold uppercase tracking-[0.26em] text-slate-500">
                            {t("journal.tradeReviews", "Trade Reviews")}
                          </p>
                          <h3 className="mt-2 text-xl font-semibold text-slate-900">
                            {t(
                              "journal.distinguishReviews",
                              "Distinguish entry_review and exit_review on the same trade_id"
                            )}
                          </h3>
                        </div>
                        <Button
                          type="button"
                          variant="secondary"
                          size="sm"
                          onClick={() => setEditingReviewType(reviewTab)}
                          disabled={Boolean(activeReviewGeneration)}
                        >
                          {selectedReview
                            ? t("journal.editReview", "Edit Review")
                            : t("journal.createReview", "Create Review")}
                        </Button>
                      </div>

                      <Tabs value={reviewTab} onValueChange={(value) => setReviewTab(value as TradeReviewType)} className="mt-5">
                        <TabsList>
                          {(["entry_review", "exit_review"] as TradeReviewType[]).map((type) => {
                            const review = tradeDetail.reviews.find(
                              (item) => item.review_type === type
                            );
                            return (
                              <TabsTrigger key={type} value={type}>
                                <span className="capitalize">
                                  {type === "entry_review"
                                    ? t("journal.entryReview", "Entry Review")
                                    : t("journal.exitReview", "Exit Review")}
                                </span>
                                <span className="ml-2 text-[11px] opacity-70">
                                  {review
                                    ? t("journal.reviewSaved", "saved")
                                    : t("journal.reviewEmpty", "empty")}
                                </span>
                              </TabsTrigger>
                            );
                          })}
                        </TabsList>
                      </Tabs>

                      {activeReviewGeneration ? (
                        <div className="mt-5 rounded-3xl border border-[var(--border)] bg-[var(--surface-strong)] px-5 py-6 text-sm text-slate-600">
                          <div className="flex flex-wrap items-center gap-3">
                            <span className="h-3 w-3 animate-pulse rounded-full bg-[var(--primary)]" aria-hidden />
                            <div>
                              <p className="font-semibold text-slate-800">
                                {t("tradeReview.generating", "Generating AI review...")}
                              </p>
                              <p className="mt-1 leading-6">
                                {t(
                                  "journal.reviewGenerationPending",
                                  "This review is being generated in the background. You can keep working here; the panel will refresh when it finishes."
                                )}
                              </p>
                            </div>
                          </div>
                        </div>
                      ) : activeReviewGenerationError ? (
                        <div className="mt-5 rounded-3xl border border-rose-200 bg-rose-50 px-5 py-5 text-sm text-rose-700">
                          {activeReviewGenerationError.message}
                        </div>
                      ) : !selectedReview ? (
                        <div className="mt-5 rounded-3xl border border-dashed border-[var(--border)] bg-[var(--surface-strong)] px-5 py-6 text-sm text-slate-500">
                          {t(
                            "journal.noReview",
                            ({ reviewType }) =>
                              `No ${reviewType} saved for this trade yet. Same-ticker history is available from the ticker-grouped list on the left.`,
                            {
                              reviewType:
                                reviewTab === "entry_review"
                                  ? t("journal.entryReview", "Entry Review")
                                  : t("journal.exitReview", "Exit Review"),
                            }
                          )}
                        </div>
                      ) : (
                        <div className="mt-5 space-y-5">
                          <div className="grid gap-4 md:grid-cols-2">
                            <ReviewCard
                              label={t("journal.thesisAssessment", "Thesis Assessment")}
                              value={selectedReview.thesis_assessment}
                            />
                            <ReviewCard
                              label={t("journal.timingAssessment", "Timing Assessment")}
                              value={selectedReview.timing_assessment}
                            />
                            <ReviewCard
                              label={t("journal.sizingAssessment", "Sizing Assessment")}
                              value={selectedReview.sizing_assessment}
                            />
                            <ReviewCard
                              label={t(
                                "journal.disciplineAssessment",
                                "Discipline Assessment"
                              )}
                              value={selectedReview.discipline_assessment}
                            />
                          </div>

                          <ReviewCard
                            label={t("journal.outcomeSummary", "Outcome Summary")}
                            value={selectedReview.outcome_summary}
                          />

                          <ReviewFollowupPanel
                            improvementActions={selectedReview.improvement_actions}
                            tickerLessons={selectedReview.ticker_specific_lessons}
                            crossTickerTags={selectedReview.cross_ticker_tags}
                          />

                          <div className="rounded-3xl border border-[var(--border)] bg-[var(--surface-strong)]/85 px-4 py-4 text-sm text-slate-600">
                            {t(
                              "journal.savedMeta",
                              ({ date, updatedAt }) =>
                                `Saved on ${date}, updated ${updatedAt}.`,
                              {
                                date: selectedReview.analysis_date,
                                updatedAt: formatDateTime(
                                  selectedReview.updated_at,
                                  locale,
                                  t("common.notSet", "Not set")
                                ),
                              }
                            )}
                            <span className="mx-1 rounded bg-white px-2 py-1 font-mono text-[12px] text-slate-700">
                              {selectedReview.review_id}
                            </span>
                          </div>
                        </div>
                      )}
                    </section>
                  </div>
                )}
              </section>
            </div>
          </section>
        </div>
      </main>

      <TradeRecordForm
        isOpen={showCreateTrade}
        mode="create"
        reports={reports}
        onClose={() => setShowCreateTrade(false)}
        onSaved={handleTradeSaved}
      />

      <TradeRecordForm
        isOpen={showEditTrade && Boolean(tradeDetail)}
        mode="edit"
        initialRecord={tradeDetail?.record ?? null}
        reports={reports}
        onClose={() => setShowEditTrade(false)}
        onSaved={handleTradeSaved}
      />

      <CloseTradeForm
        isOpen={showCloseTrade && Boolean(tradeDetail)}
        record={tradeDetail?.record ?? null}
        onClose={() => setShowCloseTrade(false)}
        onSaved={handleTradeSaved}
      />

      {editingReviewType && tradeDetail ? (
        <TradeReviewForm
          isOpen={Boolean(editingReviewType)}
          reviewType={editingReviewType}
          tradeRecord={tradeDetail.record}
          existingReview={
            tradeDetail.reviews.find(
              (review) => review.review_type === editingReviewType
            ) ?? null
          }
          onClose={() => setEditingReviewType(null)}
          onGenerateReview={(payload) =>
            handleGenerateReviewRequested(tradeDetail.record, editingReviewType, payload)
          }
          onSaved={handleReviewSaved}
        />
      ) : null}
    </>
  );
}

function SummaryCard({
  label,
  value,
  hint,
}: {
  label: string;
  value: string;
  hint: string;
}) {
  return (
    <div className="rounded-[28px] border border-[var(--border)] bg-white/90 px-5 py-5 shadow-[0_18px_36px_rgba(18,28,41,0.05)]">
      <p className="text-xs font-semibold uppercase tracking-[0.24em] text-slate-500">
        {label}
      </p>
      <p className="mt-3 text-3xl font-semibold text-slate-900">{value}</p>
      <p className="mt-2 text-sm leading-6 text-slate-500">{hint}</p>
    </div>
  );
}

function MetaCard({
  label,
  value,
}: {
  label: string;
  value: string;
}) {
  return (
    <div className="viewer-meta-card">
      <p className="viewer-meta-label">{label}</p>
      <p className="mt-3 text-sm font-semibold text-slate-800">{value}</p>
    </div>
  );
}

function DetailMetric({
  label,
  value,
  hint,
}: {
  label: string;
  value: string;
  hint: string;
}) {
  return (
    <div className="rounded-[26px] border border-[var(--border)] bg-white/90 px-5 py-5 shadow-[0_18px_36px_rgba(18,28,41,0.05)]">
      <p className="text-[10px] font-semibold uppercase tracking-[0.22em] text-slate-500">
        {label}
      </p>
      <p className="mt-3 text-2xl font-semibold tracking-tight text-slate-900">{value}</p>
      <p className="mt-2 text-sm leading-6 text-slate-500">{hint}</p>
    </div>
  );
}

function MetaItem({
  label,
  value,
}: {
  label: string;
  value: string;
}) {
  return (
    <div className="rounded-2xl border border-[var(--border)] bg-[var(--surface-strong)]/80 px-3 py-3">
      <p className="text-[10px] font-semibold uppercase tracking-[0.22em] text-slate-500">
        {label}
      </p>
      <p className="mt-2 text-sm font-semibold text-slate-800">{value}</p>
    </div>
  );
}

type ReviewTextMarker =
  | "Verdict"
  | "Score"
  | "Evidence"
  | "Impact"
  | "Cannot conclude"
  | "Record quality"
  | "Setup"
  | "Process"
  | "Confidence"
  | "Main root cause"
  | "Remediation";

type ReviewTextLanguage = "zh" | "en";

type LocalizedReviewText = Record<ReviewTextLanguage, string>;
type DisplayReviewTextMarker = Exclude<ReviewTextMarker, "Cannot conclude">;

const REVIEW_TEXT_MARKER_ALIASES: Record<ReviewTextMarker, string[]> = {
  Verdict: ["Verdict", "判断"],
  Score: ["Score", "评分"],
  Evidence: ["Evidence", "依据", "证据"],
  Impact: ["Impact", "影响"],
  "Cannot conclude": ["Cannot conclude"],
  "Record quality": ["Record quality", "记录质量"],
  Setup: ["Setup", "形态"],
  Process: ["Process", "过程"],
  Confidence: ["Confidence", "置信度"],
  "Main root cause": ["Main root cause", "主要原因"],
  Remediation: ["Remediation", "修复要求", "改进要求"],
};

const REVIEW_TEXT_LABELS: Record<DisplayReviewTextMarker, LocalizedReviewText> = {
  Verdict: { zh: "判断", en: "Verdict" },
  Score: { zh: "评分", en: "Score" },
  Evidence: { zh: "依据", en: "Evidence" },
  Impact: { zh: "影响", en: "Impact" },
  "Record quality": { zh: "记录质量", en: "Record quality" },
  Setup: { zh: "形态", en: "Setup" },
  Process: { zh: "过程", en: "Process" },
  Confidence: { zh: "置信度", en: "Confidence" },
  "Main root cause": { zh: "主要原因", en: "Main root cause" },
  Remediation: { zh: "修复", en: "Remediation" },
};

const REVIEW_TERM_LABELS: Record<string, LocalizedReviewText> = {
  technical_decision_checks: { zh: "技术检查", en: "technical checks" },
  local_price_history: { zh: "本地价格历史", en: "local price history" },
  key_metrics: { zh: "关键指标", en: "key metrics" },
  strategy_tags: { zh: "策略标签", en: "strategy tags" },
  entry_reason: { zh: "入场理由", en: "entry reason" },
  initial_thesis: { zh: "初始假设", en: "initial thesis" },
  invalidation_condition: { zh: "失效条件", en: "invalidation condition" },
  breakout_level: { zh: "突破位", en: "breakout level" },
  confirmation_method: { zh: "确认方式", en: "confirmation method" },
  entry_price: { zh: "入场价", en: "entry price" },
  previous_20d_high: { zh: "20日高点", en: "20-day high" },
  entry_vs_previous_20d_high_pct: {
    zh: "较20日高点",
    en: "entry vs. 20-day high",
  },
  latest_close: { zh: "最新收盘价", en: "latest close" },
  entry_vs_latest_close_pct: { zh: "较最新收盘价", en: "entry vs. latest close" },
  volume_vs_20d_avg: { zh: "较20日均量", en: "volume vs. 20-day average" },
  rsi_14: { zh: "RSI(14)", en: "RSI(14)" },
  close_vs_sma_20_pct: { zh: "较20日均线", en: "close vs. 20-day SMA" },
  atr_14: { zh: "ATR(14)", en: "ATR(14)" },
  stop_loss: { zh: "止损", en: "stop loss" },
  take_profit: { zh: "止盈", en: "take profit" },
  planned_horizon: { zh: "计划周期", en: "planned horizon" },
  plan_execution: { zh: "执行记录", en: "execution record" },
  external_news: { zh: "外部新闻", en: "external news" },
  take_profit_or_reward_target: {
    zh: "止盈或收益目标",
    en: "take profit or reward target",
  },
  testable_invalidation: { zh: "可验证失效条件", en: "testable invalidation" },
  reward_target: { zh: "收益目标", en: "reward target" },
  entry_vs_previous_20d_high: {
    zh: "较20日高点",
    en: "entry vs. 20-day high",
  },
  return_20d_pct: { zh: "20日涨幅", en: "20-day return" },
  account_risk: { zh: "账户风险", en: "account risk" },
  risk_reward: { zh: "风险收益比", en: "risk/reward" },
  position_size: { zh: "仓位", en: "position size" },
  size: { zh: "仓位", en: "size" },
  risk_plan_undefined: { zh: "风险计划未定义", en: "risk plan undefined" },
  breakout_execution_undefined: {
    zh: "突破执行未定义",
    en: "breakout execution undefined",
  },
  late_breakout_entry: { zh: "突破追高入场", en: "late breakout entry" },
  overextended_momentum: { zh: "动量延伸过高", en: "overextended momentum" },
  intraday_chase: { zh: "盘中追涨", en: "intraday chase" },
  breakout: { zh: "突破", en: "breakout" },
};

const REVIEW_VALUE_LABELS: Record<string, LocalizedReviewText> = {
  null: { zh: "未设置", en: "not set" },
  unknown: { zh: "未记录", en: "unknown" },
  unavailable: { zh: "不可用", en: "unavailable" },
  available: { zh: "可用", en: "available" },
  medium: { zh: "中等", en: "medium" },
  low: { zh: "低", en: "low" },
  high: { zh: "高", en: "high" },
  poor: { zh: "较差", en: "poor" },
  weak: { zh: "偏弱", en: "weak" },
  good: { zh: "良好", en: "good" },
  excellent: { zh: "优秀", en: "excellent" },
};

interface ReviewTextSegment {
  label: string | null;
  body: string;
}

function formatReviewTextSegments(value: string, locale: string): ReviewTextSegment[] {
  const normalized = value.trim();
  if (!normalized) {
    return [{ label: null, body: "" }];
  }
  const language = getReviewTextLanguage(locale);

  const pipeSegments = normalized
    .split(/\s*\|\s*/u)
    .map((segment) => segment.trim())
    .filter(Boolean);

  const rawSegments =
    pipeSegments.length > 1 ? pipeSegments : splitReviewTextByMarkers(normalized);

  return rawSegments
    .map((segment) => parseReviewTextSegment(segment, language))
    .filter(isReviewTextSegment);
}

function splitReviewTextByMarkers(value: string): string[] {
  const escapedMarkers = getReviewMarkerAliases().map(escapeRegExp);
  const markerPattern = new RegExp(
    `(^|[\\s|。；;])(?:${escapedMarkers.join("|")})\\s*[:：]`,
    "gu"
  );
  const matches = [...value.matchAll(markerPattern)];

  if (matches.length <= 1) {
    return [value];
  }

  const segments: string[] = [];
  const firstMarkerIndex = (matches[0].index ?? 0) + matches[0][1].length;
  const prefix = value.slice(0, firstMarkerIndex).trim();

  if (prefix) {
    segments.push(prefix);
  }

  matches.forEach((match, index) => {
    const start = (match.index ?? 0) + match[1].length;
    const nextMatch = matches[index + 1];
    const nextStart = nextMatch
      ? (nextMatch.index ?? 0) + nextMatch[1].length
      : value.length;
    const segment = value.slice(start, nextStart).trim();

    if (segment) {
      segments.push(segment.replace(/[。；.;]\s*$/u, ""));
    }
  });

  return segments;
}

function parseReviewTextSegment(
  segment: string,
  language: ReviewTextLanguage
): ReviewTextSegment | null {
  const markerAliases = getReviewMarkerAliases().map(escapeRegExp);
  const labelMatch = segment.match(
    new RegExp(`^(${markerAliases.join("|")})\\s*[:：]\\s*(.+)$`, "u")
  );

  if (!labelMatch) {
    return { label: null, body: prettifyReviewText(segment, language) };
  }

  const marker = getReviewTextMarker(labelMatch[1]);
  if (marker === "Cannot conclude") {
    return null;
  }

  return {
    label: REVIEW_TEXT_LABELS[marker][language],
    body: prettifyReviewText(labelMatch[2], language),
  };
}

function isReviewTextSegment(
  segment: ReviewTextSegment | null
): segment is ReviewTextSegment {
  return segment !== null;
}

function prettifyReviewText(value: string, localeOrLanguage: string): string {
  let output = value.trim();
  const language = getReviewTextLanguage(localeOrLanguage);

  const terms = Object.entries(REVIEW_TERM_LABELS).sort(
    ([left], [right]) => right.length - left.length
  );
  terms.forEach(([term, labels]) => {
    output = output.replace(
      new RegExp(`(^|[^A-Za-z0-9_])${escapeRegExp(term)}(?=$|[^A-Za-z0-9_])`, "giu"),
      (_, prefix: string) => `${prefix}${labels[language]}`
    );
  });

  Object.entries(REVIEW_VALUE_LABELS).forEach(([term, labels]) => {
    output = output.replace(
      new RegExp(`(^|[^A-Za-z0-9_])${escapeRegExp(term)}(?=$|[^A-Za-z0-9_])`, "giu"),
      (_, prefix: string) => `${prefix}${labels[language]}`
    );
  });

  const assignmentSeparator = language === "zh" ? "：" : ": ";
  const clauseSeparator = language === "zh" ? "；" : "; ";
  const listSeparator = language === "zh" ? "，" : ", ";

  return output
    .replace(/\s*=\s*/gu, assignmentSeparator)
    .replace(/\s*;\s*/gu, clauseSeparator)
    .replace(/\s*,\s*/gu, listSeparator)
    .replace(/\s{2,}/gu, " ");
}

function escapeRegExp(value: string): string {
  return value.replace(/[.*+?^${}()|[\]\\]/gu, "\\$&");
}

function getReviewMarkerAliases(): string[] {
  return Object.values(REVIEW_TEXT_MARKER_ALIASES)
    .flat()
    .sort((left, right) => right.length - left.length);
}

function getReviewTextMarker(value: string): ReviewTextMarker {
  const normalized = value.trim().toLowerCase();
  for (const [marker, aliases] of Object.entries(REVIEW_TEXT_MARKER_ALIASES)) {
    if (aliases.some((alias) => alias.toLowerCase() === normalized)) {
      return marker as ReviewTextMarker;
    }
  }
  return "Verdict";
}

function getReviewTextLanguage(locale: string): ReviewTextLanguage {
  return locale.toLowerCase().startsWith("zh") ? "zh" : "en";
}

function ReviewCard({
  label,
  value,
}: {
  label: string;
  value: string;
}) {
  const { locale } = usePreferences();
  const segments = formatReviewTextSegments(value, locale);

  return (
    <div className="rounded-[26px] border border-[var(--border)] bg-white/70 p-5 shadow-[0_18px_36px_rgba(18,28,41,0.035)]">
      <p className="text-xs font-semibold tracking-[0.18em] text-slate-500">
        {label}
      </p>
      <div className="mt-4 space-y-2 text-sm leading-7 text-slate-700">
        {segments.map((segment, index) => (
          <p
            key={`${segment.label ?? "text"}-${index}`}
            className="whitespace-pre-wrap"
          >
            {segment.label ? (
              <span className="mr-2 font-semibold text-slate-900">
                {segment.label}:
              </span>
            ) : null}
            {segment.body}
          </p>
        ))}
      </div>
    </div>
  );
}

function ReviewFollowupPanel({
  improvementActions,
  tickerLessons,
  crossTickerTags,
}: {
  improvementActions: string[];
  tickerLessons: string[];
  crossTickerTags: string[];
}) {
  const { locale, t } = usePreferences();

  return (
    <div className="grid gap-4 lg:grid-cols-[minmax(0,1.25fr)_minmax(0,0.75fr)]">
      <section className="rounded-[26px] border border-[var(--border)] bg-white/70 p-5 shadow-[0_18px_36px_rgba(18,28,41,0.035)]">
        <p className="text-xs font-semibold tracking-[0.18em] text-slate-500">
          {t("journal.improvementActions", "Improvement Actions")}
        </p>
        <ReviewListItems
          values={improvementActions}
          emptyLabel={t("journal.noneSaved", "None saved")}
          locale={locale}
        />
      </section>

      <section className="rounded-[26px] border border-[var(--border)] bg-white/70 p-5 shadow-[0_18px_36px_rgba(18,28,41,0.035)]">
        <p className="text-xs font-semibold tracking-[0.18em] text-slate-500">
          {t("journal.tickerSpecificLessons", "Ticker-Specific Lessons")}
        </p>
        <ReviewListItems
          values={tickerLessons}
          emptyLabel={t("journal.noneSaved", "None saved")}
          locale={locale}
          compact
        />

        {crossTickerTags.length > 0 ? (
          <div className="mt-5 border-t border-[var(--border)] pt-4">
            <p className="mb-3 text-xs font-semibold tracking-[0.18em] text-slate-500">
              {t("journal.crossTickerTags", "Cross-Ticker Tags")}
            </p>
            <div className="flex flex-wrap gap-2">
              {crossTickerTags.map((value) => (
                <span
                  key={value}
                  className="rounded-full border border-[var(--border)] bg-white/60 px-3 py-1 text-xs font-medium text-slate-600"
                >
                  {prettifyReviewText(value, locale)}
                </span>
              ))}
            </div>
          </div>
        ) : null}
      </section>
    </div>
  );
}

function ReviewListItems({
  values,
  emptyLabel,
  locale,
  compact = false,
}: {
  values: string[];
  emptyLabel: string;
  locale: string;
  compact?: boolean;
}) {
  if (values.length === 0) {
    return (
      <p className="mt-4 rounded-[18px] border border-dashed border-[var(--border)] bg-[var(--surface-strong)] px-4 py-3 text-sm text-slate-500">
        {emptyLabel}
      </p>
    );
  }

  return (
    <ol className={cn("mt-4 space-y-3 text-sm leading-7 text-slate-700", compact && "space-y-2")}>
      {values.map((value, index) => (
        <li
          key={`${value}-${index}`}
          className="grid grid-cols-[1.5rem_minmax(0,1fr)] gap-3"
        >
          <span className="mt-1 flex h-5 w-5 items-center justify-center rounded-full bg-[var(--surface-strong)] text-[11px] font-semibold text-[var(--primary-strong)]">
            {index + 1}
          </span>
          <span>{prettifyReviewText(value, locale)}</span>
        </li>
      ))}
    </ol>
  );
}

function StatusBadge({
  label,
  tone,
}: {
  label: string;
  tone: "primary" | "accent";
}) {
  const { t } = usePreferences();
  const classes =
    tone === "primary"
      ? "border-[rgba(93,116,112,0.22)] bg-[var(--primary-soft)] text-[var(--primary-strong)]"
      : "border-[rgba(28,56,83,0.14)] bg-[var(--accent-soft)] text-[var(--accent)]";

  return (
    <span
      className={`rounded-full border px-3 py-1 text-[11px] font-semibold uppercase tracking-[0.18em] ${classes}`}
    >
      {localizeTradeValue(label, t)}
    </span>
  );
}

function formatNumber(value: number | null, locale: string, notSetLabel: string): string {
  if (typeof value !== "number") {
    return notSetLabel;
  }

  return new Intl.NumberFormat(locale, {
    maximumFractionDigits: 2,
  }).format(value);
}

function formatPercent(value: number | null, locale: string, notSetLabel: string): string {
  if (typeof value !== "number") {
    return notSetLabel;
  }
  return `${new Intl.NumberFormat(locale, {
    maximumFractionDigits: 2,
  }).format(value)}%`;
}

function formatDateTime(value: string | null, locale: string, notSetLabel: string): string {
  if (!value) {
    return notSetLabel;
  }

  const normalized = value.replace("Z", "+00:00");
  const parsed = new Date(normalized);
  if (Number.isNaN(parsed.getTime())) {
    return value;
  }

  return parsed.toLocaleString(locale, {
    year: "numeric",
    month: "short",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
}

function localizeTradeValue(
  value: string,
  t: ReturnType<typeof usePreferences>["t"]
) {
  const normalized = value.trim().toLowerCase();
  if (normalized === "all") {
    return t("journal.timeWindow.all", "all");
  }
  if (normalized === "long" || normalized === "short") {
    return t(`trade.side.${normalized}`, value);
  }
  if (normalized === "open" || normalized === "closed" || normalized === "close") {
    const statusKey = normalized === "close" ? "closed" : normalized;
    return t(`trade.status.${statusKey}`, value);
  }
  return value;
}

function compactTickerLabel(value: string): string {
  if (value.length <= 8) {
    return value;
  }
  return value.slice(0, 7);
}

function compareTradesNewestFirst(left: TradeRecord, right: TradeRecord): number {
  const leftTimestamp = activityTimestamp(left) ?? 0;
  const rightTimestamp = activityTimestamp(right) ?? 0;

  if (rightTimestamp !== leftTimestamp) {
    return rightTimestamp - leftTimestamp;
  }

  return right.trade_id.localeCompare(left.trade_id);
}

function withinTimeWindow(record: TradeRecord, timeWindow: TimeWindow): boolean {
  if (timeWindow === "all") {
    return true;
  }

  const timestamp = activityTimestamp(record);
  if (timestamp === null) {
    return false;
  }

  const now = Date.now();
  const maxAgeMs =
    timeWindow === "30d"
      ? 30 * 24 * 60 * 60 * 1000
      : timeWindow === "90d"
        ? 90 * 24 * 60 * 60 * 1000
        : 365 * 24 * 60 * 60 * 1000;

  return now - timestamp <= maxAgeMs;
}

function activityDateValue(record: TradeRecord): string | null {
  const candidates = [
    record.updated_at,
    record.exit_timestamp,
    record.entry_timestamp,
    record.created_at,
  ];

  return candidates.find((candidate) => Boolean(candidate)) ?? null;
}

function activityTimestamp(record: TradeRecord): number | null {
  const candidates = [
    record.updated_at,
    record.exit_timestamp,
    record.entry_timestamp,
    record.created_at,
  ];

  for (const candidate of candidates) {
    if (!candidate) {
      continue;
    }

    const parsed = Date.parse(candidate);
    if (!Number.isNaN(parsed)) {
      return parsed;
    }
  }

  return null;
}
