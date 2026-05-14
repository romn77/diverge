"use client";

import { useEffect, useMemo, useState } from "react";
import { usePreferences } from "@/components/PreferencesProvider";
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
  saveTradeReview,
  type TradeRecord,
  type TradeReview,
  type TradeReviewGenerateRequest,
  type TradeReviewType,
} from "@/lib/api";

interface TradeReviewFormProps {
  isOpen: boolean;
  reviewType: TradeReviewType;
  tradeRecord: TradeRecord;
  existingReview?: TradeReview | null;
  onClose: () => void;
  onGenerateReview: (payload: TradeReviewGenerateRequest) => void;
  onSaved: (review: TradeReview) => void;
}

interface TradeReviewFormState {
  analysis_date: string;
  output_language: string;
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
  onGenerateReview,
  onSaved,
}: TradeReviewFormProps) {
  const { t } = usePreferences();
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
    reviewType === "entry_review"
      ? t("journal.entryReview", "Entry Review")
      : t("journal.exitReview", "Exit Review");
  const isEntryReview = reviewType === "entry_review";
  const actionLabel = isEntryReview
    ? t("journal.entry", "Entry")
    : t("journal.exit", "Exit");
  const actionPrice = isEntryReview ? tradeRecord.entry_price : tradeRecord.exit_price;
  const reviewFocus =
    isEntryReview
      ? t(
          "tradeReview.entryFocus",
          "Use AI to judge whether this entry price was justified by the evidence available at the time."
        )
      : t(
          "tradeReview.exitFocus",
          "Use AI to judge whether this exit price was a disciplined action relative to the plan and updated evidence."
        );

  const submitReview = async () => {
    setSaving(true);
    setError(null);

    try {
      const decisionContext = optionalText(
        formState.thesis_assessment,
        buildDefaultDecisionContext(tradeRecord, t)
      );
      const priceAssessment = optionalText(
        formState.timing_assessment,
        buildDefaultPriceAssessment(actionLabel, t)
      );
      const review = await saveTradeReview(tradeRecord.trade_id, reviewType, {
        analysis_date: requireText(
          formState.analysis_date,
          t("tradeReview.analysisDate", "Analysis date"),
          t
        ),
        analysis_references: referenceSummary.length > 0 ? referenceSummary : undefined,
        thesis_assessment: decisionContext,
        timing_assessment: priceAssessment,
        sizing_assessment: optionalText(
          formState.sizing_assessment,
          buildDefaultSizingAssessment(tradeRecord, t)
        ),
        discipline_assessment: optionalText(
          formState.discipline_assessment,
          buildDefaultDisciplineAssessment(actionLabel, t)
        ),
        outcome_summary: optionalText(
          formState.outcome_summary,
          priceAssessment
        ),
        improvement_actions: splitOptionalMultilineList(formState.improvement_actions),
        ticker_specific_lessons: splitOptionalMultilineList(formState.ticker_specific_lessons),
        cross_ticker_tags: splitTagList(formState.cross_ticker_tags),
      });
      onSaved(review);
    } catch (submitError) {
      setError(
        submitError instanceof Error
          ? submitError.message
          : t("tradeReview.error.save", "Unable to save the review")
      );
    } finally {
      setSaving(false);
    }
  };

  const generateReview = () => {
    setError(null);

    try {
      onGenerateReview({
        analysis_date: requireText(
          formState.analysis_date,
          t("tradeReview.analysisDate", "Analysis date"),
          t
        ),
        analysis_references: referenceSummary.length > 0 ? referenceSummary : undefined,
        output_language: formState.output_language,
      });
    } catch (generateError) {
      setError(
        generateError instanceof Error
          ? generateError.message
          : t("tradeReview.error.generate", "Unable to generate the AI review")
      );
    }
  };

  return (
    <Dialog open={isOpen} onOpenChange={(open) => !open && onClose()}>
      <DialogContent
        aria-label={reviewTitle}
        className="modal-panel max-w-4xl"
        onMouseDown={(event) => event.stopPropagation()}
      >
        <DialogHeader className="pr-12">
          <p className="text-[11px] font-semibold uppercase tracking-[0.34em] text-[var(--primary)]">
            {t("tradeReview.manualReview", "Manual Review")}
          </p>
          <DialogTitle>{reviewTitle}</DialogTitle>
          <DialogDescription className="max-w-3xl">
            {reviewFocus}{" "}
            {t(
              "tradeReview.dialogDescriptionPrefix",
              "Use the saved trade plan, reasons, and linked snapshots to draft the structured review for trade"
            )}
            <span className="mx-1 rounded bg-slate-100 px-2 py-1 font-mono text-[12px] text-slate-700">
              {tradeRecord.trade_id}
            </span>
            {t(
              "tradeReview.dialogDescriptionSuffix",
              "and keep the result attached to the same stable trade record."
            )}
          </DialogDescription>
        </DialogHeader>

        <div className="mt-8 grid gap-6">
          <section className="rounded-[28px] border border-[var(--border)] bg-white/85 p-5">
            <div className="flex flex-wrap items-start justify-between gap-4">
              <div>
                <p className="text-xs font-semibold uppercase tracking-[0.24em] text-slate-500">
                  {t("tradeReview.aiAssist", "AI Review")}
                </p>
                <h3 className="mt-2 text-xl font-semibold text-slate-900">
                  {t(
                    "tradeReview.generateFromJournal",
                    ({ action, price }) =>
                      `Let AI review this ${String(action ?? "action").toLowerCase()} at ${price}`,
                    {
                      action: actionLabel,
                      price: formatPrice(actionPrice),
                    }
                  )}
                </h3>
              </div>
            </div>

            <div className="mt-5 grid gap-3 rounded-3xl border border-[var(--border)] bg-[var(--surface-strong)] px-5 py-4 md:grid-cols-[minmax(0,1fr)_190px_auto] md:items-center">
              <p className="max-w-2xl text-sm leading-6 text-slate-600">
                {t(
                  "tradeReview.adminConfiguredModel",
                  "AI review generation uses the admin-configured trade journal review model. Choose the output language here for this journal review."
                )}
              </p>
              <label className="grid gap-1 text-xs font-semibold uppercase tracking-[0.2em] text-slate-500">
                {t("analysis.outputLanguage", "Output Language")}
                <Select
                  value={formState.output_language}
                  onValueChange={(value) =>
                    setFormState((current) => ({
                      ...current,
                      output_language: value,
                    }))
                  }
                >
                  <SelectTrigger className="h-11 border-[var(--border)] bg-white text-slate-800">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="cn">简体中文</SelectItem>
                    <SelectItem value="en">English</SelectItem>
                  </SelectContent>
                </Select>
              </label>
              <Button
                type="button"
                variant="secondary"
                onClick={generateReview}
              >
                {existingReview
                  ? t("tradeReview.regenerateReview", "Regenerate AI Review")
                  : t("tradeReview.generateReview", "Generate and Save AI Review")}
              </Button>
            </div>
          </section>

          <section className="rounded-[28px] border border-[var(--border)] bg-white/85 p-5">
            <div className="flex flex-wrap items-center justify-between gap-3">
              <div>
                <p className="text-xs font-semibold uppercase tracking-[0.24em] text-slate-500">
                  {t("tradeReview.snapshotContext", "Snapshot Context")}
                </p>
                <h3 className="mt-2 text-xl font-semibold text-slate-900">
                  {t(
                    "tradeReview.linkedSnapshots",
                    ({ count }) => `Using ${count} linked snapshot${count === 1 ? "" : "s"}`,
                    { count: referenceSummary.length }
                  )}
                </h3>
              </div>
              <label className="block rounded-3xl border border-[var(--border)] bg-[var(--surface-strong)] px-4 py-3">
                <span className="text-xs font-semibold uppercase tracking-[0.2em] text-slate-500">
                  {t("tradeReview.analysisDate", "Analysis Date")}
                </span>
                <Input
                  type="date"
                  value={formState.analysis_date}
                  onChange={(event) =>
                    setFormState((current) => ({
                      ...current,
                      analysis_date: event.target.value,
                    }))
                  }
                  className="mt-2 min-w-[180px] bg-white text-slate-800"
                />
              </label>
            </div>

            {referenceSummary.length === 0 ? (
              <div className="mt-4 rounded-3xl border border-dashed border-amber-300 bg-amber-50 px-5 py-5 text-sm text-amber-800">
                {t(
                  "tradeReview.noReferences",
                  "No analysis references are currently attached. AI can still review the saved trade record; linked reports will be used as supplementary evidence when available."
                )}
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

          <section className="rounded-[28px] border border-[var(--border)] bg-white/85 p-5">
            <div className="flex flex-wrap items-start justify-between gap-4">
              <div>
                <p className="text-xs font-semibold uppercase tracking-[0.24em] text-slate-500">
                  {t("tradeReview.manualAdjustments", "Manual Adjustments")}
                </p>
                <h3 className="mt-2 text-xl font-semibold text-slate-900">
                  {t(
                    "tradeReview.reviewThisAction",
                    ({ action, price }) => `${action} at ${price}`,
                    {
                      action: actionLabel,
                      price: formatPrice(actionPrice),
                    }
                  )}
                </h3>
                <p className="mt-2 max-w-2xl text-sm leading-6 text-slate-500">
                  {t(
                    "tradeReview.recordContextHint",
                    "The original trade plan and reasons are already part of the trade record, so this section is only for optional corrections or lessons."
                  )}
                </p>
              </div>
            </div>

            <div className="mt-5 grid gap-4">
              <ReviewField
                label={t(
                  "tradeReview.priceAssessment",
                  ({ action }) => `${action} Price Assessment`,
                  { action: actionLabel }
                )}
                helper={t(
                  "tradeReview.priceAssessmentHelper",
                  "Optional before saving. Leave this blank when you want the saved review to inherit the trade record and let AI or a later pass make the price verdict."
                )}
                value={formState.timing_assessment}
                onChange={(value) =>
                  setFormState((current) => ({
                    ...current,
                    timing_assessment: value,
                  }))
                }
                placeholder={t(
                  "tradeReview.timingPlaceholder",
                  ({ action }) =>
                    `What should AI decide about this ${String(action ?? "action").toLowerCase()} price? For example: chased, patient, too early, protected gains, or cut risk.`,
                  { action: actionLabel }
                )}
                rows={4}
              />
              <ListField
                label={t("journal.improvementActions", "Next-Time Guardrail")}
                helper={t(
                  "tradeReview.actionsHelper",
                  "Optional. One concrete rule per line if you already know the lesson."
                )}
                value={formState.improvement_actions}
                onChange={(value) =>
                  setFormState((current) => ({
                    ...current,
                    improvement_actions: value,
                  }))
                }
                placeholder={t(
                  "tradeReview.actionsPlaceholder",
                  "Wait for confirmation before entering.\nUse the planned stop before adding."
                )}
                rows={3}
              />
            </div>
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
            <Button
              type="button"
              onClick={() => void submitReview()}
              disabled={saving}
            >
              {saving
                ? t("tradeRecord.saving", "Saving...")
                : t(
                    "tradeReview.save",
                    ({ title }) => `Save ${title}`,
                    { title: reviewTitle }
                  )}
            </Button>
          </div>
        </div>
      </DialogContent>
    </Dialog>
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
    output_language: "cn",
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

function optionalText(value: string, fallback: string): string {
  const normalized = value.trim();
  return normalized || fallback;
}

function splitOptionalMultilineList(value: string): string[] {
  return value
    .split(/\r?\n/)
    .map((item) => item.trim())
    .filter(Boolean);
}

function buildDefaultSizingAssessment(
  tradeRecord: TradeRecord,
  t: ReturnType<typeof usePreferences>["t"]
): string {
  if (tradeRecord.size === null || tradeRecord.size === undefined) {
    return t(
      "tradeReview.defaultSizingAssessment",
      "Position size was not separately reviewed in this manual adjustment."
    );
  }

  return t(
    "tradeReview.defaultSizingAssessmentWithSize",
    ({ size }) =>
      `Position size was recorded as ${size}; sizing was not separately expanded in this manual adjustment.`,
    { size: tradeRecord.size }
  );
}

function buildDefaultDisciplineAssessment(
  actionLabel: string,
  t: ReturnType<typeof usePreferences>["t"]
): string {
  return t(
    "tradeReview.defaultDisciplineAssessment",
    ({ action }) =>
      `This manual adjustment focused on the ${String(action ?? "action").toLowerCase()} price decision; rule discipline was not separately expanded.`,
    { action: actionLabel }
  );
}

function buildDefaultDecisionContext(
  tradeRecord: TradeRecord,
  t: ReturnType<typeof usePreferences>["t"]
): string {
  const contextParts = [
    tradeRecord.entry_reason,
    tradeRecord.invalidation_condition,
    tradeRecord.exit_reason,
    tradeRecord.initial_thesis,
  ]
    .map((part) => part?.trim())
    .filter(Boolean);

  if (contextParts.length > 0) {
    return contextParts.join("\n\n");
  }

  return t(
    "tradeReview.defaultDecisionContext",
    "Review context was inherited from the saved trade record."
  );
}

function buildDefaultPriceAssessment(
  actionLabel: string,
  t: ReturnType<typeof usePreferences>["t"]
): string {
  return t(
    "tradeReview.defaultPriceAssessment",
    ({ action }) =>
      `This manual adjustment inherited the saved trade context; the ${String(action ?? "action").toLowerCase()} price verdict was left for AI review or a later structured pass.`,
    { action: actionLabel }
  );
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

function formatPrice(value: number | null | undefined): string {
  return value === null || value === undefined ? "N/A" : String(value);
}

function ReviewField({
  label,
  helper,
  value,
  onChange,
  placeholder,
  rows = 5,
}: {
  label: string;
  helper?: string;
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
      {helper ? <span className="mt-2 block text-xs text-slate-500">{helper}</span> : null}
      <Textarea
        value={value}
        onChange={(event) => onChange(event.target.value)}
        rows={rows}
        placeholder={placeholder}
        className="mt-3 border-[var(--border)] bg-[var(--surface-strong)] text-slate-800"
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
  rows = 5,
}: {
  label: string;
  helper: string;
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
      <span className="mt-2 block text-xs text-slate-500">{helper}</span>
      <Textarea
        value={value}
        onChange={(event) => onChange(event.target.value)}
        rows={rows}
        placeholder={placeholder}
        className="mt-3 border-[var(--border)] bg-[var(--surface-strong)] text-slate-800"
      />
    </label>
  );
}
