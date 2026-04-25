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
  const reviewFocus =
    reviewType === "entry_review"
      ? t(
          "tradeReview.entryFocus",
          "Stay anchored on thesis quality, timing, sizing, and discipline at the point of entry."
        )
      : t(
          "tradeReview.exitFocus",
          "Judge the exit relative to the original thesis, stated horizon, and how risk was actually managed."
        );

  const submitReview = async () => {
    if (referenceSummary.length === 0) {
      setError(
        t(
          "tradeReview.linkSnapshotFirst",
          "Link at least one analysis snapshot on the trade record before saving a review."
        )
      );
      return;
    }

    setSaving(true);
    setError(null);

    try {
      const review = await saveTradeReview(tradeRecord.trade_id, reviewType, {
        analysis_date: requireText(
          formState.analysis_date,
          t("tradeReview.analysisDate", "Analysis date")
        ),
        analysis_references: referenceSummary,
        thesis_assessment: requireText(
          formState.thesis_assessment,
          t("journal.thesisAssessment", "Thesis assessment")
        ),
        timing_assessment: requireText(
          formState.timing_assessment,
          t("journal.timingAssessment", "Timing assessment")
        ),
        sizing_assessment: requireText(
          formState.sizing_assessment,
          t("journal.sizingAssessment", "Sizing assessment")
        ),
        discipline_assessment: requireText(
          formState.discipline_assessment,
          t("journal.disciplineAssessment", "Discipline assessment")
        ),
        outcome_summary: requireText(
          formState.outcome_summary,
          t("journal.outcomeSummary", "Outcome summary")
        ),
        improvement_actions: splitMultilineList(formState.improvement_actions, t),
        ticker_specific_lessons: splitMultilineList(
          formState.ticker_specific_lessons,
          t
        ),
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
    if (referenceSummary.length === 0) {
      setError(
        t(
          "tradeReview.linkSnapshotFirstGenerate",
          "Link at least one analysis snapshot on the trade record before generating a review."
        )
      );
      return;
    }
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
        analysis_references: referenceSummary,
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
            {reviewFocus} This editor stores a structured manual review for trade
            <span className="mx-1 rounded bg-slate-100 px-2 py-1 font-mono text-[12px] text-slate-700">
              {tradeRecord.trade_id}
            </span>
            and keeps it attached to the same stable trade record.
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
                    "Generate from the trade record, notes, and linked snapshots"
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
                      referenceSummary.length === 0 ||
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
                  "No analysis references are currently attached to this trade. Edit the trade record first so the review can stay aligned with the MAY-8 report and full-state-log contract."
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

          <section className="grid gap-4 md:grid-cols-2">
            <ReviewField
              label={t("journal.thesisAssessment", "Thesis Assessment")}
              value={formState.thesis_assessment}
              onChange={(value) =>
                setFormState((current) => ({
                  ...current,
                  thesis_assessment: value,
                }))
              }
              placeholder={t(
                "tradeReview.thesisPlaceholder",
                "Was the thesis explicit, evidence-based, and appropriate for this setup?"
              )}
            />
            <ReviewField
              label={t("journal.timingAssessment", "Timing Assessment")}
              value={formState.timing_assessment}
              onChange={(value) =>
                setFormState((current) => ({
                  ...current,
                  timing_assessment: value,
                }))
              }
              placeholder={t(
                "tradeReview.timingPlaceholder",
                "Judge the entry or exit timing relative to the plan and information available then."
              )}
            />
            <ReviewField
              label={t("journal.sizingAssessment", "Sizing Assessment")}
              value={formState.sizing_assessment}
              onChange={(value) =>
                setFormState((current) => ({
                  ...current,
                  sizing_assessment: value,
                }))
              }
              placeholder={t(
                "tradeReview.sizingPlaceholder",
                "Did size respect the stop distance, risk budget, and conviction?"
              )}
            />
            <ReviewField
              label={t("journal.disciplineAssessment", "Discipline Assessment")}
              value={formState.discipline_assessment}
              onChange={(value) =>
                setFormState((current) => ({
                  ...current,
                  discipline_assessment: value,
                }))
              }
              placeholder={t(
                "tradeReview.disciplinePlaceholder",
                "Did execution stay aligned with the stated rules and risk plan?"
              )}
            />
          </section>

          <section className="grid gap-4">
            <ReviewField
              label={t("journal.outcomeSummary", "Outcome Summary")}
              value={formState.outcome_summary}
              onChange={(value) =>
                setFormState((current) => ({
                  ...current,
                  outcome_summary: value,
                }))
              }
              placeholder={t(
                "tradeReview.outcomePlaceholder",
                "Summarize what happened without reducing the verdict to PnL alone."
              )}
              rows={4}
            />

            <div className="grid gap-4 md:grid-cols-3">
              <ListField
                label={t("journal.improvementActions", "Improvement Actions")}
                helper={t("tradeReview.actionsHelper", "One concrete action per line.")}
                value={formState.improvement_actions}
                onChange={(value) =>
                  setFormState((current) => ({
                    ...current,
                    improvement_actions: value,
                  }))
                }
                placeholder={t(
                  "tradeReview.actionsPlaceholder",
                  "Write the invalidation clause before entry.\nConfirm catalyst quality before adding."
                )}
              />
              <ListField
                label={t(
                  "journal.tickerSpecificLessons",
                  "Ticker-Specific Lessons"
                )}
                helper={t(
                  "tradeReview.lessonsHelper",
                  "Lessons that apply directly to this ticker or setup."
                )}
                value={formState.ticker_specific_lessons}
                onChange={(value) =>
                  setFormState((current) => ({
                    ...current,
                    ticker_specific_lessons: value,
                  }))
                }
                placeholder={t(
                  "tradeReview.lessonsPlaceholder",
                  "MSFT setups improve when cloud commentary confirms demand durability."
                )}
              />
              <ListField
                label={t("journal.crossTickerTags", "Cross-Ticker Tags")}
                helper={t(
                  "tradeReview.tagsHelper",
                  "Optional. Use one per line or separate with commas."
                )}
                value={formState.cross_ticker_tags}
                onChange={(value) =>
                  setFormState((current) => ({
                    ...current,
                    cross_ticker_tags: value,
                  }))
                }
                placeholder={t(
                  "tradeReview.tagsPlaceholder",
                  "planned_stop\nquality_growth"
                )}
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
              disabled={saving || referenceSummary.length === 0}
              className={referenceSummary.length === 0 ? "border-slate-200 bg-slate-200 text-slate-500 shadow-none hover:brightness-100" : undefined}
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

function splitMultilineList(
  value: string,
  t: ReturnType<typeof usePreferences>["t"]
): string[] {
  const items = value
    .split(/\r?\n/)
    .map((item) => item.trim())
    .filter(Boolean);

  if (items.length === 0) {
    throw new Error(
      t(
        "tradeReview.listItemRequired",
        "Add at least one list item before saving the review."
      )
    );
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
      <Textarea
        value={value}
        onChange={(event) => onChange(event.target.value)}
        rows={6}
        placeholder={placeholder}
        className="mt-3 border-[var(--border)] bg-[var(--surface-strong)] text-slate-800"
      />
    </label>
  );
}
