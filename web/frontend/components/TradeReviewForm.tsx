"use client";

import { useEffect, useMemo, useState } from "react";
import {
  saveTradeReview,
  type TradeRecord,
  type TradeReview,
  type TradeReviewType,
} from "@/lib/api";

interface TradeReviewFormProps {
  isOpen: boolean;
  reviewType: TradeReviewType;
  tradeRecord: TradeRecord;
  existingReview?: TradeReview | null;
  onClose: () => void;
  onSaved: (review: TradeReview) => void;
}

interface TradeReviewFormState {
  analysis_date: string;
  thesis_assessment: string;
  timing_assessment: string;
  sizing_assessment: string;
  discipline_assessment: string;
  outcome_summary: string;
  improvement_actions: string;
  ticker_specific_lessons: string;
  cross_ticker_tags: string;
}

export function TradeReviewForm({
  isOpen,
  reviewType,
  tradeRecord,
  existingReview = null,
  onClose,
  onSaved,
}: TradeReviewFormProps) {
  const [formState, setFormState] = useState<TradeReviewFormState>(() =>
    buildInitialState(existingReview, tradeRecord)
  );
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!isOpen) {
      return;
    }

    setFormState(buildInitialState(existingReview, tradeRecord));
    setSaving(false);
    setError(null);
  }, [existingReview, isOpen, tradeRecord]);

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

  const referenceSummary = useMemo(
    () =>
      existingReview?.analysis_references?.length
        ? existingReview.analysis_references
        : tradeRecord.analysis_references,
    [existingReview, tradeRecord.analysis_references]
  );

  if (!isOpen) {
    return null;
  }

  const reviewTitle =
    reviewType === "entry_review" ? "Entry Review" : "Exit Review";
  const reviewFocus =
    reviewType === "entry_review"
      ? "Stay anchored on thesis quality, timing, sizing, and discipline at the point of entry."
      : "Judge the exit relative to the original thesis, stated horizon, and how risk was actually managed.";

  const submitReview = async () => {
    if (referenceSummary.length === 0) {
      setError(
        "Link at least one analysis snapshot on the trade record before saving a review."
      );
      return;
    }

    setSaving(true);
    setError(null);

    try {
      const review = await saveTradeReview(tradeRecord.trade_id, reviewType, {
        analysis_date: requireText(formState.analysis_date, "Analysis date"),
        analysis_references: referenceSummary,
        thesis_assessment: requireText(
          formState.thesis_assessment,
          "Thesis assessment"
        ),
        timing_assessment: requireText(
          formState.timing_assessment,
          "Timing assessment"
        ),
        sizing_assessment: requireText(
          formState.sizing_assessment,
          "Sizing assessment"
        ),
        discipline_assessment: requireText(
          formState.discipline_assessment,
          "Discipline assessment"
        ),
        outcome_summary: requireText(formState.outcome_summary, "Outcome summary"),
        improvement_actions: splitMultilineList(formState.improvement_actions),
        ticker_specific_lessons: splitMultilineList(
          formState.ticker_specific_lessons
        ),
        cross_ticker_tags: splitTagList(formState.cross_ticker_tags),
      });
      onSaved(review);
    } catch (submitError) {
      setError(
        submitError instanceof Error
          ? submitError.message
          : "Unable to save the review"
      );
    } finally {
      setSaving(false);
    }
  };

  return (
    <div
      className="modal-backdrop fixed inset-0 z-[80] flex items-center justify-center bg-[rgba(17,24,39,0.42)] px-4 py-6"
      onClick={onClose}
    >
      <div
        role="dialog"
        aria-modal="true"
        aria-label={reviewTitle}
        className="modal-panel fade-in max-h-[92vh] w-full max-w-4xl overflow-y-auto rounded-[30px] border border-[var(--border)] bg-[var(--surface)] p-6 shadow-[0_28px_80px_rgba(18,28,41,0.24)] md:p-8"
        onClick={(event) => event.stopPropagation()}
      >
        <div className="flex flex-wrap items-start justify-between gap-4">
          <div>
            <p className="text-[11px] font-semibold uppercase tracking-[0.34em] text-[var(--primary)]">
              Manual Review
            </p>
            <h2 className="font-heading mt-3 text-3xl font-bold tracking-tight text-slate-900">
              {reviewTitle}
            </h2>
            <p className="mt-2 max-w-3xl text-sm leading-6 text-slate-600">
              {reviewFocus} This editor stores a structured manual review for trade
              <span className="mx-1 rounded bg-slate-100 px-2 py-1 font-mono text-[12px] text-slate-700">
                {tradeRecord.trade_id}
              </span>
              and keeps it attached to the same stable trade record.
            </p>
          </div>
          <button
            type="button"
            className="interactive-button focus-ring rounded-full border border-[var(--border)] bg-white px-4 py-2 text-xs font-semibold uppercase tracking-[0.2em] text-slate-600"
            onClick={onClose}
          >
            Close
          </button>
        </div>

        <div className="mt-6 rounded-[26px] border border-[rgba(28,56,83,0.12)] bg-[var(--accent-soft)]/70 px-5 py-4 text-sm text-slate-700">
          Manual-only MVP: reviews stay process-focused and snapshot-linked. The UI
          does not imply automated trade execution or broker sync.
        </div>

        <div className="mt-8 grid gap-6">
          <section className="rounded-[28px] border border-[var(--border)] bg-white/85 p-5">
            <div className="flex flex-wrap items-center justify-between gap-3">
              <div>
                <p className="text-xs font-semibold uppercase tracking-[0.24em] text-slate-500">
                  Snapshot Context
                </p>
                <h3 className="mt-2 text-xl font-semibold text-slate-900">
                  Using {referenceSummary.length} linked snapshot
                  {referenceSummary.length === 1 ? "" : "s"}
                </h3>
              </div>
              <label className="block rounded-3xl border border-[var(--border)] bg-[var(--surface-strong)] px-4 py-3">
                <span className="text-xs font-semibold uppercase tracking-[0.2em] text-slate-500">
                  Analysis Date
                </span>
                <input
                  type="date"
                  value={formState.analysis_date}
                  onChange={(event) =>
                    setFormState((current) => ({
                      ...current,
                      analysis_date: event.target.value,
                    }))
                  }
                  className="focus-ring mt-2 w-full min-w-[180px] rounded-2xl border border-[var(--border)] bg-white px-4 py-3 text-sm text-slate-800"
                />
              </label>
            </div>

            {referenceSummary.length === 0 ? (
              <div className="mt-4 rounded-3xl border border-dashed border-amber-300 bg-amber-50 px-5 py-5 text-sm text-amber-800">
                No analysis references are currently attached to this trade. Edit the
                trade record first so the review can stay aligned with the MAY-8
                report and full-state-log contract.
              </div>
            ) : (
              <div className="mt-4 space-y-3">
                {referenceSummary.map((reference) => (
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

          <section className="grid gap-4 md:grid-cols-2">
            <ReviewField
              label="Thesis Assessment"
              value={formState.thesis_assessment}
              onChange={(value) =>
                setFormState((current) => ({
                  ...current,
                  thesis_assessment: value,
                }))
              }
              placeholder="Was the thesis explicit, evidence-based, and appropriate for this setup?"
            />
            <ReviewField
              label="Timing Assessment"
              value={formState.timing_assessment}
              onChange={(value) =>
                setFormState((current) => ({
                  ...current,
                  timing_assessment: value,
                }))
              }
              placeholder="Judge the entry or exit timing relative to the plan and information available then."
            />
            <ReviewField
              label="Sizing Assessment"
              value={formState.sizing_assessment}
              onChange={(value) =>
                setFormState((current) => ({
                  ...current,
                  sizing_assessment: value,
                }))
              }
              placeholder="Did size respect the stop distance, risk budget, and conviction?"
            />
            <ReviewField
              label="Discipline Assessment"
              value={formState.discipline_assessment}
              onChange={(value) =>
                setFormState((current) => ({
                  ...current,
                  discipline_assessment: value,
                }))
              }
              placeholder="Did execution stay aligned with the stated rules and risk plan?"
            />
          </section>

          <section className="grid gap-4">
            <ReviewField
              label="Outcome Summary"
              value={formState.outcome_summary}
              onChange={(value) =>
                setFormState((current) => ({
                  ...current,
                  outcome_summary: value,
                }))
              }
              placeholder="Summarize what happened without reducing the verdict to PnL alone."
              rows={4}
            />

            <div className="grid gap-4 md:grid-cols-3">
              <ListField
                label="Improvement Actions"
                helper="One concrete action per line."
                value={formState.improvement_actions}
                onChange={(value) =>
                  setFormState((current) => ({
                    ...current,
                    improvement_actions: value,
                  }))
                }
                placeholder={"Write the invalidation clause before entry.\nConfirm catalyst quality before adding."}
              />
              <ListField
                label="Ticker-Specific Lessons"
                helper="Lessons that apply directly to this ticker or setup."
                value={formState.ticker_specific_lessons}
                onChange={(value) =>
                  setFormState((current) => ({
                    ...current,
                    ticker_specific_lessons: value,
                  }))
                }
                placeholder={"MSFT setups improve when cloud commentary confirms demand durability."}
              />
              <ListField
                label="Cross-Ticker Tags"
                helper="Optional. Use one per line or separate with commas."
                value={formState.cross_ticker_tags}
                onChange={(value) =>
                  setFormState((current) => ({
                    ...current,
                    cross_ticker_tags: value,
                  }))
                }
                placeholder={"planned_stop\nquality_growth"}
              />
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
              Cancel
            </button>
            <button
              type="button"
              className={`interactive-button focus-ring rounded-full border px-5 py-3 text-xs font-semibold uppercase tracking-[0.2em] ${
                referenceSummary.length === 0
                  ? "cursor-not-allowed border-slate-200 bg-slate-200 text-slate-500"
                  : "border-[var(--primary)] bg-[var(--primary)] text-white"
              }`}
              onClick={() => void submitReview()}
              disabled={saving || referenceSummary.length === 0}
            >
              {saving ? "Saving..." : `Save ${reviewTitle}`}
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}

function buildInitialState(
  review: TradeReview | null,
  tradeRecord: TradeRecord
): TradeReviewFormState {
  const defaultAnalysisDate =
    review?.analysis_date ||
    tradeRecord.analysis_references[0]?.analysis_date ||
    tradeRecord.entry_timestamp?.slice(0, 10) ||
    "";

  return {
    analysis_date: defaultAnalysisDate,
    thesis_assessment: review?.thesis_assessment ?? "",
    timing_assessment: review?.timing_assessment ?? "",
    sizing_assessment: review?.sizing_assessment ?? "",
    discipline_assessment: review?.discipline_assessment ?? "",
    outcome_summary: review?.outcome_summary ?? "",
    improvement_actions: joinList(review?.improvement_actions ?? []),
    ticker_specific_lessons: joinList(review?.ticker_specific_lessons ?? []),
    cross_ticker_tags: joinList(review?.cross_ticker_tags ?? []),
  };
}

function requireText(value: string, fieldName: string): string {
  const normalized = value.trim();
  if (!normalized) {
    throw new Error(`${fieldName} is required.`);
  }
  return normalized;
}

function splitMultilineList(value: string): string[] {
  const items = value
    .split(/\r?\n/)
    .map((item) => item.trim())
    .filter(Boolean);

  if (items.length === 0) {
    throw new Error("Add at least one list item before saving the review.");
  }

  return items;
}

function splitTagList(value: string): string[] {
  return value
    .split(/[\r\n,]+/)
    .map((item) => item.trim())
    .filter(Boolean);
}

function joinList(items: string[]): string {
  return items.join("\n");
}

function ReviewField({
  label,
  value,
  onChange,
  placeholder,
  rows = 5,
}: {
  label: string;
  value: string;
  onChange: (value: string) => void;
  placeholder: string;
  rows?: number;
}) {
  return (
    <label className="field-shell block rounded-3xl border border-[var(--border)] bg-white/90 p-4">
      <span className="text-xs font-semibold uppercase tracking-[0.24em] text-slate-500">
        {label}
      </span>
      <textarea
        value={value}
        onChange={(event) => onChange(event.target.value)}
        rows={rows}
        placeholder={placeholder}
        className="focus-ring mt-3 w-full rounded-2xl border border-[var(--border)] bg-[var(--surface-strong)] px-4 py-3 text-sm leading-6 text-slate-800"
      />
    </label>
  );
}

function ListField({
  label,
  helper,
  value,
  onChange,
  placeholder,
}: {
  label: string;
  helper: string;
  value: string;
  onChange: (value: string) => void;
  placeholder: string;
}) {
  return (
    <label className="field-shell block rounded-3xl border border-[var(--border)] bg-white/90 p-4">
      <span className="text-xs font-semibold uppercase tracking-[0.24em] text-slate-500">
        {label}
      </span>
      <span className="mt-2 block text-xs text-slate-500">{helper}</span>
      <textarea
        value={value}
        onChange={(event) => onChange(event.target.value)}
        rows={6}
        placeholder={placeholder}
        className="focus-ring mt-3 w-full rounded-2xl border border-[var(--border)] bg-[var(--surface-strong)] px-4 py-3 text-sm leading-6 text-slate-800"
      />
    </label>
  );
}
