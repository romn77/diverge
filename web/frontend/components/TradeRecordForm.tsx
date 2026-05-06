"use client";

import { useEffect, useMemo, useState, type Dispatch, type SetStateAction } from "react";
import { usePreferences } from "@/components/PreferencesProvider";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Textarea } from "@/components/ui/textarea";
import {
  createTrade,
  resolveMarketSymbol,
  updateTrade,
  type AnalysisReference,
  type MarketResolution,
  type MarketResolutionMarket,
  type Report,
  type TradeRecord,
  type TradeRecordCreateRequest,
} from "@/lib/api";

interface TradeRecordFormProps {
  isOpen: boolean;
  mode: "create" | "edit";
  initialRecord?: TradeRecord | null;
  reports: Report[];
  onClose: () => void;
  onSaved: (record: TradeRecord) => void;
}

interface TradeRecordFormState {
  raw_symbol: string;
  side: string;
  entry_timestamp: string;
  entry_price: string;
  size: string;
  strategy_tags: string[];
  custom_strategy_tag: string;
  planned_horizon: string;
  entry_reason: string;
  invalidation_condition: string;
  stop_loss: string;
  take_profit: string;
  market_override: "auto" | MarketResolutionMarket;
  exchange_override: string;
  initial_thesis: string;
  analysis_references: AnalysisReference[];
}

const EMPTY_REFERENCE: AnalysisReference = {
  analysis_date: "",
  report_path: "",
  full_state_log_path: "",
};

const STRATEGY_TAGS = [
  "breakout",
  "pullback",
  "trend_following",
  "mean_reversion",
  "earnings_catalyst",
  "news_catalyst",
  "valuation_reversion",
  "technical_reversal",
  "momentum",
  "defensive",
  "event_driven",
  "other",
];

const PLANNED_HORIZONS = [
  "unknown",
  "intraday",
  "multi_day",
  "swing_1_4w",
  "position_1_6m",
  "long_term_6m_plus",
  "event_driven",
];

export function TradeRecordForm({
  isOpen,
  mode,
  initialRecord = null,
  reports,
  onClose,
  onSaved,
}: TradeRecordFormProps) {
  const { t } = usePreferences();
  const [formState, setFormState] = useState<TradeRecordFormState>(() =>
    buildInitialState(initialRecord)
  );
  const [marketResolution, setMarketResolution] = useState<MarketResolution | null>(
    initialRecord?.market_resolution ?? null
  );
  const [resolvingMarket, setResolvingMarket] = useState(false);
  const [advancedOpen, setAdvancedOpen] = useState(false);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!isOpen) {
      return;
    }
    setFormState(buildInitialState(initialRecord));
    setMarketResolution(initialRecord?.market_resolution ?? null);
    setAdvancedOpen(false);
    setSaving(false);
    setError(null);
  }, [initialRecord, isOpen]);

  useEffect(() => {
    if (!isOpen) {
      return;
    }
    const rawSymbol = formState.raw_symbol.trim();
    if (!rawSymbol) {
      setMarketResolution(null);
      return;
    }

    let isActive = true;
    setResolvingMarket(true);
    const timeoutId = window.setTimeout(() => {
      const overrides =
        formState.market_override === "auto"
          ? undefined
          : {
              manual_market: formState.market_override,
              manual_exchange: formState.exchange_override || null,
              manual_asset_type: null,
            };
      void resolveMarketSymbol(rawSymbol, overrides)
        .then((resolution) => {
          if (isActive) {
            setMarketResolution(resolution);
          }
        })
        .catch((resolveError) => {
          if (isActive) {
            setMarketResolution(null);
            setError(resolveError instanceof Error ? resolveError.message : "Unable to resolve market");
          }
        })
        .finally(() => {
          if (isActive) {
            setResolvingMarket(false);
          }
        });
    }, 300);

    return () => {
      isActive = false;
      window.clearTimeout(timeoutId);
    };
  }, [
    formState.exchange_override,
    formState.market_override,
    formState.raw_symbol,
    isOpen,
  ]);

  const suggestedReports = useMemo(() => {
    const normalizedTicker = (
      marketResolution?.canonical_symbol || formState.raw_symbol
    ).trim().toUpperCase();
    const matchingReports = normalizedTicker
      ? reports.filter((report) => report.ticker === normalizedTicker)
      : reports;
    return matchingReports.slice(0, 6);
  }, [formState.raw_symbol, marketResolution?.canonical_symbol, reports]);

  if (!isOpen) {
    return null;
  }

  const localizedTitle =
    mode === "create"
      ? t("tradeRecord.recordTrade", "Record Trade")
      : t("tradeRecord.editTrade", "Edit Trade");

  const submitTrade = async () => {
    setSaving(true);
    setError(null);

    try {
      const payload = buildPayload(formState, marketResolution, initialRecord, t);
      const record =
        mode === "create" || !initialRecord
          ? await createTrade(payload)
          : await updateTrade(initialRecord.trade_id, payload);
      onSaved(record);
    } catch (submitError) {
      setError(
        submitError instanceof Error
          ? submitError.message
          : t("tradeRecord.error.save", "Unable to save the trade record")
      );
    } finally {
      setSaving(false);
    }
  };

  return (
    <Dialog open={isOpen} onOpenChange={(open) => !open && onClose()}>
      <DialogContent
        aria-label={localizedTitle}
        className="modal-panel scrollbar-hidden max-h-[92vh] max-w-4xl overflow-y-auto"
        onMouseDown={(event) => event.stopPropagation()}
      >
        <DialogHeader className="pr-12">
          <p className="text-[11px] font-semibold uppercase tracking-[0.34em] text-[var(--primary)]">
            {t("tradeRecord.manualJournal", "Manual Journal")}
          </p>
          <DialogTitle>{localizedTitle}</DialogTitle>
          <DialogDescription className="max-w-3xl">
            {t(
              "tradeRecord.v2Description",
              "Capture the setup, trigger, invalidation, and risk plan. Market and status are inferred automatically."
            )}
          </DialogDescription>
        </DialogHeader>

        <div className="mt-8 grid gap-6">
          <section className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
            <label className="field-shell block rounded-3xl border border-[var(--border)] bg-white/90 p-4">
              <span className="text-xs font-semibold uppercase tracking-[0.24em] text-slate-500">
                {t("analysis.ticker", "Ticker")}
              </span>
              <Input
                type="text"
                value={formState.raw_symbol}
                onChange={(event) =>
                  setFormState((current) => ({
                    ...current,
                    raw_symbol: event.target.value.toUpperCase(),
                  }))
                }
                placeholder="MSFT"
                className="mt-3 border-[var(--border)] bg-[var(--surface-strong)] font-semibold text-slate-800"
              />
            </label>

            <label className="field-shell block rounded-3xl border border-[var(--border)] bg-white/90 p-4">
              <span className="text-xs font-semibold uppercase tracking-[0.24em] text-slate-500">
                {t("tradeRecord.entryTime", "Entry Time")}
              </span>
              <input
                type="datetime-local"
                value={formState.entry_timestamp}
                onChange={(event) =>
                  setFormState((current) => ({
                    ...current,
                    entry_timestamp: event.target.value,
                  }))
                }
                className="focus-ring mt-3 w-full rounded-2xl border border-[var(--border)] bg-[var(--surface-strong)] px-4 py-3 text-sm font-medium text-slate-800"
              />
            </label>

            <NumberField
              label={t("tradeRecord.entryPrice", "Entry Price")}
              value={formState.entry_price}
              onChange={(value) => setFormState((current) => ({ ...current, entry_price: value }))}
              placeholder="420.00"
            />
            <NumberField
              label={t("tradeRecord.size", "Size")}
              value={formState.size}
              onChange={(value) => setFormState((current) => ({ ...current, size: value }))}
              placeholder="10"
            />
          </section>

          <MarketResolutionPanel
            resolution={marketResolution}
            resolving={resolvingMarket}
            marketOverride={formState.market_override}
            exchangeOverride={formState.exchange_override}
            onMarketOverrideChange={(value) =>
              setFormState((current) => ({
                ...current,
                market_override: value,
              }))
            }
            onExchangeOverrideChange={(value) =>
              setFormState((current) => ({ ...current, exchange_override: value }))
            }
          />

          <section className="rounded-[28px] border border-[var(--border)] bg-white/90 p-5">
            <p className="text-xs font-semibold uppercase tracking-[0.24em] text-slate-500">
              {t("tradeRecord.strategyTags", "Strategy Tags")}
            </p>
            <div className="mt-4 flex flex-wrap gap-2">
              {STRATEGY_TAGS.map((tag) => {
                const selected = formState.strategy_tags.includes(tag);
                return (
                  <button
                    key={tag}
                    type="button"
                    data-active={selected}
                    className={`interactive-button focus-ring rounded-full border px-3 py-2 text-xs font-semibold uppercase tracking-[0.12em] ${
                      selected
                        ? "border-[var(--primary)] bg-[var(--primary-soft)] text-[var(--primary-strong)]"
                        : "border-[var(--border)] bg-white text-slate-600"
                    }`}
                    onClick={() =>
                      setFormState((current) => ({
                        ...current,
                        strategy_tags: toggleTag(current.strategy_tags, tag),
                      }))
                    }
                  >
                    {tag.replaceAll("_", " ")}
                  </button>
                );
              })}
            </div>
            {formState.strategy_tags.includes("other") ? (
              <Input
                type="text"
                value={formState.custom_strategy_tag}
                onChange={(event) =>
                  setFormState((current) => ({
                    ...current,
                    custom_strategy_tag: event.target.value,
                  }))
                }
                placeholder={t("tradeRecord.customStrategy", "Custom strategy")}
                className="mt-4 max-w-md border-[var(--border)] bg-[var(--surface-strong)] text-slate-800"
              />
            ) : null}
          </section>

          <section className="grid gap-4 md:grid-cols-3">
            <label className="field-shell block rounded-3xl border border-[var(--border)] bg-white/90 p-4">
              <span className="text-xs font-semibold uppercase tracking-[0.24em] text-slate-500">
                {t("tradeRecord.plannedHorizon", "Planned Horizon")}
              </span>
              <Select
                value={formState.planned_horizon}
                onValueChange={(value) =>
                  setFormState((current) => ({ ...current, planned_horizon: value }))
                }
              >
                <SelectTrigger className="mt-3 border-[var(--border)] bg-[var(--surface-strong)] font-medium text-slate-800">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  {PLANNED_HORIZONS.map((horizon) => (
                    <SelectItem key={horizon} value={horizon}>
                      {horizon.replaceAll("_", " ")}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </label>
            <NumberField
              label={t("tradeRecord.stopLoss", "Stop Loss")}
              value={formState.stop_loss}
              onChange={(value) => setFormState((current) => ({ ...current, stop_loss: value }))}
              placeholder="408.00"
            />
            <NumberField
              label={t("tradeRecord.takeProfit", "Take Profit")}
              value={formState.take_profit}
              onChange={(value) => setFormState((current) => ({ ...current, take_profit: value }))}
              placeholder="448.00"
            />
          </section>

          <section className="grid gap-4 xl:grid-cols-2">
            <label className="field-shell block rounded-3xl border border-[var(--border)] bg-white/90 p-4">
              <span className="text-xs font-semibold uppercase tracking-[0.24em] text-slate-500">
                {t("tradeRecord.entryReason", "Entry Reason")}
              </span>
              <Textarea
                value={formState.entry_reason}
                onChange={(event) =>
                  setFormState((current) => ({ ...current, entry_reason: event.target.value }))
                }
                rows={6}
                placeholder={t(
                  "tradeRecord.entryReasonPlaceholder",
                  "What triggered this entry, and what evidence supported acting now?"
                )}
                className="mt-3 min-h-[160px] border-[var(--border)] bg-[var(--surface-strong)] text-slate-800"
              />
            </label>

            <label className="field-shell block rounded-3xl border border-[var(--border)] bg-white/90 p-4">
              <span className="text-xs font-semibold uppercase tracking-[0.24em] text-slate-500">
                {t("tradeRecord.invalidationCondition", "Invalidation Condition")}
              </span>
              <Textarea
                value={formState.invalidation_condition}
                onChange={(event) =>
                  setFormState((current) => ({
                    ...current,
                    invalidation_condition: event.target.value,
                  }))
                }
                rows={6}
                placeholder={t(
                  "tradeRecord.invalidationPlaceholder",
                  "What would prove this trade wrong?"
                )}
                className="mt-3 min-h-[160px] border-[var(--border)] bg-[var(--surface-strong)] text-slate-800"
              />
            </label>
          </section>

          <section className="rounded-[28px] border border-[var(--border)] bg-white/85 p-5">
            <button
              type="button"
              className="interactive-button focus-ring flex w-full items-center justify-between gap-4 text-left"
              onClick={() => setAdvancedOpen((current) => !current)}
            >
              <div>
                <p className="text-xs font-semibold uppercase tracking-[0.28em] text-slate-500">
                  {t("tradeRecord.advancedSupplement", "Advanced / Supplement")}
                </p>
                <h3 className="mt-2 text-xl font-semibold text-slate-900">
                  {t("tradeRecord.snapshotsAndThesis", "Snapshots and optional thesis")}
                </h3>
              </div>
              <Badge variant="secondary" className="text-slate-500">
                {advancedOpen ? t("common.open", "Open") : t("common.closed", "Closed")}
              </Badge>
            </button>

            {advancedOpen ? (
              <div className="mt-5 grid gap-5">
                <section className="grid gap-4 md:grid-cols-2">
                  <label className="field-shell block rounded-3xl border border-[var(--border)] bg-white/90 p-4">
                    <span className="text-xs font-semibold uppercase tracking-[0.24em] text-slate-500">
                      {t("tradeRecord.side", "Side")}
                    </span>
                    <Select
                      value={formState.side}
                      onValueChange={(value) =>
                        setFormState((current) => ({ ...current, side: value }))
                      }
                    >
                      <SelectTrigger className="mt-3 border-[var(--border)] bg-[var(--surface-strong)] font-medium text-slate-800">
                        <SelectValue />
                      </SelectTrigger>
                      <SelectContent>
                        <SelectItem value="long">{t("trade.side.long", "long")}</SelectItem>
                        <SelectItem value="short">{t("trade.side.short", "short")}</SelectItem>
                      </SelectContent>
                    </Select>
                  </label>
                  <label className="field-shell block rounded-3xl border border-[var(--border)] bg-white/90 p-4">
                    <span className="text-xs font-semibold uppercase tracking-[0.24em] text-slate-500">
                      {t("tradeRecord.initialThesis", "Initial Thesis")}
                    </span>
                    <Textarea
                      value={formState.initial_thesis}
                      onChange={(event) =>
                        setFormState((current) => ({
                          ...current,
                          initial_thesis: event.target.value,
                        }))
                      }
                      rows={4}
                      placeholder={t(
                        "tradeRecord.initialThesisPlaceholder",
                        "Optional broader thesis. Entry reason will be used if this is blank."
                      )}
                      className="mt-3 border-[var(--border)] bg-[var(--surface-strong)] text-slate-800"
                    />
                  </label>
                </section>

                <SnapshotReferences
                  references={formState.analysis_references}
                  suggestedReports={suggestedReports}
                  setFormState={setFormState}
                />
              </div>
            ) : null}
          </section>

          {error ? (
            <div className="rounded-3xl border border-rose-200 bg-rose-50 px-5 py-4 text-sm text-rose-700">
              {error}
            </div>
          ) : null}

          <div className="flex flex-wrap items-center justify-end gap-3">
            <Button type="button" variant="secondary" onClick={onClose} disabled={saving}>
              {t("common.cancel", "Cancel")}
            </Button>
            <Button type="button" onClick={() => void submitTrade()} disabled={saving || resolvingMarket}>
              {saving
                ? t("tradeRecord.saving", "Saving...")
                : mode === "create"
                  ? t("tradeRecord.create", "Create Trade")
                  : t("tradeRecord.saveChanges", "Save Changes")}
            </Button>
          </div>
        </div>
      </DialogContent>
    </Dialog>
  );
}

function MarketResolutionPanel({
  resolution,
  resolving,
  marketOverride,
  exchangeOverride,
  onMarketOverrideChange,
  onExchangeOverrideChange,
}: {
  resolution: MarketResolution | null;
  resolving: boolean;
  marketOverride: "auto" | MarketResolutionMarket;
  exchangeOverride: string;
  onMarketOverrideChange: (value: "auto" | MarketResolutionMarket) => void;
  onExchangeOverrideChange: (value: string) => void;
}) {
  const needsOverride = resolution?.market === "unknown" || resolution?.confidence === "low";
  return (
    <section className="rounded-[28px] border border-[var(--border)] bg-white/90 p-5">
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <p className="text-xs font-semibold uppercase tracking-[0.26em] text-slate-500">
            Market Resolution
          </p>
          <h3 className="mt-2 text-xl font-semibold text-slate-900">
            {resolving
              ? "Resolving symbol..."
              : resolution
                ? `${resolution.display_symbol} · ${resolution.market.toUpperCase()}`
                : "Enter a ticker to resolve"}
          </h3>
          {resolution ? (
            <p className="mt-2 text-sm leading-6 text-slate-600">
              {resolution.asset_type} · {resolution.exchange ?? "no exchange"} · {resolution.source} ·{" "}
              {resolution.confidence}
            </p>
          ) : null}
        </div>
        {resolution ? (
          <Badge variant={needsOverride ? "destructive" : "secondary"}>
            {needsOverride ? "needs review" : "resolved"}
          </Badge>
        ) : null}
      </div>

      {resolution?.warnings.length ? (
        <div className="mt-4 rounded-3xl border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-800">
          {resolution.warnings.join(" ")}
        </div>
      ) : null}

      {needsOverride || marketOverride !== "auto" ? (
        <div className="mt-4 grid gap-4 md:grid-cols-2">
          <label className="block">
            <span className="text-xs font-semibold uppercase tracking-[0.2em] text-slate-500">
              Market Override
            </span>
            <Select value={marketOverride} onValueChange={(value) => onMarketOverrideChange(value as "auto" | MarketResolutionMarket)}>
              <SelectTrigger className="mt-2 border-[var(--border)] bg-[var(--surface-strong)] text-slate-800">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="auto">auto</SelectItem>
                <SelectItem value="cn">cn</SelectItem>
                <SelectItem value="us">us</SelectItem>
                <SelectItem value="unknown">unknown</SelectItem>
              </SelectContent>
            </Select>
          </label>
          <label className="block">
            <span className="text-xs font-semibold uppercase tracking-[0.2em] text-slate-500">
              Exchange Override
            </span>
            <Input
              value={exchangeOverride}
              onChange={(event) => onExchangeOverrideChange(event.target.value.toUpperCase())}
              placeholder="SH, SZ, NASDAQ"
              className="mt-2 border-[var(--border)] bg-[var(--surface-strong)] text-slate-800"
            />
          </label>
        </div>
      ) : null}
    </section>
  );
}

function SnapshotReferences({
  references,
  suggestedReports,
  setFormState,
}: {
  references: AnalysisReference[];
  suggestedReports: Report[];
  setFormState: Dispatch<SetStateAction<TradeRecordFormState>>;
}) {
  return (
    <section className="rounded-[28px] border border-[var(--border)] bg-white/85 p-5">
      <div className="flex flex-wrap items-center justify-between gap-4">
        <div>
          <p className="text-xs font-semibold uppercase tracking-[0.28em] text-slate-500">
            Snapshot References
          </p>
          <h3 className="mt-2 text-lg font-semibold text-slate-900">
            Optional analysis context
          </h3>
        </div>
        <Button
          type="button"
          variant="secondary"
          onClick={() =>
            setFormState((current) => ({
              ...current,
              analysis_references: [...current.analysis_references, { ...EMPTY_REFERENCE }],
            }))
          }
        >
          Add Blank Reference
        </Button>
      </div>

      <div className="mt-4 flex flex-wrap gap-2">
        {suggestedReports.map((report) => {
          const reference = buildReferenceFromReport(report);
          return (
            <button
              key={report.id}
              type="button"
              disabled={!reference}
              className="interactive-button focus-ring rounded-full border border-[var(--border)] bg-white px-3 py-2 text-xs font-semibold uppercase tracking-[0.12em] text-slate-600 disabled:cursor-not-allowed disabled:bg-slate-100 disabled:text-slate-400"
              onClick={() => {
                if (!reference) {
                  return;
                }
                setFormState((current) => ({
                  ...current,
                  analysis_references: addUniqueReference(
                    current.analysis_references,
                    reference
                  ),
                }));
              }}
            >
              {report.ticker} · {report.date ?? report.id}
            </button>
          );
        })}
      </div>

      <div className="mt-5 space-y-4">
        {references.map((reference, index) => (
          <div
            key={`${reference.report_path}-${reference.full_state_log_path}-${index}`}
            className="rounded-3xl border border-[var(--border)] bg-[var(--surface-strong)]/80 p-4"
          >
            <div className="flex items-center justify-between gap-4">
              <p className="text-xs font-semibold uppercase tracking-[0.24em] text-slate-500">
                Snapshot {index + 1}
              </p>
              <button
                type="button"
                className="interactive-button focus-ring rounded-full border border-[var(--border)] bg-white px-3 py-1.5 text-[11px] font-semibold uppercase tracking-[0.18em] text-slate-600"
                onClick={() =>
                  setFormState((current) => ({
                    ...current,
                    analysis_references: current.analysis_references.filter(
                      (_item, itemIndex) => itemIndex !== index
                    ),
                  }))
                }
              >
                Remove
              </button>
            </div>
            <div className="mt-4 grid gap-4">
              <Input
                type="date"
                value={reference.analysis_date}
                onChange={(event) =>
                  updateReferenceField(setFormState, index, "analysis_date", event.target.value)
                }
              />
              <Input
                type="text"
                value={reference.report_path}
                onChange={(event) =>
                  updateReferenceField(setFormState, index, "report_path", event.target.value)
                }
                placeholder="data/reports/<report_id>/complete_report.md"
              />
            </div>
          </div>
        ))}
      </div>
    </section>
  );
}

function NumberField({
  label,
  value,
  onChange,
  placeholder,
}: {
  label: string;
  value: string;
  onChange: (value: string) => void;
  placeholder: string;
}) {
  return (
    <label className="field-shell block rounded-3xl border border-[var(--border)] bg-white/90 p-4">
      <span className="text-xs font-semibold uppercase tracking-[0.24em] text-slate-500">
        {label}
      </span>
      <input
        type="number"
        inputMode="decimal"
        value={value}
        onChange={(event) => onChange(event.target.value)}
        placeholder={placeholder}
        className="focus-ring mt-3 w-full rounded-2xl border border-[var(--border)] bg-[var(--surface-strong)] px-4 py-3 text-sm font-medium text-slate-800"
      />
    </label>
  );
}

function buildInitialState(record: TradeRecord | null): TradeRecordFormState {
  const tags = record?.strategy_tags ?? [];
  const builtInTags = tags.filter((tag) => STRATEGY_TAGS.includes(tag));
  const customTags = tags.filter((tag) => !STRATEGY_TAGS.includes(tag));
  return {
    raw_symbol: record?.raw_symbol ?? record?.ticker ?? "",
    side: record?.side ?? "long",
    entry_timestamp: toDateTimeLocalValue(record?.entry_timestamp ?? null),
    entry_price: toInputNumber(record?.entry_price ?? null),
    size: toInputNumber(record?.size ?? null),
    strategy_tags: builtInTags.length > 0 ? builtInTags : [],
    custom_strategy_tag: customTags.join(", "),
    planned_horizon: record?.planned_horizon ?? "unknown",
    entry_reason: record?.entry_reason ?? record?.initial_thesis ?? "",
    invalidation_condition: record?.invalidation_condition ?? "",
    stop_loss: toInputNumber(record?.stop_loss ?? null),
    take_profit: toInputNumber(record?.take_profit ?? null),
    market_override: record?.market_resolution?.source === "manual" ? record.market : "auto",
    exchange_override: record?.market_resolution?.source === "manual" ? record.exchange ?? "" : "",
    initial_thesis: record?.initial_thesis ?? "",
    analysis_references:
      record?.analysis_references.map((reference) => ({ ...reference })) ?? [],
  };
}

function buildPayload(
  state: TradeRecordFormState,
  marketResolution: MarketResolution | null,
  record: TradeRecord | null,
  t: ReturnType<typeof usePreferences>["t"]
): TradeRecordCreateRequest {
  const strategyTags = normalizeStrategyTags(state);
  return {
    raw_symbol: requireText(state.raw_symbol, t("analysis.ticker", "Ticker")).toUpperCase(),
    side: state.side,
    entry_timestamp: normalizeRequiredTimestamp(
      state.entry_timestamp,
      t("tradeRecord.entryTime", "Entry time"),
      record?.entry_timestamp ?? null
    ),
    entry_price: parseRequiredNumber(
      state.entry_price,
      t("tradeRecord.entryPrice", "Entry price")
    ),
    size: parseRequiredNumber(state.size, t("tradeRecord.size", "Size")),
    strategy_tags: strategyTags,
    entry_reason: requireText(
      state.entry_reason,
      t("tradeRecord.entryReason", "Entry reason")
    ),
    invalidation_condition: requireText(
      state.invalidation_condition,
      t("tradeRecord.invalidationCondition", "Invalidation condition")
    ),
    planned_horizon: state.planned_horizon || "unknown",
    stop_loss: parseOptionalNumber(
      state.stop_loss,
      t("tradeRecord.stopLoss", "Stop loss")
    ),
    take_profit: parseOptionalNumber(
      state.take_profit,
      t("tradeRecord.takeProfit", "Take profit")
    ),
    initial_thesis: state.initial_thesis.trim(),
    market_resolution:
      state.market_override !== "auto" && marketResolution
        ? { ...marketResolution, source: "manual", confidence: "manual" }
        : marketResolution,
    analysis_references: normalizeAnalysisReferences(state.analysis_references),
  };
}

function normalizeStrategyTags(state: TradeRecordFormState): string[] {
  const values = [...state.strategy_tags];
  const customTags = state.custom_strategy_tag
    .split(",")
    .map((tag) => tag.trim())
    .filter(Boolean);
  values.push(...customTags);
  const normalized = Array.from(
    new Set(values.map((tag) => tag.toLowerCase().replace(/[^a-z0-9_]+/g, "_").replace(/^_+|_+$/g, "")))
  ).filter(Boolean);
  if (normalized.length === 0) {
    throw new Error("Strategy tags are required.");
  }
  if (normalized.includes("other") && normalized.length === 1 && state.entry_reason.trim().length < 12) {
    throw new Error("Other strategy requires a custom tag or a specific entry reason.");
  }
  return normalized;
}

function requireText(value: string, fieldName: string): string {
  const normalized = value.trim();
  if (!normalized) {
    throw new Error(`${fieldName} is required.`);
  }
  return normalized;
}

function normalizeRequiredTimestamp(
  value: string,
  fieldName: string,
  originalValue: string | null
): string {
  const normalized = value.trim();
  if (!normalized) {
    throw new Error(`${fieldName} is required.`);
  }
  if (originalValue && normalized === toDateTimeLocalValue(originalValue)) {
    return originalValue;
  }
  return toOffsetDateTimeString(parseDateTimeLocalValue(normalized, fieldName));
}

function parseRequiredNumber(value: string, fieldName: string): number {
  const parsed = parseOptionalNumber(value, fieldName);
  if (parsed === null) {
    throw new Error(`${fieldName} is required.`);
  }
  return parsed;
}

function parseOptionalNumber(value: string, fieldName: string): number | null {
  const normalized = value.trim();
  if (!normalized) {
    return null;
  }
  const parsed = Number(normalized);
  if (!Number.isFinite(parsed)) {
    throw new Error(`${fieldName} must be numeric.`);
  }
  return parsed;
}

function normalizeAnalysisReferences(
  references: AnalysisReference[]
): AnalysisReference[] {
  return references.reduce<AnalysisReference[]>((accumulator, reference, index) => {
    const analysisDate = reference.analysis_date.trim();
    const reportPath = reference.report_path.trim();
    const fullStateLogPath = reference.full_state_log_path.trim();

    if (!analysisDate && !reportPath && !fullStateLogPath) {
      return accumulator;
    }

    if (!analysisDate || !reportPath) {
      throw new Error(`Snapshot reference ${index + 1} is incomplete.`);
    }

    accumulator.push({
      analysis_date: analysisDate,
      report_path: reportPath,
      full_state_log_path: fullStateLogPath,
    });
    return accumulator;
  }, []);
}

function toggleTag(tags: string[], tag: string): string[] {
  return tags.includes(tag)
    ? tags.filter((item) => item !== tag)
    : [...tags, tag];
}

function addUniqueReference(
  references: AnalysisReference[],
  reference: AnalysisReference
): AnalysisReference[] {
  if (
    references.some(
      (item) =>
        item.report_path === reference.report_path &&
        item.full_state_log_path === reference.full_state_log_path &&
        item.analysis_date === reference.analysis_date
    )
  ) {
    return references;
  }
  return [...references, reference];
}

function buildReferenceFromReport(report: Report): AnalysisReference | null {
  const analysisDate = normalizeReportAnalysisDate(report);
  if (!analysisDate) {
    return null;
  }
  return {
    analysis_date: analysisDate,
    report_path: `data/reports/${report.id}/complete_report.md`,
    full_state_log_path: "",
  };
}

function normalizeReportAnalysisDate(report: Report): string | null {
  if (/^\d{4}-\d{2}-\d{2}$/.test(report.date)) {
    return report.date;
  }
  const match = report.id.match(/_(\d{4})(\d{2})(\d{2})_/);
  if (!match) {
    return null;
  }
  return `${match[1]}-${match[2]}-${match[3]}`;
}

function updateReferenceField(
  setFormState: Dispatch<SetStateAction<TradeRecordFormState>>,
  index: number,
  field: keyof AnalysisReference,
  value: string
) {
  setFormState((current) => ({
    ...current,
    analysis_references: current.analysis_references.map((reference, itemIndex) =>
      itemIndex === index ? { ...reference, [field]: value } : reference
    ),
  }));
}

function toDateTimeLocalValue(value: string | null): string {
  if (!value) {
    return "";
  }
  const normalized = value.trim();
  if (!normalized) {
    return "";
  }
  const parsed = new Date(normalized);
  if (Number.isNaN(parsed.getTime())) {
    const fallback = normalized.match(/^(\d{4}-\d{2}-\d{2}T\d{2}:\d{2})/);
    return fallback ? fallback[1] : "";
  }
  return formatDateTimeLocalValue(parsed);
}

function toInputNumber(value: number | null): string {
  return typeof value === "number" ? String(value) : "";
}

function parseDateTimeLocalValue(value: string, fieldName: string): Date {
  const match = value.match(/^(\d{4})-(\d{2})-(\d{2})T(\d{2}):(\d{2})$/);
  if (!match) {
    throw new Error(`${fieldName} must use YYYY-MM-DDTHH:MM format.`);
  }
  const year = Number(match[1]);
  const month = Number(match[2]);
  const day = Number(match[3]);
  const hour = Number(match[4]);
  const minute = Number(match[5]);
  const parsed = new Date(year, month - 1, day, hour, minute, 0, 0);
  if (
    Number.isNaN(parsed.getTime()) ||
    parsed.getFullYear() !== year ||
    parsed.getMonth() !== month - 1 ||
    parsed.getDate() !== day ||
    parsed.getHours() !== hour ||
    parsed.getMinutes() !== minute
  ) {
    throw new Error(`${fieldName} must be a valid date and time.`);
  }
  return parsed;
}

function formatDateTimeLocalValue(value: Date): string {
  return `${value.getFullYear()}-${padDateTimePart(value.getMonth() + 1)}-${padDateTimePart(value.getDate())}T${padDateTimePart(value.getHours())}:${padDateTimePart(value.getMinutes())}`;
}

function toOffsetDateTimeString(value: Date): string {
  const timezoneOffsetMinutes = -value.getTimezoneOffset();
  const sign = timezoneOffsetMinutes >= 0 ? "+" : "-";
  const absoluteOffsetMinutes = Math.abs(timezoneOffsetMinutes);
  const offsetHours = Math.floor(absoluteOffsetMinutes / 60);
  const offsetMinutes = absoluteOffsetMinutes % 60;
  return `${formatDateTimeLocalValue(value)}:00${sign}${padDateTimePart(offsetHours)}:${padDateTimePart(offsetMinutes)}`;
}

function padDateTimePart(value: number): string {
  return String(value).padStart(2, "0");
}
