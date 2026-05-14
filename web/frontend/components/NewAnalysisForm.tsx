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
  type ModelProfileOption,
  type ReportVisibility,
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
  const profileOptions = configOptions?.model_profiles ?? [];
  const selectedProfileOption =
    profileOptions.find((profile) => profile.value === formState?.model_profile) ??
    null;
  const isCustomModelProfile = formState?.model_profile === "custom";
  const enabledProviderOptions = providerOptions.filter((provider) => provider.enabled);
  const selectedProviderOption =
    enabledProviderOptions.find((provider) => provider.value === formState?.llm_provider) ??
    null;
  const selectedProvider = isCustomModelProfile
    ? selectedProviderOption?.value ?? ""
    : selectedProfileOption?.default_provider ?? formState?.llm_provider ?? "";
  const selectedModels = useMemo(() => {
    if (!configOptions || !selectedProvider) {
      return { quick: [], deep: [] };
    }

    return configOptions.models[selectedProvider] ?? { quick: [], deep: [] };
  }, [configOptions, selectedProvider]);

  useEffect(() => {
    if (!configOptions || !formState || formState.model_profile !== "custom") {
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

  const onProfileChange = (profileValue: string) => {
    if (!configOptions || !formState) {
      return;
    }
    const profile = configOptions.model_profiles.find(
      (option) => option.value === profileValue
    );
    if (!profile?.enabled) {
      return;
    }
    if (profile.value === "custom") {
      const fallbackProvider =
        formState.llm_provider ??
        configOptions.providers.find((provider) => provider.enabled)?.value ??
        "";
      setFormState({
        ...formState,
        model_profile: "custom",
        ...buildProviderSelection(configOptions, fallbackProvider),
      });
      return;
    }
    setFormState({
      ...formState,
      ...buildModelProfileSelection(profile),
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
    if (isCustomModelProfile && !selectedProviderOption?.enabled) {
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
            <section className="grid gap-4 md:grid-cols-[1.2fr_0.8fr]">
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

              <AnalysisSelectField
                label={t("analysis.tickerExchange", "Exchange")}
                value={formState.ticker_exchange ?? "auto"}
                onChange={(value) =>
                  setFormState({
                    ...formState,
                    ticker_exchange: value as TaskCreateRequest["ticker_exchange"],
                  })
                }
                hint={t(
                  "analysis.tickerExchangeHint",
                  "Auto adds SH or SZ for plain 6-digit CN tickers. BJ is not supported yet."
                )}
                className="field-shell block rounded-3xl border border-[var(--border)] bg-white/90 p-4"
              >
                <SelectItem value="auto">
                  {t("analysis.tickerExchange.auto", "Auto")}
                </SelectItem>
                <SelectItem value="SH">
                  {t("analysis.tickerExchange.sh", "SH")}
                </SelectItem>
                <SelectItem value="SZ">
                  {t("analysis.tickerExchange.sz", "SZ")}
                </SelectItem>
                <SelectItem value="BJ">
                  {t("analysis.tickerExchange.bj", "BJ")}
                </SelectItem>
              </AnalysisSelectField>
            </section>

            <section className="rounded-3xl border border-[var(--border)] bg-white/90 p-4">
              <AnalysisSelectField
                label={t("analysis.reportVisibility", "Report Visibility")}
                value={formState.report_visibility}
                onChange={(value) =>
                  setFormState({
                    ...formState,
                    report_visibility: value as ReportVisibility,
                  })
                }
                hint={t(
                  "analysis.reportVisibilityHint",
                  "Private reports stay visible only to you. Workspace reports are visible to users in this tenant."
                )}
              >
                <SelectItem value="private">
                  {t("analysis.visibility.private", "Private")}
                </SelectItem>
                <SelectItem value="workspace">
                  {t("analysis.visibility.workspace", "Workspace")}
                </SelectItem>
              </AnalysisSelectField>
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
                      className={`h-auto w-full flex-col items-stretch justify-start overflow-hidden rounded-[24px] p-4 text-left whitespace-normal ${
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
                      <p className="min-w-0 text-sm font-semibold">{localizedLabel}</p>
                      {localizedDescription ? (
                        <p className="mt-2 min-w-0 break-words text-xs leading-5">
                          {localizedDescription}
                        </p>
                      ) : null}
                    </Button>
                  );
                })}
              </div>
            </section>

            <section className="rounded-3xl border border-[var(--border)] bg-white/90 p-4">
              <p className="text-sm font-semibold text-[var(--text-primary)]">
                {t("analysis.modelProfile", "Model Profile")}
              </p>
              <div className="mt-3 grid gap-3 md:grid-cols-4">
                {profileOptions.map((profile) => {
                  const active = formState.model_profile === profile.value;
                  return (
                    <Button
                      key={profile.value}
                      type="button"
                      variant={active ? "default" : "secondary"}
                      disabled={!profile.enabled}
                      className={`h-auto min-h-[116px] w-full flex-col items-stretch justify-start overflow-hidden rounded-[20px] p-4 text-left whitespace-normal ${
                        active
                          ? "bg-[var(--accent)] text-white hover:bg-[var(--accent)] hover:brightness-105"
                          : "text-slate-600"
                      }`}
                      onClick={() => onProfileChange(profile.value)}
                    >
                      <span className="min-w-0 text-sm font-semibold">
                        {t(`analysis.modelProfile.${optionKey(profile.value)}`, profile.label)}
                      </span>
                      <span className="mt-2 min-w-0 break-words text-xs leading-5">
                        {t(
                          `analysis.modelProfile.${optionKey(profile.value)}.description`,
                          profile.description
                        )}
                      </span>
                      {!profile.enabled && profile.disabled_reason ? (
                        <span className="mt-2 min-w-0 break-words text-xs leading-5">
                          {profile.disabled_reason}
                        </span>
                      ) : null}
                    </Button>
                  );
                })}
              </div>
            </section>

            <section className="grid gap-4 rounded-3xl border border-[var(--border)] bg-white/90 p-4 md:grid-cols-2">
              {isCustomModelProfile ? (
              <AnalysisSelectField
                label={t("analysis.provider", "LLM Provider")}
                value={formState.llm_provider ?? ""}
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
              ) : null}

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

              {isCustomModelProfile ? (
              <AnalysisSelectField
                label={t("analysis.quickModel", "Quick Model")}
                value={formState.quick_think_llm ?? ""}
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
              ) : null}

              {isCustomModelProfile ? (
              <AnalysisSelectField
                label={t("analysis.deepModel", "Deep Model")}
                value={formState.deep_think_llm ?? ""}
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
              ) : null}
            </section>

            {selectedProvider === "openai" ? (
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

            {selectedProvider === "google" ? (
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
                disabled={
                  loading ||
                  (isCustomModelProfile
                    ? !selectedProviderOption?.enabled
                    : !selectedProfileOption?.enabled)
                }
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
  const profile =
    configOptions.model_profiles.find(
      (option) => option.enabled && option.value === "balanced"
    ) ??
    configOptions.model_profiles.find((option) => option.enabled) ??
    null;
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
    ticker_exchange: "auto",
    analysis_date: null,
    analysts: configOptions.analysts.map((option) => option.value),
    research_depth: Number(firstDepth),
    output_language: firstLanguage,
    report_visibility: "workspace",
    ...(profile && profile.value !== "custom"
      ? buildModelProfileSelection(profile)
      : {
          model_profile: "custom",
          ...buildProviderSelection(configOptions, provider),
        }),
  };
}

function buildModelProfileSelection(
  profile: ModelProfileOption
): Pick<
  FormState,
  | "model_profile"
  | "llm_provider"
  | "quick_think_llm"
  | "deep_think_llm"
  | "openai_reasoning_effort"
  | "google_thinking_level"
> {
  return {
    model_profile: profile.value,
    llm_provider: profile.default_provider ?? null,
    quick_think_llm: profile.default_quick_model ?? null,
    deep_think_llm: profile.default_deep_model ?? null,
    openai_reasoning_effort: profile.default_provider === "openai" ? "medium" : null,
    google_thinking_level: profile.default_provider === "google" ? "high" : null,
  };
}

function buildProviderSelection(
  configOptions: ConfigOptions,
  provider: string
): Pick<
  FormState,
  | "model_profile"
  | "llm_provider"
  | "quick_think_llm"
  | "deep_think_llm"
  | "openai_reasoning_effort"
  | "google_thinking_level"
> {
  const providerModels = configOptions.models[provider] ?? { quick: [], deep: [] };

  return {
    model_profile: "custom",
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
