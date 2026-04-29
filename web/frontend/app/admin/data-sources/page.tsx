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
  updateAdminDataSourceRoute,
  updateAdminDataSource,
  type AdminDataSourceRoute,
  type AdminDataSourceUsage,
} from "@/lib/api";

const MODULE_LABELS = [
  { label: "Analysis", value: "analysis" },
  { label: "Screener", value: "screener" },
  { label: "Trade Journal", value: "trade_journal" },
] as const;

const VENDOR_LABELS: Record<string, string> = {
  local: "Local Cache",
  akshare: "AkShare",
  tushare: "Tushare",
  fmp: "Financial Modeling Prep",
  yfinance: "Yahoo Finance",
  alpha_vantage: "Alpha Vantage",
  massive: "Massive",
};
const KNOWN_VENDORS = new Set(Object.keys(VENDOR_LABELS));

const MARKET_LABELS: Record<string, string> = {
  cn: "A-share",
  us: "US",
  global: "Global",
};

const CATEGORY_LABELS: Record<string, string> = {
  core_stock_apis: "Core Stock APIs",
  technical_indicators: "Technical Indicators",
  fundamental_data: "Fundamental Data",
  news_data: "News Data",
};

function formatLimit(value: number | null, interval: "day" | "hour"): string {
  return value === null ? "Unlimited" : `${value} / ${interval}`;
}

function createDailyLimitDrafts(
  sources: AdminDataSourceUsage[]
): Record<string, string> {
  return Object.fromEntries(
    sources.map((source) => [
      source.vendor,
      source.daily_limit === null ? "" : String(source.daily_limit),
    ])
  );
}

function createHourlyLimitDrafts(
  sources: AdminDataSourceUsage[]
): Record<string, string> {
  return Object.fromEntries(
    sources.map((source) => [
      source.vendor,
      source.hourly_limit === null ? "" : String(source.hourly_limit),
    ])
  );
}

function routeKey(route: Pick<AdminDataSourceRoute, "module" | "market" | "category">) {
  return `${route.module}:${route.market}:${route.category}`;
}

function createRouteDrafts(
  routes: AdminDataSourceRoute[]
): Record<string, string> {
  return Object.fromEntries(
    routes.map((route) => [routeKey(route), route.vendor_chain.join(", ")])
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

function parseHourlyLimitDraft(value: string): number | null {
  const trimmed = value.trim();
  if (!trimmed) {
    return null;
  }
  const parsed = Number(trimmed);
  if (!Number.isInteger(parsed) || parsed < 0) {
    throw new Error("Hourly limit must be a whole number or blank.");
  }
  return parsed;
}

function parseRouteDraft(value: string): string[] {
  const vendors = value
    .split(",")
    .map((item) => item.trim().toLowerCase())
    .filter(Boolean);
  const uniqueVendors = Array.from(new Set(vendors));
  if (!uniqueVendors.length) {
    throw new Error("Route chain must include at least one vendor.");
  }
  const unknownVendor = uniqueVendors.find((vendor) => !KNOWN_VENDORS.has(vendor));
  if (unknownVendor) {
    throw new Error(`Unknown vendor: ${unknownVendor}.`);
  }
  return uniqueVendors;
}

export default function AdminDataSourcesPage() {
  const router = useRouter();
  const { authState, authStatus, refreshSession } = useAuth();
  const [sources, setSources] = useState<AdminDataSourceUsage[]>([]);
  const [routes, setRoutes] = useState<AdminDataSourceRoute[]>([]);
  const [usageDate, setUsageDate] = useState("");
  const [dailyLimitDrafts, setDailyLimitDrafts] = useState<Record<string, string>>({});
  const [hourlyLimitDrafts, setHourlyLimitDrafts] = useState<Record<string, string>>({});
  const [routeDrafts, setRouteDrafts] = useState<Record<string, string>>({});
  const [loading, setLoading] = useState(true);
  const [pageError, setPageError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [mutatingVendor, setMutatingVendor] = useState<string | null>(null);
  const [mutatingRouteKey, setMutatingRouteKey] = useState<string | null>(null);

  const authEnabled = authState?.enabled ?? false;
  const shouldRedirectToLogin =
    authStatus === "ready" && authEnabled && !authState?.authenticated;
  const canLoad =
    authStatus === "ready" && authEnabled && Boolean(authState?.authenticated);
  const canManage = Boolean(authState?.permissions.includes("admin:settings"));

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
      setRoutes(payload.routes ?? []);
      setUsageDate(payload.date);
      setDailyLimitDrafts(createDailyLimitDrafts(payload.sources));
      setHourlyLimitDrafts(createHourlyLimitDrafts(payload.sources));
      setRouteDrafts(createRouteDrafts(payload.routes ?? []));
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
      const dailyLimit = parseDailyLimitDraft(dailyLimitDrafts[source.vendor] ?? "");
      const hourlyLimit = parseHourlyLimitDraft(hourlyLimitDrafts[source.vendor] ?? "");
      const payload = await updateAdminDataSource(source.vendor, {
        enabled,
        daily_limit: dailyLimit,
        hourly_limit: hourlyLimit,
      });
      setSources((current) =>
        current.map((item) =>
          item.vendor === payload.source.vendor ? payload.source : item
        )
      );
      setDailyLimitDrafts((current) => ({
        ...current,
        [payload.source.vendor]:
          payload.source.daily_limit === null ? "" : String(payload.source.daily_limit),
      }));
      setHourlyLimitDrafts((current) => ({
        ...current,
        [payload.source.vendor]:
          payload.source.hourly_limit === null ? "" : String(payload.source.hourly_limit),
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

  const saveRoute = async (route: AdminDataSourceRoute) => {
    const key = routeKey(route);
    setMutatingRouteKey(key);
    setNotice(null);
    try {
      const vendorChain = parseRouteDraft(routeDrafts[key] ?? "");
      const payload = await updateAdminDataSourceRoute(route, {
        vendor_chain: vendorChain,
      });
      setRoutes((current) =>
        current.map((item) =>
          routeKey(item) === routeKey(payload.route) ? payload.route : item
        )
      );
      setRouteDrafts((current) => ({
        ...current,
        [routeKey(payload.route)]: payload.route.vendor_chain.join(", "),
      }));
      setNotice(
        `${MODULE_LABELS.find((item) => item.value === payload.route.module)?.label ?? payload.route.module} ${MARKET_LABELS[payload.route.market] ?? payload.route.market} route saved.`
      );
    } catch (error) {
      if (!handleAuthBoundary(error)) {
        setPageError(
          error instanceof Error ? error.message : "Unable to update route policy"
        );
      }
    } finally {
      setMutatingRouteKey(null);
    }
  };

  if (authStatus !== "ready" || loading) {
    return (
      <StatusPanel
        eyebrow="Admin Console"
        title="Loading data sources"
        body="Checking admin access and data source usage."
      />
    );
  }

  if (!authEnabled) {
    return (
      <StatusPanel
        eyebrow="Auth Disabled"
        tone="muted"
        title="Admin data sources are unavailable"
        body="Enable auth to manage data source API configuration."
      />
    );
  }

  if (!canManage) {
    return (
      <StatusPanel
        eyebrow="Forbidden"
        tone="danger"
        title="This session cannot manage data sources"
        body={pageError ?? "You do not have permission to manage data sources."}
      />
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
            <Button asChild type="button" variant="secondary">
              <Link href="/admin/task-queue">Task Queue</Link>
            </Button>
            <Button asChild type="button" variant="secondary">
              <Link href="/admin/audit">Audit Log</Link>
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

                  <div className="grid gap-3 md:grid-cols-4 xl:grid-cols-7">
                    <MetricBlock label="Used today" value={`${source.used_today}`} />
                    <MetricBlock label="Used this hour" value={`${source.used_this_hour}`} />
                    <MetricBlock label="Daily limit" value={formatLimit(source.daily_limit, "day")} />
                    <MetricBlock label="Hourly limit" value={formatLimit(source.hourly_limit, "hour")} />
                    <MetricBlock
                      label="Daily remaining"
                      value={
                        source.remaining_today === null
                          ? "Unlimited"
                          : `${source.remaining_today}`
                      }
                    />
                    <MetricBlock
                      label="Hourly remaining"
                      value={
                        source.remaining_this_hour === null
                          ? "Unlimited"
                          : `${source.remaining_this_hour}`
                      }
                    />
                    <MetricBlock label="Success" value={`${source.success_count}`} />
                    <MetricBlock label="Failure" value={`${source.failure_count}`} />
                  </div>

                  <div className="grid gap-4 lg:grid-cols-[minmax(0,1fr)_360px]">
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

                    <div className="field-shell rounded-lg border border-[var(--border)] bg-white/90 p-4">
                      <div className="grid gap-3 sm:grid-cols-2">
                        <label className="block">
                          <span className="field-label text-xs font-semibold uppercase tracking-[0.24em] text-slate-500">
                            Daily limit
                          </span>
                          <Input
                            className="mt-3"
                            value={dailyLimitDrafts[source.vendor] ?? ""}
                            placeholder="Unlimited"
                            onChange={(event) =>
                              setDailyLimitDrafts((current) => ({
                                ...current,
                                [source.vendor]: event.target.value,
                              }))
                            }
                          />
                        </label>
                        <label className="block">
                          <span className="field-label text-xs font-semibold uppercase tracking-[0.24em] text-slate-500">
                            Hourly limit
                          </span>
                          <Input
                            className="mt-3"
                            value={hourlyLimitDrafts[source.vendor] ?? ""}
                            placeholder="Unlimited"
                            onChange={(event) =>
                              setHourlyLimitDrafts((current) => ({
                                ...current,
                                [source.vendor]: event.target.value,
                              }))
                            }
                          />
                        </label>
                      </div>
                      <div className="mt-3 flex justify-end">
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
                        Leave blank for no quota.
                      </p>
                    </div>
                  </div>

                  <p className="text-xs text-slate-500">
                    Last called: {source.last_called_at ?? "Never"}
                  </p>
                </CardContent>
              </Card>
            );
          })}
        </section>

        <section className="grid gap-3">
          <div>
            <h2 className="text-xl font-semibold tracking-normal text-slate-950">
              Routing Policies
            </h2>
            <p className="mt-1 text-sm leading-6 text-slate-600">
              Configure the vendor chain used by each workflow and market. Changes are
              read at runtime.
            </p>
          </div>
          <Card className="rounded-lg border-[var(--border)]">
            <CardContent className="grid gap-3 p-5">
              {routes.map((route) => {
                const key = routeKey(route);
                const isSaving = mutatingRouteKey === key;
                return (
                  <div
                    key={key}
                    className="grid gap-3 rounded-lg border border-[var(--border)] bg-[var(--surface-strong)] px-4 py-3 lg:grid-cols-[180px_140px_minmax(160px,1fr)_minmax(260px,1.5fr)_auto]"
                  >
                    <div>
                      <p className="text-xs font-semibold uppercase tracking-[0.2em] text-slate-500">
                        Module
                      </p>
                      <p className="mt-1 text-sm font-semibold text-slate-950">
                        {MODULE_LABELS.find((item) => item.value === route.module)
                          ?.label ?? route.module}
                      </p>
                    </div>
                    <div>
                      <p className="text-xs font-semibold uppercase tracking-[0.2em] text-slate-500">
                        Market
                      </p>
                      <p className="mt-1 text-sm font-semibold text-slate-950">
                        {MARKET_LABELS[route.market] ?? route.market}
                      </p>
                    </div>
                    <div>
                      <p className="text-xs font-semibold uppercase tracking-[0.2em] text-slate-500">
                        Category
                      </p>
                      <p className="mt-1 text-sm font-semibold text-slate-950">
                        {CATEGORY_LABELS[route.category] ?? route.category}
                      </p>
                    </div>
                    <label className="block">
                      <span className="sr-only">Vendor chain</span>
                      <Input
                        value={routeDrafts[key] ?? ""}
                        placeholder={route.default_vendor_chain.join(", ")}
                        onChange={(event) =>
                          setRouteDrafts((current) => ({
                            ...current,
                            [key]: event.target.value,
                          }))
                        }
                      />
                    </label>
                    <Button
                      type="button"
                      variant="secondary"
                      disabled={isSaving}
                      onClick={() => void saveRoute(route)}
                    >
                      <Save className="size-4" />
                    </Button>
                  </div>
                );
              })}
            </CardContent>
          </Card>
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
