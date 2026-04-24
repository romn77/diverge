"use client";

import { useCallback, useEffect, useMemo, useState, type ReactNode } from "react";
import { usePreferences } from "@/components/PreferencesProvider";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { Textarea } from "@/components/ui/textarea";
import {
  type AssetPositionCreateRequest,
  type AssetPositionRecord,
  type AssetSummaryPayload,
  createAssetPosition,
  deleteAssetPosition,
  getAssetPosition,
  getAssetSummary,
  refreshAssetPosition,
  refreshAssetPositions,
  updateAssetPosition,
} from "@/lib/assetsApi";

type AssetDraft = {
  platform_name: string;
  account_name: string;
  asset_name: string;
  asset_category: string;
  quantity: string;
  cost_basis: string;
  valuation_mode: "market" | "manual";
  ticker: string;
  currency: string;
  manual_price: string;
  notes: string;
};

const DEFAULT_BASE_CURRENCY = "USD";

function buildEmptyDraft(): AssetDraft {
  return {
    platform_name: "",
    account_name: "",
    asset_name: "",
    asset_category: "stock",
    quantity: "1",
    cost_basis: "0",
    valuation_mode: "market",
    ticker: "",
    currency: DEFAULT_BASE_CURRENCY,
    manual_price: "",
    notes: "",
  };
}

function buildDraftFromPosition(position: AssetPositionRecord): AssetDraft {
  return {
    platform_name: position.account.platform_name,
    account_name: position.account.account_name,
    asset_name: position.asset_name,
    asset_category: position.asset_category,
    quantity: `${position.quantity}`,
    cost_basis: `${position.cost_basis}`,
    valuation_mode: position.valuation_mode,
    ticker: position.ticker ?? "",
    currency:
      position.currency ??
      position.latest_snapshot?.quote_currency ??
      position.latest_snapshot?.base_currency ??
      DEFAULT_BASE_CURRENCY,
    manual_price:
      position.manual_price !== null && position.manual_price !== undefined
        ? `${position.manual_price}`
        : "",
    notes: position.notes ?? "",
  };
}

function draftToPayload(draft: AssetDraft): AssetPositionCreateRequest {
  return {
    platform_name: draft.platform_name.trim(),
    account_name: draft.account_name.trim(),
    asset_name: draft.asset_name.trim(),
    asset_category: draft.asset_category.trim(),
    quantity: Number(draft.quantity),
    cost_basis: Number(draft.cost_basis),
    valuation_mode: draft.valuation_mode,
    ticker: draft.valuation_mode === "market" ? draft.ticker.trim() || null : null,
    currency: draft.currency.trim() || null,
    manual_price:
      draft.valuation_mode === "manual" && draft.manual_price.trim()
        ? Number(draft.manual_price)
        : null,
    notes: draft.notes.trim() || null,
  };
}

function formatMoney(
  value: number | null | undefined,
  currency: string,
  emptyLabel = "N/A"
): string {
  if (value === null || value === undefined) {
    return emptyLabel;
  }
  return `${value.toFixed(2)} ${currency}`;
}

function flattenPositions(summary: AssetSummaryPayload | null): AssetPositionRecord[] {
  if (!summary) {
    return [];
  }

  const seen = new Set<string>();
  const items: AssetPositionRecord[] = [];

  for (const group of summary.groups) {
    for (const account of group.accounts) {
      for (const position of account.positions) {
        if (!seen.has(position.id)) {
          seen.add(position.id);
          items.push(position);
        }
      }
    }
  }

  for (const position of summary.unpriced_positions) {
    if (!seen.has(position.id)) {
      seen.add(position.id);
      items.push(position);
    }
  }

  return items;
}

export function AssetsWorkspace() {
  const { t } = usePreferences();
  const [baseCurrency, setBaseCurrency] = useState(DEFAULT_BASE_CURRENCY);
  const [summary, setSummary] = useState<AssetSummaryPayload | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [dialogOpen, setDialogOpen] = useState(false);
  const [editingPositionId, setEditingPositionId] = useState<string | null>(null);
  const [draft, setDraft] = useState<AssetDraft>(buildEmptyDraft());

  const loadSummary = useCallback(async (refreshIfStale = true) => {
    setLoading(true);
    setError(null);
    try {
      setSummary(
        await getAssetSummary({
          baseCurrency,
          refreshIfStale,
        })
      );
    } catch (nextError) {
      setError(
        nextError instanceof Error
          ? nextError.message
          : t("assets.error.loadLedger", "Unable to load the asset ledger")
      );
    } finally {
      setLoading(false);
    }
  }, [baseCurrency, t]);

  useEffect(() => {
    void loadSummary(true);
  }, [loadSummary]);

  const flatPositions = useMemo(() => flattenPositions(summary), [summary]);
  const notAvailableLabel = t("common.notAvailable", "N/A");

  const openCreateDialog = () => {
    setEditingPositionId(null);
    setDraft(buildEmptyDraft());
    setDialogOpen(true);
  };

  const openEditDialog = async (positionId: string) => {
    setSubmitting(true);
    setError(null);
    try {
      const position = await getAssetPosition(positionId);
      setEditingPositionId(position.id);
      setDraft(buildDraftFromPosition(position));
      setDialogOpen(true);
    } catch (nextError) {
      setError(
        nextError instanceof Error
          ? nextError.message
          : t("assets.error.loadSelected", "Unable to load the selected asset")
      );
    } finally {
      setSubmitting(false);
    }
  };

  const submitDraft = async () => {
    setSubmitting(true);
    setError(null);
    try {
      const payload = draftToPayload(draft);
      if (editingPositionId) {
        await updateAssetPosition(editingPositionId, payload);
      } else {
        await createAssetPosition(payload);
      }
      setDialogOpen(false);
      setEditingPositionId(null);
      setDraft(buildEmptyDraft());
      await loadSummary(true);
    } catch (nextError) {
      setError(
        nextError instanceof Error
          ? nextError.message
          : t("assets.error.save", "Unable to save the asset")
      );
    } finally {
      setSubmitting(false);
    }
  };

  const handleDelete = async (position: AssetPositionRecord) => {
    const confirmed = window.confirm(
      t(
        "assets.confirmDelete",
        ({ asset, platform, account }) =>
          `Delete ${asset} from ${platform} / ${account}?`,
        {
          asset: position.asset_name,
          platform: position.account.platform_name,
          account: position.account.account_name,
        }
      )
    );
    if (!confirmed) {
      return;
    }

    setSubmitting(true);
    setError(null);
    try {
      await deleteAssetPosition(position.id);
      await loadSummary(false);
    } catch (nextError) {
      setError(
        nextError instanceof Error
          ? nextError.message
          : t("assets.error.delete", "Unable to delete the asset")
      );
    } finally {
      setSubmitting(false);
    }
  };

  const handleRefreshOne = async (position: AssetPositionRecord) => {
    setSubmitting(true);
    setError(null);
    try {
      await refreshAssetPosition(position.id, {
        base_currency: baseCurrency,
      });
      await loadSummary(false);
    } catch (nextError) {
      setError(
        nextError instanceof Error
          ? nextError.message
          : t("assets.error.refresh", "Unable to refresh the asset")
      );
    } finally {
      setSubmitting(false);
    }
  };

  const handleRefreshAll = async (force: boolean) => {
    setSubmitting(true);
    setError(null);
    try {
      await refreshAssetPositions({
        base_currency: baseCurrency,
        force,
      });
      await loadSummary(false);
    } catch (nextError) {
      setError(
        nextError instanceof Error
          ? nextError.message
          : t("assets.error.refreshLedger", "Unable to refresh the asset ledger")
      );
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <main className="flex min-h-[100vh] flex-1 flex-col px-4 py-6 md:px-7 lg:px-9">
      <div className="mx-auto w-full max-w-7xl space-y-6">
        {error ? (
          <section className="rounded-[24px] border border-[rgba(163,53,53,0.2)] bg-[rgba(163,53,53,0.08)] px-5 py-4 text-sm text-[var(--danger)]">
            {error}
          </section>
        ) : null}
        <Card className="card-surface rounded-[30px]">
          <CardContent className="px-6 py-8 md:px-8">
          <div className="flex flex-col gap-6 lg:flex-row lg:items-end lg:justify-between">
            <div className="max-w-3xl">
              <p className="text-[11px] font-semibold uppercase tracking-[0.24em] text-[var(--primary)]">
                {t("sidebar.nav.assets", "Assets")}
              </p>
              <h1 className="mt-3 text-4xl font-semibold tracking-tight text-slate-900 md:text-[3.2rem]">
                {t("assets.title", "Portfolio ledger")}
              </h1>
              <p className="mt-4 max-w-2xl text-sm leading-7 text-slate-600">
                {t(
                  "assets.description",
                  "Track accounts, current holdings, manual assets, and marked-to-market exposure in one PostgreSQL-backed ledger that the portfolio manager can reuse during analysis runs."
                )}
              </p>
            </div>

            <div className="flex flex-wrap gap-3">
              <label className="rounded-full border border-[var(--border)] bg-white px-4 py-3 text-xs font-semibold uppercase tracking-[0.16em] text-slate-600">
                {t("assets.base", "Base")}
                <Input
                  type="text"
                  value={baseCurrency}
                  onChange={(event) => setBaseCurrency(event.target.value.toUpperCase())}
                  className="ml-2 h-auto w-14 border-none bg-transparent px-0 py-0 text-right text-sm font-semibold text-slate-900 shadow-none focus-visible:ring-0 focus-visible:ring-offset-0"
                />
              </label>
              <Button
                type="button"
                variant="secondary"
                disabled={submitting}
                onClick={() => void handleRefreshAll(false)}
              >
                {t("assets.refreshDue", "Refresh Due")}
              </Button>
              <Button
                type="button"
                disabled={submitting}
                onClick={openCreateDialog}
              >
                {t("assets.addAsset", "Add Asset")}
              </Button>
            </div>
          </div>

          <div className="mt-8 grid gap-4 md:grid-cols-4">
            <AssetMetric
              label={t("assets.metric.marketValue", "Market Value")}
              value={
                summary
                  ? formatMoney(summary.totals.market_value, baseCurrency, notAvailableLabel)
                  : "—"
              }
              meta={t("assets.metric.marketValueMeta", "Priced holdings total")}
            />
            <AssetMetric
              label={t("assets.metric.unrealized", "Unrealized P/L")}
              value={
                summary
                  ? formatMoney(summary.totals.unrealized_pnl, baseCurrency, notAvailableLabel)
                  : "—"
              }
              meta={t("assets.metric.unrealizedMeta", "Across priced positions")}
            />
            <AssetMetric
              label={t("assets.metric.positions", "Positions")}
              value={summary ? `${summary.totals.position_count}` : "—"}
              meta={t("assets.metric.positionsMeta", "Tracked assets")}
            />
            <AssetMetric
              label={t("assets.accounts", "Accounts")}
              value={summary ? `${summary.totals.account_count}` : "—"}
              meta={t("assets.metric.accountsMeta", "Portfolio buckets")}
            />
          </div>
          </CardContent>
        </Card>

        <section className="grid gap-6 xl:grid-cols-[minmax(0,1.05fr)_minmax(0,0.95fr)]">
          <section className="viewer-frame px-6 py-6 md:px-8">
            <div className="flex items-center justify-between gap-4">
              <div>
                <p className="text-[11px] font-semibold uppercase tracking-[0.2em] text-slate-500">
                  {t("assets.accounts", "Accounts")}
                </p>
                <h2 className="mt-2 text-2xl font-semibold tracking-tight text-slate-900">
                  {t("assets.groupedExposure", "Grouped exposure")}
                </h2>
              </div>
              {summary ? (
                <Badge variant="secondary" className="text-slate-500">
                  {t("assets.platformCount", ({ count }) => `${count} platform(s)`, {
                    count: summary.groups.length,
                  })}
                </Badge>
              ) : null}
            </div>

            {loading ? (
              <div className="mt-5 rounded-[24px] border border-dashed border-[var(--border)] bg-[var(--surface-strong)] px-5 py-8 text-sm text-slate-500">
                {t("assets.loadingSummary", "Loading asset summary...")}
              </div>
            ) : !summary || summary.groups.length === 0 ? (
              <div className="mt-5 rounded-[24px] border border-dashed border-[var(--border)] bg-[var(--surface-strong)] px-5 py-8 text-sm text-slate-500">
                {t(
                  "assets.noGroups",
                  "No priced platform groups yet. Add a position or refresh manual values."
                )}
              </div>
            ) : (
              <div className="mt-5 space-y-4">
                {summary.groups.map((group) => (
                  <div
                    key={group.platform_name}
                    className="rounded-[24px] border border-[var(--border)] bg-white/88 px-4 py-4"
                  >
                    <div className="flex flex-wrap items-center justify-between gap-3">
                      <div>
                        <p className="text-lg font-semibold text-slate-900">
                          {group.platform_name}
                        </p>
                        <p className="mt-1 text-xs uppercase tracking-[0.16em] text-slate-500">
                          {t("assets.accountCount", ({ count }) => `${count} account(s)`, {
                            count: group.accounts.length,
                          })}
                        </p>
                      </div>
                      <div className="text-right">
                        <p className="text-sm font-semibold text-slate-900">
                          {formatMoney(group.market_value, baseCurrency, notAvailableLabel)}
                        </p>
                        <p className="mt-1 text-xs text-slate-500">
                          {t("assets.pnlValue", ({ value }) => `P/L ${value}`, {
                            value: formatMoney(
                              group.unrealized_pnl,
                              baseCurrency,
                              notAvailableLabel
                            ),
                          })}
                        </p>
                      </div>
                    </div>

                    <div className="mt-4 space-y-3">
                      {group.accounts.map((account) => (
                        <div
                          key={account.account_id}
                          className="rounded-[20px] border border-[var(--border)] bg-[var(--surface-strong)] px-4 py-4"
                        >
                          <div className="flex items-center justify-between gap-3">
                            <div>
                              <p className="text-sm font-semibold text-slate-900">
                                {account.account_name}
                              </p>
                              <p className="mt-1 text-xs text-slate-500">
                                {t(
                                  "assets.positionCount",
                                  ({ count }) => `${count} position(s)`,
                                  { count: account.positions.length }
                                )}
                              </p>
                            </div>
                            <div className="text-right">
                              <p className="text-sm font-semibold text-slate-900">
                                {formatMoney(
                                  account.market_value,
                                  baseCurrency,
                                  notAvailableLabel
                                )}
                              </p>
                              <p className="mt-1 text-xs text-slate-500">
                                {t("assets.pnlValue", ({ value }) => `P/L ${value}`, {
                                  value: formatMoney(
                                    account.unrealized_pnl,
                                    baseCurrency,
                                    notAvailableLabel
                                  ),
                                })}
                              </p>
                            </div>
                          </div>

                          <div className="mt-4 space-y-2">
                            {account.positions.map((position) => (
                              <div
                                key={position.id}
                                className="flex flex-wrap items-center justify-between gap-3 rounded-[18px] border border-[var(--border)] bg-white px-3 py-3"
                              >
                                <div className="min-w-0">
                                  <p className="truncate text-sm font-semibold text-slate-900">
                                    {position.asset_name}
                                    {position.ticker ? ` (${position.ticker})` : ""}
                                  </p>
                                  <p className="mt-1 text-xs text-slate-500">
                                    {t(
                                      "assets.positionMeta",
                                      ({ quantity, category, state }) =>
                                        `Qty ${quantity} · ${category} · ${state}`,
                                      {
                                        quantity: position.quantity,
                                        category: position.asset_category,
                                        state: position.state,
                                      }
                                    )}
                                  </p>
                                </div>
                                <div className="text-right">
                                  <p className="text-sm font-semibold text-slate-900">
                                    {formatMoney(
                                      position.latest_snapshot?.market_value,
                                      baseCurrency,
                                      notAvailableLabel
                                    )}
                                  </p>
                                  <p className="mt-1 text-xs text-slate-500">
                                    {t("assets.pnlValue", ({ value }) => `P/L ${value}`, {
                                      value: formatMoney(
                                        position.latest_snapshot?.unrealized_pnl,
                                        baseCurrency,
                                        notAvailableLabel
                                      ),
                                    })}
                                  </p>
                                </div>
                              </div>
                            ))}
                          </div>
                        </div>
                      ))}
                    </div>
                  </div>
                ))}
              </div>
            )}
          </section>

          <div className="space-y-6">
            <Card className="card-surface rounded-[28px]">
              <CardContent className="px-6 py-6">
              <div className="flex items-center justify-between gap-4">
                <div>
                  <p className="text-[11px] font-semibold uppercase tracking-[0.2em] text-slate-500">
                    {t("assets.ledgerHealth", "Ledger Health")}
                  </p>
                  <h2 className="mt-2 text-2xl font-semibold tracking-tight text-slate-900">
                    {t("assets.pricingState", "Pricing state")}
                  </h2>
                </div>
                {summary ? (
                  <Badge variant="secondary" className="text-slate-500">
                    {summary.base_currency}
                  </Badge>
                ) : null}
              </div>

              <div className="mt-5 grid gap-3 sm:grid-cols-2">
                <AssetHealthTile
                  label={t("assets.priced", "Priced")}
                  value={summary ? `${summary.totals.priced_position_count}` : "—"}
                />
                <AssetHealthTile
                  label={t("assets.unpriced", "Unpriced")}
                  value={summary ? `${summary.totals.unpriced_position_count}` : "—"}
                />
              </div>

              <Button
                type="button"
                variant="secondary"
                className="mt-5 w-full"
                disabled={submitting}
                onClick={() => void handleRefreshAll(true)}
              >
                {t("assets.forceRevalue", "Force Revalue All Positions")}
              </Button>
              </CardContent>
            </Card>

            <Card className="card-surface rounded-[28px]">
              <CardContent className="px-6 py-6">
              <p className="text-[11px] font-semibold uppercase tracking-[0.2em] text-slate-500">
                {t("assets.unpricedQueue", "Unpriced Queue")}
              </p>
              <div className="mt-4 space-y-3">
                {!summary || summary.unpriced_positions.length === 0 ? (
                  <div className="rounded-[22px] border border-dashed border-[var(--border)] bg-[var(--surface-strong)] px-4 py-6 text-sm text-slate-500">
                    {t(
                      "assets.noUnpriced",
                      "No unresolved or manual-only positions waiting for pricing attention."
                    )}
                  </div>
                ) : (
                  summary.unpriced_positions.map((position) => (
                    <div
                      key={position.id}
                      className="rounded-[20px] border border-[var(--border)] bg-white/88 px-4 py-4"
                    >
                      <div className="flex items-center justify-between gap-4">
                        <div className="min-w-0">
                          <p className="truncate text-sm font-semibold text-slate-900">
                            {position.asset_name}
                          </p>
                          <p className="mt-1 text-xs text-slate-500">
                            {position.account.platform_name} / {position.account.account_name}
                          </p>
                        </div>
                        <Badge variant="secondary">
                          {position.state}
                        </Badge>
                      </div>
                      {position.error_message ? (
                        <p className="mt-3 text-sm leading-6 text-[var(--danger)]">
                          {position.error_message}
                        </p>
                      ) : null}
                    </div>
                  ))
                )}
              </div>
              </CardContent>
            </Card>
          </div>
        </section>

        <Card className="card-surface rounded-[28px]">
          <CardContent className="px-6 py-6">
          <div className="flex items-center justify-between gap-4">
            <div>
              <p className="text-[11px] font-semibold uppercase tracking-[0.2em] text-slate-500">
                {t("assets.ledgerTable", "Ledger Table")}
              </p>
              <h2 className="mt-2 text-2xl font-semibold tracking-tight text-slate-900">
                {t("assets.allPositions", "All positions")}
              </h2>
            </div>
            <Badge variant="secondary" className="text-slate-500">
              {flatPositions.length}
            </Badge>
          </div>

          {loading ? (
            <div className="mt-5 rounded-[24px] border border-dashed border-[var(--border)] bg-[var(--surface-strong)] px-5 py-8 text-sm text-slate-500">
              {t("assets.loadingLedger", "Loading asset ledger...")}
            </div>
          ) : flatPositions.length === 0 ? (
            <div className="mt-5 rounded-[24px] border border-dashed border-[var(--border)] bg-[var(--surface-strong)] px-5 py-8 text-sm text-slate-500">
              {t("assets.noPositions", "No tracked positions yet.")}
            </div>
          ) : (
            <div className="mt-5">
              <Table className="min-w-full border-separate border-spacing-y-3">
                <TableHeader>
                  <TableRow className="text-left text-[11px] uppercase tracking-[0.18em] text-slate-500">
                    <TableHead>{t("assets.asset", "Asset")}</TableHead>
                    <TableHead>{t("assets.account", "Account")}</TableHead>
                    <TableHead>{t("assets.quantityShort", "Qty")}</TableHead>
                    <TableHead>{t("assets.state", "State")}</TableHead>
                    <TableHead>{t("assets.value", "Value")}</TableHead>
                    <TableHead>{t("assets.actions", "Actions")}</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {flatPositions.map((position) => (
                    <TableRow
                      key={position.id}
                      className="rounded-[22px] border border-[var(--border)] bg-white/90 shadow-[0_8px_20px_rgba(18,28,41,0.04)]"
                    >
                      <TableCell className="rounded-l-[22px]">
                        <p className="font-semibold text-slate-900">
                          {position.asset_name}
                        </p>
                        <p className="mt-1 text-xs text-slate-500">
                          {position.ticker || position.asset_category}
                        </p>
                      </TableCell>
                      <TableCell className="text-sm text-slate-700">
                        {position.account.platform_name}
                        <div className="mt-1 text-xs text-slate-500">
                          {position.account.account_name}
                        </div>
                      </TableCell>
                      <TableCell className="text-sm text-slate-700">
                        {position.quantity}
                      </TableCell>
                      <TableCell>
                        <Badge variant="secondary">
                          {position.state}
                        </Badge>
                      </TableCell>
                      <TableCell className="text-sm text-slate-700">
                        {formatMoney(
                          position.latest_snapshot?.market_value,
                          baseCurrency,
                          notAvailableLabel
                        )}
                      </TableCell>
                      <TableCell className="rounded-r-[22px]">
                        <div className="flex flex-wrap gap-2">
                          <Button
                            type="button"
                            variant="secondary"
                            size="sm"
                            disabled={submitting}
                            onClick={() => void handleRefreshOne(position)}
                          >
                            {t("common.refresh", "Refresh")}
                          </Button>
                          <Button
                            type="button"
                            variant="secondary"
                            size="sm"
                            disabled={submitting}
                            onClick={() => void openEditDialog(position.id)}
                          >
                            {t("common.edit", "Edit")}
                          </Button>
                          <Button
                            type="button"
                            variant="outline"
                            size="sm"
                            className="border-[rgba(163,53,53,0.2)] bg-[rgba(163,53,53,0.08)] text-[var(--danger)] hover:bg-[rgba(163,53,53,0.12)] hover:text-[var(--danger)]"
                            disabled={submitting}
                            onClick={() => void handleDelete(position)}
                          >
                            {t("common.delete", "Delete")}
                          </Button>
                        </div>
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </div>
          )}
          </CardContent>
        </Card>
      </div>

      <Dialog open={dialogOpen} onOpenChange={(open) => !open && setDialogOpen(false)}>
        <DialogContent
          aria-label={
            editingPositionId
              ? t("assets.editAsset", "Edit asset")
              : t("assets.addAsset", "Add asset")
          }
          className="modal-panel max-w-3xl"
        >
        <DialogHeader className="pr-12">
          <p className="text-[11px] font-semibold uppercase tracking-[0.34em] text-[var(--primary)]">
            {t("sidebar.nav.assets", "Assets")}
          </p>
          <DialogTitle>
            {editingPositionId
              ? t("assets.editAsset", "Edit Asset")
              : t("assets.addAsset", "Add Asset")}
          </DialogTitle>
          <DialogDescription className="max-w-2xl">
            {t(
              "assets.dialogDescription",
              "Store the account bucket, the held quantity, and either a market ticker or a manual valuation so the ledger and portfolio manager stay aligned."
            )}
          </DialogDescription>
        </DialogHeader>

        <div className="mt-8 grid gap-6">
          <section className="grid gap-4 md:grid-cols-2">
            <Field label={t("assets.platform", "Platform")}>
              <Input
                type="text"
                value={draft.platform_name}
                onChange={(event) =>
                  setDraft((current) => ({
                    ...current,
                    platform_name: event.target.value,
                  }))
                }
                className="mt-3 border-[var(--border)] bg-[var(--surface-strong)] font-semibold text-slate-900"
                placeholder="Broker"
              />
            </Field>
            <Field label={t("assets.account", "Account")}>
              <Input
                type="text"
                value={draft.account_name}
                onChange={(event) =>
                  setDraft((current) => ({
                    ...current,
                    account_name: event.target.value,
                  }))
                }
                className="mt-3 border-[var(--border)] bg-[var(--surface-strong)] font-semibold text-slate-900"
                placeholder="Taxable"
              />
            </Field>
          </section>

          <section className="grid gap-4 md:grid-cols-2">
            <Field label={t("assets.assetName", "Asset Name")}>
              <Input
                type="text"
                value={draft.asset_name}
                onChange={(event) =>
                  setDraft((current) => ({
                    ...current,
                    asset_name: event.target.value,
                  }))
                }
                className="mt-3 border-[var(--border)] bg-[var(--surface-strong)] font-semibold text-slate-900"
                placeholder="Apple Inc."
              />
            </Field>
            <Field label={t("assets.category", "Category")}>
              <Input
                type="text"
                value={draft.asset_category}
                onChange={(event) =>
                  setDraft((current) => ({
                    ...current,
                    asset_category: event.target.value,
                  }))
                }
                className="mt-3 border-[var(--border)] bg-[var(--surface-strong)] font-semibold text-slate-900"
                placeholder="stock, crypto, cash"
              />
            </Field>
          </section>

          <section className="grid gap-4 md:grid-cols-3">
            <Field label={t("assets.quantity", "Quantity")}>
              <Input
                type="number"
                step="any"
                value={draft.quantity}
                onChange={(event) =>
                  setDraft((current) => ({
                    ...current,
                    quantity: event.target.value,
                  }))
                }
                className="mt-3 border-[var(--border)] bg-[var(--surface-strong)] font-semibold text-slate-900"
              />
            </Field>
            <Field label={t("assets.costBasis", "Cost Basis")}>
              <Input
                type="number"
                step="any"
                value={draft.cost_basis}
                onChange={(event) =>
                  setDraft((current) => ({
                    ...current,
                    cost_basis: event.target.value,
                  }))
                }
                className="mt-3 border-[var(--border)] bg-[var(--surface-strong)] font-semibold text-slate-900"
              />
            </Field>
            <Field label={t("assets.currency", "Currency")}>
              <Input
                type="text"
                value={draft.currency}
                onChange={(event) =>
                  setDraft((current) => ({
                    ...current,
                    currency: event.target.value.toUpperCase(),
                  }))
                }
                className="mt-3 border-[var(--border)] bg-[var(--surface-strong)] font-semibold text-slate-900"
                placeholder="USD"
              />
            </Field>
          </section>

          <section className="rounded-3xl border border-[var(--border)] bg-white/90 p-4">
            <p className="text-xs font-semibold uppercase tracking-[0.24em] text-slate-500">
              {t("assets.valuationMode", "Valuation Mode")}
            </p>
            <div className="mt-3 flex flex-wrap gap-3">
              {(["market", "manual"] as const).map((mode) => {
                const active = draft.valuation_mode === mode;
                return (
                  <Button
                    key={mode}
                    type="button"
                    variant={active ? "default" : "secondary"}
                    size="sm"
                    onClick={() =>
                      setDraft((current) => ({
                        ...current,
                        valuation_mode: mode,
                        ticker: mode === "manual" ? "" : current.ticker,
                        manual_price:
                          mode === "market" ? "" : current.manual_price,
                      }))
                    }
                  >
                    {t(`assets.valuationMode.${mode}`, mode)}
                  </Button>
                );
              })}
            </div>
          </section>

          {draft.valuation_mode === "market" ? (
            <Field label={t("assets.ticker", "Ticker")}>
              <Input
                type="text"
                value={draft.ticker}
                onChange={(event) =>
                  setDraft((current) => ({
                    ...current,
                    ticker: event.target.value.toUpperCase(),
                  }))
                }
                className="mt-3 border-[var(--border)] bg-[var(--surface-strong)] font-semibold text-slate-900"
                placeholder="AAPL"
              />
            </Field>
          ) : (
            <Field label={t("assets.manualPrice", "Manual Price")}>
              <Input
                type="number"
                step="any"
                value={draft.manual_price}
                onChange={(event) =>
                  setDraft((current) => ({
                    ...current,
                    manual_price: event.target.value,
                  }))
                }
                className="mt-3 border-[var(--border)] bg-[var(--surface-strong)] font-semibold text-slate-900"
                placeholder="10000"
              />
            </Field>
          )}

          <Field label={t("assets.notes", "Notes")}>
            <Textarea
              value={draft.notes}
              onChange={(event) =>
                setDraft((current) => ({
                  ...current,
                  notes: event.target.value,
                }))
              }
              rows={4}
              className="mt-3 border-[var(--border)] bg-[var(--surface-strong)] text-slate-900"
              placeholder={t(
                "assets.notesPlaceholder",
                "Optional internal notes about this position."
              )}
            />
          </Field>

          <div className="flex flex-wrap justify-end gap-3">
            <Button type="button" variant="secondary" onClick={() => setDialogOpen(false)}>
              {t("common.cancel", "Cancel")}
            </Button>
            <Button
              type="button"
              disabled={submitting}
              onClick={() => void submitDraft()}
            >
              {editingPositionId
                ? t("assets.saveAsset", "Save Asset")
                : t("assets.createAsset", "Create Asset")}
            </Button>
          </div>
        </div>
        </DialogContent>
      </Dialog>
    </main>
  );
}

function Field({
  label,
  children,
}: {
  label: string;
  children: ReactNode;
}) {
  return (
    <label className="field-shell block rounded-3xl border border-[var(--border)] bg-white/90 p-4">
      <span className="field-label text-xs font-semibold uppercase tracking-[0.24em] text-slate-500">
        {label}
      </span>
      {children}
    </label>
  );
}

function AssetMetric({
  label,
  value,
  meta,
}: {
  label: string;
  value: string;
  meta: string;
}) {
  return (
    <Card className="rounded-[24px] bg-white/88">
      <CardContent className="px-4 py-4">
      <p className="text-[11px] font-semibold uppercase tracking-[0.18em] text-slate-500">
        {label}
      </p>
      <p className="mt-3 text-3xl font-semibold tracking-tight text-slate-900">
        {value}
      </p>
      <p className="mt-2 text-sm text-slate-500">{meta}</p>
      </CardContent>
    </Card>
  );
}

function AssetHealthTile({
  label,
  value,
}: {
  label: string;
  value: string;
}) {
  return (
    <Card className="rounded-[22px] bg-white/88">
      <CardContent className="px-4 py-4">
      <p className="text-[11px] font-semibold uppercase tracking-[0.18em] text-slate-500">
        {label}
      </p>
      <p className="mt-3 text-2xl font-semibold tracking-tight text-slate-900">
        {value}
      </p>
      </CardContent>
    </Card>
  );
}
