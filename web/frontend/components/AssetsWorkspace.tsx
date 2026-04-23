"use client";

import { useEffect, useMemo, useState, type ReactNode } from "react";
import { AccessibleDialog } from "@/components/AccessibleDialog";
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

function formatMoney(value: number | null | undefined, currency: string): string {
  if (value === null || value === undefined) {
    return "N/A";
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
  const [baseCurrency, setBaseCurrency] = useState(DEFAULT_BASE_CURRENCY);
  const [summary, setSummary] = useState<AssetSummaryPayload | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [dialogOpen, setDialogOpen] = useState(false);
  const [editingPositionId, setEditingPositionId] = useState<string | null>(null);
  const [draft, setDraft] = useState<AssetDraft>(buildEmptyDraft());

  const loadSummary = async (refreshIfStale = true) => {
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
          : "Unable to load the asset ledger"
      );
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    void loadSummary(true);
  }, [baseCurrency]);

  const flatPositions = useMemo(() => flattenPositions(summary), [summary]);

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
          : "Unable to load the selected asset"
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
          : "Unable to save the asset"
      );
    } finally {
      setSubmitting(false);
    }
  };

  const handleDelete = async (position: AssetPositionRecord) => {
    const confirmed = window.confirm(
      `Delete ${position.asset_name} from ${position.account.platform_name} / ${position.account.account_name}?`
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
          : "Unable to delete the asset"
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
          : "Unable to refresh the asset"
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
          : "Unable to refresh the asset ledger"
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
        <section className="card-surface rounded-[30px] px-6 py-8 md:px-8">
          <div className="flex flex-col gap-6 lg:flex-row lg:items-end lg:justify-between">
            <div className="max-w-3xl">
              <p className="text-[11px] font-semibold uppercase tracking-[0.24em] text-[var(--primary)]">
                Assets
              </p>
              <h1 className="mt-3 text-4xl font-semibold tracking-tight text-slate-900 md:text-[3.2rem]">
                Portfolio ledger
              </h1>
              <p className="mt-4 max-w-2xl text-sm leading-7 text-slate-600">
                Track accounts, current holdings, manual assets, and marked-to-market
                exposure in one PostgreSQL-backed ledger that the portfolio manager can
                reuse during analysis runs.
              </p>
            </div>

            <div className="flex flex-wrap gap-3">
              <label className="rounded-full border border-[var(--border)] bg-white px-4 py-3 text-xs font-semibold uppercase tracking-[0.16em] text-slate-600">
                Base
                <input
                  type="text"
                  value={baseCurrency}
                  onChange={(event) => setBaseCurrency(event.target.value.toUpperCase())}
                  className="ml-2 w-14 border-none bg-transparent text-right text-sm font-semibold text-slate-900 outline-none"
                />
              </label>
              <button
                type="button"
                className="interactive-button focus-ring rounded-full border border-[var(--border-strong)] bg-white px-5 py-3 text-xs font-semibold tracking-[0.04em] text-slate-700"
                disabled={submitting}
                onClick={() => void handleRefreshAll(false)}
              >
                Refresh Due
              </button>
              <button
                type="button"
                className="interactive-button focus-ring rounded-full border border-[var(--primary)] bg-[var(--primary)] px-5 py-3 text-xs font-semibold tracking-[0.04em] text-white"
                disabled={submitting}
                onClick={openCreateDialog}
              >
                Add Asset
              </button>
            </div>
          </div>

          <div className="mt-8 grid gap-4 md:grid-cols-4">
            <AssetMetric
              label="Market Value"
              value={summary ? formatMoney(summary.totals.market_value, baseCurrency) : "—"}
              meta="Priced holdings total"
            />
            <AssetMetric
              label="Unrealized P/L"
              value={summary ? formatMoney(summary.totals.unrealized_pnl, baseCurrency) : "—"}
              meta="Across priced positions"
            />
            <AssetMetric
              label="Positions"
              value={summary ? `${summary.totals.position_count}` : "—"}
              meta="Tracked assets"
            />
            <AssetMetric
              label="Accounts"
              value={summary ? `${summary.totals.account_count}` : "—"}
              meta="Portfolio buckets"
            />
          </div>
        </section>

        <section className="grid gap-6 xl:grid-cols-[minmax(0,1.05fr)_minmax(0,0.95fr)]">
          <section className="viewer-frame px-6 py-6 md:px-8">
            <div className="flex items-center justify-between gap-4">
              <div>
                <p className="text-[11px] font-semibold uppercase tracking-[0.2em] text-slate-500">
                  Accounts
                </p>
                <h2 className="mt-2 text-2xl font-semibold tracking-tight text-slate-900">
                  Grouped exposure
                </h2>
              </div>
              {summary ? (
                <span className="rounded-full border border-[var(--border)] bg-white px-3 py-1 text-[11px] font-semibold text-slate-500">
                  {summary.groups.length} platform(s)
                </span>
              ) : null}
            </div>

            {loading ? (
              <div className="mt-5 rounded-[24px] border border-dashed border-[var(--border)] bg-[var(--surface-strong)] px-5 py-8 text-sm text-slate-500">
                Loading asset summary...
              </div>
            ) : !summary || summary.groups.length === 0 ? (
              <div className="mt-5 rounded-[24px] border border-dashed border-[var(--border)] bg-[var(--surface-strong)] px-5 py-8 text-sm text-slate-500">
                No priced platform groups yet. Add a position or refresh manual values.
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
                          {group.accounts.length} account(s)
                        </p>
                      </div>
                      <div className="text-right">
                        <p className="text-sm font-semibold text-slate-900">
                          {formatMoney(group.market_value, baseCurrency)}
                        </p>
                        <p className="mt-1 text-xs text-slate-500">
                          P/L {formatMoney(group.unrealized_pnl, baseCurrency)}
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
                                {account.positions.length} position(s)
                              </p>
                            </div>
                            <div className="text-right">
                              <p className="text-sm font-semibold text-slate-900">
                                {formatMoney(account.market_value, baseCurrency)}
                              </p>
                              <p className="mt-1 text-xs text-slate-500">
                                P/L {formatMoney(account.unrealized_pnl, baseCurrency)}
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
                                    Qty {position.quantity} · {position.asset_category} ·{" "}
                                    {position.state}
                                  </p>
                                </div>
                                <div className="text-right">
                                  <p className="text-sm font-semibold text-slate-900">
                                    {formatMoney(
                                      position.latest_snapshot?.market_value,
                                      baseCurrency
                                    )}
                                  </p>
                                  <p className="mt-1 text-xs text-slate-500">
                                    P/L{" "}
                                    {formatMoney(
                                      position.latest_snapshot?.unrealized_pnl,
                                      baseCurrency
                                    )}
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
            <section className="card-surface rounded-[28px] px-6 py-6">
              <div className="flex items-center justify-between gap-4">
                <div>
                  <p className="text-[11px] font-semibold uppercase tracking-[0.2em] text-slate-500">
                    Ledger Health
                  </p>
                  <h2 className="mt-2 text-2xl font-semibold tracking-tight text-slate-900">
                    Pricing state
                  </h2>
                </div>
                {summary ? (
                  <span className="rounded-full border border-[var(--border)] bg-white px-3 py-1 text-[11px] font-semibold text-slate-500">
                    {summary.base_currency}
                  </span>
                ) : null}
              </div>

              <div className="mt-5 grid gap-3 sm:grid-cols-2">
                <AssetHealthTile
                  label="Priced"
                  value={summary ? `${summary.totals.priced_position_count}` : "—"}
                />
                <AssetHealthTile
                  label="Unpriced"
                  value={summary ? `${summary.totals.unpriced_position_count}` : "—"}
                />
              </div>

              <button
                type="button"
                className="interactive-button focus-ring mt-5 w-full rounded-[20px] border border-[var(--border-strong)] bg-white px-4 py-3 text-sm font-semibold text-slate-700"
                disabled={submitting}
                onClick={() => void handleRefreshAll(true)}
              >
                Force Revalue All Positions
              </button>
            </section>

            <section className="card-surface rounded-[28px] px-6 py-6">
              <p className="text-[11px] font-semibold uppercase tracking-[0.2em] text-slate-500">
                Unpriced Queue
              </p>
              <div className="mt-4 space-y-3">
                {!summary || summary.unpriced_positions.length === 0 ? (
                  <div className="rounded-[22px] border border-dashed border-[var(--border)] bg-[var(--surface-strong)] px-4 py-6 text-sm text-slate-500">
                    No unresolved or manual-only positions waiting for pricing attention.
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
                        <span className="rounded-full border border-[var(--border)] bg-[var(--surface-strong)] px-3 py-1 text-[10px] font-semibold uppercase tracking-[0.16em] text-slate-600">
                          {position.state}
                        </span>
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
            </section>
          </div>
        </section>

        <section className="card-surface rounded-[28px] px-6 py-6">
          <div className="flex items-center justify-between gap-4">
            <div>
              <p className="text-[11px] font-semibold uppercase tracking-[0.2em] text-slate-500">
                Ledger Table
              </p>
              <h2 className="mt-2 text-2xl font-semibold tracking-tight text-slate-900">
                All positions
              </h2>
            </div>
            <span className="rounded-full border border-[var(--border)] bg-white px-3 py-1 text-[11px] font-semibold text-slate-500">
              {flatPositions.length}
            </span>
          </div>

          {loading ? (
            <div className="mt-5 rounded-[24px] border border-dashed border-[var(--border)] bg-[var(--surface-strong)] px-5 py-8 text-sm text-slate-500">
              Loading asset ledger...
            </div>
          ) : flatPositions.length === 0 ? (
            <div className="mt-5 rounded-[24px] border border-dashed border-[var(--border)] bg-[var(--surface-strong)] px-5 py-8 text-sm text-slate-500">
              No tracked positions yet.
            </div>
          ) : (
            <div className="mt-5 overflow-x-auto">
              <table className="min-w-full border-separate border-spacing-y-3">
                <thead>
                  <tr className="text-left text-[11px] uppercase tracking-[0.18em] text-slate-500">
                    <th className="px-3 py-2">Asset</th>
                    <th className="px-3 py-2">Account</th>
                    <th className="px-3 py-2">Qty</th>
                    <th className="px-3 py-2">State</th>
                    <th className="px-3 py-2">Value</th>
                    <th className="px-3 py-2">Actions</th>
                  </tr>
                </thead>
                <tbody>
                  {flatPositions.map((position) => (
                    <tr
                      key={position.id}
                      className="rounded-[22px] border border-[var(--border)] bg-white/90 shadow-[0_8px_20px_rgba(18,28,41,0.04)]"
                    >
                      <td className="rounded-l-[22px] px-3 py-4">
                        <p className="font-semibold text-slate-900">
                          {position.asset_name}
                        </p>
                        <p className="mt-1 text-xs text-slate-500">
                          {position.ticker || position.asset_category}
                        </p>
                      </td>
                      <td className="px-3 py-4 text-sm text-slate-700">
                        {position.account.platform_name}
                        <div className="mt-1 text-xs text-slate-500">
                          {position.account.account_name}
                        </div>
                      </td>
                      <td className="px-3 py-4 text-sm text-slate-700">
                        {position.quantity}
                      </td>
                      <td className="px-3 py-4">
                        <span className="rounded-full border border-[var(--border)] bg-[var(--surface-strong)] px-3 py-1 text-[10px] font-semibold uppercase tracking-[0.16em] text-slate-600">
                          {position.state}
                        </span>
                      </td>
                      <td className="px-3 py-4 text-sm text-slate-700">
                        {formatMoney(position.latest_snapshot?.market_value, baseCurrency)}
                      </td>
                      <td className="rounded-r-[22px] px-3 py-4">
                        <div className="flex flex-wrap gap-2">
                          <button
                            type="button"
                            className="focus-ring rounded-full border border-[var(--border)] bg-white px-3 py-2 text-xs font-semibold text-slate-700"
                            disabled={submitting}
                            onClick={() => void handleRefreshOne(position)}
                          >
                            Refresh
                          </button>
                          <button
                            type="button"
                            className="focus-ring rounded-full border border-[var(--border)] bg-white px-3 py-2 text-xs font-semibold text-slate-700"
                            disabled={submitting}
                            onClick={() => void openEditDialog(position.id)}
                          >
                            Edit
                          </button>
                          <button
                            type="button"
                            className="focus-ring rounded-full border border-[rgba(163,53,53,0.2)] bg-[rgba(163,53,53,0.08)] px-3 py-2 text-xs font-semibold text-[var(--danger)]"
                            disabled={submitting}
                            onClick={() => void handleDelete(position)}
                          >
                            Delete
                          </button>
                        </div>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </section>
      </div>

      <AccessibleDialog
        isOpen={dialogOpen}
        onClose={() => setDialogOpen(false)}
        ariaLabel={editingPositionId ? "Edit asset" : "Add asset"}
        panelClassName="modal-panel scrollbar-hidden fade-in max-h-[92vh] w-full max-w-3xl overflow-y-auto rounded-[30px] border border-[var(--border)] bg-[var(--surface)] p-6 shadow-[0_28px_80px_rgba(18,28,41,0.24)] md:p-8"
      >
        <div className="flex flex-wrap items-start justify-between gap-4">
          <div>
            <p className="text-[11px] font-semibold uppercase tracking-[0.34em] text-[var(--primary)]">
              Assets
            </p>
            <h2 className="mt-3 text-3xl font-bold tracking-tight text-slate-900">
              {editingPositionId ? "Edit Asset" : "Add Asset"}
            </h2>
            <p className="mt-2 max-w-2xl text-sm leading-6 text-slate-600">
              Store the account bucket, the held quantity, and either a market ticker
              or a manual valuation so the ledger and portfolio manager stay aligned.
            </p>
          </div>
          <button
            type="button"
            className="interactive-button focus-ring rounded-full border border-[var(--border)] bg-white px-4 py-2 text-xs font-semibold uppercase tracking-[0.2em] text-slate-600"
            onClick={() => setDialogOpen(false)}
          >
            Close
          </button>
        </div>

        <div className="mt-8 grid gap-6">
          <section className="grid gap-4 md:grid-cols-2">
            <Field label="Platform">
              <input
                type="text"
                value={draft.platform_name}
                onChange={(event) =>
                  setDraft((current) => ({
                    ...current,
                    platform_name: event.target.value,
                  }))
                }
                className="focus-ring mt-3 w-full rounded-2xl border border-[var(--border)] bg-[var(--surface-strong)] px-4 py-3 text-sm font-semibold text-slate-900"
                placeholder="Broker"
              />
            </Field>
            <Field label="Account">
              <input
                type="text"
                value={draft.account_name}
                onChange={(event) =>
                  setDraft((current) => ({
                    ...current,
                    account_name: event.target.value,
                  }))
                }
                className="focus-ring mt-3 w-full rounded-2xl border border-[var(--border)] bg-[var(--surface-strong)] px-4 py-3 text-sm font-semibold text-slate-900"
                placeholder="Taxable"
              />
            </Field>
          </section>

          <section className="grid gap-4 md:grid-cols-2">
            <Field label="Asset Name">
              <input
                type="text"
                value={draft.asset_name}
                onChange={(event) =>
                  setDraft((current) => ({
                    ...current,
                    asset_name: event.target.value,
                  }))
                }
                className="focus-ring mt-3 w-full rounded-2xl border border-[var(--border)] bg-[var(--surface-strong)] px-4 py-3 text-sm font-semibold text-slate-900"
                placeholder="Apple Inc."
              />
            </Field>
            <Field label="Category">
              <input
                type="text"
                value={draft.asset_category}
                onChange={(event) =>
                  setDraft((current) => ({
                    ...current,
                    asset_category: event.target.value,
                  }))
                }
                className="focus-ring mt-3 w-full rounded-2xl border border-[var(--border)] bg-[var(--surface-strong)] px-4 py-3 text-sm font-semibold text-slate-900"
                placeholder="stock, crypto, cash"
              />
            </Field>
          </section>

          <section className="grid gap-4 md:grid-cols-3">
            <Field label="Quantity">
              <input
                type="number"
                step="any"
                value={draft.quantity}
                onChange={(event) =>
                  setDraft((current) => ({
                    ...current,
                    quantity: event.target.value,
                  }))
                }
                className="focus-ring mt-3 w-full rounded-2xl border border-[var(--border)] bg-[var(--surface-strong)] px-4 py-3 text-sm font-semibold text-slate-900"
              />
            </Field>
            <Field label="Cost Basis">
              <input
                type="number"
                step="any"
                value={draft.cost_basis}
                onChange={(event) =>
                  setDraft((current) => ({
                    ...current,
                    cost_basis: event.target.value,
                  }))
                }
                className="focus-ring mt-3 w-full rounded-2xl border border-[var(--border)] bg-[var(--surface-strong)] px-4 py-3 text-sm font-semibold text-slate-900"
              />
            </Field>
            <Field label="Currency">
              <input
                type="text"
                value={draft.currency}
                onChange={(event) =>
                  setDraft((current) => ({
                    ...current,
                    currency: event.target.value.toUpperCase(),
                  }))
                }
                className="focus-ring mt-3 w-full rounded-2xl border border-[var(--border)] bg-[var(--surface-strong)] px-4 py-3 text-sm font-semibold text-slate-900"
                placeholder="USD"
              />
            </Field>
          </section>

          <section className="rounded-3xl border border-[var(--border)] bg-white/90 p-4">
            <p className="text-xs font-semibold uppercase tracking-[0.24em] text-slate-500">
              Valuation Mode
            </p>
            <div className="mt-3 flex flex-wrap gap-3">
              {(["market", "manual"] as const).map((mode) => {
                const active = draft.valuation_mode === mode;
                return (
                  <button
                    key={mode}
                    type="button"
                    className={`interactive-button focus-ring rounded-full border px-4 py-2 text-xs font-semibold uppercase tracking-[0.18em] ${
                      active
                        ? "border-[var(--primary)] bg-[var(--primary-soft)] text-[var(--primary-strong)]"
                        : "border-[var(--border)] bg-[var(--surface-strong)] text-slate-600"
                    }`}
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
                    {mode}
                  </button>
                );
              })}
            </div>
          </section>

          {draft.valuation_mode === "market" ? (
            <Field label="Ticker">
              <input
                type="text"
                value={draft.ticker}
                onChange={(event) =>
                  setDraft((current) => ({
                    ...current,
                    ticker: event.target.value.toUpperCase(),
                  }))
                }
                className="focus-ring mt-3 w-full rounded-2xl border border-[var(--border)] bg-[var(--surface-strong)] px-4 py-3 text-sm font-semibold text-slate-900"
                placeholder="AAPL"
              />
            </Field>
          ) : (
            <Field label="Manual Price">
              <input
                type="number"
                step="any"
                value={draft.manual_price}
                onChange={(event) =>
                  setDraft((current) => ({
                    ...current,
                    manual_price: event.target.value,
                  }))
                }
                className="focus-ring mt-3 w-full rounded-2xl border border-[var(--border)] bg-[var(--surface-strong)] px-4 py-3 text-sm font-semibold text-slate-900"
                placeholder="10000"
              />
            </Field>
          )}

          <Field label="Notes">
            <textarea
              value={draft.notes}
              onChange={(event) =>
                setDraft((current) => ({
                  ...current,
                  notes: event.target.value,
                }))
              }
              rows={4}
              className="focus-ring mt-3 w-full rounded-2xl border border-[var(--border)] bg-[var(--surface-strong)] px-4 py-3 text-sm text-slate-900"
              placeholder="Optional internal notes about this position."
            />
          </Field>

          <div className="flex flex-wrap justify-end gap-3">
            <button
              type="button"
              className="interactive-button focus-ring rounded-full border border-[var(--border-strong)] bg-white px-5 py-3 text-xs font-semibold tracking-[0.04em] text-slate-700"
              onClick={() => setDialogOpen(false)}
            >
              Cancel
            </button>
            <button
              type="button"
              className="interactive-button focus-ring rounded-full border border-[var(--primary)] bg-[var(--primary)] px-5 py-3 text-xs font-semibold tracking-[0.04em] text-white"
              disabled={submitting}
              onClick={() => void submitDraft()}
            >
              {editingPositionId ? "Save Asset" : "Create Asset"}
            </button>
          </div>
        </div>
      </AccessibleDialog>
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
    <div className="rounded-[24px] border border-[var(--border)] bg-white/88 px-4 py-4">
      <p className="text-[11px] font-semibold uppercase tracking-[0.18em] text-slate-500">
        {label}
      </p>
      <p className="mt-3 text-3xl font-semibold tracking-tight text-slate-900">
        {value}
      </p>
      <p className="mt-2 text-sm text-slate-500">{meta}</p>
    </div>
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
    <div className="rounded-[22px] border border-[var(--border)] bg-white/88 px-4 py-4">
      <p className="text-[11px] font-semibold uppercase tracking-[0.18em] text-slate-500">
        {label}
      </p>
      <p className="mt-3 text-2xl font-semibold tracking-tight text-slate-900">
        {value}
      </p>
    </div>
  );
}
