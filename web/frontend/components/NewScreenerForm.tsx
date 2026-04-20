"use client";

import { useEffect, useState } from "react";
import { AccessibleDialog } from "@/components/AccessibleDialog";
import { usePreferences } from "@/components/PreferencesProvider";
import {
  createScreenerTask,
  getScreenerConfigOptions,
  type ScreenTaskCreateRequest,
  type ScreenerConfigOptions,
} from "@/lib/api";
import { getLocalDateInputValue } from "@/lib/localDate";
import { optionKey } from "@/lib/uiPreferences";

interface NewScreenerFormProps {
  isOpen: boolean;
  onClose: () => void;
  onTaskCreated: (taskId: string) => void;
}

function validateScreenerRequest(
  formState: ScreenTaskCreateRequest,
  t: ReturnType<typeof usePreferences>["t"]
): string | null {
  if (formState.markets.length === 0) {
    return t("screener.selectMarket", "Select at least one market.");
  }

  if (!Number.isFinite(formState.top_k) || formState.top_k <= 0) {
    return t("screener.topKPositive", "Top K must be positive.");
  }

  if (!/^\d{4}-\d{2}-\d{2}$/.test(formState.as_of_date)) {
    return t(
      "screener.dateFormat",
      "as_of_date must use YYYY-MM-DD format."
    );
  }

  return null;
}

export function NewScreenerForm({
  isOpen,
  onClose,
  onTaskCreated,
}: NewScreenerFormProps) {
  const { t } = usePreferences();
  const [configOptions, setConfigOptions] = useState<ScreenerConfigOptions | null>(null);
  const [formState, setFormState] = useState<ScreenTaskCreateRequest | null>(null);
  const [loadingOptions, setLoadingOptions] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const loadOptionsErrorLabel = t(
    "screener.error.loadOptions",
    "Unable to load screener options"
  );
  const createTaskErrorLabel = t(
    "screener.error.createTask",
    "Unable to create screener task"
  );

  useEffect(() => {
    if (!isOpen) {
      return;
    }

    let isActive = true;
    const loadOptions = async () => {
      setLoadingOptions(true);
      setError(null);
      try {
        const nextOptions = await getScreenerConfigOptions();
        if (!isActive) {
          return;
        }
        setConfigOptions(nextOptions);
        setFormState({
          markets: nextOptions.markets.filter((market) => market.enabled).slice(0, 1).map((market) => market.value),
          as_of_date: getLocalDateInputValue(),
          cn_data_source: nextOptions.defaults.cn_data_source,
          top_k: nextOptions.defaults.top_k,
        });
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
  }, [isOpen, loadOptionsErrorLabel]);

  if (!isOpen) {
    return null;
  }

  const toggleMarket = (value: string) => {
    if (!formState) {
      return;
    }
    const exists = formState.markets.includes(value);
    const markets = exists
      ? formState.markets.filter((market) => market !== value)
      : [...formState.markets, value];
    setFormState({ ...formState, markets });
  };

  const submitTask = async () => {
    if (!formState) {
      return;
    }
    setError(null);
    const validationError = validateScreenerRequest(formState, t);
    if (validationError) {
      setError(validationError);
      return;
    }

    setLoading(true);
    try {
      const response = await createScreenerTask(formState);
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
      ariaLabel={t("screener.dialog", "New screener")}
      panelClassName="modal-panel fade-in w-full max-w-2xl rounded-[30px] border border-[var(--border)] bg-[var(--surface)] p-6 shadow-[0_28px_80px_rgba(18,28,41,0.24)] md:p-8"
      panelProps={{
        onMouseDown: (event) => event.stopPropagation(),
      }}
    >
        <div className="flex items-start justify-between gap-4">
          <div>
            <p className="text-[11px] font-semibold uppercase tracking-[0.34em] text-[var(--primary)]">
              {t("screener.kicker", "Launch Screener")}
            </p>
            <h2 className="font-heading mt-3 text-3xl font-bold tracking-tight text-slate-900">
              {t("screener.title", "New Screener")}
            </h2>
          </div>
          <button
            type="button"
            className="interactive-button focus-ring rounded-full border border-[var(--border)] bg-white px-4 py-2 text-xs font-semibold uppercase tracking-[0.2em] text-slate-600"
            onClick={onClose}
          >
            {t("common.close", "Close")}
          </button>
        </div>

        {loadingOptions || !configOptions || !formState ? (
          <div className="mt-8 rounded-3xl border border-dashed border-[var(--border)] bg-[var(--surface-strong)] px-5 py-8 text-sm text-slate-600">
            {t("screener.loadingOptions", "Loading screener options...")}
          </div>
        ) : (
          <div className="mt-8 grid gap-6">
            <section className="rounded-3xl border border-[var(--border)] bg-white/90 p-4">
              <p className="text-xs font-semibold uppercase tracking-[0.24em] text-slate-500">
                {t("screener.markets", "Markets")}
              </p>
              <div className="mt-3 flex flex-wrap gap-3">
                {configOptions.markets.map((market) => {
                  const active = formState.markets.includes(market.value);
                  return (
                    <button
                      key={market.value}
                      type="button"
                      disabled={!market.enabled}
                      className={`interactive-button focus-ring rounded-full border px-4 py-2 text-xs font-semibold uppercase tracking-[0.18em] ${
                        active
                          ? "border-[var(--primary)] bg-[var(--primary-soft)] text-[var(--primary-strong)]"
                          : "border-[var(--border)] bg-[var(--surface-strong)] text-slate-600"
                      }`}
                      onClick={() => toggleMarket(market.value)}
                    >
                      {t(`screener.market.${optionKey(market.value)}`, market.label)}
                    </button>
                  );
                })}
              </div>
              <p className="mt-2 text-xs leading-5 text-slate-500">
                {t(
                  "screener.marketHelp",
                  "Disabled backend markets usually require server-side setup such as SCREEN_US_MANIFEST_PATH."
                )}
              </p>
            </section>

            <section className="grid gap-4 md:grid-cols-2">
              {formState.markets.includes("cn") ? (
                <label className="field-shell block rounded-3xl border border-[var(--border)] bg-white/90 p-4 md:col-span-2">
                  <span className="field-label text-xs font-semibold uppercase tracking-[0.24em] text-slate-500">
                    {t("screener.cnDataSource", "CN Data Source")}
                  </span>
                  <div className="mt-3 flex flex-wrap gap-3">
                    {configOptions.cn_data_sources.map((sourceOption) => {
                      const active = formState.cn_data_source === sourceOption.value;
                      return (
                        <button
                          key={sourceOption.value}
                          type="button"
                          className={`interactive-button focus-ring rounded-full border px-4 py-2 text-xs font-semibold uppercase tracking-[0.18em] ${
                            active
                              ? "border-[var(--primary)] bg-[var(--primary-soft)] text-[var(--primary-strong)]"
                              : "border-[var(--border)] bg-[var(--surface-strong)] text-slate-600"
                          }`}
                          onClick={() =>
                            setFormState({
                              ...formState,
                              cn_data_source: sourceOption.value,
                            })
                          }
                        >
                          {t(
                            `screener.cnSource.${optionKey(sourceOption.value)}`,
                            sourceOption.label
                          )}
                        </button>
                      );
                    })}
                  </div>
                </label>
              ) : null}

              <label className="field-shell block rounded-3xl border border-[var(--border)] bg-white/90 p-4">
                <span className="field-label text-xs font-semibold uppercase tracking-[0.24em] text-slate-500">
                  {t("screener.asOfDate", "As Of Date")}
                </span>
                <input
                  type="date"
                  value={formState.as_of_date}
                  onChange={(event) =>
                    setFormState({ ...formState, as_of_date: event.target.value })
                  }
                  className="focus-ring mt-3 w-full rounded-2xl border border-[var(--border)] bg-[var(--surface-strong)] px-4 py-3 text-sm font-semibold text-slate-900"
                />
              </label>

              <label className="field-shell block rounded-3xl border border-[var(--border)] bg-white/90 p-4">
                <span className="field-label text-xs font-semibold uppercase tracking-[0.24em] text-slate-500">
                  {t("screener.topK", "Top K")}
                </span>
                <input
                  type="number"
                  value={formState.top_k}
                  onChange={(event) =>
                    setFormState({ ...formState, top_k: Number(event.target.value) })
                  }
                  className="focus-ring mt-3 w-full rounded-2xl border border-[var(--border)] bg-[var(--surface-strong)] px-4 py-3 text-sm font-semibold text-slate-900"
                />
              </label>
            </section>

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
                disabled={loading}
                onClick={() => void submitTask()}
              >
                {loading
                  ? t("screener.starting", "Launching...")
                  : t("screener.start", "Start Screener")}
              </button>
            </div>
          </div>
        )}
    </AccessibleDialog>
  );
}
