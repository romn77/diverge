"use client";

import Link from "next/link";
import { startTransition, useEffect, useMemo, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { ChevronDown, Play, RefreshCw, Save, SlidersHorizontal } from "lucide-react";
import { usePreferences } from "@/components/PreferencesProvider";
import { ScreenerResultsViewer } from "@/components/ScreenerResultsViewer";
import { useWorkbench } from "@/components/WorkbenchProvider";
import { Button } from "@/components/ui/button";
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
  listScreenerPresets,
  replaceScreenerPresets,
  type ScreenTaskCreateRequest,
  type ScreenerConfigOptions,
  type ScreenerPresetRecord,
} from "@/lib/api";
import {
  buildScreenerHref,
  buildScreenerTaskHref,
} from "@/lib/workbenchRoutes";

type ScreenerBarState = Omit<ScreenTaskCreateRequest, "top_k"> & {
  top_k: string;
};

type ScreenerFilterTab = "technical" | "pattern" | "fundamental";

interface SavedScreenerBar {
  id: string;
  name: string;
  fingerprint: string;
  config: ScreenTaskCreateRequest;
  created_at: string;
  updated_at: string;
}

interface SelectedFilterSummary {
  id: string;
  label: string;
  value: string;
}

const SAVED_SCREENER_BARS_KEY = "diverge.screener.savedBars";
const LAST_SCREENER_BAR_KEY = "diverge.screener.lastRunBar";
const CURRENT_SCREEN_VALUE = "__current__";
const TOP_K_LIMIT = 100;
const CONTROL_INPUT_CLASS =
  "h-9 rounded-2xl border-[var(--border-strong)] bg-[var(--surface-strong)] text-[var(--text)]";
const COMPACT_SELECT_CLASS =
  "h-8 min-w-0 rounded-2xl border-[var(--border-strong)] bg-[var(--surface-strong)] text-sm font-semibold text-[var(--text)]";
const FALLBACK_FILTER_PRESET_SELECTIONS: Record<string, string> = {
  ma20_position: "price_above_ma20",
};

const filterTabs: Array<{
  id: ScreenerFilterTab;
}> = [
  { id: "technical" },
  { id: "pattern" },
  { id: "fundamental" },
];

const FILTER_GROUP_CATEGORY: Record<string, ScreenerFilterTab> = {
  rsi: "technical",
  ma20_position: "technical",
  ma60_position: "technical",
  ma_alignment: "technical",
  ret_20: "technical",
  ret_60: "technical",
  volatility: "technical",
  liquidity: "technical",
  pattern: "pattern",
  volume: "pattern",
  pe_ttm: "fundamental",
  ps_ttm: "fundamental",
  pb: "fundamental",
  peg: "fundamental",
  roe: "fundamental",
  gross_margin: "fundamental",
  net_margin: "fundamental",
  revenue_growth_yoy: "fundamental",
  net_income_growth_yoy: "fundamental",
  current_ratio: "fundamental",
  debt_to_assets: "fundamental",
};

const FUNDAMENTAL_FILTER_GROUPS = new Set(
  Object.entries(FILTER_GROUP_CATEGORY)
    .filter(([, category]) => category === "fundamental")
    .map(([groupId]) => groupId)
);
const SPECIFIC_BREAKOUT_PATTERNS = new Set([
  "platform_breakout",
  "box_breakout",
  "wedge_breakout",
]);
const LEGACY_FILTER_OPTION_GROUPS: Record<string, Record<string, string>> = {
  moving_average: {
    price_above_ma20: "ma20_position",
    near_ma20_3pct: "ma20_position",
    below_ma20: "ma20_position",
    price_above_ma60: "ma60_position",
    below_ma60: "ma60_position",
    bullish_alignment: "ma_alignment",
  },
  performance: {
    ret20_positive: "ret_20",
    ret20_5: "ret_20",
    ret20_negative: "ret_20",
    ret60_positive: "ret_60",
    ret60_10: "ret_60",
  },
  valuation: {
    pe_lte_10: "pe_ttm",
    pe_lte_20: "pe_ttm",
    pe_lte_40: "pe_ttm",
    ps_lte_3: "ps_ttm",
    ps_lte_5: "ps_ttm",
    ps_lte_10: "ps_ttm",
    pb_lte_1: "pb",
    pb_lte_3: "pb",
    pb_lte_5: "pb",
    peg_lte_1: "peg",
    peg_lte_1_5: "peg",
    peg_lte_2: "peg",
  },
  quality: {
    roe_gte_10: "roe",
    roe_gte_20: "roe",
    gross_margin_gte_30: "gross_margin",
    net_margin_gte_10: "net_margin",
  },
  growth: {
    revenue_growth_gte_10: "revenue_growth_yoy",
    revenue_growth_gte_20: "revenue_growth_yoy",
    income_growth_gte_10: "net_income_growth_yoy",
  },
  balance_sheet: {
    current_ratio_gte_1: "current_ratio",
    current_ratio_gte_1_5: "current_ratio",
    debt_assets_lte_60: "debt_to_assets",
  },
};

function hasActiveFilterSelection(selections: Record<string, string>): boolean {
  return Object.values(selections).some((value) => value !== "any");
}

function withFallbackFilterPresetSelection(
  selections: Record<string, string>
): Record<string, string> {
  if (hasActiveFilterSelection(selections)) {
    return selections;
  }

  return sortRecord({
    ...selections,
    ...FALLBACK_FILTER_PRESET_SELECTIONS,
  });
}

function createDefaultFormState(options: ScreenerConfigOptions): ScreenerBarState {
  const filterPresetSelections = withFallbackFilterPresetSelection(
    normalizeFilterPresetSelections(options.defaults.filter_preset_selections)
  );

  return {
    markets: options.markets
      .filter((market) => market.enabled)
      .slice(0, 1)
      .map((market) => market.value),
    cn_data_source: options.defaults.cn_data_source,
    us_data_source: options.defaults.us_data_source,
    history_cache_policy: options.defaults.history_cache_policy,
    top_k: String(options.defaults.top_k),
    breakout_types: options.defaults.breakout_types,
    filter_preset_selections: filterPresetSelections,
    ranking_profile_id: options.defaults.ranking_profile_id,
    include_fundamentals: options.defaults.include_fundamentals,
    cn_fundamental_source: options.defaults.cn_fundamental_source,
    us_fundamental_source: options.defaults.us_fundamental_source,
  };
}

function createFormStateFromPayload(
  payload: ScreenTaskCreateRequest,
  options: ScreenerConfigOptions
): ScreenerBarState {
  const fallback = createDefaultFormState(options);
  const filterPresetSelections = withFallbackFilterPresetSelection(
    normalizeFilterPresetSelections(payload.filter_preset_selections)
  );

  return {
    ...fallback,
    ...payload,
    markets: payload.markets.length > 0 ? [...payload.markets] : fallback.markets,
    breakout_types: payload.breakout_types ? [...payload.breakout_types] : fallback.breakout_types,
    filter_preset_selections: filterPresetSelections,
    top_k: String(payload.top_k || fallback.top_k),
  };
}

function sortRecord(value: Record<string, string> | undefined): Record<string, string> {
  const source = value ?? {};
  return Object.fromEntries(
    Object.keys(source)
      .sort()
      .map((key) => [key, source[key]])
  );
}

function normalizeFilterPresetSelections(
  value: Record<string, string> | undefined
): Record<string, string> {
  const nextSelections = { ...(value ?? {}) };
  for (const [legacyGroup, optionGroups] of Object.entries(
    LEGACY_FILTER_OPTION_GROUPS
  )) {
    const legacyValue = nextSelections[legacyGroup];
    delete nextSelections[legacyGroup];

    if (legacyValue && legacyValue !== "any") {
      const mappedGroup = optionGroups[legacyValue];
      if (mappedGroup && !nextSelections[mappedGroup]) {
        nextSelections[mappedGroup] = legacyValue;
      }
    }
  }

  return sortRecord(nextSelections);
}

function buildScreenerPayload(formState: ScreenerBarState): ScreenTaskCreateRequest {
  const filterPresetSelections = normalizeFilterPresetSelections(
    formState.filter_preset_selections
  );
  const selectedPattern = filterPresetSelections.pattern;

  return {
    ...formState,
    markets: [...formState.markets],
    breakout_types:
      selectedPattern && SPECIFIC_BREAKOUT_PATTERNS.has(selectedPattern)
        ? [selectedPattern]
        : [],
    filter_preset_selections: filterPresetSelections,
    top_k: Number(formState.top_k),
  };
}

function fingerprintScreenerPayload(payload: ScreenTaskCreateRequest): string {
  return JSON.stringify({
    ...payload,
    markets: [...payload.markets].sort(),
    breakout_types: [...payload.breakout_types].sort(),
    filter_preset_selections: normalizeFilterPresetSelections(
      payload.filter_preset_selections
    ),
  });
}

function validateScreenerBar(
  formState: ScreenerBarState,
  t: ReturnType<typeof usePreferences>["t"]
): string | null {
  if (formState.markets.length === 0) {
    return t("screener.selectMarket", "Select at least one market.");
  }

  const topK = Number(formState.top_k);
  if (!Number.isFinite(topK) || topK <= 0) {
    return t("screener.topKPositive", "Top K must be positive.");
  }
  if (topK > TOP_K_LIMIT) {
    return t("screener.topKMax", "Top K must be 100 or less.");
  }

  return null;
}

function readSavedScreenerBars(): SavedScreenerBar[] {
  if (typeof window === "undefined") {
    return [];
  }

  try {
    const rawValue = window.localStorage.getItem(SAVED_SCREENER_BARS_KEY);
    const parsedValue = rawValue ? JSON.parse(rawValue) : [];
    return Array.isArray(parsedValue) ? parsedValue : [];
  } catch {
    return [];
  }
}

function writeSavedScreenerBars(items: SavedScreenerBar[]): void {
  window.localStorage.setItem(SAVED_SCREENER_BARS_KEY, JSON.stringify(items));
}

function readLastScreenerBar(): ScreenTaskCreateRequest | null {
  if (typeof window === "undefined") {
    return null;
  }

  try {
    const rawValue = window.localStorage.getItem(LAST_SCREENER_BAR_KEY);
    if (!rawValue) {
      return null;
    }
    const parsedValue = JSON.parse(rawValue) as Partial<ScreenTaskCreateRequest>;
    if (!Array.isArray(parsedValue.markets) || typeof parsedValue.top_k !== "number") {
      return null;
    }
    return parsedValue as ScreenTaskCreateRequest;
  } catch {
    return null;
  }
}

function writeLastScreenerBar(payload: ScreenTaskCreateRequest): void {
  window.localStorage.setItem(LAST_SCREENER_BAR_KEY, JSON.stringify(payload));
}

function createSavedId(): string {
  if (typeof crypto !== "undefined" && "randomUUID" in crypto) {
    return crypto.randomUUID();
  }
  return `screen_${Date.now()}`;
}

function savedBarFromPresetRecord(record: ScreenerPresetRecord): SavedScreenerBar {
  return {
    id: record.id,
    name: record.name,
    fingerprint: record.fingerprint ?? fingerprintScreenerPayload(record.config),
    config: record.config,
    created_at: record.created_at,
    updated_at: record.updated_at,
  };
}

function buildSelectedFilterSummaries(
  options: ScreenerConfigOptions | null,
  selections: Record<string, string> | undefined,
  t: ReturnType<typeof usePreferences>["t"]
): SelectedFilterSummary[] {
  if (!options || !selections) {
    return [];
  }

  return options.filter_preset_groups
    .map((group) => {
      const selectedValue = selections[group.id];
      if (!selectedValue || selectedValue === "any") {
        return null;
      }
      const selectedOption = group.options.find((option) => option.value === selectedValue);
      return {
        id: group.id,
        label: localizeFilterGroupLabel(group.id, group.label, t),
        value: localizeFilterOptionLabel(
          group.id,
          selectedValue,
          selectedOption?.label ?? selectedValue,
          t
        ),
      };
    })
    .filter((item): item is SelectedFilterSummary => item !== null);
}

function localizeMarketLabel(
  value: string,
  fallback: string,
  t: ReturnType<typeof usePreferences>["t"]
): string {
  return t(`screener.market.${value}`, fallback);
}

function localizeRankingProfileLabel(
  id: string,
  fallback: string,
  t: ReturnType<typeof usePreferences>["t"]
): string {
  return t(`screenerDashboard.ranking.${id}`, fallback);
}

function localizeFilterTabLabel(
  id: ScreenerFilterTab,
  t: ReturnType<typeof usePreferences>["t"]
): string {
  return t(`screenerDashboard.filterTab.${id}`, id);
}

function localizeFilterTabNote(
  id: ScreenerFilterTab,
  t: ReturnType<typeof usePreferences>["t"]
): string {
  return t(`screenerDashboard.filterTab.${id}.note`, "");
}

function localizeFilterGroupLabel(
  id: string,
  fallback: string,
  t: ReturnType<typeof usePreferences>["t"]
): string {
  return t(`screenerDashboard.filterGroup.${id}`, fallback);
}

function localizeFilterOptionLabel(
  groupId: string,
  value: string,
  fallback: string,
  t: ReturnType<typeof usePreferences>["t"]
): string {
  return t(`screenerDashboard.filterOption.${groupId}.${value}`, fallback);
}

export function ScreenerDashboard() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const { t } = usePreferences();
  const {
    activeScreenerTasks,
    newScreenerDisabled,
    refreshScreenerRuns,
    refreshScreenerTasks,
    screenerRuns,
  } = useWorkbench();
  const [configOptions, setConfigOptions] = useState<ScreenerConfigOptions | null>(null);
  const [formState, setFormState] = useState<ScreenerBarState | null>(null);
  const [savedBars, setSavedBars] = useState<SavedScreenerBar[]>([]);
  const [selectedSavedBarId, setSelectedSavedBarId] = useState(CURRENT_SCREEN_VALUE);
  const [presetName, setPresetName] = useState("");
  const [activeFilterTab, setActiveFilterTab] = useState<ScreenerFilterTab>("technical");
  const [loadingOptions, setLoadingOptions] = useState(true);
  const [running, setRunning] = useState(false);
  const [feedback, setFeedback] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [resultStale, setResultStale] = useState(false);
  const [hideLatestRun, setHideLatestRun] = useState(false);
  const [isConfigCollapsed, setIsConfigCollapsed] = useState(false);
  const firstActiveScreenerTask = activeScreenerTasks[0];
  const selectedRunId = searchParams.get("runId");
  const latestScreenerRunId = useMemo(
    () => screenerRuns.find((run) => run.snapshot_available !== false)?.id ?? null,
    [screenerRuns]
  );
  const displayedRunId = selectedRunId ?? (hideLatestRun ? null : latestScreenerRunId);

  const markResultStale = () => {
    if (displayedRunId) {
      setResultStale(true);
    }
  };

  const dismissSelectedRun = () => {
    setResultStale(false);
    if (selectedRunId) {
      startTransition(() => {
        router.replace(buildScreenerHref(), { scroll: false });
      });
      return;
    }
    setHideLatestRun(true);
  };

  useEffect(() => {
    setResultStale(false);
  }, [displayedRunId]);

  useEffect(() => {
    if (selectedRunId) {
      setHideLatestRun(false);
    }
  }, [selectedRunId]);

  useEffect(() => {
    setSavedBars(readSavedScreenerBars());

    let isActive = true;
    const loadBackendPresets = async () => {
      try {
        const records = await listScreenerPresets();
        if (!isActive || records.length === 0) {
          return;
        }
        const nextSavedBars = records.map(savedBarFromPresetRecord);
        setSavedBars(nextSavedBars);
        writeSavedScreenerBars(nextSavedBars);
      } catch {
        // Local saved bars still keep the screener usable when backend sync is unavailable.
      }
    };

    void loadBackendPresets();
    return () => {
      isActive = false;
    };
  }, []);

  useEffect(() => {
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
        const lastPayload = readLastScreenerBar();
        setFormState(
          lastPayload
            ? createFormStateFromPayload(lastPayload, nextOptions)
            : createDefaultFormState(nextOptions)
        );
        setPresetName("");
      } catch (nextError) {
        if (isActive) {
          setError(
            nextError instanceof Error
              ? nextError.message
              : t("screener.error.loadOptions", "Unable to load screener options")
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
  }, [t]);

  const enabledMarketOptions = useMemo(() => {
    return configOptions?.markets.filter((market) => market.enabled) ?? [];
  }, [configOptions]);
  const marketSelectOptions = useMemo(() => {
    const singleMarketOptions = enabledMarketOptions.map((market) => ({
      label: localizeMarketLabel(market.value, market.label, t),
      value: market.value,
    }));
    if (enabledMarketOptions.length > 1) {
      return [
        {
          label: enabledMarketOptions.map((market) => market.label).join(" + "),
          value: enabledMarketOptions.map((market) => market.value).sort().join(","),
        },
        ...singleMarketOptions,
      ];
    }
    return singleMarketOptions;
  }, [enabledMarketOptions, t]);
  const selectedMarketValue = formState?.markets.slice().sort().join(",") ?? "";
  const selectedMarketLabel =
    marketSelectOptions.find((market) => market.value === selectedMarketValue)?.label ??
    selectedMarketValue
      .split(",")
      .filter(Boolean)
      .map((market) => market.toUpperCase())
      .join(" + ") ??
    "—";
  const visibleFilterGroups = useMemo(() => {
    return (
      configOptions?.filter_preset_groups.filter(
        (group) => FILTER_GROUP_CATEGORY[group.id] === activeFilterTab
      ) ?? []
    );
  }, [activeFilterTab, configOptions]);
  const activeFilterTabNote = localizeFilterTabNote(activeFilterTab, t);
  const selectedFilterCount = useMemo(() => {
    return Object.values(formState?.filter_preset_selections ?? {}).filter(
      (value) => value !== "any"
    ).length;
  }, [formState?.filter_preset_selections]);
  const selectedRankingProfileLabel =
    (() => {
      const profile = configOptions?.ranking_profiles.find(
        (item) => item.id === formState?.ranking_profile_id
      );
      return profile ? localizeRankingProfileLabel(profile.id, profile.label, t) : null;
    })() ??
    formState?.ranking_profile_id ??
    "—";
  const selectedFilterSummaries = useMemo(
    () =>
      buildSelectedFilterSummaries(
        configOptions,
        formState?.filter_preset_selections,
        t
      ),
    [configOptions, formState?.filter_preset_selections, t]
  );
  const visibleSelectedFilterSummaries = selectedFilterSummaries.slice(0, 3);
  const hiddenSelectedFilterCount = Math.max(
    selectedFilterSummaries.length - visibleSelectedFilterSummaries.length,
    0
  );

  const updateFilterPreset = (groupId: string, value: string) => {
    if (!formState) {
      return;
    }
    markResultStale();
    setFeedback(null);
    setSelectedSavedBarId(CURRENT_SCREEN_VALUE);
    setFormState({
      ...formState,
      include_fundamentals:
        formState.include_fundamentals ||
        (FUNDAMENTAL_FILTER_GROUPS.has(groupId) && value !== "any"),
      filter_preset_selections: {
        ...(formState.filter_preset_selections ?? {}),
        [groupId]: value,
      },
    });
  };

  const loadSavedBar = (savedBarId: string) => {
    markResultStale();
    setSelectedSavedBarId(savedBarId);
    setFeedback(null);
    const savedBar = savedBars.find((item) => item.id === savedBarId);
    if (!savedBar) {
      setPresetName("");
      return;
    }
    setFormState({
      ...savedBar.config,
      filter_preset_selections: normalizeFilterPresetSelections(
        savedBar.config.filter_preset_selections
      ),
      top_k: String(savedBar.config.top_k),
    });
    setPresetName(savedBar.name);
  };

  const saveCurrentBar = () => {
    if (!formState || !configOptions) {
      return;
    }
    const validationError = validateScreenerBar(formState, t);
    if (validationError) {
      setError(validationError);
      return;
    }

    const payload = buildScreenerPayload(formState);
    const fingerprint = fingerprintScreenerPayload(payload);
    const now = new Date().toISOString();
    const marketLabel = payload.markets
      .map((market) => localizeMarketLabel(market, market.toUpperCase(), t))
      .join(" + ");
    const selectedProfile = configOptions.ranking_profiles.find(
      (profile) => profile.id === payload.ranking_profile_id
    );
    const rankingLabel = selectedProfile
      ? localizeRankingProfileLabel(selectedProfile.id, selectedProfile.label, t)
      : payload.ranking_profile_id ?? t("screenerDashboard.rankingFallback", "Ranking");
    const fallbackName = `${marketLabel || t("screenerDashboard.marketFallback", "Market")} - ${rankingLabel}`;
    const name = presetName.trim() || fallbackName;
    const existing = savedBars.find((item) => item.fingerprint === fingerprint);
    const nextSavedBar: SavedScreenerBar = existing
      ? { ...existing, name, config: payload, updated_at: now }
      : {
          id: createSavedId(),
          name,
          fingerprint,
          config: payload,
          created_at: now,
          updated_at: now,
        };
    const nextSavedBars = [
      nextSavedBar,
      ...savedBars.filter((item) => item.id !== nextSavedBar.id),
    ];

    writeSavedScreenerBars(nextSavedBars);
    setSavedBars(nextSavedBars);
    setSelectedSavedBarId(nextSavedBar.id);
    setPresetName(nextSavedBar.name);
    setError(null);
    setFeedback(t("screenerDashboard.savedBar", "Screen saved."));
    void replaceScreenerPresets(nextSavedBars)
      .then((records) => {
        const syncedBars = records.map(savedBarFromPresetRecord);
        setSavedBars(syncedBars);
        writeSavedScreenerBars(syncedBars);
      })
      .catch(() => {
        // Local persistence is still available; backend sync can retry on the next save.
      });
  };

  const runCurrentBar = async () => {
    if (!formState) {
      return;
    }
    const validationError = validateScreenerBar(formState, t);
    if (validationError) {
      setError(validationError);
      return;
    }

    setRunning(true);
    setError(null);
    setFeedback(null);
    let didNavigate = false;
    try {
      const payload = buildScreenerPayload(formState);
      writeLastScreenerBar(payload);
      const response = await createScreenerTask(payload);
      startTransition(() => {
        router.push(buildScreenerTaskHref(response.task_id));
      });
      didNavigate = true;
      void refreshScreenerTasks();
      void refreshScreenerRuns();
    } catch (submitError) {
      setError(
        submitError instanceof Error
          ? submitError.message
          : t("screener.error.createTask", "Unable to create screener task")
      );
    } finally {
      if (!didNavigate) {
        setRunning(false);
      }
    }
  };

  const controlsDisabled = loadingOptions || !configOptions || !formState;

  return (
    <main className="workbench-page-shell flex min-h-[100vh] flex-1 flex-col">
      <div className="workbench-content-frame space-y-6">
        <section className="screener-config-panel viewer-frame">
          <div className="flex flex-wrap items-center justify-between gap-3 border-b border-[var(--border)] px-4 py-3 md:px-5">
            <div className="flex min-w-0 items-center gap-3">
              <span className="flex size-9 shrink-0 items-center justify-center rounded-full border border-[var(--border)] bg-[var(--surface-strong)] text-[var(--primary)]">
                <SlidersHorizontal className="size-4" />
              </span>
              <div className="min-w-0">
                <p className="text-[11px] font-semibold uppercase tracking-[0.2em] text-[var(--primary)]">
                  {t("screenerDashboard.configPanel", "Screen Config")}
                </p>
                <div className="mt-1 flex flex-wrap gap-2 text-xs font-semibold text-slate-600">
                  <span>{selectedMarketLabel || "—"}</span>
                  <span aria-hidden="true">·</span>
                  <span className="truncate">{selectedRankingProfileLabel}</span>
                  <span aria-hidden="true">·</span>
                  <span>{t("screener.topK", "Top K")} {formState?.top_k ?? "—"}</span>
                  <span aria-hidden="true">·</span>
                  <span>
                    {selectedFilterCount}{" "}
                    {t("screenerDashboard.configSelectedSuffix", "selected")}
                  </span>
                </div>
              </div>
            </div>
            <Button
              type="button"
              variant="secondary"
              size="sm"
              aria-expanded={!isConfigCollapsed}
              onClick={() => setIsConfigCollapsed((current) => !current)}
              className="rounded-full"
            >
              <ChevronDown
                className={`size-4 transition-transform ${
                  isConfigCollapsed ? "" : "rotate-180"
                }`}
              />
              {isConfigCollapsed
                ? t("screenerDashboard.expandConfig", "Expand")
                : t("screenerDashboard.collapseConfig", "Collapse")}
            </Button>
          </div>

          {isConfigCollapsed ? (
            <div className="screener-config-summary grid gap-3 px-4 py-3 md:px-5 lg:grid-cols-[1fr_auto] lg:items-center">
              <div className="flex min-w-0 flex-wrap gap-2">
                {visibleSelectedFilterSummaries.length > 0 ? (
                  visibleSelectedFilterSummaries.map((item) => (
                    <span
                      key={item.id}
                      className="rounded-full border border-[var(--border)] bg-[var(--surface)] px-3 py-1 text-xs font-semibold text-[var(--text)]"
                    >
                      {item.label}: {item.value}
                    </span>
                  ))
                ) : (
                  <span className="rounded-full border border-dashed border-[var(--border)] px-3 py-1 text-xs font-semibold text-slate-500">
                    {t("screenerDashboard.noConfigFilters", "No active filters")}
                  </span>
                )}
                {hiddenSelectedFilterCount > 0 ? (
                  <span className="rounded-full border border-[var(--border)] bg-[var(--primary-soft)] px-3 py-1 text-xs font-semibold text-[var(--primary)]">
                    +{hiddenSelectedFilterCount}
                  </span>
                ) : null}
              </div>
              <div className="flex flex-wrap gap-2 lg:justify-end">
                <Button
                  type="button"
                  variant="secondary"
                  disabled={controlsDisabled}
                  onClick={saveCurrentBar}
                  size="sm"
                  className="rounded-full"
                >
                  <Save className="mr-2 size-4" />
                  {t("common.save", "Save")}
                </Button>
                <Button
                  type="button"
                  disabled={controlsDisabled || newScreenerDisabled || running}
                  onClick={() => void runCurrentBar()}
                  size="sm"
                  className="rounded-full"
                >
                  <Play className="mr-2 size-4" />
                  {running
                    ? t("screenerDashboard.running", "Running...")
                    : t("screenerDashboard.run", "Run")}
                </Button>
              </div>
            </div>
          ) : (
            <>
          <div className="grid gap-3 border-b border-[var(--border)] px-4 py-4 lg:grid-cols-4 xl:grid-cols-[220px_230px_170px_minmax(240px,1fr)_100px_auto_auto]">
            <label>
              <span className="mb-1 block text-xs font-semibold text-slate-600">
                {t("screenerDashboard.preset", "Preset")}
              </span>
              <Select
                value={selectedSavedBarId}
                onValueChange={loadSavedBar}
                disabled={controlsDisabled}
              >
                <SelectTrigger className={CONTROL_INPUT_CLASS}>
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value={CURRENT_SCREEN_VALUE}>
                    {t("screenerDashboard.currentScreen", "Current Screen")}
                  </SelectItem>
                  {savedBars.map((savedBar) => (
                    <SelectItem key={savedBar.id} value={savedBar.id}>
                      {savedBar.name}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </label>

            <label>
              <span className="mb-1 block text-xs font-semibold text-slate-600">
                {t("screenerDashboard.presetName", "Preset Name")}
              </span>
              <Input
                value={presetName}
                onChange={(event) => {
                  setPresetName(event.target.value);
                  setFeedback(null);
                }}
                disabled={controlsDisabled}
                placeholder={t("screenerDashboard.presetNamePlaceholder", "Name this screen")}
                className={CONTROL_INPUT_CLASS}
              />
            </label>

            <label>
              <span className="mb-1 block text-xs font-semibold text-slate-600">
                {t("screenerDashboard.market", "Market")}
              </span>
              <Select
                value={selectedMarketValue}
                onValueChange={(value) => {
                  markResultStale();
                  setSelectedSavedBarId(CURRENT_SCREEN_VALUE);
                  setFormState((current) =>
                    current ? { ...current, markets: value.split(",").filter(Boolean) } : current
                  );
                }}
                disabled={controlsDisabled || marketSelectOptions.length === 0}
              >
                <SelectTrigger className={CONTROL_INPUT_CLASS}>
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  {marketSelectOptions.map((market) => (
                    <SelectItem key={market.value} value={market.value}>
                      {market.label}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </label>

            <label>
              <span className="mb-1 block text-xs font-semibold text-slate-600">
                {t("screenerDashboard.rankingModel", "Ranking Model")}
              </span>
              <Select
                value={formState?.ranking_profile_id ?? ""}
                onValueChange={(value) => {
                  markResultStale();
                  const selectedProfile = configOptions?.ranking_profiles.find(
                    (profile) => profile.id === value
                  );
                  const usesFundamentals =
                    Number(selectedProfile?.weights.fundamental ?? 0) > 0;
                  setSelectedSavedBarId(CURRENT_SCREEN_VALUE);
                  setFormState((current) =>
                    current
                      ? {
                          ...current,
                          ranking_profile_id: value,
                          include_fundamentals:
                            current.include_fundamentals || usesFundamentals,
                        }
                      : current
                  );
                }}
                disabled={controlsDisabled}
              >
                <SelectTrigger className={CONTROL_INPUT_CLASS}>
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  {configOptions?.ranking_profiles.map((profile) => (
                    <SelectItem key={profile.id} value={profile.id}>
                      {localizeRankingProfileLabel(profile.id, profile.label, t)}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </label>

            <label>
              <span className="mb-1 block text-xs font-semibold text-slate-600">
                {t("screener.topK", "Top K")}
              </span>
              <Input
                type="number"
                min={1}
                max={TOP_K_LIMIT}
                value={formState?.top_k ?? ""}
                onChange={(event) => {
                  markResultStale();
                  setSelectedSavedBarId(CURRENT_SCREEN_VALUE);
                  setFormState((current) =>
                    current ? { ...current, top_k: event.target.value } : current
                  );
                }}
                disabled={controlsDisabled}
                className={CONTROL_INPUT_CLASS}
              />
            </label>

            <Button
              type="button"
              variant="secondary"
              disabled={controlsDisabled}
              onClick={saveCurrentBar}
              className="mt-5 h-9 rounded-full"
            >
              <Save className="mr-2 size-4" />
              {t("common.save", "Save")}
            </Button>
            <Button
              type="button"
              disabled={controlsDisabled || newScreenerDisabled || running}
              onClick={() => void runCurrentBar()}
              className="mt-5 h-9 rounded-full"
            >
              <Play className="mr-2 size-4" />
              {running
                ? t("screenerDashboard.running", "Running...")
                : t("screenerDashboard.run", "Run")}
            </Button>
          </div>

          <div className="flex flex-wrap justify-center border-b border-[var(--border)] bg-[var(--surface-quiet)]/55">
            {filterTabs.map((tab) => (
              <button
                key={tab.id}
                type="button"
                onClick={() => setActiveFilterTab(tab.id)}
                className={`h-9 border-r border-[var(--border)] px-4 text-sm font-semibold transition ${
                  activeFilterTab === tab.id
                    ? "bg-[var(--surface)] text-[var(--text)] shadow-[inset_0_-2px_0_var(--primary)]"
                    : "text-slate-600 hover:bg-[color:var(--surface-hover)] hover:text-[var(--text)]"
                }`}
              >
                {localizeFilterTabLabel(tab.id, t)}
              </button>
            ))}
          </div>

          <div className="space-y-3 px-3 py-4">
            <div className="flex flex-wrap items-center justify-between gap-3 text-sm font-medium text-slate-600">
              <p>{activeFilterTabNote}</p>
              <span className="rounded-full border border-[var(--border)] bg-[var(--surface)] px-3 py-1 text-xs font-semibold text-[var(--text)]">
                {t("screenerDashboard.selectedCount", ({ count }) => `${count} selected`, {
                  count: selectedFilterCount,
                })}
              </span>
            </div>
            {loadingOptions ? (
              <div className="flex items-center gap-2 text-sm font-medium text-slate-600">
                <RefreshCw className="size-4 animate-spin" />
                {t("screener.loadingOptions", "Loading screener options...")}
              </div>
            ) : null}
            <div className="grid gap-x-8 gap-y-3 border-t border-[var(--border)] pt-3 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4">
              {visibleFilterGroups.map((group) => (
                <label
                  key={group.id}
                  className="grid grid-cols-[minmax(76px,max-content)_minmax(0,1fr)] items-center gap-2"
                >
                  <span className="truncate text-right text-sm font-semibold text-[var(--text)]">
                    {localizeFilterGroupLabel(group.id, group.label, t)}
                  </span>
                  <Select
                    value={formState?.filter_preset_selections?.[group.id] ?? "any"}
                    onValueChange={(value) => updateFilterPreset(group.id, value)}
                    disabled={controlsDisabled}
                  >
                    <SelectTrigger className={COMPACT_SELECT_CLASS}>
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      {group.options.map((option) => (
                        <SelectItem key={option.value} value={option.value}>
                          {localizeFilterOptionLabel(group.id, option.value, option.label, t)}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </label>
              ))}
            </div>
          </div>

            </>
          )}

          {error || feedback || firstActiveScreenerTask ? (
            <div className="flex flex-wrap items-center justify-between gap-3 border-t border-[var(--border)] px-4 py-3 text-sm">
              <div>
                {error ? <span className="font-semibold text-[var(--danger)]">{error}</span> : null}
                {feedback ? (
                  <span className="font-semibold text-[var(--success)]">{feedback}</span>
                ) : null}
              </div>
              {firstActiveScreenerTask ? (
                <Link
                  href={buildScreenerTaskHref(firstActiveScreenerTask.id)}
                  className="font-semibold text-[var(--primary)]"
                >
                  {t("screenerDashboard.activeTask", "Active screener task")}
                </Link>
              ) : null}
            </div>
          ) : null}
        </section>

        {displayedRunId && resultStale ? (
          <div className="flex flex-wrap items-center justify-between gap-3 rounded-[24px] border border-[var(--border)] bg-[var(--accent-soft)] px-4 py-3 text-sm text-[var(--text)] shadow-[var(--button-secondary-shadow)]">
            <div>
              <p className="font-semibold">
                {t("screenerDashboard.staleResultTitle", "Screen changed")}
              </p>
              <p className="mt-1">
                {t(
                  "screenerDashboard.staleResultBody",
                  "The results below are from the previous run. Run again to refresh them with the current filters."
                )}
              </p>
            </div>
            <Button
              type="button"
              variant="secondary"
              size="sm"
              onClick={dismissSelectedRun}
            >
              {t("screenerDashboard.staleResultDismiss", "Hide previous result")}
            </Button>
          </div>
        ) : null}

        {displayedRunId ? (
          <ScreenerResultsViewer runId={displayedRunId} embedded />
        ) : (
          <ScreenerResultPlaceholder
            activeTaskId={firstActiveScreenerTask?.id ?? null}
            marketLabel={selectedMarketLabel || "—"}
            selectedFilterCount={selectedFilterCount}
            topK={formState?.top_k ?? "—"}
          />
        )}
      </div>
    </main>
  );
}

interface ScreenerResultPlaceholderProps {
  activeTaskId: string | null;
  marketLabel: string;
  selectedFilterCount: number;
  topK: string;
}

function ScreenerResultPlaceholder({
  activeTaskId,
  marketLabel,
  selectedFilterCount,
  topK,
}: ScreenerResultPlaceholderProps) {
  const { t } = usePreferences();
  const isRunning = Boolean(activeTaskId);

  return (
    <section className="viewer-frame">
      <div className="flex flex-wrap items-start justify-between gap-4 border-b border-[var(--border)] px-4 py-4 md:px-6">
        <div>
          <p className="text-xs font-semibold uppercase tracking-[0.22em] text-[var(--primary)]">
            {t("screenerDashboard.resultSlot", "Screener Results")}
          </p>
          <h2 className="workbench-section-title mt-2 text-2xl">
            {isRunning
              ? t("screenerDashboard.placeholderRunningTitle", "Building candidate pool")
              : t("screenerDashboard.placeholderReadyTitle", "Ready for a run")}
          </h2>
        </div>
        {activeTaskId ? (
          <Button
            asChild
            variant="secondary"
            size="sm"
          >
            <Link href={buildScreenerTaskHref(activeTaskId)}>
              {t("screenerDashboard.placeholderOpenTask", "Open task")}
            </Link>
          </Button>
        ) : null}
      </div>

      <div className="grid gap-3 px-4 py-4 md:grid-cols-3">
        <PlaceholderMetric
          label={t("screenerDashboard.placeholderMarket", "Market")}
          value={marketLabel}
        />
        <PlaceholderMetric
          label={t("screenerDashboard.placeholderFilters", "Filters")}
          value={String(selectedFilterCount)}
        />
        <PlaceholderMetric
          label={t("screenerDashboard.placeholderTopK", "Top K")}
          value={topK}
        />
      </div>

      <div className="px-4 pb-4">
        <div className="grid min-h-40 gap-3 rounded-[24px] border border-dashed border-[var(--border-strong)] bg-[var(--surface-strong)]/70 p-4 md:grid-cols-3">
          {["total", "trend", "pattern"].map((item) => (
            <div key={item} className="rounded-2xl border border-[var(--border)] bg-[var(--surface)] p-4">
              <div className="h-2 w-16 rounded-full bg-[var(--surface-quiet)]" />
              <div className="mt-5 h-7 w-24 rounded-full bg-[var(--primary-soft)]" />
              <div className="mt-4 space-y-2">
                <div className="h-2 rounded-full bg-[var(--primary-soft)]" />
                <div className="h-2 w-2/3 rounded-full bg-[var(--primary-soft)]" />
              </div>
            </div>
          ))}
        </div>
      </div>
    </section>
  );
}

function PlaceholderMetric({ label, value }: { label: string; value: string }) {
  return (
    <div className="metric-card px-4 py-3">
      <p className="text-[11px] font-semibold uppercase tracking-[0.18em] text-slate-500">
        {label}
      </p>
      <p className="metric-card-value mt-2 text-xl font-semibold text-[var(--text)]">
        {value || "—"}
      </p>
    </div>
  );
}
