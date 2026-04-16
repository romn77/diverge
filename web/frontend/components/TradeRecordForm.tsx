"use client";

import { useEffect, useMemo, useState, type Dispatch, type SetStateAction } from "react";
import { usePreferences } from "@/components/PreferencesProvider";
import {
  createTrade,
  updateTrade,
  type AnalysisReference,
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
  ticker: string;
  exchange_or_market: string;
  side: string;
  status: string;
  entry_timestamp: string;
  entry_price: string;
  exit_timestamp: string;
  exit_price: string;
  size: string;
  initial_thesis: string;
  planned_horizon: string;
  stop_loss: string;
  take_profit: string;
  notes: string;
  analysis_references: AnalysisReference[];
}

const EMPTY_REFERENCE: AnalysisReference = {
  analysis_date: "",
  report_path: "",
  full_state_log_path: "",
};

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
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!isOpen) {
      return;
    }

    setFormState(buildInitialState(initialRecord));
    setSaving(false);
    setError(null);
  }, [initialRecord, isOpen]);

  useEffect(() => {
    if (!isOpen) {
      return;
    }

    const handleKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape") {
        onClose();
      }
    };

    window.addEventListener("keydown", handleKeyDown);
    return () => {
      window.removeEventListener("keydown", handleKeyDown);
    };
  }, [isOpen, onClose]);

  const suggestedReports = useMemo(() => {
    const normalizedTicker = formState.ticker.trim().toUpperCase();
    const matchingReports = normalizedTicker
      ? reports.filter((report) => report.ticker === normalizedTicker)
      : reports;

    return matchingReports.slice(0, 6);
  }, [formState.ticker, reports]);

  if (!isOpen) {
    return null;
  }

  const localizedTitle =
    mode === "create"
      ? t("tradeRecord.recordTrade", "Record Trade")
      : t("tradeRecord.editTrade", "Edit Trade");
  const description =
    mode === "create"
      ? t(
          "tradeRecord.createDescription",
          "Capture a hand-entered trade record for the manual review."
        )
      : t(
          "tradeRecord.editDescription",
          "Update the saved hand-entered trade record without changing the backend schema."
        );

  const submitTrade = async () => {
    setSaving(true);
    setError(null);

    try {
      const payload = buildPayload(formState, initialRecord, t);
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
    <div
      className="modal-backdrop fixed inset-0 z-[70] flex items-center justify-center bg-[rgba(17,24,39,0.42)] px-4 py-6"
      onClick={onClose}
    >
      <div
        role="dialog"
        aria-modal="true"
        aria-label={localizedTitle}
        className="modal-panel scrollbar-hidden fade-in max-h-[92vh] w-full max-w-5xl overflow-y-auto rounded-[30px] border border-[var(--border)] bg-[var(--surface)] p-6 shadow-[0_28px_80px_rgba(18,28,41,0.24)] md:p-8"
        onClick={(event) => event.stopPropagation()}
      >
        <div className="flex flex-wrap items-start justify-between gap-4">
          <div>
            <p className="text-[11px] font-semibold uppercase tracking-[0.34em] text-[var(--primary)]">
              {t("tradeRecord.manualJournal", "Manual Journal")}
            </p>
            <h2 className="font-heading mt-3 text-3xl font-bold tracking-tight text-slate-900">
              {localizedTitle}
            </h2>
            <p className="mt-2 max-w-3xl text-sm leading-6 text-slate-600">
              {description}
            </p>
          </div>
          <button
            type="button"
            className="interactive-button focus-ring rounded-full border border-[var(--border)] bg-white px-4 py-2 text-xs font-semibold uppercase tracking-[0.2em] text-slate-600"
            onClick={onClose}
          >
            {t("common.close", "Close")}
          </button>
        </div>

        <div className="mt-8 grid gap-6">
          <section className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
            <label className="field-shell block rounded-3xl border border-[var(--border)] bg-white/90 p-4">
              <span className="text-xs font-semibold uppercase tracking-[0.24em] text-slate-500">
                {t("analysis.ticker", "Ticker")}
              </span>
              <input
                type="text"
                value={formState.ticker}
                onChange={(event) =>
                  setFormState((current) => ({
                    ...current,
                    ticker: event.target.value.toUpperCase(),
                  }))
                }
                placeholder="MSFT"
                className="focus-ring mt-3 w-full rounded-2xl border border-[var(--border)] bg-[var(--surface-strong)] px-4 py-3 text-sm font-semibold text-slate-800"
              />
            </label>

            <label className="field-shell block rounded-3xl border border-[var(--border)] bg-white/90 p-4">
              <span className="text-xs font-semibold uppercase tracking-[0.24em] text-slate-500">
                {t("tradeRecord.marketExchange", "Market / Exchange")}
              </span>
              <input
                type="text"
                value={formState.exchange_or_market}
                onChange={(event) =>
                  setFormState((current) => ({
                    ...current,
                    exchange_or_market: event.target.value,
                  }))
                }
                placeholder="NASDAQ"
                className="focus-ring mt-3 w-full rounded-2xl border border-[var(--border)] bg-[var(--surface-strong)] px-4 py-3 text-sm font-medium text-slate-800"
              />
            </label>

            <label className="field-shell block rounded-3xl border border-[var(--border)] bg-white/90 p-4">
              <span className="text-xs font-semibold uppercase tracking-[0.24em] text-slate-500">
                {t("tradeRecord.side", "Side")}
              </span>
              <select
                value={formState.side}
                onChange={(event) =>
                  setFormState((current) => ({
                    ...current,
                    side: event.target.value,
                  }))
                }
                className="focus-ring mt-3 w-full rounded-2xl border border-[var(--border)] bg-[var(--surface-strong)] px-4 py-3 text-sm font-medium text-slate-800"
              >
                <option value="long">{t("trade.side.long", "long")}</option>
                <option value="short">{t("trade.side.short", "short")}</option>
              </select>
            </label>

            <label className="field-shell block rounded-3xl border border-[var(--border)] bg-white/90 p-4">
              <span className="text-xs font-semibold uppercase tracking-[0.24em] text-slate-500">
                {t("tradeRecord.status", "Status")}
              </span>
              <input
                type="text"
                value={formState.status}
                onChange={(event) =>
                  setFormState((current) => ({
                    ...current,
                    status: event.target.value,
                  }))
                }
                placeholder="open"
                className="focus-ring mt-3 w-full rounded-2xl border border-[var(--border)] bg-[var(--surface-strong)] px-4 py-3 text-sm font-medium text-slate-800"
              />
            </label>
          </section>

          <section className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
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

            <label className="field-shell block rounded-3xl border border-[var(--border)] bg-white/90 p-4">
              <span className="text-xs font-semibold uppercase tracking-[0.24em] text-slate-500">
                {t("tradeRecord.entryPrice", "Entry Price")}
              </span>
              <input
                type="number"
                inputMode="decimal"
                value={formState.entry_price}
                onChange={(event) =>
                  setFormState((current) => ({
                    ...current,
                    entry_price: event.target.value,
                  }))
                }
                placeholder="420.00"
                className="focus-ring mt-3 w-full rounded-2xl border border-[var(--border)] bg-[var(--surface-strong)] px-4 py-3 text-sm font-medium text-slate-800"
              />
            </label>

            <label className="field-shell block rounded-3xl border border-[var(--border)] bg-white/90 p-4">
              <span className="text-xs font-semibold uppercase tracking-[0.24em] text-slate-500">
                {t("tradeRecord.exitTime", "Exit Time")}
              </span>
              <input
                type="datetime-local"
                value={formState.exit_timestamp}
                onChange={(event) =>
                  setFormState((current) => ({
                    ...current,
                    exit_timestamp: event.target.value,
                  }))
                }
                className="focus-ring mt-3 w-full rounded-2xl border border-[var(--border)] bg-[var(--surface-strong)] px-4 py-3 text-sm font-medium text-slate-800"
              />
            </label>

            <label className="field-shell block rounded-3xl border border-[var(--border)] bg-white/90 p-4">
              <span className="text-xs font-semibold uppercase tracking-[0.24em] text-slate-500">
                {t("tradeRecord.exitPrice", "Exit Price")}
              </span>
              <input
                type="number"
                inputMode="decimal"
                value={formState.exit_price}
                onChange={(event) =>
                  setFormState((current) => ({
                    ...current,
                    exit_price: event.target.value,
                  }))
                }
                placeholder="436.50"
                className="focus-ring mt-3 w-full rounded-2xl border border-[var(--border)] bg-[var(--surface-strong)] px-4 py-3 text-sm font-medium text-slate-800"
              />
            </label>
          </section>

          <section className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
            <label className="field-shell block rounded-3xl border border-[var(--border)] bg-white/90 p-4">
              <span className="text-xs font-semibold uppercase tracking-[0.24em] text-slate-500">
                {t("tradeRecord.size", "Size")}
              </span>
              <input
                type="number"
                inputMode="decimal"
                value={formState.size}
                onChange={(event) =>
                  setFormState((current) => ({
                    ...current,
                    size: event.target.value,
                  }))
                }
                placeholder="10"
                className="focus-ring mt-3 w-full rounded-2xl border border-[var(--border)] bg-[var(--surface-strong)] px-4 py-3 text-sm font-medium text-slate-800"
              />
            </label>

            <label className="field-shell block rounded-3xl border border-[var(--border)] bg-white/90 p-4">
              <span className="text-xs font-semibold uppercase tracking-[0.24em] text-slate-500">
                {t("tradeRecord.plannedHorizon", "Planned Horizon")}
              </span>
              <input
                type="text"
                value={formState.planned_horizon}
                onChange={(event) =>
                  setFormState((current) => ({
                    ...current,
                    planned_horizon: event.target.value,
                  }))
                }
                placeholder="swing_2w"
                className="focus-ring mt-3 w-full rounded-2xl border border-[var(--border)] bg-[var(--surface-strong)] px-4 py-3 text-sm font-medium text-slate-800"
              />
            </label>

            <label className="field-shell block rounded-3xl border border-[var(--border)] bg-white/90 p-4">
              <span className="text-xs font-semibold uppercase tracking-[0.24em] text-slate-500">
                {t("tradeRecord.stopLoss", "Stop Loss")}
              </span>
              <input
                type="number"
                inputMode="decimal"
                value={formState.stop_loss}
                onChange={(event) =>
                  setFormState((current) => ({
                    ...current,
                    stop_loss: event.target.value,
                  }))
                }
                placeholder="408.00"
                className="focus-ring mt-3 w-full rounded-2xl border border-[var(--border)] bg-[var(--surface-strong)] px-4 py-3 text-sm font-medium text-slate-800"
              />
            </label>

            <label className="field-shell block rounded-3xl border border-[var(--border)] bg-white/90 p-4">
              <span className="text-xs font-semibold uppercase tracking-[0.24em] text-slate-500">
                {t("tradeRecord.takeProfit", "Take Profit")}
              </span>
              <input
                type="number"
                inputMode="decimal"
                value={formState.take_profit}
                onChange={(event) =>
                  setFormState((current) => ({
                    ...current,
                    take_profit: event.target.value,
                  }))
                }
                placeholder="448.00"
                className="focus-ring mt-3 w-full rounded-2xl border border-[var(--border)] bg-[var(--surface-strong)] px-4 py-3 text-sm font-medium text-slate-800"
              />
            </label>
          </section>

          <section className="grid gap-4 xl:grid-cols-[minmax(0,1.25fr)_minmax(0,0.75fr)]">
            <label className="field-shell block rounded-3xl border border-[var(--border)] bg-white/90 p-4">
              <span className="text-xs font-semibold uppercase tracking-[0.24em] text-slate-500">
                {t("tradeRecord.initialThesis", "Initial Thesis")}
              </span>
              <textarea
                value={formState.initial_thesis}
                onChange={(event) =>
                  setFormState((current) => ({
                    ...current,
                    initial_thesis: event.target.value,
                  }))
                }
                rows={6}
                placeholder={t(
                  "tradeRecord.initialThesisPlaceholder",
                  "Document the setup, catalyst, and why this trade exists."
                )}
                className="focus-ring mt-3 w-full rounded-2xl border border-[var(--border)] bg-[var(--surface-strong)] px-4 py-3 text-sm leading-6 text-slate-800"
              />
            </label>

            <label className="field-shell block rounded-3xl border border-[var(--border)] bg-white/90 p-4">
              <span className="text-xs font-semibold uppercase tracking-[0.24em] text-slate-500">
                {t("tradeRecord.notes", "Notes")}
              </span>
              <textarea
                value={formState.notes}
                onChange={(event) =>
                  setFormState((current) => ({
                    ...current,
                    notes: event.target.value,
                  }))
                }
                rows={6}
                placeholder={t(
                  "tradeRecord.notesPlaceholder",
                  "Execution notes, context, or manual follow-up items."
                )}
                className="focus-ring mt-3 w-full rounded-2xl border border-[var(--border)] bg-[var(--surface-strong)] px-4 py-3 text-sm leading-6 text-slate-800"
              />
            </label>
          </section>

          <section className="rounded-[28px] border border-[var(--border)] bg-white/85 p-5">
            <div className="flex flex-wrap items-start justify-between gap-4">
              <div>
                <p className="text-xs font-semibold uppercase tracking-[0.28em] text-slate-500">
                  {t("tradeRecord.snapshots", "Snapshot References")}
                </p>
                <h3 className="mt-2 text-xl font-semibold text-slate-900">
                  {t(
                    "tradeRecord.bindSnapshots",
                    "Bind analysis snapshots instead of copying full reports"
                  )}
                </h3>
                <p className="mt-2 max-w-3xl text-sm leading-6 text-slate-600">
                  {t(
                    "tradeRecord.contractPrefix",
                    "The defaults follow the MAY-8 file contract:"
                  )}
                  <code className="ml-1 rounded bg-slate-100 px-2 py-1 text-[12px]">
                    reports/&lt;report_id&gt;/complete_report.md
                  </code>
                  <code className="ml-1 rounded bg-slate-100 px-2 py-1 text-[12px]">
                    eval_results/&lt;ticker&gt;/TradingAgentsStrategy_logs/full_states_log_&lt;date&gt;.json
                  </code>
                </p>
              </div>
              <button
                type="button"
                className="interactive-button focus-ring rounded-full border border-[var(--border)] bg-white px-4 py-2 text-xs font-semibold uppercase tracking-[0.2em] text-slate-600"
                onClick={() =>
                  setFormState((current) => ({
                    ...current,
                    analysis_references: [
                      ...current.analysis_references,
                      { ...EMPTY_REFERENCE },
                    ],
                  }))
                }
              >
                {t("tradeRecord.addBlankReference", "Add Blank Reference")}
              </button>
            </div>

            <div className="mt-5">
              <p className="text-xs font-semibold uppercase tracking-[0.24em] text-slate-500">
                {t("tradeRecord.quickAdd", "Quick add from reports")}
              </p>
              <div className="mt-3 flex flex-wrap gap-2">
                {suggestedReports.length === 0 ? (
                  <span className="rounded-full border border-[var(--border)] px-3 py-2 text-xs font-medium text-slate-500">
                    {t(
                      "tradeRecord.noQuickReports",
                      "No reports available for quick attach yet."
                    )}
                  </span>
                ) : (
                  suggestedReports.map((report) => {
                    const reference = buildReferenceFromReport(report);
                    const disabled = reference === null;
                    return (
                      <button
                        key={report.id}
                        type="button"
                        disabled={disabled}
                        className={`interactive-button focus-ring rounded-full border px-3 py-2 text-xs font-semibold uppercase tracking-[0.16em] ${
                          disabled
                            ? "cursor-not-allowed border-slate-200 bg-slate-100 text-slate-400"
                            : "border-[var(--border)] bg-white text-slate-600 hover:border-[var(--primary)] hover:text-[var(--primary)]"
                        }`}
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
                  })
                )}
              </div>
            </div>

            <div className="mt-5 space-y-4">
              {formState.analysis_references.length === 0 ? (
                <div className="rounded-3xl border border-dashed border-[var(--border)] bg-[var(--surface-strong)] px-5 py-6 text-sm text-slate-500">
                  {t(
                    "tradeRecord.noReferences",
                    "No snapshot references linked yet. Records can still be saved, but entry/exit review saving will need at least one valid report plus full state log reference."
                  )}
                </div>
              ) : (
                formState.analysis_references.map((reference, index) => (
                  <div
                    key={`${reference.report_path}-${reference.full_state_log_path}-${index}`}
                    className="rounded-3xl border border-[var(--border)] bg-[var(--surface-strong)]/80 p-4"
                  >
                    <div className="flex items-center justify-between gap-4">
                      <p className="text-xs font-semibold uppercase tracking-[0.24em] text-slate-500">
                        {t("tradeRecord.snapshot", ({ index: snapshotIndex }) => `Snapshot ${snapshotIndex}`, {
                          index: index + 1,
                        })}
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
                        {t("tradeRecord.remove", "Remove")}
                      </button>
                    </div>

                    <div className="mt-4 grid gap-4 xl:grid-cols-[180px_minmax(0,1fr)]">
                      <label className="block">
                        <span className="text-xs font-semibold uppercase tracking-[0.2em] text-slate-500">
                          {t("analysis.analysisDate", "Analysis Date")}
                        </span>
                        <input
                          type="date"
                          value={reference.analysis_date}
                          onChange={(event) =>
                            updateReferenceField(
                              setFormState,
                              index,
                              "analysis_date",
                              event.target.value
                            )
                          }
                          className="focus-ring mt-2 w-full rounded-2xl border border-[var(--border)] bg-white px-4 py-3 text-sm text-slate-800"
                        />
                      </label>

                      <div className="grid gap-4">
                        <label className="block">
                          <span className="text-xs font-semibold uppercase tracking-[0.2em] text-slate-500">
                            {t("tradeRecord.reportPath", "Report Path")}
                          </span>
                          <input
                            type="text"
                            value={reference.report_path}
                            onChange={(event) =>
                              updateReferenceField(
                                setFormState,
                                index,
                                "report_path",
                                event.target.value
                              )
                            }
                            className="focus-ring mt-2 w-full rounded-2xl border border-[var(--border)] bg-white px-4 py-3 text-sm text-slate-800"
                          />
                        </label>

                        <label className="block">
                          <span className="text-xs font-semibold uppercase tracking-[0.2em] text-slate-500">
                            {t(
                              "tradeRecord.fullStateLogPath",
                              "Full State Log Path"
                            )}
                          </span>
                          <input
                            type="text"
                            value={reference.full_state_log_path}
                            onChange={(event) =>
                              updateReferenceField(
                                setFormState,
                                index,
                                "full_state_log_path",
                                event.target.value
                              )
                            }
                            className="focus-ring mt-2 w-full rounded-2xl border border-[var(--border)] bg-white px-4 py-3 text-sm text-slate-800"
                          />
                        </label>
                      </div>
                    </div>
                  </div>
                ))
              )}
            </div>
          </section>

          {error ? (
            <div className="rounded-3xl border border-rose-200 bg-rose-50 px-5 py-4 text-sm text-rose-700">
              {error}
            </div>
          ) : null}

          <div className="flex flex-wrap items-center justify-end gap-3">
            <button
              type="button"
              className="interactive-button focus-ring rounded-full border border-[var(--border)] bg-white px-5 py-3 text-xs font-semibold uppercase tracking-[0.2em] text-slate-600"
              onClick={onClose}
              disabled={saving}
            >
              {t("common.cancel", "Cancel")}
            </button>
            <button
              type="button"
              className="interactive-button focus-ring rounded-full border border-[var(--primary)] bg-[var(--primary)] px-5 py-3 text-xs font-semibold uppercase tracking-[0.2em] text-white"
              onClick={() => void submitTrade()}
              disabled={saving}
            >
              {saving
                ? t("tradeRecord.saving", "Saving...")
                : mode === "create"
                  ? t("tradeRecord.create", "Create Trade")
                  : t("tradeRecord.saveChanges", "Save Changes")}
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}

function buildInitialState(record: TradeRecord | null): TradeRecordFormState {
  return {
    ticker: record?.ticker ?? "",
    exchange_or_market: record?.exchange_or_market ?? "",
    side: record?.side ?? "long",
    status: record?.status ?? "open",
    entry_timestamp: toDateTimeLocalValue(record?.entry_timestamp ?? null),
    entry_price: toInputNumber(record?.entry_price ?? null),
    exit_timestamp: toDateTimeLocalValue(record?.exit_timestamp ?? null),
    exit_price: toInputNumber(record?.exit_price ?? null),
    size: toInputNumber(record?.size ?? null),
    initial_thesis: record?.initial_thesis ?? "",
    planned_horizon: record?.planned_horizon ?? "",
    stop_loss: toInputNumber(record?.stop_loss ?? null),
    take_profit: toInputNumber(record?.take_profit ?? null),
    notes: record?.notes ?? "",
    analysis_references:
      record?.analysis_references.map((reference) => ({ ...reference })) ?? [],
  };
}

function buildPayload(
  state: TradeRecordFormState,
  record: TradeRecord | null,
  t: ReturnType<typeof usePreferences>["t"]
): TradeRecordCreateRequest {
  return {
    ticker: requireText(state.ticker, t("analysis.ticker", "Ticker")).toUpperCase(),
    exchange_or_market: requireText(
      state.exchange_or_market,
      t("tradeRecord.marketExchange", "Market / exchange")
    ),
    side: requireText(state.side, t("tradeRecord.side", "Side")).toLowerCase(),
    status: requireText(state.status, t("tradeRecord.status", "Status")),
    entry_timestamp: normalizeOptionalTimestamp(
      state.entry_timestamp,
      t("tradeRecord.entryTime", "Entry time"),
      record?.entry_timestamp ?? null
    ),
    entry_price: parseOptionalNumber(
      state.entry_price,
      t("tradeRecord.entryPrice", "Entry price")
    ),
    exit_timestamp: normalizeOptionalTimestamp(
      state.exit_timestamp,
      t("tradeRecord.exitTime", "Exit time"),
      record?.exit_timestamp ?? null
    ),
    exit_price: parseOptionalNumber(
      state.exit_price,
      t("tradeRecord.exitPrice", "Exit price")
    ),
    size: parseOptionalNumber(state.size, t("tradeRecord.size", "Size")),
    initial_thesis: requireText(
      state.initial_thesis,
      t("tradeRecord.initialThesis", "Initial thesis")
    ),
    planned_horizon: requireText(
      state.planned_horizon,
      t("tradeRecord.plannedHorizon", "Planned horizon")
    ),
    stop_loss: parseOptionalNumber(
      state.stop_loss,
      t("tradeRecord.stopLoss", "Stop loss")
    ),
    take_profit: parseOptionalNumber(
      state.take_profit,
      t("tradeRecord.takeProfit", "Take profit")
    ),
    notes: state.notes.trim(),
    analysis_references: normalizeAnalysisReferences(state.analysis_references),
  };
}

function requireText(value: string, fieldName: string): string {
  const normalized = value.trim();
  if (!normalized) {
    throw new Error(`${fieldName} is required.`);
  }
  return normalized;
}

function normalizeOptionalTimestamp(
  value: string,
  fieldName: string,
  originalValue: string | null
): string | null {
  const normalized = value.trim();
  if (!normalized) {
    return null;
  }

  if (originalValue && normalized === toDateTimeLocalValue(originalValue)) {
    return originalValue;
  }

  return toOffsetDateTimeString(parseDateTimeLocalValue(normalized, fieldName));
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

    if (!analysisDate || !reportPath || !fullStateLogPath) {
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
    report_path: `reports/${report.id}/complete_report.md`,
    full_state_log_path: `eval_results/${report.ticker}/TradingAgentsStrategy_logs/full_states_log_${analysisDate}.json`,
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
  const match = value.match(
    /^(\d{4})-(\d{2})-(\d{2})T(\d{2}):(\d{2})$/
  );
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
