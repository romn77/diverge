"use client";

import Link from "next/link";
import { FileText, RefreshCw } from "lucide-react";
import { useEffect, useState } from "react";
import { usePreferences } from "@/components/PreferencesProvider";
import { useWorkbenchChrome } from "@/components/WorkbenchShell";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import {
  listMarketBriefs,
  type MarketBriefIndexResponse,
} from "@/lib/api";
import { buildReportHref } from "@/lib/workbenchRoutes";


export function MarketBriefDashboard() {
  const { t } = usePreferences();
  const { setTopbarActions } = useWorkbenchChrome();
  const [briefIndex, setBriefIndex] = useState<MarketBriefIndexResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const refresh = async () => {
    setError(null);
    const nextBriefs = await listMarketBriefs();
    setBriefIndex(nextBriefs);
    setLoading(false);
  };

  useEffect(() => {
    void refresh().catch((loadError) => {
      setError(loadError instanceof Error ? loadError.message : t("marketBrief.error.load", "Unable to load brief"));
      setLoading(false);
    });
  }, [t]);

  useEffect(() => {
    setTopbarActions(
      <Button
        type="button"
        variant="secondary"
        size="sm"
        onClick={() => void refresh()}
        disabled={loading}
      >
        <RefreshCw className="size-4" aria-hidden />
        <span>{t("marketBrief.refresh", "Refresh")}</span>
      </Button>
    );
    return () => setTopbarActions(null);
  }, [loading, setTopbarActions, t]);

  return (
    <main className="workbench-page-shell flex min-h-dvh flex-1 flex-col">
      <div className="workbench-content-frame space-y-5">
        <Card className="card-surface rounded-[24px]">
          <CardContent className="space-y-5 p-5 md:p-6">
            <div className="flex flex-wrap items-start justify-between gap-4">
              <div className="min-w-0">
                <p className="text-[11px] font-semibold uppercase tracking-[0.22em] text-muted-foreground">
                  {t("marketBrief.kicker", "External Briefs")}
                </p>
                <h2 className="mt-2 text-xl font-bold tracking-tight text-[var(--text)]">
                  {t("marketBrief.title", "Premarket brief")}
                </h2>
              </div>
              <Badge variant="secondary" className="gap-1.5">
                <FileText className="size-3.5" aria-hidden />
                {t("marketBrief.source.multica", "multica markdown")}
              </Badge>
            </div>

            {error ? (
              <div className="rounded-[14px] border border-[var(--border)] bg-[var(--surface-strong)] px-4 py-3 text-sm text-[var(--danger)]">
                {error}
              </div>
            ) : null}
          </CardContent>
        </Card>

        <section>
          <Card className="card-surface rounded-[24px]">
            <CardContent className="p-5 md:p-6">
              <div className="flex items-center justify-between gap-3">
                <h2 className="text-base font-bold text-[var(--text)]">
                  {t("marketBrief.history", "Last 7 days")}
                </h2>
                <Badge variant="secondary">
                  {briefIndex?.briefs.length ?? 0}
                </Badge>
              </div>

              <div className="mt-4 space-y-3">
                {loading ? (
                  <p className="text-sm text-muted-foreground">
                    {t("marketBrief.loading", "Loading briefs...")}
                  </p>
                ) : briefIndex?.briefs.length ? (
                  briefIndex.briefs.map((brief) => (
                    <Link
                      key={brief.brief_id}
                      href={brief.report_id ? buildReportHref(brief.report_id) : "#"}
                      className="block rounded-[14px] border border-[var(--border)] bg-[var(--surface)] px-4 py-3 transition hover:border-[var(--border-strong)] hover:bg-[color:var(--surface-hover)]"
                    >
                      <div className="flex flex-wrap items-center justify-between gap-2">
                        <p className="font-semibold text-[var(--text)]">{brief.title}</p>
                        <span className="text-xs text-muted-foreground">
                          {brief.date} {brief.time}
                        </span>
                      </div>
                      {brief.summary ? (
                        <p className="mt-2 text-sm leading-6 text-muted-foreground">
                          {brief.summary}
                        </p>
                      ) : null}
                      <div className="mt-3 flex flex-wrap gap-2">
                        {brief.markets.map((market) => (
                          <Badge key={market} variant="secondary">
                            {formatMarketBriefMarket(market, t)}
                          </Badge>
                        ))}
                        <Badge variant="outline">
                          {formatQualityLevel(brief.data_quality_level, t)}
                        </Badge>
                      </div>
                    </Link>
                  ))
                ) : (
                  <p className="rounded-[14px] border border-dashed border-[var(--border)] bg-[var(--surface-strong)] px-4 py-6 text-sm text-muted-foreground">
                    {t("marketBrief.empty", "No market brief markdown files found in the 7-day window.")}
                  </p>
                )}
              </div>
            </CardContent>
          </Card>
        </section>
      </div>
    </main>
  );
}

function formatMarketBriefMarket(
  market: string,
  t: ReturnType<typeof usePreferences>["t"]
): string {
  const normalized = market.toLowerCase();
  if (normalized === "cn") {
    return t("marketBrief.market.cn", "A-share");
  }
  if (normalized === "us") {
    return t("marketBrief.market.us", "US");
  }
  return market.toUpperCase();
}

function formatQualityLevel(
  qualityLevel: string | null,
  t: ReturnType<typeof usePreferences>["t"]
): string {
  const normalized = (qualityLevel ?? "unknown").toLowerCase();
  return t(`marketBrief.quality.${normalized}`, humanizeCode(normalized));
}

function humanizeCode(value: string): string {
  return value
    .split(/[_\s-]+/)
    .filter(Boolean)
    .map((part) => `${part.charAt(0).toUpperCase()}${part.slice(1).toLowerCase()}`)
    .join(" ");
}
