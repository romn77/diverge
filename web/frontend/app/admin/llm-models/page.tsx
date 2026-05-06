"use client";

import { useEffect, useMemo, useState, type ReactNode } from "react";
import { RefreshCw, Save } from "lucide-react";

import {
  AdminConsolePage,
  AdminNotice,
  AdminPanel,
} from "@/components/admin/AdminConsolePage";
import { Badge } from "@/components/ui/badge";
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
  listAdminLLMModels,
  updateAdminLLMModel,
  updateAdminLLMModuleSetting,
  updateAdminLLMProfileRoutes,
  updateAdminLLMProvider,
  type AdminLLMModel,
  type AdminLLMModuleSetting,
  type AdminLLMModelsResponse,
  type AdminLLMProfile,
  type AdminLLMProvider,
  type UserRole,
} from "@/lib/api";

const ROLE_OPTIONS: UserRole[] = ["admin", "operator", "viewer"];
const CUSTOM_PROFILE_ID = "custom";

type ModuleDraft = {
  enabled: boolean;
  model_profile: string;
  output_language: string;
  custom_provider: string;
  custom_model: string;
  openai_reasoning_effort: string;
  google_thinking_level: string;
};

const MODULE_OUTPUT_LANGUAGE_OPTIONS = [
  { value: "cn", label: "Chinese (cn)" },
  { value: "en", label: "English (en)" },
];

const OPENAI_REASONING_OPTIONS = [
  { value: "low", label: "low" },
  { value: "medium", label: "medium" },
  { value: "high", label: "high" },
];

const GOOGLE_THINKING_OPTIONS = [
  { value: "minimal", label: "minimal" },
  { value: "high", label: "high" },
];

function limitDraft(value: number | null): string {
  return value === null ? "" : String(value);
}

function parseLimit(value: string): number | null {
  const trimmed = value.trim();
  if (!trimmed) {
    return null;
  }
  const parsed = Number(trimmed);
  if (!Number.isInteger(parsed) || parsed < 0) {
    throw new Error("Limits must be whole numbers or blank.");
  }
  return parsed;
}

function routeDraft(profile: AdminLLMProfile): string {
  return profile.routes
    .map((route) => `${route.provider}:${route.quick_model}:${route.deep_model}`)
    .join("\n");
}

function parseRouteDraft(value: string) {
  return value
    .split("\n")
    .map((line) => line.trim())
    .filter(Boolean)
    .map((line) => {
      const [provider, quick_model, ...deepParts] = line.split(":");
      return {
        provider: provider?.trim().toLowerCase() ?? "",
        quick_model: quick_model?.trim() ?? "",
        deep_model: deepParts.join(":").trim(),
      };
    });
}

export default function AdminLLMModelsPage() {
  const [payload, setPayload] = useState<AdminLLMModelsResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [providerDrafts, setProviderDrafts] = useState<Record<string, { enabled: boolean; base_url: string; daily_limit: string; hourly_limit: string }>>({});
  const [modelDrafts, setModelDrafts] = useState<Record<string, { enabled: boolean; cost_tier: string; visible_to_roles: string; daily_limit: string; weekly_limit: string }>>({});
  const [routeDrafts, setRouteDrafts] = useState<Record<string, string>>({});
  const [moduleDrafts, setModuleDrafts] = useState<Record<string, ModuleDraft>>({});

  const modelsByProvider = useMemo(() => {
    const grouped: Record<string, AdminLLMModel[]> = {};
    for (const model of payload?.models ?? []) {
      grouped[model.provider] = [...(grouped[model.provider] ?? []), model];
    }
    return grouped;
  }, [payload]);

  const load = async () => {
    setLoading(true);
    setError(null);
    try {
      const nextPayload = await listAdminLLMModels();
      setPayload(nextPayload);
      setProviderDrafts(Object.fromEntries(nextPayload.providers.map((provider) => [
        provider.provider,
        {
          enabled: provider.enabled,
          base_url: provider.base_url,
          daily_limit: limitDraft(provider.daily_limit),
          hourly_limit: limitDraft(provider.hourly_limit),
        },
      ])));
      setModelDrafts(Object.fromEntries(nextPayload.models.map((model) => [
        model.id,
        {
          enabled: model.enabled,
          cost_tier: model.cost_tier,
          visible_to_roles: model.visible_to_roles,
          daily_limit: limitDraft(model.daily_limit),
          weekly_limit: limitDraft(model.weekly_limit),
        },
      ])));
      setRouteDrafts(Object.fromEntries(nextPayload.profiles.map((profile) => [
        profile.profile_id,
        routeDraft(profile),
      ])));
      setModuleDrafts(Object.fromEntries((nextPayload.module_settings ?? []).map((setting) => [
        setting.module,
        {
          enabled: setting.enabled,
          model_profile: setting.model_profile,
          output_language: setting.output_language,
          custom_provider: setting.custom_provider ?? nextPayload.providers.find((provider) => provider.enabled)?.provider ?? "",
          custom_model: setting.custom_model ?? "",
          openai_reasoning_effort: setting.openai_reasoning_effort ?? "",
          google_thinking_level: setting.google_thinking_level ?? "",
        },
      ])));
    } catch (nextError) {
      setError(nextError instanceof Error ? nextError.message : "Unable to load LLM models.");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    void load();
  }, []);

  const saveProvider = async (provider: AdminLLMProvider) => {
    const draft = providerDrafts[provider.provider];
    if (!draft) {
      return;
    }
    setSaving(`provider:${provider.provider}`);
    try {
      await updateAdminLLMProvider(provider.provider, {
        enabled: draft.enabled,
        base_url: draft.base_url,
        daily_limit: parseLimit(draft.daily_limit),
        hourly_limit: parseLimit(draft.hourly_limit),
      });
      await load();
    } catch (nextError) {
      setError(nextError instanceof Error ? nextError.message : "Unable to save provider.");
    } finally {
      setSaving(null);
    }
  };

  const saveModel = async (model: AdminLLMModel) => {
    const draft = modelDrafts[model.id];
    if (!draft) {
      return;
    }
    setSaving(`model:${model.id}`);
    try {
      await updateAdminLLMModel(model.provider, model.model_id, {
        enabled: draft.enabled,
        cost_tier: draft.cost_tier,
        visible_to_roles: draft.visible_to_roles
          .split(",")
          .map((role) => role.trim())
          .filter((role): role is UserRole => ROLE_OPTIONS.includes(role as UserRole)),
        daily_limit: parseLimit(draft.daily_limit),
        weekly_limit: parseLimit(draft.weekly_limit),
      });
      await load();
    } catch (nextError) {
      setError(nextError instanceof Error ? nextError.message : "Unable to save model.");
    } finally {
      setSaving(null);
    }
  };

  const saveRoutes = async (profile: AdminLLMProfile) => {
    setSaving(`profile:${profile.profile_id}`);
    try {
      await updateAdminLLMProfileRoutes(profile.profile_id, {
        routes: parseRouteDraft(routeDrafts[profile.profile_id] ?? ""),
      });
      await load();
    } catch (nextError) {
      setError(nextError instanceof Error ? nextError.message : "Unable to save profile routes.");
    } finally {
      setSaving(null);
    }
  };

  const saveModuleSetting = async (setting: AdminLLMModuleSetting) => {
    const draft = moduleDrafts[setting.module];
    if (!draft) {
      return;
    }
    setSaving(`module:${setting.module}`);
    try {
      await updateAdminLLMModuleSetting(setting.module, {
        enabled: draft.enabled,
        model_profile: draft.model_profile,
        output_language: draft.output_language,
        custom_provider: draft.model_profile === "custom" ? draft.custom_provider : null,
        custom_model: draft.model_profile === "custom" ? draft.custom_model : null,
        openai_reasoning_effort: draft.openai_reasoning_effort.trim() || null,
        google_thinking_level: draft.google_thinking_level.trim() || null,
      });
      await load();
    } catch (nextError) {
      setError(nextError instanceof Error ? nextError.message : "Unable to save module setting.");
    } finally {
      setSaving(null);
    }
  };

  return (
    <AdminConsolePage
      activeTab="llm-models"
      title="LLM Models"
      description="Manage provider availability, per-model visibility, quota limits, and profile routing."
      actions={
        <Button type="button" variant="secondary" size="sm" onClick={() => void load()}>
          <RefreshCw className="h-4 w-4" />
          Refresh
        </Button>
      }
    >

        {error ? (
          <AdminNotice>{error}</AdminNotice>
        ) : null}

        <section className="grid gap-3 lg:grid-cols-3">
          {(payload?.providers ?? []).map((provider) => {
            const draft = providerDrafts[provider.provider];
            return (
              <AdminPanel key={provider.provider} contentClassName="space-y-3 p-4">
                  <div className="flex items-start justify-between gap-3">
                    <div>
                      <h2 className="font-semibold">{provider.label}</h2>
                      <p className="mt-1 text-xs text-slate-500">{provider.api_key_env ?? "No key required"}</p>
                    </div>
                    <Badge variant={provider.key_status === "configured" ? "default" : "secondary"}>
                      {provider.key_status}
                    </Badge>
                  </div>
                  {draft ? (
                    <>
                      <label className="flex items-center gap-2 text-sm">
                        <input
                          type="checkbox"
                          checked={draft.enabled}
                          onChange={(event) => setProviderDrafts((current) => ({
                            ...current,
                            [provider.provider]: { ...draft, enabled: event.target.checked },
                          }))}
                        />
                        Enabled
                      </label>
                      <Input
                        value={draft.base_url}
                        onChange={(event) => setProviderDrafts((current) => ({
                          ...current,
                          [provider.provider]: { ...draft, base_url: event.target.value },
                        }))}
                      />
                      <div className="grid gap-3 sm:grid-cols-2">
                        <Input
                          placeholder="Daily limit"
                          value={draft.daily_limit}
                          onChange={(event) => setProviderDrafts((current) => ({
                            ...current,
                            [provider.provider]: { ...draft, daily_limit: event.target.value },
                          }))}
                        />
                        <Input
                          placeholder="Hourly limit"
                          value={draft.hourly_limit}
                          onChange={(event) => setProviderDrafts((current) => ({
                            ...current,
                            [provider.provider]: { ...draft, hourly_limit: event.target.value },
                          }))}
                        />
                      </div>
                      <Button
                        type="button"
                        size="sm"
                        disabled={saving === `provider:${provider.provider}`}
                        onClick={() => void saveProvider(provider)}
                      >
                        <Save className="h-4 w-4" />
                        Save
                      </Button>
                    </>
                  ) : null}
              </AdminPanel>
            );
          })}
        </section>

        <section className="space-y-3">
          <h2 className="text-lg font-semibold">Module Defaults</h2>
          <div className="grid gap-3 lg:grid-cols-2">
            {(payload?.module_settings ?? []).map((setting) => {
              const draft = moduleDrafts[setting.module];
              return (
                <ModuleSettingCard
                  key={setting.module}
                  draft={draft}
                  moduleSetting={setting}
                  profiles={payload?.profiles ?? []}
                  providers={payload?.providers ?? []}
                  models={payload?.models ?? []}
                  saving={saving === `module:${setting.module}`}
                  onDraftChange={(nextDraft) =>
                    setModuleDrafts((current) => ({
                      ...current,
                      [setting.module]: nextDraft,
                    }))
                  }
                  onSave={() => void saveModuleSetting(setting)}
                />
              );
            })}
          </div>
        </section>

        <section className="space-y-3">
          <h2 className="text-lg font-semibold">Profiles</h2>
          <div className="grid gap-3 lg:grid-cols-3">
            {(payload?.profiles ?? []).map((profile) => (
              <AdminPanel key={profile.profile_id} contentClassName="space-y-3 p-4">
                  <div>
                    <h3 className="font-semibold">{profile.label}</h3>
                    <p className="mt-1 text-sm text-slate-500">{profile.description}</p>
                  </div>
                  <textarea
                    className="min-h-[104px] w-full rounded-[12px] border border-[var(--border)] bg-white px-3 py-2 text-sm"
                    value={routeDrafts[profile.profile_id] ?? ""}
                    onChange={(event) => setRouteDrafts((current) => ({
                      ...current,
                      [profile.profile_id]: event.target.value,
                    }))}
                  />
                  <Button
                    type="button"
                    size="sm"
                    disabled={saving === `profile:${profile.profile_id}`}
                    onClick={() => void saveRoutes(profile)}
                  >
                    <Save className="h-4 w-4" />
                    Save Routes
                  </Button>
              </AdminPanel>
            ))}
          </div>
        </section>

        <section className="space-y-3">
          <h2 className="text-lg font-semibold">Models</h2>
          {Object.entries(modelsByProvider).map(([provider, models]) => (
            <AdminPanel key={provider} contentClassName="space-y-3 p-4">
                <h3 className="font-semibold">{provider}</h3>
                <div className="grid gap-3">
                  {models.slice(0, 12).map((model) => {
                    const draft = modelDrafts[model.id];
                    return (
                      <div key={model.id} className="grid gap-3 rounded-[12px] border border-[var(--border)] p-3 lg:grid-cols-[1fr_120px_160px_120px_120px_auto]">
                        <div>
                          <p className="text-sm font-semibold">{model.label}</p>
                          <p className="text-xs text-slate-500">{model.model_id}</p>
                          <p className="mt-1 text-xs text-slate-500">Used today: {model.used_today}</p>
                        </div>
                        {draft ? (
                          <>
                            <label className="flex items-center gap-2 text-sm">
                              <input
                                type="checkbox"
                                checked={draft.enabled}
                                onChange={(event) => setModelDrafts((current) => ({
                                  ...current,
                                  [model.id]: { ...draft, enabled: event.target.checked },
                                }))}
                              />
                              Enabled
                            </label>
                            <Input
                              value={draft.cost_tier}
                              onChange={(event) => setModelDrafts((current) => ({
                                ...current,
                                [model.id]: { ...draft, cost_tier: event.target.value },
                              }))}
                            />
                            <Input
                              placeholder="Daily"
                              value={draft.daily_limit}
                              onChange={(event) => setModelDrafts((current) => ({
                                ...current,
                                [model.id]: { ...draft, daily_limit: event.target.value },
                              }))}
                            />
                            <Input
                              placeholder="Weekly"
                              value={draft.weekly_limit}
                              onChange={(event) => setModelDrafts((current) => ({
                                ...current,
                                [model.id]: { ...draft, weekly_limit: event.target.value },
                              }))}
                            />
                            <Button
                              type="button"
                              size="sm"
                              disabled={saving === `model:${model.id}`}
                              onClick={() => void saveModel(model)}
                            >
                              Save
                            </Button>
                          </>
                        ) : null}
                      </div>
                    );
                  })}
                </div>
            </AdminPanel>
          ))}
        </section>

        {loading ? <p className="text-sm text-slate-500">Loading model configuration...</p> : null}
    </AdminConsolePage>
  );
}

function ModuleSettingCard({
  draft,
  moduleSetting,
  profiles,
  providers,
  models,
  saving,
  onDraftChange,
  onSave,
}: {
  draft: ModuleDraft | undefined;
  moduleSetting: AdminLLMModuleSetting;
  profiles: AdminLLMProfile[];
  providers: AdminLLMProvider[];
  models: AdminLLMModel[];
  saving: boolean;
  onDraftChange: (draft: ModuleDraft) => void;
  onSave: () => void;
}) {
  if (!draft) {
    return null;
  }

  const profileOptions = [
    ...profiles,
    {
      profile_id: CUSTOM_PROFILE_ID,
      label: "Custom",
      description: "Choose a configured provider and concrete review model manually.",
      enabled: true,
      default_for_roles: "",
      sort_order: 999,
      routes: [],
    },
  ];
  const enabledProviders = providers.filter(
    (provider) => provider.enabled && provider.key_status === "configured"
  );
  const isCustomModelProfile = draft.model_profile === CUSTOM_PROFILE_ID;
  const selectedProfile = profileOptions.find(
    (profile) => profile.profile_id === draft.model_profile
  );
  const selectedProvider = isCustomModelProfile
    ? draft.custom_provider
    : selectedProfile?.routes.find((route) => route.available)?.provider ?? "";
  const selectedProviderLabel =
    providers.find((provider) => provider.provider === selectedProvider)?.label ??
    selectedProvider;
  const selectedCustomModels = getEnabledDeepModels(models, draft.custom_provider);

  const updateDraft = (patch: Partial<ModuleDraft>) => {
    onDraftChange({
      ...draft,
      ...patch,
    });
  };
  const updateProfile = (profileId: string) => {
    if (profileId === CUSTOM_PROFILE_ID) {
      const fallbackProvider =
        draft.custom_provider || enabledProviders[0]?.provider || "";
      const fallbackModel =
        draft.custom_model ||
        getEnabledDeepModels(models, fallbackProvider)[0]?.model_id ||
        "";
      updateDraft({
        model_profile: CUSTOM_PROFILE_ID,
        custom_provider: fallbackProvider,
        custom_model: fallbackModel,
      });
      return;
    }

    updateDraft({ model_profile: profileId });
  };
  const updateProvider = (provider: string) => {
    updateDraft({
      custom_provider: provider,
      custom_model: getEnabledDeepModels(models, provider)[0]?.model_id ?? "",
    });
  };

  return (
    <AdminPanel contentClassName="space-y-5 p-5">
      <div>
        <h3 className="text-lg font-semibold">{moduleSetting.label}</h3>
        <p className="mt-1 text-sm leading-6 text-slate-500">
          {moduleSetting.description}
        </p>
      </div>

      <label className="flex items-center gap-3 text-sm font-medium text-slate-700">
        <input
          type="checkbox"
          checked={draft.enabled}
          className="h-4 w-4"
          onChange={(event) => updateDraft({ enabled: event.target.checked })}
        />
        Auto-generate after journal saves
      </label>

      <section className="rounded-3xl border border-[var(--border)] bg-white/90 p-4">
        <p className="text-sm font-semibold text-[var(--text-primary)]">
          Model Profile
        </p>
        <div className="mt-3 grid gap-3 md:grid-cols-2 xl:grid-cols-4">
          {profileOptions.map((profile) => {
            const active = draft.model_profile === profile.profile_id;
            const disabled = !profile.enabled;
            return (
              <Button
                key={profile.profile_id}
                type="button"
                variant={active ? "default" : "secondary"}
                disabled={disabled}
                className={`h-auto min-h-[116px] w-full flex-col items-stretch justify-start overflow-hidden rounded-[20px] p-4 text-left whitespace-normal ${
                  active
                    ? "bg-[var(--accent)] text-white hover:bg-[var(--accent)] hover:brightness-105"
                    : "text-slate-600"
                }`}
                onClick={() => updateProfile(profile.profile_id)}
              >
                <span className="min-w-0 text-sm font-semibold">
                  {profile.label}
                </span>
                <span className="mt-2 min-w-0 break-words text-xs leading-5">
                  {profile.description}
                </span>
              </Button>
            );
          })}
        </div>
      </section>

      <section className="grid gap-4 rounded-3xl border border-[var(--border)] bg-white/90 p-4 md:grid-cols-2">
        {isCustomModelProfile ? (
          <ModuleSelectField
            label="LLM Provider"
            value={draft.custom_provider}
            onChange={updateProvider}
            hint={
              enabledProviders.length > 0
                ? "Only providers with configured API keys are shown."
                : "No configured LLM providers are available."
            }
          >
            {enabledProviders.map((provider) => (
              <SelectItem key={provider.provider} value={provider.provider}>
                {provider.label}
              </SelectItem>
            ))}
          </ModuleSelectField>
        ) : (
          <div>
            <p className="text-xs font-semibold uppercase tracking-[0.24em] text-slate-500">
              Routed Provider
            </p>
            <p className="mt-3 rounded-2xl border border-[var(--border)] bg-[var(--surface-strong)] px-4 py-3 text-sm font-semibold text-slate-900">
              {selectedProviderLabel || "Profile route"}
            </p>
          </div>
        )}

        <ModuleSelectField
          label="Output Language"
          value={draft.output_language}
          onChange={(value) => updateDraft({ output_language: value })}
        >
          {MODULE_OUTPUT_LANGUAGE_OPTIONS.map((language) => (
            <SelectItem key={language.value} value={language.value}>
              {language.label}
            </SelectItem>
          ))}
        </ModuleSelectField>

        {isCustomModelProfile ? (
          <ModuleSelectField
            label="Review Model"
            value={draft.custom_model}
            onChange={(value) => updateDraft({ custom_model: value })}
            hint="Trade journal reviews use the selected model for coach-style entry and exit review generation."
          >
            {selectedCustomModels.length === 0 ? (
              <SelectItem value="__none" disabled>
                No enabled review models
              </SelectItem>
            ) : null}
            {selectedCustomModels.map((model) => (
              <SelectItem key={model.id} value={model.model_id}>
                {model.label}
              </SelectItem>
            ))}
          </ModuleSelectField>
        ) : null}
      </section>

      {selectedProvider === "openai" ? (
        <ModuleSelectField
          label="OpenAI Reasoning Effort"
          value={draft.openai_reasoning_effort || "medium"}
          onChange={(value) => updateDraft({ openai_reasoning_effort: value })}
          className="rounded-3xl border border-[var(--border)] bg-white/90 p-4"
        >
          {OPENAI_REASONING_OPTIONS.map((option) => (
            <SelectItem key={option.value} value={option.value}>
              {option.label}
            </SelectItem>
          ))}
        </ModuleSelectField>
      ) : null}

      {selectedProvider === "google" ? (
        <ModuleSelectField
          label="Google Thinking Level"
          value={draft.google_thinking_level || "high"}
          onChange={(value) => updateDraft({ google_thinking_level: value })}
          className="rounded-3xl border border-[var(--border)] bg-white/90 p-4"
        >
          {GOOGLE_THINKING_OPTIONS.map((option) => (
            <SelectItem key={option.value} value={option.value}>
              {option.label}
            </SelectItem>
          ))}
        </ModuleSelectField>
      ) : null}

      <Button
        type="button"
        disabled={
          saving ||
          (isCustomModelProfile &&
            (!draft.custom_provider ||
              !draft.custom_model ||
              draft.custom_model === "__none"))
        }
        onClick={onSave}
      >
        <Save className="h-4 w-4" />
        Save Module Default
      </Button>
    </AdminPanel>
  );
}

function ModuleSelectField({
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

function getEnabledDeepModels(
  models: AdminLLMModel[],
  provider: string
): AdminLLMModel[] {
  return models.filter(
    (model) =>
      model.provider === provider &&
      model.enabled &&
      model.supports_deep
  );
}
