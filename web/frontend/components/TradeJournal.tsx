"use client";

import { useEffect, useMemo, useState } from "react";
import { usePreferences } from "@/components/PreferencesProvider";
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
  getTickerTradeFeedback,
  getTrade,
  listTrades,
  type Report,
  type TradeDetail,
  type TradeFeedbackPayload,
  type TradeRecord,
  type TradeReview,
  type TradeReviewType,
} from "@/lib/api";
import { TickerPricePanel } from "./TickerPricePanel";
import { TradeRecordForm } from "./TradeRecordForm";
import { TradeReviewForm } from "./TradeReviewForm";

interface TradeJournalProps {
  reports: Report[];
  onOpenSidebar?: () => void;
  sidebarOpen?: boolean;
}

type TimeWindow = "all" | "30d" | "90d" | "365d";

export function TradeJournal({
  reports,
  onOpenSidebar,
  sidebarOpen = false,
}: TradeJournalProps) {
  const { locale, t } = usePreferences();
  const [trades, setTrades] = useState<TradeRecord[]>([]);
  const [selectedTradeId, setSelectedTradeId] = useState<string | null>(null);
  const [tradeDetail, setTradeDetail] = useState<TradeDetail | null>(null);
  const [feedback, setFeedback] = useState<TradeFeedbackPayload | null>(null);
  const [tickerFilter, setTickerFilter] = useState("");
  const [statusFilter, setStatusFilter] = useState("all");
  const [timeWindow, setTimeWindow] = useState<TimeWindow>("all");
  const [reviewTab, setReviewTab] = useState<TradeReviewType>("entry_review");
  const [loadingTrades, setLoadingTrades] = useState(true);
  const [loadingDetail, setLoadingDetail] = useState(false);
  const [loadingFeedback, setLoadingFeedback] = useState(false);
  const [tradesError, setTradesError] = useState<string | null>(null);
  const [detailError, setDetailError] = useState<string | null>(null);
  const [feedbackError, setFeedbackError] = useState<string | null>(null);
  const [showCreateTrade, setShowCreateTrade] = useState(false);
  const [showEditTrade, setShowEditTrade] = useState(false);
  const [editingReviewType, setEditingReviewType] = useState<TradeReviewType | null>(
    null
  );

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
      setFeedbackError(null);
      return;
    }

    let isActive = true;

    const loadFeedback = async () => {
      setLoadingFeedback(true);
      setFeedbackError(null);

      try {
        const data = await getTickerTradeFeedback(tradeDetail.record.ticker, {
          limit: 3,
        });
        if (!isActive) {
          return;
        }
        setFeedback(data);
      } catch (error) {
        if (!isActive) {
          return;
        }

        setFeedback(null);
        setFeedbackError(
          error instanceof Error
            ? error.message
            : t(
                "journal.error.loadFeedback",
                "Unable to load same-ticker feedback"
              )
        );
      } finally {
        if (isActive) {
          setLoadingFeedback(false);
        }
      }
    };

    void loadFeedback();
    return () => {
      isActive = false;
    };
  }, [tradeDetail?.record.ticker, t]);

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
    setLoadingFeedback(true);
    setFeedbackError(null);

    try {
      const data = await getTickerTradeFeedback(ticker, { limit: 3 });
      setFeedback(data);
    } catch (error) {
      setFeedbackError(
        error instanceof Error
          ? error.message
          : t(
              "journal.error.loadFeedback",
              "Unable to load same-ticker feedback"
            )
      );
    } finally {
      setLoadingFeedback(false);
    }
  };

  const filteredTrades = useMemo(() => {
    return trades.filter((trade) => {
      const normalizedFilter = tickerFilter.trim().toUpperCase();
      const matchesTicker =
        !normalizedFilter ||
        trade.ticker.includes(normalizedFilter) ||
        trade.trade_id.toUpperCase().includes(normalizedFilter);
      const matchesStatus =
        statusFilter === "all" || trade.status.toLowerCase() === statusFilter;
      const matchesTimeWindow = withinTimeWindow(trade, timeWindow);
      return matchesTicker && matchesStatus && matchesTimeWindow;
    });
  }, [statusFilter, tickerFilter, timeWindow, trades]);

  useEffect(() => {
    if (filteredTrades.length === 0 || !selectedTradeId) {
      return;
    }

    if (!filteredTrades.some((trade) => trade.trade_id === selectedTradeId)) {
      setSelectedTradeId(filteredTrades[0].trade_id);
    }
  }, [filteredTrades, selectedTradeId]);

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
  const openTrades = trades.filter((trade) => trade.status.toLowerCase() === "open");
  const reviewCoverageLabel = tradeDetail
    ? `${tradeDetail.reviews.length}/2 reviews`
    : "0/2 reviews";
  const selectionSummaryCards = useMemo(() => {
    if (!tradeDetail) {
      return [];
    }

    return [
      {
        label: "Trade Health",
        value: localizeTradeValue(tradeDetail.record.status, t),
        hint: `${localizeTradeValue(tradeDetail.record.side, t)} · ${tradeDetail.record.exchange_or_market}`,
      },
      {
        label: "Review Coverage",
        value: reviewCoverageLabel,
        hint: `${tradeDetail.record.analysis_references.length} linked snapshots`,
      },
      {
        label: "Feedback Loop",
        value:
          feedback && feedback.reviews.length > 0
            ? t("journal.feedbackReady", "Ready")
            : t("journal.feedbackBuilding", "Building"),
        hint:
          feedback && feedback.reviews.length > 0
            ? `${feedback.reviews.length} saved examples will inform future analyses`
            : "Save at least one review to seed future context",
      },
    ];
  }, [feedback, reviewCoverageLabel, t, tradeDetail]);

  const handleTradeSaved = (record: TradeRecord) => {
    setShowCreateTrade(false);
    setShowEditTrade(false);
    setSelectedTradeId(record.trade_id);
    void refreshTrades(record.trade_id);
    void refreshTradeDetail(record.trade_id);
    void refreshFeedback(record.ticker);
  };

  const handleReviewSaved = (review: TradeReview) => {
    setEditingReviewType(null);
    setReviewTab(review.review_type);
    void refreshTrades(review.trade_id);
    void refreshTradeDetail(review.trade_id);
    void refreshFeedback(review.ticker);
  };

  return (
    <>
      <main className="flex min-h-[100vh] flex-1 flex-col px-4 py-6 md:px-7 lg:px-9">
        <div className="workbench-content-frame flex flex-col gap-6">
          <Card className="viewer-frame overflow-hidden">
            <CardContent className="px-6 py-7 md:px-8 md:py-8">
            <div className="flex flex-wrap items-start justify-between gap-4">
              <div className="max-w-3xl">
                <p className="text-[12px] font-semibold uppercase tracking-[0.38em] text-[var(--primary)]">
                  {t("sidebar.tradeJournal", "Trade Journal")}
                </p>
                <h1 className="font-heading mt-3 text-3xl font-bold tracking-tight text-slate-900 md:text-4xl">
                  {t(
                    "journal.title",
                    "Record trades, separate entry and exit reviews, and preview future same-ticker feedback"
                  )}
                </h1>
              </div>

              <div className="flex flex-wrap items-center gap-3">
                {onOpenSidebar ? (
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
                ) : null}
                <Button type="button" onClick={() => setShowCreateTrade(true)}>
                  {t("journal.recordTrade", "Record Trade")}
                </Button>
              </div>
            </div>

            <div className="mt-7 grid gap-4 xl:grid-cols-[minmax(0,1fr)_180px_180px]">
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
            </CardContent>
          </Card>

          <section className="grid gap-6 xl:grid-cols-[minmax(0,0.95fr)_minmax(0,2.05fr)]">
            <Card className="card-surface p-4 md:p-5">
              <CardContent className="p-0">
              <div className="flex items-center justify-between gap-4">
                <div>
                  <p className="text-xs font-semibold uppercase tracking-[0.3em] text-slate-500">
                    {t("journal.history", "History")}
                  </p>
                  <h2 className="mt-2 text-xl font-semibold text-slate-900">
                    {t("journal.tradeRecords", "Trade records")}
                  </h2>
                </div>
                <Badge variant="secondary" className="text-slate-500">
                  {t("sidebar.shownCount", ({ count }) => `${count} shown`, {
                    count: filteredTrades.length,
                  })}
                </Badge>
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
                <div className="mt-4 space-y-3">
                  {filteredTrades.map((trade) => {
                    const isSelected = selectedTradeId === trade.trade_id;
                    return (
                      <Button
                        key={trade.trade_id}
                        type="button"
                        data-active={isSelected}
                        variant="secondary"
                        className={`h-auto w-full flex-col items-stretch justify-start overflow-hidden rounded-[26px] p-4 text-left whitespace-normal ${
                          isSelected
                            ? "border-[var(--primary)] bg-[var(--primary-soft)]/75 text-slate-900 shadow-[0_18px_36px_rgba(28,36,48,0.12)] hover:bg-[var(--primary-soft)]/75"
                            : "bg-white/85 text-slate-900 hover:bg-white"
                        }`}
                        onClick={() => setSelectedTradeId(trade.trade_id)}
                      >
                        <div className="flex items-start justify-between gap-4">
                          <div>
                            <p className="text-lg font-semibold text-slate-900">
                              {trade.ticker}
                            </p>
                            <p className="mt-1 font-mono text-[11px] text-slate-500">
                              {trade.trade_id}
                            </p>
                          </div>
                          <div className="flex flex-wrap gap-2">
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
                          {tradeDetail.record.ticker}
                        </h2>
                        <p className="mt-2 font-mono text-[12px] text-slate-500">
                          {tradeDetail.record.trade_id}
                        </p>
                      </div>

                      <div className="flex flex-wrap items-center gap-3">
                        <StatusBadge label={tradeDetail.record.side} tone="accent" />
                        <StatusBadge label={tradeDetail.record.status} tone="primary" />
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
                      symbol={tradeDetail.record.ticker}
                      market={tradeDetail.record.exchange_or_market}
                      title={t("journal.priceTrend", "Price Trend")}
                      subtitle={t(
                        "journal.priceTrendHint",
                        "400-day vendor-backed history for the selected trade ticker."
                      )}
                    />

                    <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
                      <MetaCard
                        label={t("journal.marketExchange", "Market / Exchange")}
                        value={tradeDetail.record.exchange_or_market}
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
                          {t("journal.initialThesis", "Initial Thesis")}
                        </p>
                        <p className="mt-3 whitespace-pre-wrap text-sm leading-7 text-slate-700">
                          {tradeDetail.record.initial_thesis}
                        </p>
                      </section>

                      <section className="rounded-[28px] border border-[var(--border)] bg-white/90 p-5">
                        <p className="text-xs font-semibold uppercase tracking-[0.26em] text-slate-500">
                          {t("journal.notes", "Notes")}
                        </p>
                        <p className="mt-3 whitespace-pre-wrap text-sm leading-7 text-slate-700">
                          {tradeDetail.record.notes ||
                            t("journal.noNotes", "No notes saved.")}
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
                        <Button type="button" variant="secondary" size="sm" onClick={() => setEditingReviewType(reviewTab)}>
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

                      {!selectedReview ? (
                        <div className="mt-5 rounded-3xl border border-dashed border-[var(--border)] bg-[var(--surface-strong)] px-5 py-6 text-sm text-slate-500">
                          {t(
                            "journal.noReview",
                            ({ reviewType }) =>
                              `No ${reviewType} saved for this trade yet. Use the manual review editor to add the structured assessment fields required by the backend schema.`,
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

                          <div className="grid gap-4 md:grid-cols-3">
                            <TagCard
                              label={t(
                                "journal.improvementActions",
                                "Improvement Actions"
                              )}
                              values={selectedReview.improvement_actions}
                            />
                            <TagCard
                              label={t(
                                "journal.tickerSpecificLessons",
                                "Ticker-Specific Lessons"
                              )}
                              values={selectedReview.ticker_specific_lessons}
                            />
                            <TagCard
                              label={t("journal.crossTickerTags", "Cross-Ticker Tags")}
                              values={selectedReview.cross_ticker_tags}
                            />
                          </div>

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

              <Card className="card-surface p-5 md:p-6">
                <CardContent className="p-0">
                <div className="flex flex-wrap items-center justify-between gap-4">
                  <div>
                    <p className="text-xs font-semibold uppercase tracking-[0.3em] text-slate-500">
                      {t("journal.sameTickerFeedback", "Same-Ticker Feedback")}
                    </p>
                    <h2 className="mt-2 text-xl font-semibold text-slate-900">
                      {t(
                        "journal.futureAnalyses",
                        "Future analyses will read this saved review context"
                      )}
                    </h2>
                  </div>
                  {tradeDetail?.record.ticker ? (
                    <Badge variant="secondary" className="text-slate-500">
                      {tradeDetail.record.ticker}
                    </Badge>
                  ) : null}
                </div>

                {feedbackError ? (
                  <div className="mt-4 rounded-3xl border border-rose-200 bg-rose-50 px-4 py-4 text-sm text-rose-700">
                    {feedbackError}
                  </div>
                ) : loadingFeedback ? (
                  <div className="mt-4 rounded-3xl border border-dashed border-[var(--border)] bg-[var(--surface-strong)] px-4 py-8 text-sm text-slate-500">
                    {t(
                      "journal.loadingFeedback",
                      "Loading same-ticker feedback preview..."
                    )}
                  </div>
                ) : !feedback || feedback.reviews.length === 0 ? (
                  <div className="mt-4 rounded-3xl border border-dashed border-[var(--border)] bg-[var(--surface-strong)] px-5 py-8 text-sm text-slate-500">
                    {t(
                      "journal.noFeedback",
                      "No saved feedback prompt is available yet for this ticker. Once an entry_review or exit_review is stored, later analyses can reuse it."
                    )}
                  </div>
                ) : (
                  <div className="mt-4 space-y-5">
                    <div className="grid gap-4 md:grid-cols-3">
                      {feedback.reviews.map((review) => (
                        <div
                          key={review.review_id}
                          className="rounded-3xl border border-[var(--border)] bg-[var(--surface-strong)]/85 p-4"
                        >
                          <p className="text-xs font-semibold uppercase tracking-[0.22em] text-slate-500">
                            {review.review_type === "entry_review"
                              ? t("journal.entryReview", "Entry Review")
                              : t("journal.exitReview", "Exit Review")}
                          </p>
                          <p className="mt-2 font-mono text-[11px] text-slate-500">
                            {review.trade_id}
                          </p>
                          <p className="mt-3 text-sm leading-6 text-slate-700">
                            {review.outcome_summary}
                          </p>
                        </div>
                      ))}
                    </div>

                    <div className="rounded-[28px] border border-[var(--border)] bg-[var(--surface-strong)] px-5 py-5">
                      <p className="text-xs font-semibold uppercase tracking-[0.24em] text-slate-500">
                        {t("journal.promptPreview", "Prompt Preview")}
                      </p>
                      <pre className="mt-3 overflow-x-auto whitespace-pre-wrap rounded-3xl bg-white/85 px-4 py-4 font-mono text-[12px] leading-6 text-slate-700">
                        {feedback.prompt}
                      </pre>
                    </div>
                  </div>
                )}
                </CardContent>
              </Card>
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

function ReviewCard({
  label,
  value,
}: {
  label: string;
  value: string;
}) {
  return (
    <div className="rounded-[26px] border border-[var(--border)] bg-[var(--surface-strong)]/80 p-4">
      <p className="text-xs font-semibold uppercase tracking-[0.24em] text-slate-500">
        {label}
      </p>
      <p className="mt-3 whitespace-pre-wrap text-sm leading-7 text-slate-700">
        {value}
      </p>
    </div>
  );
}

function TagCard({
  label,
  values,
}: {
  label: string;
  values: string[];
}) {
  const { t } = usePreferences();
  return (
    <div className="rounded-[26px] border border-[var(--border)] bg-[var(--surface-strong)]/80 p-4">
      <p className="text-xs font-semibold uppercase tracking-[0.24em] text-slate-500">
        {label}
      </p>
      <div className="mt-4 flex flex-wrap gap-2">
        {values.length === 0 ? (
          <span className="rounded-full border border-[var(--border)] bg-white px-3 py-1 text-xs text-slate-500">
            {t("journal.noneSaved", "None saved")}
          </span>
        ) : (
          values.map((value) => (
            <span
              key={value}
              className="rounded-full border border-[var(--border)] bg-white px-3 py-1 text-xs font-medium text-slate-700"
            >
              {value}
            </span>
          ))
        )}
      </div>
    </div>
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
