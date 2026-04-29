"use client";

import { useEffect, useMemo, useState } from "react";
import Link from "next/link";
import { RefreshCw, Save } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import {
  listAdminLLMModels,
  updateAdminLLMModel,
  updateAdminLLMProfileRoutes,
  updateAdminLLMProvider,
  type AdminLLMModel,
  type AdminLLMModelsResponse,
  type AdminLLMProfile,
  type AdminLLMProvider,
  type UserRole,
} from "@/lib/api";

const ROLE_OPTIONS: UserRole[] = ["admin", "operator", "viewer"];

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

  return (
    <main className="min-h-screen bg-[var(--page-bg)] px-4 py-8 text-[var(--text-primary)] sm:px-6 lg:px-8">
      <div className="mx-auto flex max-w-7xl flex-col gap-6">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div>
            <p className="text-sm font-semibold uppercase tracking-[0.24em] text-slate-500">
              Admin
            </p>
            <h1 className="mt-2 text-3xl font-semibold">LLM Models</h1>
            <div className="mt-4 flex flex-wrap gap-2">
              <Button asChild type="button" size="sm" variant="secondary">
                <Link href="/admin/users">User Management</Link>
              </Button>
              <Button asChild type="button" size="sm" variant="secondary">
                <Link href="/admin/data-sources">Data Sources</Link>
              </Button>
              <Button asChild type="button" size="sm" variant="secondary">
                <Link href="/admin/task-queue">Task Queue</Link>
              </Button>
              <Button asChild type="button" size="sm" variant="secondary">
                <Link href="/admin/audit">Audit Log</Link>
              </Button>
            </div>
          </div>
          <Button type="button" variant="secondary" onClick={() => void load()}>
            <RefreshCw className="h-4 w-4" />
            Refresh
          </Button>
        </div>

        {error ? (
          <div className="rounded-2xl border border-[rgba(163,53,53,0.2)] bg-[rgba(163,53,53,0.08)] px-4 py-3 text-sm text-[var(--danger)]">
            {error}
          </div>
        ) : null}

        <section className="grid gap-4 lg:grid-cols-3">
          {(payload?.providers ?? []).map((provider) => {
            const draft = providerDrafts[provider.provider];
            return (
              <Card key={provider.provider}>
                <CardContent className="space-y-4 p-5">
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
                        disabled={saving === `provider:${provider.provider}`}
                        onClick={() => void saveProvider(provider)}
                      >
                        <Save className="h-4 w-4" />
                        Save
                      </Button>
                    </>
                  ) : null}
                </CardContent>
              </Card>
            );
          })}
        </section>

        <section className="space-y-4">
          <h2 className="text-xl font-semibold">Profiles</h2>
          <div className="grid gap-4 lg:grid-cols-3">
            {(payload?.profiles ?? []).map((profile) => (
              <Card key={profile.profile_id}>
                <CardContent className="space-y-4 p-5">
                  <div>
                    <h3 className="font-semibold">{profile.label}</h3>
                    <p className="mt-1 text-sm text-slate-500">{profile.description}</p>
                  </div>
                  <textarea
                    className="min-h-[120px] w-full rounded-xl border border-[var(--border)] bg-white px-3 py-2 text-sm"
                    value={routeDrafts[profile.profile_id] ?? ""}
                    onChange={(event) => setRouteDrafts((current) => ({
                      ...current,
                      [profile.profile_id]: event.target.value,
                    }))}
                  />
                  <Button
                    type="button"
                    disabled={saving === `profile:${profile.profile_id}`}
                    onClick={() => void saveRoutes(profile)}
                  >
                    <Save className="h-4 w-4" />
                    Save Routes
                  </Button>
                </CardContent>
              </Card>
            ))}
          </div>
        </section>

        <section className="space-y-4">
          <h2 className="text-xl font-semibold">Models</h2>
          {Object.entries(modelsByProvider).map(([provider, models]) => (
            <Card key={provider}>
              <CardContent className="space-y-3 p-5">
                <h3 className="font-semibold">{provider}</h3>
                <div className="grid gap-3">
                  {models.slice(0, 12).map((model) => {
                    const draft = modelDrafts[model.id];
                    return (
                      <div key={model.id} className="grid gap-3 rounded-2xl border border-[var(--border)] p-3 lg:grid-cols-[1fr_120px_160px_120px_120px_auto]">
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
              </CardContent>
            </Card>
          ))}
        </section>

        {loading ? <p className="text-sm text-slate-500">Loading model configuration...</p> : null}
      </div>
    </main>
  );
}
