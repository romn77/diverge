"use client";

import { useEffect, useMemo, useState } from "react";
import { AccessibleDialog } from "@/components/AccessibleDialog";
import { usePreferences } from "@/components/PreferencesProvider";
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
    "This provider is unavailable because its API key is not configured."
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
      setFormState(buildInitialFormState(configOptions, defaultOutputLanguage));
      setError(null);
    }
  }, [configOptions, formState, isOpen]);

  const providerOptions = configOptions?.providers ?? [];
  const selectedProviderOption =
    providerOptions.find((provider) => provider.value === formState?.llm_provider) ??
    null;
  const selectedProvider = formState?.llm_provider ?? providerOptions[0]?.value ?? "";
  const selectedModels = useMemo(() => {
    if (!configOptions || !selectedProvider) {
      return { quick: [], deep: [] };
    }

    return configOptions.models[selectedProvider] ?? { quick: [], deep: [] };
  }, [configOptions, selectedProvider]);

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
    const providerModels = configOptions.models[provider];
    setFormState({
      ...formState,
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
    <AccessibleDialog
      isOpen={isOpen}
      onClose={onClose}
      ariaLabel={t("analysis.dialog", "New analysis")}
      panelClassName="modal-panel scrollbar-hidden fade-in max-h-[92vh] w-full max-w-3xl overflow-y-auto rounded-[30px] border border-[var(--border)] bg-[var(--surface)] p-6 shadow-[0_28px_80px_rgba(18,28,41,0.24)] md:p-8"
      panelProps={{
        onMouseDown: (event) => event.stopPropagation(),
      }}
    >
        <div className="flex flex-wrap items-start justify-between gap-4">
          <div>
            <p className="text-[11px] font-semibold uppercase tracking-[0.34em] text-[var(--primary)]">
              {t("analysis.kicker", "Launch Analysis")}
            </p>
            <h2 className="font-heading mt-3 text-3xl font-bold tracking-tight text-slate-900">
              {t("analysis.title", "New Analysis")}
            </h2>
            <p className="mt-2 max-w-2xl text-sm leading-6 text-slate-600">
              {t(
                "analysis.description",
                "Pick the ticker, debate depth, provider stack, and language we should use for this research run."
              )}
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
                <input
                  type="text"
                  value={formState.ticker}
                  onChange={(event) =>
                    setFormState({
                      ...formState,
                      ticker: event.target.value.toUpperCase(),
                    })
                  }
                  className="focus-ring mt-3 w-full rounded-2xl border border-[var(--border)] bg-[var(--surface-strong)] px-4 py-3 text-sm font-semibold text-slate-900"
                  placeholder="SPY"
                />
              </label>

              <label className="field-shell block rounded-3xl border border-[var(--border)] bg-white/90 p-4">
                <span className="field-label text-xs font-semibold uppercase tracking-[0.24em] text-slate-500">
                  {t("analysis.analysisDate", "Analysis Date")}
                </span>
                <input
                  type="date"
                  value={formState.analysis_date}
                  onChange={(event) =>
                    setFormState({
                      ...formState,
                      analysis_date: event.target.value,
                    })
                  }
                  className="focus-ring mt-3 w-full rounded-2xl border border-[var(--border)] bg-[var(--surface-strong)] px-4 py-3 text-sm font-semibold text-slate-900"
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
                    <button
                      key={analyst.value}
                      type="button"
                      className={`interactive-button focus-ring rounded-full border px-4 py-2 text-xs font-semibold uppercase tracking-[0.18em] ${
                        active
                          ? "border-[var(--primary)] bg-[var(--primary-soft)] text-[var(--primary-strong)]"
                          : "border-[var(--border)] bg-[var(--surface-strong)] text-slate-600"
                      }`}
                      onClick={() => toggleAnalyst(analyst.value)}
                    >
                      {t(
                        `analysis.analyst.${optionKey(analyst.value)}`,
                        analyst.label
                      )}
                    </button>
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
                    <button
                      key={option.value}
                      type="button"
                      className={`interactive-button focus-ring rounded-[24px] border p-4 text-left ${
                        active
                          ? "border-[var(--accent)] bg-[var(--accent-soft)] text-slate-900"
                          : "border-[var(--border)] bg-[var(--surface-strong)] text-slate-600"
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
                    </button>
                  );
                })}
              </div>
            </section>

            <section className="grid gap-4 rounded-3xl border border-[var(--border)] bg-white/90 p-4 md:grid-cols-2">
              <label className="block">
                <span className="text-xs font-semibold uppercase tracking-[0.24em] text-slate-500">
                  {t("analysis.provider", "LLM Provider")}
                </span>
                <select
                  value={formState.llm_provider}
                  onChange={(event) => onProviderChange(event.target.value)}
                  className="focus-ring mt-3 w-full rounded-2xl border border-[var(--border)] bg-[var(--surface-strong)] px-4 py-3 text-sm font-semibold text-slate-900"
                >
                  {configOptions.providers.map((provider) => {
                    const providerLabel = t(
                      `analysis.provider.${optionKey(provider.value)}`,
                      provider.label
                    );
                    return (
                      <option
                        key={provider.value}
                        value={provider.value}
                        disabled={!provider.enabled}
                      >
                        {provider.enabled
                          ? providerLabel
                          : t(
                              "analysis.disabledProvider",
                              ({ label }) => `${label} (API key not configured)`,
                              { label: providerLabel }
                            )}
                      </option>
                    );
                  })}
                </select>
                <p className="mt-2 text-xs leading-5 text-slate-500">
                  {selectedProviderOption?.enabled
                    ? t(
                        "analysis.providerHint",
                        "Providers without a configured API key are unavailable in web tasks."
                      )
                    : providerUnavailableLabel}
                </p>
              </label>

              <label className="block">
                <span className="text-xs font-semibold uppercase tracking-[0.24em] text-slate-500">
                  {t("analysis.outputLanguage", "Output Language")}
                </span>
                <select
                  value={formState.output_language}
                  onChange={(event) =>
                    setFormState({
                      ...formState,
                      output_language: event.target.value,
                    })
                  }
                  className="focus-ring mt-3 w-full rounded-2xl border border-[var(--border)] bg-[var(--surface-strong)] px-4 py-3 text-sm font-semibold text-slate-900"
                >
                  {configOptions.output_languages.map((language) => (
                    <option key={language.value} value={language.value}>
                      {t(
                        `analysis.outputLanguage.${optionKey(language.value)}`,
                        language.label
                      )}
                    </option>
                  ))}
                </select>
              </label>

              <label className="block">
                <span className="text-xs font-semibold uppercase tracking-[0.24em] text-slate-500">
                  {t("analysis.quickModel", "Quick Model")}
                </span>
                <select
                  value={formState.quick_think_llm}
                  onChange={(event) =>
                    setFormState({
                      ...formState,
                      quick_think_llm: event.target.value,
                    })
                  }
                  className="focus-ring mt-3 w-full rounded-2xl border border-[var(--border)] bg-[var(--surface-strong)] px-4 py-3 text-sm font-semibold text-slate-900"
                >
                  {selectedModels.quick.map((option) => (
                    <option key={option.value} value={option.value}>
                      {option.label}
                    </option>
                  ))}
                </select>
              </label>

              <label className="block">
                <span className="text-xs font-semibold uppercase tracking-[0.24em] text-slate-500">
                  {t("analysis.deepModel", "Deep Model")}
                </span>
                <select
                  value={formState.deep_think_llm}
                  onChange={(event) =>
                    setFormState({
                      ...formState,
                      deep_think_llm: event.target.value,
                    })
                  }
                  className="focus-ring mt-3 w-full rounded-2xl border border-[var(--border)] bg-[var(--surface-strong)] px-4 py-3 text-sm font-semibold text-slate-900"
                >
                  {selectedModels.deep.map((option) => (
                    <option key={option.value} value={option.value}>
                      {option.label}
                    </option>
                  ))}
                </select>
              </label>
            </section>

            {formState.llm_provider === "openai" ? (
              <label className="block rounded-3xl border border-[var(--border)] bg-white/90 p-4">
                <span className="text-xs font-semibold uppercase tracking-[0.24em] text-slate-500">
                  {t("analysis.openaiReasoning", "OpenAI Reasoning Effort")}
                </span>
                <select
                  value={formState.openai_reasoning_effort ?? ""}
                  onChange={(event) =>
                    setFormState({
                      ...formState,
                      openai_reasoning_effort: event.target.value,
                    })
                  }
                  className="focus-ring mt-3 w-full rounded-2xl border border-[var(--border)] bg-[var(--surface-strong)] px-4 py-3 text-sm font-semibold text-slate-900"
                >
                  {configOptions.provider_settings.openai?.openai_reasoning_effort?.map(
                    (option) => (
                      <option key={option.value} value={option.value}>
                        {t(
                          `analysis.reasoning.${optionKey(option.value)}`,
                          option.label
                        )}
                      </option>
                    )
                  )}
                </select>
              </label>
            ) : null}

            {formState.llm_provider === "google" ? (
              <label className="block rounded-3xl border border-[var(--border)] bg-white/90 p-4">
                <span className="text-xs font-semibold uppercase tracking-[0.24em] text-slate-500">
                  {t("analysis.googleThinking", "Google Thinking Level")}
                </span>
                <select
                  value={formState.google_thinking_level ?? ""}
                  onChange={(event) =>
                    setFormState({
                      ...formState,
                      google_thinking_level: event.target.value,
                    })
                  }
                  className="focus-ring mt-3 w-full rounded-2xl border border-[var(--border)] bg-[var(--surface-strong)] px-4 py-3 text-sm font-semibold text-slate-900"
                >
                  {configOptions.provider_settings.google?.google_thinking_level?.map(
                    (option) => (
                      <option key={option.value} value={option.value}>
                        {t(
                          `analysis.googleThinking.${optionKey(option.value)}`,
                          option.label
                        )}
                      </option>
                    )
                  )}
                </select>
              </label>
            ) : null}

            {error ? (
              <div className="rounded-2xl border border-[rgba(163,53,53,0.2)] bg-[rgba(163,53,53,0.08)] px-4 py-3 text-sm text-[var(--danger)]">
                {error}
              </div>
            ) : null}

            <div className="flex flex-wrap items-center justify-end gap-3">
              <button
                type="button"
                className="interactive-button focus-ring rounded-full border border-[var(--border)] bg-white px-5 py-3 text-xs font-semibold uppercase tracking-[0.2em] text-slate-600"
                onClick={onClose}
              >
                {t("common.cancel", "Cancel")}
              </button>
              <button
                type="button"
                className="interactive-button focus-ring rounded-full border border-[var(--primary)] bg-[var(--primary)] px-5 py-3 text-xs font-semibold uppercase tracking-[0.2em] text-white"
                disabled={loading || !selectedProviderOption?.enabled}
                onClick={() => void submitTask()}
              >
                {loading
                  ? t("analysis.starting", "Launching...")
                  : t("analysis.start", "Start Analysis")}
              </button>
            </div>
          </div>
        )}
    </AccessibleDialog>
  );
}

function buildInitialFormState(
  configOptions: ConfigOptions,
  defaultOutputLanguage: string | null
): FormState {
  const provider =
    configOptions.providers.find((option) => option.enabled)?.value ??
    configOptions.providers[0]?.value ??
    "openai";
  const providerModels = configOptions.models[provider];
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
    llm_provider: provider,
    quick_think_llm: providerModels?.quick[0]?.value ?? "",
    deep_think_llm: providerModels?.deep[0]?.value ?? "",
    output_language: firstLanguage,
    google_thinking_level:
      provider === "google"
        ? configOptions.provider_settings.google?.google_thinking_level?.[0]
            ?.value ?? "high"
        : null,
    openai_reasoning_effort:
      provider === "openai"
        ? configOptions.provider_settings.openai?.openai_reasoning_effort?.[0]
            ?.value ?? "medium"
        : null,
  };
}
