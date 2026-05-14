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
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import {
  createScreenerTask,
  getScreenerConfigOptions,
  type ScreenTaskCreateRequest,
  type ScreenerConfigOptions,
} from "@/lib/api";
import { optionKey } from "@/lib/uiPreferences";

interface NewScreenerFormProps {
  isOpen: boolean;
  onClose: () => void;
  onTaskCreated: (taskId: string) => void;
}

type ScreenerFormState = Omit<ScreenTaskCreateRequest, "top_k"> & {
  top_k: string;
};

const BREAKOUT_LABELS: Record<string, string> = {
  platform_breakout: "Platform Breakout",
  box_breakout: "Box Breakout",
  wedge_breakout: "Wedge Breakout",
};

function validateScreenerRequest(
  formState: ScreenerFormState,
  t: ReturnType<typeof usePreferences>["t"]
): string | null {
  if (formState.markets.length === 0) {
    return t("screener.selectMarket", "Select at least one market.");
  }

  const topK = Number(formState.top_k);
  if (!Number.isFinite(topK) || topK <= 0) {
    return t("screener.topKPositive", "Top K must be positive.");
  }
  if (topK > 100) {
    return t("screener.topKMax", "Top K must be 100 or less.");
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
  const [formState, setFormState] = useState<ScreenerFormState | null>(null);
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
          cn_data_source: nextOptions.defaults.cn_data_source,
          us_data_source: nextOptions.defaults.us_data_source,
          history_cache_policy: nextOptions.defaults.history_cache_policy,
          top_k: String(nextOptions.defaults.top_k),
          breakout_types: nextOptions.defaults.breakout_types,
          filter_preset_selections: nextOptions.defaults.filter_preset_selections,
          ranking_profile_id: nextOptions.defaults.ranking_profile_id,
          include_fundamentals: nextOptions.defaults.include_fundamentals,
          cn_fundamental_source: nextOptions.defaults.cn_fundamental_source,
          us_fundamental_source: nextOptions.defaults.us_fundamental_source,
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

  const updateFilterPreset = (groupId: string, value: string) => {
    if (!formState) {
      return;
    }
    setFormState({
      ...formState,
      filter_preset_selections: {
        ...(formState.filter_preset_selections ?? {}),
        [groupId]: value,
      },
    });
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
      const response = await createScreenerTask({
        ...formState,
        top_k: Number(formState.top_k),
      });
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
              "Pick the markets, candidate count, and breakout signals for this ranking run."
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
                      variant="secondary"
                      size="sm"
                      data-active={active}
                      aria-pressed={active}
                      className="choice-pill"
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
                  "Disabled backend markets usually require server-side setup such as DATA_DIR/manifest/us.csv."
                )}
              </p>
            </section>

            <section className="grid gap-4 md:grid-cols-2">
              <section className="field-shell rounded-3xl border border-[var(--border)] bg-white/90 p-4 md:col-span-2">
                <p className="field-label text-xs font-semibold uppercase tracking-[0.24em] text-slate-500">
                  {t("screener.rankingProfile", "Ranking Profile")}
                </p>
                <Select
                  value={formState.ranking_profile_id ?? ""}
                  onValueChange={(value) =>
                    setFormState({ ...formState, ranking_profile_id: value })
                  }
                >
                  <SelectTrigger className="mt-3">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    {configOptions.ranking_profiles.map((profile) => (
                      <SelectItem key={profile.id} value={profile.id}>
                        {profile.label}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </section>

              <section className="field-shell rounded-3xl border border-[var(--border)] bg-white/90 p-4 md:col-span-2">
                <p className="field-label text-xs font-semibold uppercase tracking-[0.24em] text-slate-500">
                  {t("screener.presetFilters", "Preset Filters")}
                </p>
                <div className="mt-3 grid gap-3 md:grid-cols-2">
                  {configOptions.filter_preset_groups.map((group) => (
                    <label key={group.id} className="block">
                      <span className="text-xs font-semibold text-slate-500">
                        {group.label}
                      </span>
                      <Select
                        value={
                          formState.filter_preset_selections?.[group.id] ?? "any"
                        }
                        onValueChange={(value) => updateFilterPreset(group.id, value)}
                      >
                        <SelectTrigger className="mt-2">
                          <SelectValue />
                        </SelectTrigger>
                        <SelectContent>
                          {group.options.map((option) => (
                            <SelectItem key={option.value} value={option.value}>
                              {option.label}
                            </SelectItem>
                          ))}
                        </SelectContent>
                      </Select>
                    </label>
                  ))}
                </div>
              </section>

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
                        variant="secondary"
                        size="sm"
                        data-active={active}
                        aria-pressed={active}
                        className="choice-pill"
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
                    "Selected breakout signals restrict final candidates to matching breakout setups and add ranking bonus."
                  )}
                </p>
              </section>

              <label className="field-shell block rounded-3xl border border-[var(--border)] bg-white/90 p-4">
                <span className="field-label text-xs font-semibold uppercase tracking-[0.24em] text-slate-500">
                  {t("screener.topK", "Top K")}
                </span>
                <Input
                  type="number"
                  min={1}
                  max={100}
                  value={formState.top_k}
                  onChange={(event) =>
                    setFormState({ ...formState, top_k: event.target.value })
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
