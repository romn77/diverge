"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { useRouter } from "next/navigation";
import {
  KeyRound,
  Power,
  PowerOff,
  RefreshCw,
  RotateCcw,
  Save,
  ShieldAlert,
} from "lucide-react";

import { useAuth } from "@/components/AuthProvider";
import {
  AdminConsolePage,
  AdminMetricCard,
  AdminMetricGrid,
  AdminNotice,
  AdminPanel,
} from "@/components/admin/AdminConsolePage";
import { StatusPanel } from "@/components/workbench/StatusPanel";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import {
  ApiError,
  getAdminSearchQuota,
  reactivateAdminSearchProvider,
  resetAdminSearchProviderUsage,
  updateAdminSearchGlobal,
  updateAdminSearchProvider,
  type AdminSearchProviderName,
  type AdminSearchQuotaProvider,
} from "@/lib/api";

function createQuotaDrafts(
  providers: AdminSearchQuotaProvider[],
  field: "monthly_free_quota" | "monthly_hard_cap"
): Record<string, string> {
  return Object.fromEntries(
    providers.map((provider) => [provider.provider, String(provider[field])])
  );
}

function parseQuotaDraft(value: string, label: string): number {
  const parsed = Number(value.trim());
  if (!Number.isInteger(parsed) || parsed < 0) {
    throw new Error(`${label} must be a non-negative whole number.`);
  }
  return parsed;
}

function formatDateTime(value: string | null): string {
  return value ?? "Never";
}

function mergeProvider(
  providers: AdminSearchQuotaProvider[],
  updated: AdminSearchQuotaProvider
): AdminSearchQuotaProvider[] {
  return providers.map((provider) =>
    provider.provider === updated.provider ? updated : provider
  );
}

export default function AdminSearchQuotaPage() {
  const router = useRouter();
  const { authState, authStatus, refreshSession } = useAuth();
  const [providers, setProviders] = useState<AdminSearchQuotaProvider[]>([]);
  const [usageMonth, setUsageMonth] = useState("");
  const [globalEnabled, setGlobalEnabled] = useState(false);
  const [globalDisabledReason, setGlobalDisabledReason] = useState<string | null>(null);
  const [freeQuotaDrafts, setFreeQuotaDrafts] = useState<Record<string, string>>({});
  const [hardCapDrafts, setHardCapDrafts] = useState<Record<string, string>>({});
  const [loading, setLoading] = useState(true);
  const [pageError, setPageError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [mutatingProvider, setMutatingProvider] = useState<string | null>(null);
  const [mutatingGlobal, setMutatingGlobal] = useState(false);

  const authEnabled = authState?.enabled ?? false;
  const shouldRedirectToLogin =
    authStatus === "ready" && authEnabled && !authState?.authenticated;
  const canLoad =
    authStatus === "ready" && authEnabled && Boolean(authState?.authenticated);
  const canManage = Boolean(authState?.permissions.includes("admin:settings"));

  const totals = useMemo(() => {
    const used = providers.reduce((sum, provider) => sum + provider.used_this_month, 0);
    const remaining = providers.reduce(
      (sum, provider) => sum + provider.remaining_to_hard_cap,
      0
    );
    const disabled = providers.filter((provider) => !provider.enabled).length;
    const missingKeys = providers.filter(
      (provider) => provider.key_status === "missing"
    ).length;
    return { used, remaining, disabled, missingKeys };
  }, [providers]);

  const handleAuthBoundary = useCallback(
    (error: unknown): boolean => {
      if (error instanceof ApiError && error.status === 401) {
        void refreshSession({ silent: true });
        return true;
      }
      if (error instanceof ApiError && error.status === 403) {
        setPageError("You do not have permission to manage Search Quota.");
        return true;
      }
      return false;
    },
    [refreshSession]
  );

  const loadSearchQuota = useCallback(async () => {
    setLoading(true);
    setPageError(null);
    try {
      const payload = await getAdminSearchQuota();
      setProviders(payload.providers);
      setUsageMonth(payload.month);
      setGlobalEnabled(payload.global.enabled);
      setGlobalDisabledReason(payload.global.disabled_reason);
      setFreeQuotaDrafts(createQuotaDrafts(payload.providers, "monthly_free_quota"));
      setHardCapDrafts(createQuotaDrafts(payload.providers, "monthly_hard_cap"));
    } catch (error) {
      if (!handleAuthBoundary(error)) {
        setPageError(
          error instanceof Error ? error.message : "Unable to load Search Quota."
        );
      }
    } finally {
      setLoading(false);
    }
  }, [handleAuthBoundary]);

  useEffect(() => {
    if (shouldRedirectToLogin) {
      router.replace("/login?next=/admin/search-quota");
    }
  }, [router, shouldRedirectToLogin]);

  useEffect(() => {
    if (!canLoad || !canManage) {
      setLoading(false);
      return;
    }
    void loadSearchQuota();
  }, [canLoad, canManage, loadSearchQuota]);

  const saveGlobal = async (enabled: boolean) => {
    setMutatingGlobal(true);
    setNotice(null);
    try {
      const payload = await updateAdminSearchGlobal({ enabled });
      setGlobalEnabled(payload.global.enabled);
      setGlobalDisabledReason(payload.global.disabled_reason);
      setNotice(`Global Web Search ${enabled ? "enabled" : "disabled"}.`);
    } catch (error) {
      if (!handleAuthBoundary(error)) {
        setPageError(
          error instanceof Error ? error.message : "Unable to update global Search Quota."
        );
      }
    } finally {
      setMutatingGlobal(false);
    }
  };

  const saveProvider = async (
    provider: AdminSearchQuotaProvider,
    enabled: boolean | null = null
  ) => {
    setMutatingProvider(provider.provider);
    setNotice(null);
    try {
      const monthlyFreeQuota = parseQuotaDraft(
        freeQuotaDrafts[provider.provider] ?? "0",
        "Monthly free quota"
      );
      const monthlyHardCap = parseQuotaDraft(
        hardCapDrafts[provider.provider] ?? "0",
        "Monthly hard cap"
      );
      const payload = await updateAdminSearchProvider(provider.provider, {
        enabled: enabled ?? provider.enabled,
        monthly_free_quota: monthlyFreeQuota,
        monthly_hard_cap: monthlyHardCap,
      });
      setProviders((current) => mergeProvider(current, payload.provider));
      setFreeQuotaDrafts((current) => ({
        ...current,
        [payload.provider.provider]: String(payload.provider.monthly_free_quota),
      }));
      setHardCapDrafts((current) => ({
        ...current,
        [payload.provider.provider]: String(payload.provider.monthly_hard_cap),
      }));
      setNotice(`${payload.provider.label} saved.`);
    } catch (error) {
      if (!handleAuthBoundary(error)) {
        setPageError(
          error instanceof Error ? error.message : "Unable to update provider."
        );
      }
    } finally {
      setMutatingProvider(null);
    }
  };

  const reactivateProvider = async (provider: AdminSearchQuotaProvider) => {
    setMutatingProvider(provider.provider);
    setNotice(null);
    try {
      const payload = await reactivateAdminSearchProvider(provider.provider);
      setProviders((current) => mergeProvider(current, payload.provider));
      setNotice(`${payload.provider.label} reactivated.`);
    } catch (error) {
      if (!handleAuthBoundary(error)) {
        setPageError(
          error instanceof Error ? error.message : "Unable to reactivate provider."
        );
      }
    } finally {
      setMutatingProvider(null);
    }
  };

  const resetUsage = async (provider: AdminSearchQuotaProvider) => {
    setMutatingProvider(provider.provider);
    setNotice(null);
    try {
      const payload = await resetAdminSearchProviderUsage(provider.provider);
      setProviders((current) => mergeProvider(current, payload.provider));
      setNotice(`${payload.provider.label} usage reset (${payload.reset_count} call(s)).`);
    } catch (error) {
      if (!handleAuthBoundary(error)) {
        setPageError(
          error instanceof Error ? error.message : "Unable to reset provider usage."
        );
      }
    } finally {
      setMutatingProvider(null);
    }
  };

  if (authStatus !== "ready" || loading) {
    return (
      <StatusPanel
        eyebrow="Admin Console"
        title="Loading Search Quota"
        body="Checking admin access and provider quota state."
      />
    );
  }

  if (!authEnabled) {
    return (
      <StatusPanel
        eyebrow="Auth Disabled"
        tone="muted"
        title="Search Quota is unavailable"
        body="Enable auth to manage Web Search quota configuration."
      />
    );
  }

  if (!canManage) {
    return (
      <StatusPanel
        eyebrow="Forbidden"
        tone="danger"
        title="This session cannot manage Search Quota"
        body={pageError ?? "You do not have permission to manage Search Quota."}
      />
    );
  }

  return (
    <AdminConsolePage
      activeTab="search-quota"
      title="Search Quota"
      badges={
        <Badge variant={globalEnabled ? "secondary" : "destructive"}>
          {globalEnabled ? "global enabled" : "global disabled"}
        </Badge>
      }
      actions={
        <Button
          type="button"
          variant="secondary"
          size="sm"
          onClick={() => void loadSearchQuota()}
        >
          <RefreshCw className="size-4" />
          Refresh
        </Button>
      }
    >
      <AdminMetricGrid>
        <AdminMetricCard label="Usage month" value={usageMonth || "-"} />
        <AdminMetricCard label="Used this month" value={totals.used} />
        <AdminMetricCard label="Remaining to hard cap" value={totals.remaining} />
        <AdminMetricCard label="Missing keys" value={totals.missingKeys} />
      </AdminMetricGrid>

      {pageError ? <AdminNotice>{pageError}</AdminNotice> : null}
      {notice ? <AdminNotice tone="success">{notice}</AdminNotice> : null}

      <AdminPanel>
        <div className="grid gap-3 md:grid-cols-[minmax(0,1fr)_auto] md:items-center">
          <div>
            <div className="flex flex-wrap items-center gap-2">
              <h2 className="text-base font-semibold text-slate-950">
                Global Web Search
              </h2>
              <Badge variant={globalEnabled ? "secondary" : "destructive"}>
                {globalEnabled ? "enabled" : "disabled"}
              </Badge>
            </div>
            {globalDisabledReason ? (
              <p className="mt-1 text-xs leading-5 text-slate-600">
                Disabled reason: {globalDisabledReason}
              </p>
            ) : null}
          </div>
          <div className="flex flex-wrap gap-2">
            <Button
              type="button"
              variant="secondary"
              size="sm"
              disabled={mutatingGlobal}
              onClick={() => void saveGlobal(true)}
            >
              <Power className="size-4" />
              Enable
            </Button>
            <Button
              type="button"
              variant="secondary"
              size="sm"
              disabled={mutatingGlobal}
              onClick={() => void saveGlobal(false)}
            >
              <PowerOff className="size-4" />
              Disable
            </Button>
          </div>
        </div>
      </AdminPanel>

      <section className="grid gap-3">
        {providers.map((provider) => {
          const isSaving = mutatingProvider === provider.provider;
          return (
            <AdminPanel key={provider.provider}>
              <div className="grid gap-4">
                <div className="flex flex-wrap items-start justify-between gap-3">
                  <div>
                    <div className="flex flex-wrap items-center gap-2">
                      <h2 className="text-base font-semibold text-slate-950">
                        {provider.label}
                      </h2>
                      <Badge variant={provider.enabled ? "secondary" : "destructive"}>
                        {provider.enabled ? "enabled" : "disabled"}
                      </Badge>
                      <Badge
                        variant={
                          provider.key_status === "configured"
                            ? "secondary"
                            : "destructive"
                        }
                      >
                        <KeyRound className="size-3" />
                        {provider.key_status}
                      </Badge>
                      {provider.hard_cap_reached ? (
                        <Badge variant="destructive">hard cap reached</Badge>
                      ) : null}
                    </div>
                    <p className="mt-1 text-xs uppercase tracking-[0.2em] text-slate-500">
                      {provider.provider}
                    </p>
                  </div>
                  <div className="flex flex-wrap gap-2">
                    <Button
                      type="button"
                      variant="secondary"
                      size="sm"
                      disabled={isSaving}
                      onClick={() => void saveProvider(provider, true)}
                    >
                      <Power className="size-4" />
                      Enable
                    </Button>
                    <Button
                      type="button"
                      variant="secondary"
                      size="sm"
                      disabled={isSaving}
                      onClick={() => void saveProvider(provider, false)}
                    >
                      <PowerOff className="size-4" />
                      Disable
                    </Button>
                    <Button
                      type="button"
                      variant="secondary"
                      size="sm"
                      disabled={isSaving}
                      onClick={() => void reactivateProvider(provider)}
                    >
                      <ShieldAlert className="size-4" />
                      Reactivate
                    </Button>
                  </div>
                </div>

                <div className="grid gap-2 md:grid-cols-4 xl:grid-cols-7">
                  <AdminMetricCard label="Key status" value={provider.key_status} />
                  <AdminMetricCard label="Used this month" value={provider.used_this_month} />
                  <AdminMetricCard label="Remaining to hard cap" value={provider.remaining_to_hard_cap} />
                  <AdminMetricCard label="Success" value={provider.success_count} />
                  <AdminMetricCard label="Failure" value={provider.failure_count} />
                  <AdminMetricCard label="Last called" value={formatDateTime(provider.last_called_at)} />
                  <AdminMetricCard label="Disabled until" value={formatDateTime(provider.disabled_until)} />
                </div>

                <div className="grid gap-4 lg:grid-cols-[minmax(0,1fr)_360px]">
                  <div className="rounded-[12px] border border-[var(--border)] bg-[var(--surface-strong)] px-3 py-2 text-xs leading-5 text-slate-600">
                    {provider.disabled_reason ? (
                      <p>Disabled reason: {provider.disabled_reason}</p>
                    ) : (
                      <p>Provider requests count whether successful or failed. Cache hits do not count.</p>
                    )}
                    {provider.last_error ? (
                      <p className="mt-1">Last error: {provider.last_error}</p>
                    ) : null}
                    <p className="mt-2 font-semibold text-[var(--danger)]">
                      Reset usage only after confirming the month counter should be cleared.
                    </p>
                  </div>

                  <div className="field-shell rounded-[12px] border border-[var(--border)] bg-white/90 p-3">
                    <div className="grid gap-3 sm:grid-cols-2">
                      <label className="block">
                        <span className="field-label text-[10px] font-semibold uppercase tracking-[0.16em] text-slate-500">
                          Monthly free quota
                        </span>
                        <Input
                          className="mt-2"
                          value={freeQuotaDrafts[provider.provider] ?? "0"}
                          disabled={!canManage}
                          onChange={(event) =>
                            setFreeQuotaDrafts((current) => ({
                              ...current,
                              [provider.provider]: event.target.value,
                            }))
                          }
                        />
                      </label>
                      <label className="block">
                        <span className="field-label text-[10px] font-semibold uppercase tracking-[0.16em] text-slate-500">
                          Monthly hard cap
                        </span>
                        <Input
                          className="mt-2"
                          value={hardCapDrafts[provider.provider] ?? "0"}
                          disabled={!canManage}
                          onChange={(event) =>
                            setHardCapDrafts((current) => ({
                              ...current,
                              [provider.provider]: event.target.value,
                            }))
                          }
                        />
                      </label>
                    </div>
                    <div className="mt-3 flex justify-end gap-2">
                      <Button
                        type="button"
                        variant="secondary"
                        disabled={isSaving}
                        onClick={() => void resetUsage(provider)}
                      >
                        <RotateCcw className="size-4" />
                        Reset usage
                      </Button>
                      <Button
                        type="button"
                        variant="secondary"
                        disabled={isSaving}
                        onClick={() => void saveProvider(provider)}
                      >
                        <Save className="size-4" />
                      </Button>
                    </div>
                  </div>
                </div>
              </div>
            </AdminPanel>
          );
        })}
      </section>
    </AdminConsolePage>
  );
}
