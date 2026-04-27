"use client";

import { useEffect, useMemo, useState, type ReactNode } from "react";
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
  createTradeReview,
  getConfigOptions,
  saveTradeReview,
  type ConfigOptions,
  type SelectOption,
  type TradeRecord,
  type TradeReview,
  type TradeReviewCreateRequest,
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

type ReviewGenerationState = Pick<
  TradeReviewCreateRequest,
  | "llm_provider"
  | "model"
  | "output_language"
  | "google_thinking_level"
  | "openai_reasoning_effort"
>;

export function TradeReviewForm({
  isOpen,
  reviewType,
  tradeRecord,
  existingReview = null,
  onClose,
  onSaved,
}: TradeReviewFormProps) {
  const { language, t } = usePreferences();
  const [formState, setFormState] = useState<TradeReviewFormState>(() =>
    buildInitialState(existingReview, tradeRecord)
  );
  const [configOptions, setConfigOptions] = useState<ConfigOptions | null>(null);
  const [generationState, setGenerationState] =
    useState<ReviewGenerationState | null>(null);
  const [saving, setSaving] = useState(false);
  const [generating, setGenerating] = useState(false);
  const [loadingOptions, setLoadingOptions] = useState(false);
  const [generatedReview, setGeneratedReview] = useState<TradeReview | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!isOpen) {
      return;
    }

    setFormState(buildInitialState(existingReview, tradeRecord));
    setSaving(false);
    setGenerating(false);
    setGeneratedReview(null);
    setError(null);
  }, [existingReview, isOpen, tradeRecord]);

  useEffect(() => {
    if (!isOpen) {
      return;
    }

    let isActive = true;

    const loadOptions = async () => {
      if (configOptions) {
        return;
      }

      setLoadingOptions(true);
      setError(null);

      try {
        const nextOptions = await getConfigOptions();
        if (!isActive) {
          return;
        }
        setConfigOptions(nextOptions);
        setGenerationState(buildInitialGenerationState(nextOptions, language));
      } catch (optionsError) {
        if (isActive) {
          setError(
            optionsError instanceof Error
              ? optionsError.message
              : t("tradeReview.error.loadOptions", "Unable to load AI review options")
          );
        }
      } finally {
        if (isActive) {
          setLoadingOptions(false);
        }
      }
    };

    void loadOptions();

    return () => {
      isActive = false;
    };
  }, [configOptions, isOpen, language, t]);

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
  const enabledProviderOptions = configOptions?.providers.filter(
    (provider) => provider.enabled
  ) ?? [];
  const reviewModelOptions =
    configOptions && generationState
      ? getReviewModelOptions(configOptions, generationState.llm_provider)
      : [];

  const onProviderChange = (provider: string) => {
    if (!configOptions) {
      return;
    }
    const providerOption = configOptions.providers.find(
      (option) => option.value === provider
    );
    if (!providerOption?.enabled) {
      return;
    }
    const nextSelection = buildGenerationProviderSelection(configOptions, provider);
    setGenerationState({
      ...nextSelection,
      output_language: generationState?.output_language ?? nextSelection.output_language,
    });
  };

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
          t("tradeReview.analysisDate", "Analysis date")
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

  const generateReview = async () => {
    if (!generationState?.llm_provider || !generationState.model) {
      setError(
        t(
          "tradeReview.providerUnavailable",
          "No configured LLM provider is available for AI review generation."
        )
      );
      return;
    }

    setGenerating(true);
    setGeneratedReview(null);
    setError(null);

    try {
      const review = await createTradeReview(tradeRecord.trade_id, {
        ...generationState,
        review_type: reviewType,
        analysis_date: requireText(
          formState.analysis_date,
          t("tradeReview.analysisDate", "Analysis date")
        ),
        analysis_references: referenceSummary.length > 0 ? referenceSummary : undefined,
      });
      setGeneratedReview(review);
      setFormState(buildInitialState(review, tradeRecord));
    } catch (generateError) {
      setError(
        generateError instanceof Error
          ? generateError.message
          : t("tradeReview.error.generate", "Unable to generate the AI review")
      );
    } finally {
      setGenerating(false);
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
            {reviewFocus} Use the saved trade thesis, notes, and linked snapshots to draft the structured review for trade
            <span className="mx-1 rounded bg-slate-100 px-2 py-1 font-mono text-[12px] text-slate-700">
              {tradeRecord.trade_id}
            </span>
            and keep the result attached to the same stable trade record.
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
              {generatedReview ? (
                <Button
                  type="button"
                  variant="secondary"
                  onClick={() => onSaved(generatedReview)}
                >
                  {t("tradeReview.applyGenerated", "Apply generated review")}
                </Button>
              ) : null}
            </div>

            {loadingOptions || !generationState || !configOptions ? (
              <div className="mt-4 rounded-3xl border border-dashed border-[var(--border)] bg-[var(--surface-strong)] px-5 py-6 text-sm text-slate-500">
                {t("tradeReview.loadingOptions", "Loading AI review options...")}
              </div>
            ) : (
              <div className="mt-5 grid gap-4 md:grid-cols-3">
                <ReviewSelectField
                  label={t("analysis.provider", "LLM Provider")}
                  value={generationState.llm_provider}
                  onChange={onProviderChange}
                >
                  {enabledProviderOptions.map((provider) => (
                    <SelectItem key={provider.value} value={provider.value}>
                      {provider.label}
                    </SelectItem>
                  ))}
                </ReviewSelectField>

                <ReviewSelectField
                  label={t("analysis.deepModel", "Deep Model")}
                  value={generationState.model}
                  onChange={(value) =>
                    setGenerationState({
                      ...generationState,
                      model: value,
                    })
                  }
                >
                  {reviewModelOptions.map((option) => (
                    <SelectItem key={option.value} value={option.value}>
                      {option.label}
                    </SelectItem>
                  ))}
                </ReviewSelectField>

                <ReviewSelectField
                  label={t("analysis.outputLanguage", "Output Language")}
                  value={generationState.output_language}
                  onChange={(value) =>
                    setGenerationState({
                      ...generationState,
                      output_language: value,
                    })
                  }
                >
                  {configOptions.output_languages.map((languageOption) => (
                    <SelectItem key={languageOption.value} value={languageOption.value}>
                      {languageOption.label}
                    </SelectItem>
                  ))}
                </ReviewSelectField>

                {generationState.llm_provider === "openai" ? (
                  <ReviewSelectField
                    label={t("analysis.openaiReasoning", "OpenAI Reasoning Effort")}
                    value={generationState.openai_reasoning_effort ?? ""}
                    onChange={(value) =>
                      setGenerationState({
                        ...generationState,
                        openai_reasoning_effort: value,
                      })
                    }
                  >
                    {configOptions.provider_settings.openai?.openai_reasoning_effort?.map(
                      (option) => (
                        <SelectItem key={option.value} value={option.value}>
                          {option.label}
                        </SelectItem>
                      )
                    )}
                  </ReviewSelectField>
                ) : null}

                {generationState.llm_provider === "google" ? (
                  <ReviewSelectField
                    label={t("analysis.googleThinking", "Google Thinking Level")}
                    value={generationState.google_thinking_level ?? ""}
                    onChange={(value) =>
                      setGenerationState({
                        ...generationState,
                        google_thinking_level: value,
                      })
                    }
                  >
                    {configOptions.provider_settings.google?.google_thinking_level?.map(
                      (option) => (
                        <SelectItem key={option.value} value={option.value}>
                          {option.label}
                        </SelectItem>
                      )
                    )}
                  </ReviewSelectField>
                ) : null}

                <div className="flex items-end">
                  <Button
                    type="button"
                    variant="secondary"
                    className="w-full"
                    onClick={() => void generateReview()}
                    disabled={
                      generating ||
                      loadingOptions ||
                      !generationState.llm_provider ||
                      !generationState.model
                    }
                  >
                    {generating
                      ? t("tradeReview.generating", "Generating AI review...")
                      : t("tradeReview.generateReview", "Generate and Save AI Review")}
                  </Button>
                </div>
              </div>
            )}
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
                    "The original thesis and notes are already part of the trade record, so this section is only for optional corrections or lessons."
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

function buildInitialGenerationState(
  configOptions: ConfigOptions,
  language: string
): ReviewGenerationState {
  const provider =
    configOptions.providers.find((option) => option.enabled)?.value ?? "";
  const preferredLanguage = language === "zh" ? "cn" : "en";
  const outputLanguage =
    configOptions.output_languages.find((option) => option.value === preferredLanguage)
      ?.value ??
    configOptions.output_languages[0]?.value ??
    "en";

  return {
    ...buildGenerationProviderSelection(configOptions, provider),
    output_language: outputLanguage,
  };
}

function buildGenerationProviderSelection(
  configOptions: ConfigOptions,
  provider: string
): ReviewGenerationState {
  return {
    llm_provider: provider,
    model: getReviewModelOptions(configOptions, provider)[0]?.value ?? "",
    output_language: configOptions.output_languages[0]?.value ?? "en",
    openai_reasoning_effort:
      provider === "openai"
        ? configOptions.provider_settings.openai?.openai_reasoning_effort?.[0]
            ?.value ?? "medium"
        : null,
    google_thinking_level:
      provider === "google"
        ? configOptions.provider_settings.google?.google_thinking_level?.[0]
            ?.value ?? "high"
        : null,
  };
}

function getReviewModelOptions(
  configOptions: ConfigOptions,
  provider: string
): SelectOption[] {
  const providerModels = configOptions.models[provider] ?? { quick: [], deep: [] };
  return providerModels.deep.length > 0 ? providerModels.deep : providerModels.quick;
}

function requireText(value: string, fieldName: string): string {
  const normalized = value.trim();
  if (!normalized) {
    throw new Error(`${fieldName} is required.`);
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
  const contextParts = [tradeRecord.initial_thesis, tradeRecord.notes]
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

function ReviewSelectField({
  children,
  label,
  onChange,
  value,
}: {
  children: ReactNode;
  label: string;
  onChange: (value: string) => void;
  value: string;
}) {
  return (
    <label className="block">
      <span className="text-xs font-semibold uppercase tracking-[0.2em] text-slate-500">
        {label}
      </span>
      <Select value={value} onValueChange={onChange}>
        <SelectTrigger className="mt-2 bg-white text-slate-800">
          <SelectValue placeholder={label} />
        </SelectTrigger>
        <SelectContent>{children}</SelectContent>
      </Select>
    </label>
  );
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
