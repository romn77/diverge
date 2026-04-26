"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { Power, PowerOff, RefreshCw, Save } from "lucide-react";

import { useAuth } from "@/components/AuthProvider";
import { StatusPanel } from "@/components/workbench/StatusPanel";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import {
  ApiError,
  listAdminDataSources,
  updateAdminDataSource,
  type AdminDataSourceUsage,
} from "@/lib/api";

const MODULE_LABELS = [
  { label: "Analysis", value: "analysis" },
  { label: "Screener", value: "screener" },
  { label: "Trade Journal", value: "trade_journal" },
] as const;

const VENDOR_LABELS: Record<string, string> = {
  akshare: "AkShare",
  tushare: "Tushare",
  yfinance: "Yahoo Finance",
  alpha_vantage: "Alpha Vantage",
  massive: "Massive",
};

function formatLimit(value: number | null): string {
  return value === null ? "Unlimited" : `${value} / day`;
}

function createLimitDrafts(
  sources: AdminDataSourceUsage[]
): Record<string, string> {
  return Object.fromEntries(
    sources.map((source) => [
      source.vendor,
      source.daily_limit === null ? "" : String(source.daily_limit),
    ])
  );
}

function parseDailyLimitDraft(value: string): number | null {
  const trimmed = value.trim();
  if (!trimmed) {
    return null;
  }
  const parsed = Number(trimmed);
  if (!Number.isInteger(parsed) || parsed < 0) {
    throw new Error("Daily limit must be a whole number or blank.");
  }
  return parsed;
}

export default function AdminDataSourcesPage() {
  const router = useRouter();
  const { authState, authStatus, refreshSession } = useAuth();
  const [sources, setSources] = useState<AdminDataSourceUsage[]>([]);
  const [usageDate, setUsageDate] = useState("");
  const [limitDrafts, setLimitDrafts] = useState<Record<string, string>>({});
  const [loading, setLoading] = useState(true);
  const [pageError, setPageError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [mutatingVendor, setMutatingVendor] = useState<string | null>(null);

  const authEnabled = authState?.enabled ?? false;
  const shouldRedirectToLogin =
    authStatus === "ready" && authEnabled && !authState?.authenticated;
  const canLoad =
    authStatus === "ready" && authEnabled && Boolean(authState?.authenticated);
  const canManage = authState?.user?.role === "admin";

  const totals = useMemo(() => {
    const used = sources.reduce((sum, source) => sum + source.used_today, 0);
    const exhausted = sources.filter((source) => source.exhausted).length;
    const disabled = sources.filter((source) => !source.enabled).length;
    return { used, exhausted, disabled };
  }, [sources]);

  const handleAuthBoundary = useCallback(
    (error: unknown): boolean => {
      if (error instanceof ApiError && error.status === 401) {
        void refreshSession({ silent: true });
        return true;
      }
      if (error instanceof ApiError && error.status === 403) {
        setPageError("You do not have permission to manage data sources.");
        return true;
      }
      return false;
    },
    [refreshSession]
  );

  const loadDataSources = useCallback(async () => {
    setLoading(true);
    setPageError(null);
    try {
      const payload = await listAdminDataSources();
      setSources(payload.sources);
      setUsageDate(payload.date);
      setLimitDrafts(createLimitDrafts(payload.sources));
    } catch (error) {
      if (!handleAuthBoundary(error)) {
        setPageError(
          error instanceof Error
            ? error.message
            : "Unable to load data source usage right now"
        );
      }
    } finally {
      setLoading(false);
    }
  }, [handleAuthBoundary]);

  useEffect(() => {
    if (shouldRedirectToLogin) {
      router.replace("/login?next=/admin/data-sources");
    }
  }, [router, shouldRedirectToLogin]);

  useEffect(() => {
    if (!canLoad || !canManage) {
      setLoading(false);
      return;
    }
    void loadDataSources();
  }, [canLoad, canManage, loadDataSources]);

  const saveSource = async (source: AdminDataSourceUsage, enabled: boolean) => {
    setMutatingVendor(source.vendor);
    setNotice(null);
    try {
      const dailyLimit = parseDailyLimitDraft(limitDrafts[source.vendor] ?? "");
      const payload = await updateAdminDataSource(source.vendor, {
        enabled,
        daily_limit: dailyLimit,
      });
      setSources((current) =>
        current.map((item) =>
          item.vendor === payload.source.vendor ? payload.source : item
        )
      );
      setLimitDrafts((current) => ({
        ...current,
        [payload.source.vendor]:
          payload.source.daily_limit === null ? "" : String(payload.source.daily_limit),
      }));
      setNotice(`${payload.source.label} ${enabled ? "enabled" : "disabled"}.`);
    } catch (error) {
      if (!handleAuthBoundary(error)) {
        setPageError(
          error instanceof Error ? error.message : "Unable to update data source"
        );
      }
    } finally {
      setMutatingVendor(null);
    }
  };

  if (authStatus !== "ready" || loading) {
    return (
      <main className="mx-auto flex min-h-screen w-full max-w-6xl items-center justify-center px-6 py-10">
        <StatusPanel
          title="Loading data sources"
          body="Checking admin access and data source usage."
        />
      </main>
    );
  }

  if (!authEnabled) {
    return (
      <main className="mx-auto flex min-h-screen w-full max-w-6xl items-center justify-center px-6 py-10">
        <StatusPanel
          tone="warning"
          title="Admin data sources are unavailable"
          body="Enable auth to manage data source API configuration."
        />
      </main>
    );
  }

  if (!canManage) {
    return (
      <main className="mx-auto flex min-h-screen w-full max-w-6xl items-center justify-center px-6 py-10">
        <StatusPanel
          tone="danger"
          title="This session cannot manage data sources"
          body={pageError ?? "You do not have permission to manage data sources."}
        />
      </main>
    );
  }

  return (
    <main className="min-h-screen bg-[var(--background)] px-4 py-8 text-[var(--foreground)] md:px-8">
      <div className="mx-auto grid w-full max-w-7xl gap-6">
        <header className="flex flex-wrap items-end justify-between gap-4">
          <div>
            <p className="text-[11px] font-semibold uppercase tracking-[0.32em] text-[var(--primary)]">
              Admin Console
            </p>
            <h1 className="mt-2 text-3xl font-semibold tracking-normal text-slate-950">
              Data Source Usage
            </h1>
            <p className="mt-2 max-w-3xl text-sm leading-6 text-slate-600">
              Monitor vendor API usage across Analysis, Screener, and Trade Journal
              workflows. LLM calls are not counted here.
            </p>
          </div>
          <div className="flex flex-wrap gap-2">
            <Button asChild type="button" variant="secondary">
              <Link href="/admin/users">User Management</Link>
            </Button>
            <Button
              type="button"
              variant="secondary"
              onClick={() => void loadDataSources()}
            >
              <RefreshCw className="size-4" />
              Refresh
            </Button>
          </div>
        </header>

        <section className="grid gap-3 md:grid-cols-4">
          <MetricBlock label="Usage date" value={usageDate || "-"} />
          <MetricBlock label="Used today" value={`${totals.used}`} />
          <MetricBlock label="Exhausted" value={`${totals.exhausted}`} />
          <MetricBlock label="Disabled" value={`${totals.disabled}`} />
        </section>

        {pageError ? (
          <div className="rounded-lg border border-[rgba(163,53,53,0.2)] bg-[rgba(163,53,53,0.08)] px-4 py-3 text-sm text-[var(--danger)]">
            {pageError}
          </div>
        ) : null}

        {notice ? (
          <div className="rounded-lg border border-[rgba(57,111,83,0.22)] bg-[rgba(57,111,83,0.08)] px-4 py-3 text-sm text-[var(--primary)]">
            {notice}
          </div>
        ) : null}

        <section className="grid gap-4">
          {sources.map((source) => {
            const isSaving = mutatingVendor === source.vendor;
            return (
              <Card key={source.vendor} className="rounded-lg border-[var(--border)]">
                <CardContent className="grid gap-5 p-5">
                  <div className="flex flex-wrap items-start justify-between gap-4">
                    <div>
                      <div className="flex flex-wrap items-center gap-2">
                        <h2 className="text-lg font-semibold text-slate-950">
                          {VENDOR_LABELS[source.vendor] ?? source.label}
                        </h2>
                        <Badge variant={source.enabled ? "secondary" : "destructive"}>
                          {source.enabled ? "enabled" : "disabled"}
                        </Badge>
                        {source.exhausted ? (
                          <Badge variant="destructive">quota exhausted</Badge>
                        ) : null}
                      </div>
                      <p className="mt-1 text-xs uppercase tracking-[0.2em] text-slate-500">
                        {source.vendor}
                      </p>
                    </div>
                    <div className="flex flex-wrap gap-2">
                      <Button
                        type="button"
                        variant="secondary"
                        size="sm"
                        disabled={isSaving}
                        onClick={() => void saveSource(source, true)}
                      >
                        <Power className="size-4" />
                        Enable
                      </Button>
                      <Button
                        type="button"
                        variant="secondary"
                        size="sm"
                        disabled={isSaving}
                        onClick={() => void saveSource(source, false)}
                      >
                        <PowerOff className="size-4" />
                        Disable
                      </Button>
                    </div>
                  </div>

                  <div className="grid gap-3 md:grid-cols-5">
                    <MetricBlock label="Used today" value={`${source.used_today}`} />
                    <MetricBlock label="Daily limit" value={formatLimit(source.daily_limit)} />
                    <MetricBlock
                      label="Remaining"
                      value={
                        source.remaining_today === null
                          ? "Unlimited"
                          : `${source.remaining_today}`
                      }
                    />
                    <MetricBlock label="Success" value={`${source.success_count}`} />
                    <MetricBlock label="Failure" value={`${source.failure_count}`} />
                  </div>

                  <div className="grid gap-4 lg:grid-cols-[minmax(0,1fr)_280px]">
                    <div className="grid gap-3 md:grid-cols-3">
                      {MODULE_LABELS.map((module) => {
                        const usage = source.modules[module.value];
                        return (
                          <div
                            key={module.value}
                            className="rounded-lg border border-[var(--border)] bg-[var(--surface-strong)] px-4 py-3"
                          >
                            <p className="text-xs font-semibold uppercase tracking-[0.2em] text-slate-500">
                              {module.label}
                            </p>
                            <p className="mt-2 text-2xl font-semibold text-slate-950">
                              {usage?.total_calls ?? 0}
                            </p>
                            <p className="mt-1 text-xs text-slate-500">
                              {usage?.success_count ?? 0} success /{" "}
                              {usage?.failure_count ?? 0} failed
                            </p>
                          </div>
                        );
                      })}
                    </div>

                    <label className="field-shell block rounded-lg border border-[var(--border)] bg-white/90 p-4">
                      <span className="field-label text-xs font-semibold uppercase tracking-[0.24em] text-slate-500">
                        Daily limit
                      </span>
                      <div className="mt-3 flex gap-2">
                        <Input
                          value={limitDrafts[source.vendor] ?? ""}
                          placeholder="Unlimited"
                          onChange={(event) =>
                            setLimitDrafts((current) => ({
                              ...current,
                              [source.vendor]: event.target.value,
                            }))
                          }
                        />
                        <Button
                          type="button"
                          variant="secondary"
                          disabled={isSaving}
                          onClick={() => void saveSource(source, source.enabled)}
                        >
                          <Save className="size-4" />
                        </Button>
                      </div>
                      <p className="mt-2 text-xs leading-5 text-slate-500">
                        Leave blank for no daily quota.
                      </p>
                    </label>
                  </div>

                  <p className="text-xs text-slate-500">
                    Last called: {source.last_called_at ?? "Never"}
                  </p>
                </CardContent>
              </Card>
            );
          })}
        </section>
      </div>
    </main>
  );
}

function MetricBlock({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-lg border border-[var(--border)] bg-white/90 px-4 py-3">
      <p className="text-xs font-semibold uppercase tracking-[0.2em] text-slate-500">
        {label}
      </p>
      <p className="mt-2 text-xl font-semibold text-slate-950">{value}</p>
    </div>
  );
}
