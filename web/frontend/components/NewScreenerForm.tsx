"use client";

import { useEffect, useState } from "react";
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

const BREAKOUT_LABELS: Record<string, string> = {
  platform_breakout: "Platform Breakout",
  box_breakout: "Box Breakout",
  wedge_breakout: "Wedge Breakout",
};

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
          breakout_types: nextOptions.defaults.breakout_types,
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

  const toggleBreakoutType = (value: string) => {
    if (!formState) {
      return;
    }
    const exists = formState.breakout_types.includes(value);
    const breakout_types = exists
      ? formState.breakout_types.filter((breakoutType) => breakoutType !== value)
      : [...formState.breakout_types, value];
    setFormState({ ...formState, breakout_types });
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
    <Dialog open={isOpen} onOpenChange={(open) => !open && onClose()}>
      <DialogContent
        aria-label={t("screener.dialog", "New screener")}
        className="modal-panel max-w-2xl"
        onMouseDown={(event) => event.stopPropagation()}
      >
        <DialogHeader className="pr-12">
          <p className="text-[11px] font-semibold uppercase tracking-[0.34em] text-[var(--primary)]">
            {t("screener.kicker", "Launch Screener")}
          </p>
          <DialogTitle>{t("screener.title", "New Screener")}</DialogTitle>
          <DialogDescription>
            {t(
              "screener.description",
              "Pick the markets, optional CN source, candidate count, and breakout signals for this ranking run."
            )}
          </DialogDescription>
        </DialogHeader>

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
                    <Button
                      key={market.value}
                      type="button"
                      disabled={!market.enabled}
                      variant={active ? "default" : "secondary"}
                      size="sm"
                      onClick={() => toggleMarket(market.value)}
                    >
                      {t(`screener.market.${optionKey(market.value)}`, market.label)}
                    </Button>
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
                        <Button
                          key={sourceOption.value}
                          type="button"
                          variant={active ? "default" : "secondary"}
                          size="sm"
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
                        </Button>
                      );
                    })}
                  </div>
                </label>
              ) : null}

              <section className="field-shell rounded-3xl border border-[var(--border)] bg-white/90 p-4 md:col-span-2">
                <p className="field-label text-xs font-semibold uppercase tracking-[0.24em] text-slate-500">
                  {t("screener.breakouts", "Breakout Signals")}
                </p>
                <div className="mt-3 flex flex-wrap gap-3">
                  {configOptions.breakout_types.map((breakoutOption) => {
                    const active = formState.breakout_types.includes(breakoutOption.value);
                    return (
                      <Button
                        key={breakoutOption.value}
                        type="button"
                        variant={active ? "default" : "secondary"}
                        size="sm"
                        onClick={() => toggleBreakoutType(breakoutOption.value)}
                      >
                        {t(
                          `screener.breakout.${optionKey(breakoutOption.value)}`,
                          BREAKOUT_LABELS[breakoutOption.value] ?? breakoutOption.label
                        )}
                      </Button>
                    );
                  })}
                </div>
                <p className="mt-2 text-xs leading-5 text-slate-500">
                  {t(
                    "screener.breakoutHelp",
                    "Selected breakout signals add ranking bonus and appear in results, but they do not hard-filter the pool."
                  )}
                </p>
              </section>

              <label className="field-shell block rounded-3xl border border-[var(--border)] bg-white/90 p-4">
                <span className="field-label text-xs font-semibold uppercase tracking-[0.24em] text-slate-500">
                  {t("screener.asOfDate", "As Of Date")}
                </span>
                <Input
                  type="date"
                  value={formState.as_of_date}
                  onChange={(event) =>
                    setFormState({ ...formState, as_of_date: event.target.value })
                  }
                  className="mt-3 border-[var(--border)] bg-[var(--surface-strong)] font-semibold text-slate-900"
                />
              </label>

              <label className="field-shell block rounded-3xl border border-[var(--border)] bg-white/90 p-4">
                <span className="field-label text-xs font-semibold uppercase tracking-[0.24em] text-slate-500">
                  {t("screener.topK", "Top K")}
                </span>
                <Input
                  type="number"
                  value={formState.top_k}
                  onChange={(event) =>
                    setFormState({ ...formState, top_k: Number(event.target.value) })
                  }
                  className="mt-3 border-[var(--border)] bg-[var(--surface-strong)] font-semibold text-slate-900"
                />
              </label>
            </section>

            {error ? (
              <div className="rounded-2xl border border-[rgba(163,53,53,0.2)] bg-[rgba(163,53,53,0.08)] px-4 py-3 text-sm text-[var(--danger)]">
                {error}
              </div>
            ) : null}

            <div className="flex flex-wrap items-center justify-end gap-3">
              <Button type="button" variant="secondary" onClick={onClose}>
                {t("common.cancel", "Cancel")}
              </Button>
              <Button type="button" disabled={loading} onClick={() => void submitTask()}>
                {loading
                  ? t("screener.starting", "Launching...")
                  : t("screener.start", "Start Screener")}
              </Button>
            </div>
          </div>
        )}
      </DialogContent>
    </Dialog>
  );
}
