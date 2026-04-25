import { AUTH_REQUIRED_EVENT, ApiError } from "@/lib/api";

const API_BASE =
  process.env.NEXT_PUBLIC_API_BASE_URL ||
  process.env.NEXT_PUBLIC_API_URL ||
  "http://localhost:8000";

export interface AssetAccountRecord {
  id: string;
  platform_name: string;
  account_name: string;
}

export interface AssetValuationSnapshot {
  id: string;
  position_id: string;
  status: string;
  price: number | null;
  quote_currency: string | null;
  base_currency: string | null;
  fx_rate: number | null;
  market_value: number | null;
  unrealized_pnl: number | null;
  source: string | null;
  error_message: string | null;
  captured_at: string;
}

export interface AssetPositionRecord {
  id: string;
  owner_user_id: string;
  account: AssetAccountRecord;
  asset_name: string;
  asset_category: string;
  quantity: number;
  cost_basis: number;
  valuation_mode: "market" | "manual";
  manual_price: number | null;
  ticker: string | null;
  market: string | null;
  exchange: string | null;
  quote_type: string | null;
  resolved_name: string | null;
  currency: string | null;
  vendor: string | null;
  mapping_status: string | null;
  error_message: string | null;
  notes: string | null;
  state: string;
  is_stale: boolean;
  latest_snapshot: AssetValuationSnapshot | null;
  created_at: string;
  updated_at: string;
}

export interface AssetSummaryGroupAccount {
  account_id: string;
  account_name: string;
  market_value: number;
  unrealized_pnl: number;
  positions: AssetPositionRecord[];
}

export interface AssetSummaryGroup {
  platform_name: string;
  market_value: number;
  unrealized_pnl: number;
  accounts: AssetSummaryGroupAccount[];
}

export interface AssetSummaryPayload {
  base_currency: string;
  totals: {
    market_value: number;
    unrealized_pnl: number;
    position_count: number;
    account_count: number;
    priced_position_count: number;
    unpriced_position_count: number;
  };
  groups: AssetSummaryGroup[];
  unpriced_positions: AssetPositionRecord[];
}

export interface AssetPositionCreateRequest {
  platform_name: string;
  account_name: string;
  asset_name: string;
  asset_category: string;
  quantity: number;
  cost_basis: number;
  valuation_mode: "market" | "manual";
  ticker?: string | null;
  market?: string | null;
  exchange?: string | null;
  quote_type?: string | null;
  resolved_name?: string | null;
  currency?: string | null;
  manual_price?: number | null;
  notes?: string | null;
}

export interface AssetRefreshRequest {
  base_currency: string;
  force?: boolean;
}

function buildApiUrl(path: string): string {
  return `${API_BASE}${path}`;
}

function createJsonRequestInit(method: string, payload?: unknown): RequestInit {
  const headers = new Headers();
  if (payload !== undefined) {
    headers.set("Content-Type", "application/json");
  }

  return {
    method,
    headers,
    body: payload === undefined ? undefined : JSON.stringify(payload),
  };
}

function emitAuthRequired(detail: string): void {
  if (typeof window === "undefined") {
    return;
  }

  window.dispatchEvent(
    new CustomEvent(AUTH_REQUIRED_EVENT, {
      detail: { detail },
    })
  );
}

async function parseJsonResponse<T>(response: Response): Promise<T> {
  if (!response.ok) {
    let detail = response.statusText || `${response.status}`;

    try {
      const payload = (await response.json()) as { detail?: string };
      if (typeof payload.detail === "string" && payload.detail.trim()) {
        detail = payload.detail;
      }
    } catch {
      // Fall back to status text.
    }

    if (response.status === 401) {
      emitAuthRequired(detail);
    }

    throw new ApiError(response.status, detail);
  }

  return (await response.json()) as T;
}

async function requestJson<T>(path: string, init: RequestInit = {}): Promise<T> {
  const response = await fetch(buildApiUrl(path), {
    credentials: "include",
    ...init,
  });
  return parseJsonResponse<T>(response);
}

export async function getAssetSummary(options: {
  baseCurrency?: string;
  refreshIfStale?: boolean;
}): Promise<AssetSummaryPayload> {
  const url = new URL(buildApiUrl("/api/assets/summary"));
  url.searchParams.set("base_currency", options.baseCurrency ?? "USD");
  url.searchParams.set("refresh_if_stale", String(options.refreshIfStale ?? true));

  const response = await fetch(url.toString(), {
    credentials: "include",
    cache: "no-store",
  });
  return parseJsonResponse<AssetSummaryPayload>(response);
}

export async function createAssetPosition(
  payload: AssetPositionCreateRequest
): Promise<AssetPositionRecord> {
  return requestJson<AssetPositionRecord>("/api/assets", createJsonRequestInit("POST", payload));
}

export async function getAssetPosition(positionId: string): Promise<AssetPositionRecord> {
  return requestJson<AssetPositionRecord>(`/api/assets/${positionId}`, {
    cache: "no-store",
  });
}

export async function updateAssetPosition(
  positionId: string,
  payload: Partial<AssetPositionCreateRequest>
): Promise<AssetPositionRecord> {
  return requestJson<AssetPositionRecord>(
    `/api/assets/${positionId}`,
    createJsonRequestInit("PUT", payload)
  );
}

export async function deleteAssetPosition(
  positionId: string
): Promise<{ deleted: boolean; position_id: string }> {
  return requestJson<{ deleted: boolean; position_id: string }>(
    `/api/assets/${positionId}`,
    createJsonRequestInit("DELETE")
  );
}

export async function refreshAssetPosition(
  positionId: string,
  payload: AssetRefreshRequest
): Promise<AssetPositionRecord> {
  return requestJson<AssetPositionRecord>(
    `/api/assets/${positionId}/refresh`,
    createJsonRequestInit("POST", payload)
  );
}

export async function refreshAssetPositions(
  payload: AssetRefreshRequest
): Promise<AssetPositionRecord[]> {
  return requestJson<AssetPositionRecord[]>(
    "/api/assets/refresh",
    createJsonRequestInit("POST", payload)
  );
}
