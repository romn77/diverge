"use client";

import { useEffect, useMemo, useRef, useState, type ReactNode } from "react";
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
import {
  createTask,
  getConfigOptions,
  type ConfigOptions,
  type TaskCreateRequest,
} from "@/lib/api";
import { optionKey } from "@/lib/uiPreferences";

interface NewAnalysisFormProps {
  isOpen: boolean;
  onClose: () => void;
  onTaskCreated: (taskId: string) => void;
  defaultOutputLanguage: string | null;
}

type FormState = TaskCreateRequest;

export function NewAnalysisForm({
  isOpen,
  onClose,
  onTaskCreated,
  defaultOutputLanguage,
}: NewAnalysisFormProps) {
  const { t } = usePreferences();
  const [configOptions, setConfigOptions] = useState<ConfigOptions | null>(null);
  const [formState, setFormState] = useState<FormState | null>(null);
  const [loading, setLoading] = useState(false);
  const [loadingOptions, setLoadingOptions] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const defaultOutputLanguageRef = useRef(defaultOutputLanguage);
  defaultOutputLanguageRef.current = defaultOutputLanguage;

  const loadOptionsErrorLabel = t(
    "analysis.error.loadOptions",
    "Unable to load analysis options"
  );
  const createTaskErrorLabel = t(
    "analysis.error.createTask",
    "Unable to create analysis task"
  );
  const providerUnavailableLabel = t(
    "analysis.providerUnavailable",
    "No configured LLM providers are available. Add an API key first."
  );
  const selectAnalystErrorLabel = t(
    "analysis.pickAnalyst",
    "Pick at least one analyst before launching the task."
  );

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
      } catch (nextError) {
        if (isActive) {
          setError(
            nextError instanceof Error ? nextError.message : loadOptionsErrorLabel
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
  }, [configOptions, isOpen, loadOptionsErrorLabel]);

  useEffect(() => {
    if (!isOpen) {
      setFormState(null);
      setError(null);
      setLoading(false);
      return;
    }

    if (configOptions && formState === null) {
      setFormState(buildInitialFormState(configOptions, defaultOutputLanguageRef.current));
      setError(null);
    }
  }, [configOptions, formState, isOpen]);

  const providerOptions = configOptions?.providers ?? [];
  const enabledProviderOptions = providerOptions.filter((provider) => provider.enabled);
  const selectedProviderOption =
    enabledProviderOptions.find((provider) => provider.value === formState?.llm_provider) ??
    null;
  const selectedProvider = selectedProviderOption?.value ?? "";
  const selectedModels = useMemo(() => {
    if (!configOptions || !selectedProvider) {
      return { quick: [], deep: [] };
    }

    return configOptions.models[selectedProvider] ?? { quick: [], deep: [] };
  }, [configOptions, selectedProvider]);

  useEffect(() => {
    if (!configOptions || !formState) {
      return;
    }
    if (configOptions.providers.some(
      (provider) => provider.enabled && provider.value === formState.llm_provider
    )) {
      return;
    }

    const fallbackProvider = configOptions.providers.find(
      (provider) => provider.enabled
    )?.value;
    if (!fallbackProvider) {
      return;
    }

    setFormState({
      ...formState,
      ...buildProviderSelection(configOptions, fallbackProvider),
    });
  }, [configOptions, formState]);

  if (!isOpen) {
    return null;
  }

  const onProviderChange = (provider: string) => {
    if (!configOptions || !formState) {
      return;
    }
    const providerOption = configOptions.providers.find(
      (option) => option.value === provider
    );
    if (!providerOption?.enabled) {
      return;
    }
    setFormState({
      ...formState,
      ...buildProviderSelection(configOptions, provider),
    });
  };

  const toggleAnalyst = (analyst: string) => {
    if (!formState) {
      return;
    }

    const exists = formState.analysts.includes(analyst);
    const nextAnalysts = exists
      ? formState.analysts.filter((item) => item !== analyst)
      : [...formState.analysts, analyst];

    setFormState({
      ...formState,
      analysts: nextAnalysts,
    });
  };

  const submitTask = async () => {
    if (!formState) {
      return;
    }
    if (!selectedProviderOption?.enabled) {
      setError(
        providerUnavailableLabel
      );
      return;
    }
    if (formState.analysts.length === 0) {
      setError(selectAnalystErrorLabel);
      return;
    }

    setLoading(true);
    setError(null);

    try {
      const response = await createTask(formState);
      onClose();
      onTaskCreated(response.task_id);
    } catch (submitError) {
      setError(
        submitError instanceof Error ? submitError.message : createTaskErrorLabel
      );
    } finally {
      setLoading(false);
    }
  };

  return (
    <Dialog open={isOpen} onOpenChange={(open) => !open && onClose()}>
      <DialogContent
        aria-label={t("analysis.dialog", "New analysis")}
        className="modal-panel scrollbar-hidden max-h-[92vh] max-w-3xl overflow-y-auto"
        onMouseDown={(event) => event.stopPropagation()}
      >
        <DialogHeader className="pr-12">
          <p className="text-[11px] font-semibold uppercase tracking-[0.34em] text-[var(--primary)]">
            {t("analysis.kicker", "Launch Analysis")}
          </p>
          <DialogTitle>{t("analysis.title", "New Analysis")}</DialogTitle>
          <DialogDescription className="max-w-2xl">
            {t(
              "analysis.description",
              "Select a ticker and parameters to start analysis."
            )}
          </DialogDescription>
        </DialogHeader>

        {loadingOptions || !formState || !configOptions ? (
          <div className="mt-8 rounded-3xl border border-dashed border-[var(--border)] bg-[var(--surface-strong)] px-5 py-8 text-sm text-slate-600">
            {t("analysis.loadingOptions", "Loading analysis options...")}
          </div>
        ) : (
          <div className="mt-8 grid gap-6">
            <section className="grid gap-4 md:grid-cols-2">
              <label className="field-shell block rounded-3xl border border-[var(--border)] bg-white/90 p-4">
                <span className="field-label text-xs font-semibold uppercase tracking-[0.24em] text-slate-500">
                  {t("analysis.ticker", "Ticker")}
                </span>
                <Input
                  type="text"
                  value={formState.ticker}
                  onChange={(event) =>
                    setFormState({
                      ...formState,
                      ticker: event.target.value.toUpperCase(),
                    })
                  }
                  className="mt-3 border-[var(--border)] bg-[var(--surface-strong)] font-semibold text-slate-900"
                  placeholder="SPY"
                />
              </label>

              <label className="field-shell block rounded-3xl border border-[var(--border)] bg-white/90 p-4">
                <span className="field-label text-xs font-semibold uppercase tracking-[0.24em] text-slate-500">
                  {t("analysis.analysisDate", "Analysis Date")}
                </span>
                <Input
                  type="date"
                  value={formState.analysis_date}
                  onChange={(event) =>
                    setFormState({
                      ...formState,
                      analysis_date: event.target.value,
                    })
                  }
                  className="mt-3 border-[var(--border)] bg-[var(--surface-strong)] font-semibold text-slate-900"
                />
              </label>
            </section>

            <section className="rounded-3xl border border-[var(--border)] bg-white/90 p-4">
              <p className="text-xs font-semibold uppercase tracking-[0.24em] text-slate-500">
                {t("analysis.analysts", "Analysts")}
              </p>
              <div className="mt-3 flex flex-wrap gap-3">
                {configOptions.analysts.map((analyst) => {
                  const active = formState.analysts.includes(analyst.value);
                  return (
                    <Button
                      key={analyst.value}
                      type="button"
                      variant={active ? "default" : "secondary"}
                      size="sm"
                      className="px-4"
                      onClick={() => toggleAnalyst(analyst.value)}
                    >
                      {t(
                        `analysis.analyst.${optionKey(analyst.value)}`,
                        analyst.label
                      )}
                    </Button>
                  );
                })}
              </div>
            </section>

            <section className="rounded-3xl border border-[var(--border)] bg-white/90 p-4">
              <p className="text-xs font-semibold uppercase tracking-[0.24em] text-slate-500">
                {t("analysis.researchDepth", "Research Depth")}
              </p>
              <div className="mt-3 grid gap-3 md:grid-cols-3">
                {configOptions.research_depth.map((option) => {
                  const active = formState.research_depth === option.value;
                  const localizedLabel = t(
                    `analysis.depth.${option.value}`,
                    option.label
                  );
                  const localizedDescription = t(
                    `analysis.depthDescription.${option.value}`,
                    option.description
                  );
                  return (
                    <Button
                      key={option.value}
                      type="button"
                      variant={active ? "default" : "secondary"}
                      className={`h-auto w-full justify-start rounded-[24px] p-4 text-left ${
                        active
                          ? "bg-[var(--accent)] text-white hover:bg-[var(--accent)] hover:brightness-105"
                          : "text-slate-600"
                      }`}
                      onClick={() =>
                        setFormState({
                          ...formState,
                          research_depth: Number(option.value),
                        })
                      }
                    >
                      <p className="text-sm font-semibold">{localizedLabel}</p>
                      {localizedDescription ? (
                        <p className="mt-2 text-xs leading-5">
                          {localizedDescription}
                        </p>
                      ) : null}
                    </Button>
                  );
                })}
              </div>
            </section>

            <section className="grid gap-4 rounded-3xl border border-[var(--border)] bg-white/90 p-4 md:grid-cols-2">
              <AnalysisSelectField
                label={t("analysis.marketDataSource", "Market Data Source")}
                value={formState.market_data_source}
                onChange={(value) =>
                  setFormState({
                    ...formState,
                    market_data_source: value,
                  })
                }
                hint={t(
                  "analysis.marketDataSourceHint",
                  "Use Massive for US price history when Yahoo Finance is rate limited."
                )}
              >
                {configOptions.market_data_sources.map((sourceOption) => (
                  <SelectItem key={sourceOption.value} value={sourceOption.value}>
                    {t(
                      `analysis.marketDataSource.${optionKey(sourceOption.value)}`,
                      sourceOption.label
                    )}
                  </SelectItem>
                ))}
              </AnalysisSelectField>

              <AnalysisSelectField
                label={t("analysis.provider", "LLM Provider")}
                value={formState.llm_provider}
                onChange={onProviderChange}
                hint={
                  enabledProviderOptions.length > 0
                    ? t(
                        "analysis.providerHint",
                        "Only providers with a configured API key are shown."
                      )
                    : providerUnavailableLabel
                }
              >
                {enabledProviderOptions.map((provider) => {
                  const providerLabel = t(
                    `analysis.provider.${optionKey(provider.value)}`,
                    provider.label
                  );
                  return (
                    <SelectItem
                      key={provider.value}
                      value={provider.value}
                    >
                      {providerLabel}
                    </SelectItem>
                  );
                })}
              </AnalysisSelectField>

              <AnalysisSelectField
                label={t("analysis.outputLanguage", "Output Language")}
                value={formState.output_language}
                onChange={(value) =>
                  setFormState({
                    ...formState,
                    output_language: value,
                  })
                }
              >
                {configOptions.output_languages.map((language) => (
                  <SelectItem key={language.value} value={language.value}>
                    {t(
                      `analysis.outputLanguage.${optionKey(language.value)}`,
                      language.label
                    )}
                  </SelectItem>
                ))}
              </AnalysisSelectField>

              <AnalysisSelectField
                label={t("analysis.quickModel", "Quick Model")}
                value={formState.quick_think_llm}
                onChange={(value) =>
                  setFormState({
                    ...formState,
                    quick_think_llm: value,
                  })
                }
              >
                {selectedModels.quick.map((option) => (
                  <SelectItem key={option.value} value={option.value}>
                    {option.label}
                  </SelectItem>
                ))}
              </AnalysisSelectField>

              <AnalysisSelectField
                label={t("analysis.deepModel", "Deep Model")}
                value={formState.deep_think_llm}
                onChange={(value) =>
                  setFormState({
                    ...formState,
                    deep_think_llm: value,
                  })
                }
              >
                {selectedModels.deep.map((option) => (
                  <SelectItem key={option.value} value={option.value}>
                    {option.label}
                  </SelectItem>
                ))}
              </AnalysisSelectField>
            </section>

            {formState.llm_provider === "openai" ? (
              <AnalysisSelectField
                label={t("analysis.openaiReasoning", "OpenAI Reasoning Effort")}
                value={formState.openai_reasoning_effort ?? ""}
                onChange={(value) =>
                  setFormState({
                    ...formState,
                    openai_reasoning_effort: value,
                  })
                }
                className="rounded-3xl border border-[var(--border)] bg-white/90 p-4"
              >
                  {configOptions.provider_settings.openai?.openai_reasoning_effort?.map(
                    (option) => (
                      <SelectItem key={option.value} value={option.value}>
                        {t(
                          `analysis.reasoning.${optionKey(option.value)}`,
                          option.label
                        )}
                      </SelectItem>
                    )
                  )}
              </AnalysisSelectField>
            ) : null}

            {formState.llm_provider === "google" ? (
              <AnalysisSelectField
                label={t("analysis.googleThinking", "Google Thinking Level")}
                value={formState.google_thinking_level ?? ""}
                onChange={(value) =>
                  setFormState({
                    ...formState,
                    google_thinking_level: value,
                  })
                }
                className="rounded-3xl border border-[var(--border)] bg-white/90 p-4"
              >
                  {configOptions.provider_settings.google?.google_thinking_level?.map(
                    (option) => (
                      <SelectItem key={option.value} value={option.value}>
                        {t(
                          `analysis.googleThinking.${optionKey(option.value)}`,
                          option.label
                        )}
                      </SelectItem>
                    )
                  )}
              </AnalysisSelectField>
            ) : null}

            {error ? (
              <div className="rounded-2xl border border-[rgba(163,53,53,0.2)] bg-[rgba(163,53,53,0.08)] px-4 py-3 text-sm text-[var(--danger)]">
                {error}
              </div>
            ) : null}

            <div className="flex flex-wrap items-center justify-end gap-3">
              <Button type="button" variant="secondary" onClick={onClose}>
                {t("common.cancel", "Cancel")}
              </Button>
              <Button
                type="button"
                disabled={loading || !selectedProviderOption?.enabled}
                onClick={() => void submitTask()}
              >
                {loading
                  ? t("analysis.starting", "Launching...")
                  : t("analysis.start", "Start Analysis")}
              </Button>
            </div>
          </div>
        )}
      </DialogContent>
    </Dialog>
  );
}

function AnalysisSelectField({
  className,
  label,
  value,
  onChange,
  hint,
  children,
}: {
  className?: string;
  label: string;
  value: string;
  onChange: (value: string) => void;
  hint?: string;
  children: ReactNode;
}) {
  return (
    <label className={className ?? "block"}>
      <span className="text-xs font-semibold uppercase tracking-[0.24em] text-slate-500">
        {label}
      </span>
      <Select value={value} onValueChange={onChange}>
        <SelectTrigger className="mt-3 border-[var(--border)] bg-[var(--surface-strong)] font-semibold text-slate-900">
          <SelectValue placeholder={label} />
        </SelectTrigger>
        <SelectContent>{children}</SelectContent>
      </Select>
      {hint ? <p className="mt-2 text-xs leading-5 text-slate-500">{hint}</p> : null}
    </label>
  );
}

function buildInitialFormState(
  configOptions: ConfigOptions,
  defaultOutputLanguage: string | null
): FormState {
  const provider =
    configOptions.providers.find((option) => option.enabled)?.value ??
    "";
  const firstDepth = configOptions.research_depth[0]?.value ?? 1;
  const firstLanguage =
    configOptions.output_languages.find(
      (option) => option.value === defaultOutputLanguage
    )?.value ??
    configOptions.output_languages[0]?.value ??
    "en";

  return {
    ticker: "SPY",
    analysis_date: new Date().toISOString().slice(0, 10),
    analysts: configOptions.analysts.map((option) => option.value),
    research_depth: Number(firstDepth),
    market_data_source:
      configOptions.defaults?.market_data_source ??
      configOptions.market_data_sources[0]?.value ??
      "yfinance",
    output_language: firstLanguage,
    ...buildProviderSelection(configOptions, provider),
  };
}

function buildProviderSelection(
  configOptions: ConfigOptions,
  provider: string
): Pick<
  FormState,
  | "llm_provider"
  | "quick_think_llm"
  | "deep_think_llm"
  | "openai_reasoning_effort"
  | "google_thinking_level"
> {
  const providerModels = configOptions.models[provider] ?? { quick: [], deep: [] };

  return {
    llm_provider: provider,
    quick_think_llm: providerModels.quick[0]?.value ?? "",
    deep_think_llm: providerModels.deep[0]?.value ?? "",
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
