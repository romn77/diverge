"use client";

import {
  useEffect,
  useMemo,
  useState,
  type Dispatch,
  type ReactNode,
  type SetStateAction,
} from "react";
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
  createTradePlan,
  resolveMarketSymbol,
  updateTradePlan,
  type AnalysisReference,
  type MarketResolution,
  type MarketResolutionMarket,
  type Report,
  type TradePlan,
  type TradePlanCreateRequest,
  type TradePlanUpdateRequest,
} from "@/lib/api";

interface TradePlanFormProps {
  isOpen: boolean;
  mode: "create" | "edit";
  initialPlan?: TradePlan | null;
  reports: Report[];
  onClose: () => void;
  onSaved: (plan: TradePlan) => void;
}

interface TradePlanFormState {
  raw_symbol: string;
  side: string;
  strategy_tags: string[];
  custom_strategy_tag: string;
  entry_condition: string;
  thesis: string;
  invalidation_condition: string;
  risk_rule: string;
  reward_target: string;
  position_plan: string;
  planned_horizon: string;
  stop_loss: string;
  take_profit: string;
  expires_at: string;
  notes: string;
  market_override: "auto" | MarketResolutionMarket;
  exchange_override: string;
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

export function TradePlanForm({
  isOpen,
  mode,
  initialPlan = null,
  reports,
  onClose,
  onSaved,
}: TradePlanFormProps) {
  const { t } = usePreferences();
  const [formState, setFormState] = useState<TradePlanFormState>(() =>
    buildInitialState(initialPlan)
  );
  const [marketResolution, setMarketResolution] = useState<MarketResolution | null>(
    initialPlan?.market_resolution ?? null
  );
  const [resolvingMarket, setResolvingMarket] = useState(false);
  const [advancedOpen, setAdvancedOpen] = useState(false);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!isOpen) {
      return;
    }
    setFormState(buildInitialState(initialPlan));
    setMarketResolution(initialPlan?.market_resolution ?? null);
    setAdvancedOpen(false);
    setSaving(false);
    setError(null);
  }, [initialPlan, isOpen]);

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
            setError(
              resolveError instanceof Error
                ? resolveError.message
                : t("tradePlan.error.resolveMarket", "Unable to resolve market")
            );
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
    t,
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
      ? t("tradePlan.newPlan", "New Trade Plan")
      : t("tradePlan.editPlan", "Edit Trade Plan");
  const baselineLocked = initialPlan?.status === "executed";

  const submitPlan = async () => {
    setSaving(true);
    setError(null);

    try {
      const payload = buildPayload(
        formState,
        marketResolution,
        initialPlan,
        baselineLocked,
        t
      );
      const plan =
        mode === "create" || !initialPlan
          ? await createTradePlan(payload as TradePlanCreateRequest)
          : await updateTradePlan(initialPlan.plan_id, payload as TradePlanUpdateRequest);
      onSaved(plan);
    } catch (submitError) {
      setError(
        submitError instanceof Error
          ? submitError.message
          : t("tradePlan.error.save", "Unable to save the trade plan")
      );
    } finally {
      setSaving(false);
    }
  };

  return (
    <Dialog open={isOpen} onOpenChange={(open) => !open && onClose()}>
      <DialogContent
        aria-label={localizedTitle}
        className="modal-panel scrollbar-hidden max-h-[92vh] max-w-5xl overflow-y-auto"
        onMouseDown={(event) => event.stopPropagation()}
      >
        <DialogHeader className="pr-12">
          <p className="text-[11px] font-semibold uppercase tracking-[0.34em] text-[var(--primary)]">
            {t("tradePlan.manualQueue", "Manual Plan Queue")}
          </p>
          <DialogTitle>{localizedTitle}</DialogTitle>
          <DialogDescription className="max-w-3xl">
            {t(
              "tradePlan.description",
              "Define the setup before execution. A plan may expire without a trade, but every saved plan needs a clear expiry and a quantifiable position plan."
            )}
          </DialogDescription>
        </DialogHeader>

        <div className="mt-8 grid gap-6">
          {baselineLocked ? (
            <div className="rounded-3xl border border-border bg-[var(--surface-strong)] px-5 py-4 text-sm text-muted-foreground">
              {t(
                "tradePlan.executedLocked",
                "This plan has already been executed. Baseline fields are locked; only notes can be changed."
              )}
            </div>
          ) : null}

          <section className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
            <FieldShell label={t("analysis.ticker", "Ticker")}>
              <Input
                type="text"
                value={formState.raw_symbol}
                disabled={baselineLocked}
                onChange={(event) =>
                  setFormState((current) => ({
                    ...current,
                    raw_symbol: event.target.value.toUpperCase(),
                  }))
                }
                placeholder="MSFT"
                className="mt-3"
              />
            </FieldShell>

            <FieldShell label={t("tradeRecord.side", "Side")}>
              <Select
                value={formState.side}
                disabled={baselineLocked}
                onValueChange={(value) =>
                  setFormState((current) => ({ ...current, side: value }))
                }
              >
                <SelectTrigger className="mt-3">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="long">{t("trade.side.long", "long")}</SelectItem>
                  <SelectItem value="short">{t("trade.side.short", "short")}</SelectItem>
                </SelectContent>
              </Select>
            </FieldShell>

            <FieldShell label={t("tradeRecord.plannedHorizon", "Planned Horizon")}>
              <Select
                value={formState.planned_horizon}
                disabled={baselineLocked}
                onValueChange={(value) =>
                  setFormState((current) => ({ ...current, planned_horizon: value }))
                }
              >
                <SelectTrigger className="mt-3">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  {PLANNED_HORIZONS.map((horizon) => (
                    <SelectItem key={horizon} value={horizon}>
                      {t(`tradeRecord.plannedHorizon.${horizon}`, horizon.replaceAll("_", " "))}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </FieldShell>

            <FieldShell label={t("tradePlan.expiresAt", "Expires At")}>
              <Input
                type="datetime-local"
                value={formState.expires_at}
                disabled={baselineLocked}
                onChange={(event) =>
                  setFormState((current) => ({
                    ...current,
                    expires_at: event.target.value,
                  }))
                }
                className="mt-3"
              />
            </FieldShell>
          </section>

          <MarketResolutionPanel
            resolution={marketResolution}
            resolving={resolvingMarket}
            marketOverride={formState.market_override}
            exchangeOverride={formState.exchange_override}
            disabled={baselineLocked}
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

          <section className="rounded-[28px] border border-border bg-card p-5">
            <p className="text-xs font-semibold uppercase tracking-[0.24em] text-muted-foreground">
              {t("tradeRecord.strategyTags", "Strategy Tags")}
            </p>
            <div className="mt-4 flex flex-wrap gap-2">
              {STRATEGY_TAGS.map((tag) => {
                const selected = formState.strategy_tags.includes(tag);
                return (
                  <Button
                    key={tag}
                    type="button"
                    variant="secondary"
                    size="sm"
                    data-active={selected}
                    aria-pressed={selected}
                    disabled={baselineLocked}
                    className="choice-pill choice-pill-sm focus-ring"
                    onClick={() =>
                      setFormState((current) => ({
                        ...current,
                        strategy_tags: toggleTag(current.strategy_tags, tag),
                      }))
                    }
                  >
                    {t(`tradeRecord.strategy.${tag}`, tag.replaceAll("_", " "))}
                  </Button>
                );
              })}
            </div>
            {formState.strategy_tags.includes("other") ? (
              <Input
                type="text"
                value={formState.custom_strategy_tag}
                disabled={baselineLocked}
                onChange={(event) =>
                  setFormState((current) => ({
                    ...current,
                    custom_strategy_tag: event.target.value,
                  }))
                }
                placeholder={t("tradeRecord.customStrategy", "Custom strategy")}
                className="mt-4 max-w-md"
              />
            ) : null}
          </section>

          <section className="grid gap-4 xl:grid-cols-2">
            <TextField
              label={t("tradePlan.entryCondition", "Entry Condition")}
              value={formState.entry_condition}
              disabled={baselineLocked}
              onChange={(value) =>
                setFormState((current) => ({ ...current, entry_condition: value }))
              }
              placeholder={t(
                "tradePlan.entryConditionPlaceholder",
                "What condition or price zone would justify execution?"
              )}
            />
            <TextField
              label={t("tradePlan.thesis", "Thesis")}
              value={formState.thesis}
              disabled={baselineLocked}
              onChange={(value) => setFormState((current) => ({ ...current, thesis: value }))}
              placeholder={t(
                "tradePlan.thesisPlaceholder",
                "Why is this setup worth planning before execution?"
              )}
            />
            <TextField
              label={t("tradePlan.invalidationCondition", "Invalidation Condition")}
              value={formState.invalidation_condition}
              disabled={baselineLocked}
              onChange={(value) =>
                setFormState((current) => ({
                  ...current,
                  invalidation_condition: value,
                }))
              }
              placeholder={t(
                "tradePlan.invalidationPlaceholder",
                "What would make this plan invalid before or after entry?"
              )}
            />
            <TextField
              label={t("tradePlan.riskRule", "Risk Rule")}
              value={formState.risk_rule}
              disabled={baselineLocked}
              onChange={(value) =>
                setFormState((current) => ({ ...current, risk_rule: value }))
              }
              placeholder={t(
                "tradePlan.riskRulePlaceholder",
                "How much can be lost, and how is risk controlled?"
              )}
            />
          </section>

          <section className="grid gap-4 xl:grid-cols-[minmax(0,1fr)_minmax(0,1fr)_180px_180px]">
            <TextField
              label={t("tradePlan.rewardTarget", "Reward Target")}
              value={formState.reward_target}
              disabled={baselineLocked}
              onChange={(value) =>
                setFormState((current) => ({ ...current, reward_target: value }))
              }
              rows={4}
              placeholder={t(
                "tradePlan.rewardTargetPlaceholder",
                "Target price, target return, or a textual reward condition."
              )}
            />
            <TextField
              label={t("tradePlan.positionPlan", "Position Plan")}
              value={formState.position_plan}
              disabled={baselineLocked}
              onChange={(value) =>
                setFormState((current) => ({ ...current, position_plan: value }))
              }
              rows={4}
              placeholder={t(
                "tradePlan.positionPlanPlaceholder",
                "A quantifiable size plan, for example 10 shares, 2% NAV, or max $500 risk."
              )}
            />
            <NumberField
              label={t("tradeRecord.stopLoss", "Stop Loss")}
              value={formState.stop_loss}
              disabled={baselineLocked}
              onChange={(value) =>
                setFormState((current) => ({ ...current, stop_loss: value }))
              }
              placeholder="408.00"
            />
            <NumberField
              label={t("tradeRecord.takeProfit", "Take Profit")}
              value={formState.take_profit}
              disabled={baselineLocked}
              onChange={(value) =>
                setFormState((current) => ({ ...current, take_profit: value }))
              }
              placeholder="448.00"
            />
          </section>

          <section className="rounded-[28px] border border-border bg-card p-5">
            <Button
              type="button"
              variant="secondary"
              className="h-auto w-full justify-between rounded-[22px] px-4 py-4 text-left"
              onClick={() => setAdvancedOpen((current) => !current)}
            >
              <span>
                <span className="block text-xs font-semibold uppercase tracking-[0.28em] text-muted-foreground">
                  {t("tradeRecord.advancedSupplement", "Advanced / Supplement")}
                </span>
                <span className="mt-2 block text-lg font-semibold text-foreground">
                  {t("tradePlan.referencesAndNotes", "References and notes")}
                </span>
              </span>
              <Badge variant="secondary">
                {advancedOpen ? t("common.open", "Open") : t("common.closed", "Closed")}
              </Badge>
            </Button>

            {advancedOpen ? (
              <div className="mt-5 grid gap-5">
                <SnapshotReferences
                  references={formState.analysis_references}
                  suggestedReports={suggestedReports}
                  disabled={baselineLocked}
                  setFormState={setFormState}
                />
                <TextField
                  label={t("tradePlan.notes", "Notes")}
                  value={formState.notes}
                  onChange={(value) =>
                    setFormState((current) => ({ ...current, notes: value }))
                  }
                  rows={4}
                  placeholder={t(
                    "tradePlan.notesPlaceholder",
                    "Optional non-baseline notes. These can still be updated after execution."
                  )}
                />
              </div>
            ) : null}
          </section>

          {error ? (
            <div className="rounded-3xl border border-[var(--danger-border)] bg-[var(--danger-soft)] px-5 py-4 text-sm text-destructive">
              {error}
            </div>
          ) : null}

          <div className="flex flex-wrap items-center justify-end gap-3">
            <Button type="button" variant="secondary" onClick={onClose} disabled={saving}>
              {t("common.cancel", "Cancel")}
            </Button>
            <Button
              type="button"
              onClick={() => void submitPlan()}
              disabled={saving || resolvingMarket}
            >
              {saving
                ? t("tradeRecord.saving", "Saving...")
                : mode === "create"
                  ? t("tradePlan.create", "Create Plan")
                  : t("tradePlan.saveChanges", "Save Changes")}
            </Button>
          </div>
        </div>
      </DialogContent>
    </Dialog>
  );
}

function FieldShell({
  label,
  children,
}: {
  label: string;
  children: ReactNode;
}) {
  return (
    <label className="field-shell block rounded-3xl border border-border bg-card p-4">
      <span className="text-xs font-semibold uppercase tracking-[0.24em] text-muted-foreground">
        {label}
      </span>
      {children}
    </label>
  );
}

function MarketResolutionPanel({
  resolution,
  resolving,
  marketOverride,
  exchangeOverride,
  disabled,
  onMarketOverrideChange,
  onExchangeOverrideChange,
}: {
  resolution: MarketResolution | null;
  resolving: boolean;
  marketOverride: "auto" | MarketResolutionMarket;
  exchangeOverride: string;
  disabled: boolean;
  onMarketOverrideChange: (value: "auto" | MarketResolutionMarket) => void;
  onExchangeOverrideChange: (value: string) => void;
}) {
  const { t } = usePreferences();
  const needsOverride = resolution?.market === "unknown" || resolution?.confidence === "low";
  return (
    <section className="rounded-[28px] border border-border bg-card p-5">
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <p className="text-xs font-semibold uppercase tracking-[0.26em] text-muted-foreground">
            {t("tradeRecord.marketResolution", "Market Resolution")}
          </p>
          <h3 className="mt-2 text-xl font-semibold text-foreground">
            {resolving
              ? t("tradeRecord.resolvingSymbol", "Resolving symbol...")
              : resolution
                ? `${resolution.display_symbol} · ${resolution.market.toUpperCase()}`
                : t("tradeRecord.enterTickerToResolve", "Enter a ticker to resolve")}
          </h3>
          {resolution ? (
            <p className="mt-2 text-sm leading-6 text-muted-foreground">
              {resolution.asset_type} · {resolution.exchange ?? t("tradeRecord.noExchange", "no exchange")} · {resolution.source} ·{" "}
              {resolution.confidence}
            </p>
          ) : null}
        </div>
        {resolution ? (
          <Badge variant={needsOverride ? "destructive" : "secondary"}>
            {needsOverride
              ? t("tradeRecord.needsReview", "needs review")
              : t("tradeRecord.resolved", "resolved")}
          </Badge>
        ) : null}
      </div>

      {resolution?.warnings.length ? (
        <div className="mt-4 rounded-3xl border border-[var(--accent-border)] bg-[var(--accent-soft)] px-4 py-3 text-sm text-[var(--accent)]">
          {resolution.warnings.join(" ")}
        </div>
      ) : null}

      {needsOverride || marketOverride !== "auto" ? (
        <div className="mt-4 grid gap-4 md:grid-cols-2">
          <label className="block">
            <span className="text-xs font-semibold uppercase tracking-[0.2em] text-muted-foreground">
              {t("tradeRecord.marketOverride", "Market Override")}
            </span>
            <Select
              value={marketOverride}
              disabled={disabled}
              onValueChange={(value) =>
                onMarketOverrideChange(value as "auto" | MarketResolutionMarket)
              }
            >
              <SelectTrigger className="mt-2">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="auto">{t("tradeRecord.market.auto", "auto")}</SelectItem>
                <SelectItem value="cn">{t("tradeRecord.market.cn", "cn")}</SelectItem>
                <SelectItem value="us">{t("tradeRecord.market.us", "us")}</SelectItem>
                <SelectItem value="unknown">{t("tradeRecord.market.unknown", "unknown")}</SelectItem>
              </SelectContent>
            </Select>
          </label>
          <label className="block">
            <span className="text-xs font-semibold uppercase tracking-[0.2em] text-muted-foreground">
              {t("tradeRecord.exchangeOverride", "Exchange Override")}
            </span>
            <Input
              value={exchangeOverride}
              disabled={disabled}
              onChange={(event) => onExchangeOverrideChange(event.target.value.toUpperCase())}
              placeholder="SH, SZ, NASDAQ"
              className="mt-2"
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
  disabled,
  setFormState,
}: {
  references: AnalysisReference[];
  suggestedReports: Report[];
  disabled: boolean;
  setFormState: Dispatch<SetStateAction<TradePlanFormState>>;
}) {
  const { t } = usePreferences();
  return (
    <section className="rounded-[28px] border border-border bg-[var(--surface)] p-5">
      <div className="flex flex-wrap items-center justify-between gap-4">
        <div>
          <p className="text-xs font-semibold uppercase tracking-[0.28em] text-muted-foreground">
            {t("tradeRecord.snapshots", "Snapshot References")}
          </p>
          <h3 className="mt-2 text-lg font-semibold text-foreground">
            {t("tradeRecord.optionalAnalysisContext", "Optional analysis context")}
          </h3>
        </div>
        <Button
          type="button"
          variant="secondary"
          disabled={disabled}
          onClick={() =>
            setFormState((current) => ({
              ...current,
              analysis_references: [...current.analysis_references, { ...EMPTY_REFERENCE }],
            }))
          }
        >
          {t("tradeRecord.addBlankReference", "Add Blank Reference")}
        </Button>
      </div>

      <div className="mt-4 flex flex-wrap gap-2">
        {suggestedReports.map((report) => {
          const reference = buildReferenceFromReport(report);
          return (
            <Button
              key={report.id}
              type="button"
              variant="secondary"
              size="sm"
              disabled={disabled || !reference}
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
            </Button>
          );
        })}
      </div>

      <div className="mt-5 space-y-4">
        {references.map((reference, index) => (
          <div
            key={`${reference.report_path}-${reference.full_state_log_path}-${index}`}
            className="rounded-3xl border border-border bg-[var(--surface-strong)] p-4"
          >
            <div className="flex items-center justify-between gap-4">
              <p className="text-xs font-semibold uppercase tracking-[0.24em] text-muted-foreground">
                {t("tradeRecord.snapshot", ({ index: itemIndex }) => `Snapshot ${itemIndex}`, {
                  index: index + 1,
                })}
              </p>
              <Button
                type="button"
                variant="secondary"
                size="sm"
                disabled={disabled}
                onClick={() =>
                  setFormState((current) => ({
                    ...current,
                    analysis_references: current.analysis_references.filter(
                      (_item, itemIndex) => itemIndex !== index
                    ),
                  }))
                }
              >
                {t("tradeRecord.remove", "Remove")}
              </Button>
            </div>
            <div className="mt-4 grid gap-4">
              <Input
                type="date"
                value={reference.analysis_date}
                disabled={disabled}
                onChange={(event) =>
                  updateReferenceField(setFormState, index, "analysis_date", event.target.value)
                }
              />
              <Input
                type="text"
                value={reference.report_path}
                disabled={disabled}
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

function TextField({
  label,
  value,
  onChange,
  placeholder,
  disabled = false,
  rows = 6,
}: {
  label: string;
  value: string;
  onChange: (value: string) => void;
  placeholder: string;
  disabled?: boolean;
  rows?: number;
}) {
  return (
    <label className="field-shell block rounded-3xl border border-border bg-card p-4">
      <span className="text-xs font-semibold uppercase tracking-[0.24em] text-muted-foreground">
        {label}
      </span>
      <Textarea
        value={value}
        disabled={disabled}
        onChange={(event) => onChange(event.target.value)}
        rows={rows}
        placeholder={placeholder}
        className="mt-3 min-h-[120px]"
      />
    </label>
  );
}

function NumberField({
  label,
  value,
  onChange,
  placeholder,
  disabled = false,
}: {
  label: string;
  value: string;
  onChange: (value: string) => void;
  placeholder: string;
  disabled?: boolean;
}) {
  return (
    <label className="field-shell block rounded-3xl border border-border bg-card p-4">
      <span className="text-xs font-semibold uppercase tracking-[0.24em] text-muted-foreground">
        {label}
      </span>
      <Input
        type="number"
        inputMode="decimal"
        value={value}
        disabled={disabled}
        onChange={(event) => onChange(event.target.value)}
        placeholder={placeholder}
        className="mt-3"
      />
    </label>
  );
}

function buildInitialState(plan: TradePlan | null): TradePlanFormState {
  const tags = plan?.strategy_tags ?? [];
  const builtInTags = tags.filter((tag) => STRATEGY_TAGS.includes(tag));
  const customTags = tags.filter((tag) => !STRATEGY_TAGS.includes(tag));
  return {
    raw_symbol: plan?.raw_symbol ?? plan?.ticker ?? "",
    side: plan?.side ?? "long",
    strategy_tags: builtInTags.length > 0 ? builtInTags : [],
    custom_strategy_tag: customTags.join(", "),
    entry_condition: plan?.entry_condition ?? "",
    thesis: plan?.thesis ?? "",
    invalidation_condition: plan?.invalidation_condition ?? "",
    risk_rule: plan?.risk_rule ?? "",
    reward_target: plan?.reward_target ?? "",
    position_plan: plan?.position_plan ?? "",
    planned_horizon: plan?.planned_horizon ?? "unknown",
    stop_loss: toInputNumber(plan?.stop_loss ?? null),
    take_profit: toInputNumber(plan?.take_profit ?? null),
    expires_at: toDateTimeLocalValue(plan?.expires_at ?? defaultExpiryIso()),
    notes: plan?.notes ?? "",
    market_override:
      plan?.market_resolution?.source === "manual" && plan.market
        ? plan.market
        : "auto",
    exchange_override: plan?.market_resolution?.source === "manual" ? plan.exchange ?? "" : "",
    analysis_references:
      plan?.analysis_references.map((reference) => ({ ...reference })) ?? [],
  };
}

function buildPayload(
  state: TradePlanFormState,
  marketResolution: MarketResolution | null,
  plan: TradePlan | null,
  baselineLocked: boolean,
  t: ReturnType<typeof usePreferences>["t"]
): TradePlanCreateRequest | TradePlanUpdateRequest {
  if (baselineLocked) {
    return { notes: state.notes.trim() };
  }
  const strategyTags = normalizeStrategyTags(state, t);
  return {
    raw_symbol: requireText(state.raw_symbol, t("analysis.ticker", "Ticker"), t).toUpperCase(),
    side: state.side,
    source: plan?.source ?? "manual",
    strategy_tags: strategyTags,
    entry_condition: requireText(
      state.entry_condition,
      t("tradePlan.entryCondition", "Entry condition"),
      t
    ),
    thesis: requireText(state.thesis, t("tradePlan.thesis", "Thesis"), t),
    invalidation_condition: requireText(
      state.invalidation_condition,
      t("tradePlan.invalidationCondition", "Invalidation condition"),
      t
    ),
    risk_rule: requireText(state.risk_rule, t("tradePlan.riskRule", "Risk rule"), t),
    reward_target: requireText(
      state.reward_target,
      t("tradePlan.rewardTarget", "Reward target"),
      t
    ),
    position_plan: requireQuantifiablePositionPlan(state.position_plan, t),
    planned_horizon: state.planned_horizon || "unknown",
    stop_loss: parseOptionalNumber(
      state.stop_loss,
      t("tradeRecord.stopLoss", "Stop loss"),
      t
    ),
    take_profit: parseOptionalNumber(
      state.take_profit,
      t("tradeRecord.takeProfit", "Take profit"),
      t
    ),
    expires_at: normalizeRequiredTimestamp(
      state.expires_at,
      t("tradePlan.expiresAt", "Expires at"),
      plan?.expires_at ?? null,
      t
    ),
    notes: state.notes.trim(),
    market_resolution:
      state.market_override !== "auto" && marketResolution
        ? { ...marketResolution, source: "manual", confidence: "manual" }
        : marketResolution,
    analysis_references: normalizeAnalysisReferences(state.analysis_references, t),
  };
}

function normalizeStrategyTags(
  state: TradePlanFormState,
  t: ReturnType<typeof usePreferences>["t"]
): string[] {
  const values = [...state.strategy_tags];
  const customTags = state.custom_strategy_tag
    .split(",")
    .map((tag) => tag.trim())
    .filter(Boolean);
  values.push(...customTags);
  const normalized = Array.from(
    new Set(
      values.map((tag) =>
        tag.toLowerCase().replace(/[^a-z0-9_]+/g, "_").replace(/^_+|_+$/g, "")
      )
    )
  ).filter(Boolean);
  if (normalized.length === 0) {
    throw new Error(
      t("tradeRecord.error.strategyTagsRequired", "Strategy tags are required.")
    );
  }
  return normalized;
}

function requireText(
  value: string,
  fieldName: string,
  t: ReturnType<typeof usePreferences>["t"]
): string {
  const normalized = value.trim();
  if (!normalized) {
    throw new Error(
      t("common.required", ({ field }) => `${field} is required.`, {
        field: fieldName,
      })
    );
  }
  return normalized;
}

function requireQuantifiablePositionPlan(
  value: string,
  t: ReturnType<typeof usePreferences>["t"]
): string {
  const normalized = requireText(
    value,
    t("tradePlan.positionPlan", "Position plan"),
    t
  );
  if (!/\d/.test(normalized)) {
    throw new Error(
      t(
        "tradePlan.error.positionPlanQuantified",
        "Position plan must include a quantifiable size, percent, amount, or risk limit."
      )
    );
  }
  return normalized;
}

function normalizeRequiredTimestamp(
  value: string,
  fieldName: string,
  originalValue: string | null,
  t: ReturnType<typeof usePreferences>["t"]
): string {
  const normalized = value.trim();
  if (!normalized) {
    throw new Error(
      t("common.required", ({ field }) => `${field} is required.`, {
        field: fieldName,
      })
    );
  }
  if (originalValue && normalized === toDateTimeLocalValue(originalValue)) {
    return originalValue;
  }
  return toOffsetDateTimeString(parseDateTimeLocalValue(normalized, fieldName, t));
}

function parseOptionalNumber(
  value: string,
  fieldName: string,
  t: ReturnType<typeof usePreferences>["t"]
): number | null {
  const normalized = value.trim();
  if (!normalized) {
    return null;
  }
  const parsed = Number(normalized);
  if (!Number.isFinite(parsed)) {
    throw new Error(
      t("common.mustBeNumeric", ({ field }) => `${field} must be numeric.`, {
        field: fieldName,
      })
    );
  }
  return parsed;
}

function normalizeAnalysisReferences(
  references: AnalysisReference[],
  t: ReturnType<typeof usePreferences>["t"]
): AnalysisReference[] {
  return references.reduce<AnalysisReference[]>((accumulator, reference, index) => {
    const analysisDate = reference.analysis_date.trim();
    const reportPath = reference.report_path.trim();
    const fullStateLogPath = reference.full_state_log_path.trim();

    if (!analysisDate && !reportPath && !fullStateLogPath) {
      return accumulator;
    }

    if (!analysisDate || !reportPath) {
      throw new Error(
        t(
          "tradeRecord.error.snapshotIncomplete",
          ({ index: itemIndex }) => `Snapshot reference ${itemIndex} is incomplete.`,
          { index: index + 1 }
        )
      );
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
        item.full_state_log_path === reference.full_state_log_path
    )
  ) {
    return references;
  }
  return [...references, reference];
}

function updateReferenceField(
  setFormState: Dispatch<SetStateAction<TradePlanFormState>>,
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

function buildReferenceFromReport(report: Report): AnalysisReference | null {
  if (!report.id) {
    return null;
  }
  return {
    analysis_date: report.date || "",
    report_path: `data/reports/${report.id}/complete_report.md`,
    full_state_log_path: "",
  };
}

function toInputNumber(value: number | null | undefined): string {
  return typeof value === "number" && Number.isFinite(value) ? String(value) : "";
}

function defaultExpiryIso(): string {
  return new Date(Date.now() + 24 * 60 * 60 * 1000).toISOString();
}

function toDateTimeLocalValue(value: string | null): string {
  if (!value) {
    return "";
  }
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) {
    return "";
  }
  const local = new Date(parsed.getTime() - parsed.getTimezoneOffset() * 60_000);
  return local.toISOString().slice(0, 16);
}

function parseDateTimeLocalValue(
  value: string,
  fieldName: string,
  t: ReturnType<typeof usePreferences>["t"]
): Date {
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) {
    throw new Error(
      t("common.invalidDateTime", ({ field }) => `${field} is invalid.`, {
        field: fieldName,
      })
    );
  }
  return parsed;
}

function toOffsetDateTimeString(value: Date): string {
  const offsetMinutes = -value.getTimezoneOffset();
  const sign = offsetMinutes >= 0 ? "+" : "-";
  const absoluteMinutes = Math.abs(offsetMinutes);
  const hours = String(Math.floor(absoluteMinutes / 60)).padStart(2, "0");
  const minutes = String(absoluteMinutes % 60).padStart(2, "0");
  const year = value.getFullYear();
  const month = String(value.getMonth() + 1).padStart(2, "0");
  const day = String(value.getDate()).padStart(2, "0");
  const hour = String(value.getHours()).padStart(2, "0");
  const minute = String(value.getMinutes()).padStart(2, "0");
  const second = String(value.getSeconds()).padStart(2, "0");
  return `${year}-${month}-${day}T${hour}:${minute}:${second}${sign}${hours}:${minutes}`;
}
