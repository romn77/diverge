const API_BASE =
  process.env.NEXT_PUBLIC_API_BASE_URL ||
  process.env.NEXT_PUBLIC_API_URL ||
  "http://localhost:8000";

export const AUTH_REQUIRED_EVENT = "diverge:auth-required";

export type AuthMode = "disabled" | "optional" | "required";
export type UserRole = "admin" | "operator" | "viewer";
export type UserStatus = "active" | "disabled";
export type Permission =
  | "analysis:create"
  | "analysis:read"
  | "screener:create"
  | "screener:read"
  | "assets:read"
  | "assets:write"
  | "journal:read"
  | "journal:write"
  | "admin:users"
  | "admin:settings"
  | "admin:audit";

export interface AuthTenant {
  id: string;
  name: string;
  slug: string;
  status: "active" | "disabled";
  created_at: string;
  updated_at: string;
}

export interface AuthUser {
  id: string;
  tenant_id: string;
  email: string;
  display_name: string;
  role: UserRole;
  status: UserStatus;
  must_change_password: boolean;
  last_login_at: string | null;
  created_at: string;
  updated_at: string;
  usage?: UserWeeklyUsage;
}

export interface AuthState {
  enabled: boolean;
  mode: AuthMode;
  authenticated: boolean;
  user: AuthUser | null;
  permissions: Permission[];
  tenant: AuthTenant | null;
}

export interface LoginRequest {
  email: string;
  password: string;
}

export interface ChangePasswordRequest {
  current_password: string;
  new_password: string;
}

export interface AdminUserCreateRequest {
  email: string;
  display_name: string;
  password: string;
  role: UserRole;
  status: UserStatus;
  must_change_password: boolean;
}

export interface AdminUserUpdateRequest {
  display_name?: string;
  role?: UserRole;
  status?: UserStatus;
  must_change_password?: boolean;
}

export interface AdminUserResetPasswordRequest {
  new_password: string;
  must_change_password: boolean;
}

export interface AdminAnalysisRoleLimit {
  role: UserRole;
  weekly_limit: number | null;
}

export interface AdminAnalysisLimitsResponse {
  limits: AdminAnalysisRoleLimit[];
}

export type DataSourceUsageModule = "analysis" | "screener" | "trade_journal";

export interface DataSourceUsageModuleSummary {
  total_calls: number;
  success_count: number;
  failure_count: number;
}

export interface AdminDataSourceUsage {
  vendor: string;
  label: string;
  enabled: boolean;
  daily_limit: number | null;
  hourly_limit: number | null;
  used_today: number;
  used_this_hour: number;
  remaining_today: number | null;
  remaining_this_hour: number | null;
  daily_exhausted: boolean;
  hour_exhausted: boolean;
  exhausted: boolean;
  success_count: number;
  failure_count: number;
  last_called_at: string | null;
  modules: Record<DataSourceUsageModule, DataSourceUsageModuleSummary>;
}

export type DataSourceRouteMarket = "cn" | "us" | "global";
export type DataSourceRouteCategory =
  | "core_stock_apis"
  | "technical_indicators"
  | "fundamental_data"
  | "news_data";

export interface AdminDataSourceRoute {
  module: DataSourceUsageModule;
  market: DataSourceRouteMarket;
  category: DataSourceRouteCategory;
  vendor_chain: string[];
  default_vendor_chain: string[];
}

export interface AdminDataSourceUsageResponse {
  date: string;
  sources: AdminDataSourceUsage[];
  routes: AdminDataSourceRoute[];
}

export interface AdminDataSourceUpdateRequest {
  enabled: boolean;
  daily_limit: number | null;
  hourly_limit: number | null;
}

export interface AdminDataSourceUpdateResponse {
  source: AdminDataSourceUsage;
}

export interface AdminDataSourceRouteUpdateRequest {
  vendor_chain: string[];
}

export interface AdminDataSourceRouteUpdateResponse {
  route: AdminDataSourceRoute;
}

export interface AdminLLMProvider {
  provider: string;
  label: string;
  enabled: boolean;
  base_url: string;
  api_key_env: string | null;
  key_status: "configured" | "missing";
  daily_limit: number | null;
  hourly_limit: number | null;
}

export interface AdminLLMModel {
  id: string;
  provider: string;
  model_id: string;
  label: string;
  enabled: boolean;
  supports_quick: boolean;
  supports_deep: boolean;
  cost_tier: string;
  visible_to_roles: string;
  daily_limit: number | null;
  weekly_limit: number | null;
  used_today: number;
  used_this_hour: number;
  remaining_today: number | null;
  success_count: number;
  failure_count: number;
  last_called_at: string | null;
}

export interface AdminLLMProfileRoute {
  route_order: number;
  provider: string;
  quick_model: string;
  deep_model: string;
  available: boolean;
}

export interface AdminLLMProfile {
  profile_id: string;
  label: string;
  description: string;
  enabled: boolean;
  default_for_roles: string;
  sort_order: number;
  routes: AdminLLMProfileRoute[];
}

export interface AdminLLMModelsResponse {
  date: string;
  providers: AdminLLMProvider[];
  models: AdminLLMModel[];
  profiles: AdminLLMProfile[];
}

export interface AdminLLMProviderUpdateRequest {
  enabled: boolean;
  base_url: string;
  daily_limit: number | null;
  hourly_limit: number | null;
}

export interface AdminLLMModelUpdateRequest {
  enabled: boolean;
  cost_tier: string;
  visible_to_roles: UserRole[];
  daily_limit: number | null;
  weekly_limit: number | null;
}

export interface AdminLLMProfileUpdateRequest {
  enabled: boolean;
  default_for_roles: UserRole[];
}

export interface AdminLLMProfileRoutesUpdateRequest {
  routes: Array<{
    provider: string;
    quick_model: string;
    deep_model: string;
  }>;
}

export interface AdminTaskQueueOwner {
  id: string;
  email: string;
  display_name: string;
  role: UserRole;
}

export interface AdminTaskQueueItem {
  kind: "analysis" | "screener" | "data_sync";
  task_id: string;
  label: string;
  status: TaskStatus;
  owner_user_id: string | null;
  owner: AdminTaskQueueOwner | null;
  created_at: string | null;
  queued_at: string | null;
  started_at: string | null;
  finished_at: string | null;
  queue_position: number | null;
  blocked_reason: string | null;
  blocked_vendor: string | null;
  blocked_until: string | null;
  detail_path: string;
}

export interface AdminTaskQueueResponse {
  task_backend: string;
  generated_at: string;
  totals: {
    active: number;
    queued: number;
    running: number;
    waiting_for_quota: number;
  };
  tasks: AdminTaskQueueItem[];
}

export interface AdminAuditEvent {
  id: string;
  tenant_id: string | null;
  actor_user_id: string | null;
  action: string;
  resource_type: string;
  resource_id: string | null;
  metadata: Record<string, unknown>;
  ip_address: string | null;
  user_agent: string | null;
  created_at: string;
}

export interface AdminAuditEventsResponse {
  events: AdminAuditEvent[];
}

export interface AdminAuditEventsQuery {
  action?: string;
  resource_type?: string;
  actor_user_id?: string;
  created_from?: string;
  created_to?: string;
  limit?: number;
}

export type UsageModule = "analysis" | "screener" | "assets" | "journal";

export interface UsageModuleSummary {
  used_count: number;
  weekly_limit: number | null;
  remaining_count: number | null;
}

export interface UserWeeklyUsage {
  usage_week: string;
  weekly_limit: number | null;
  modules: Record<UsageModule, UsageModuleSummary>;
}

export interface DeleteAdminUserResponse {
  deleted: boolean;
  user_id: string;
}

export interface ResetAdminUserUsageResponse {
  user_id: string;
  reset_count: number;
  usage: UserWeeklyUsage;
}

export class ApiError extends Error {
  status: number;
  detail: unknown;

  constructor(status: number, message: string, detail?: unknown) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.detail = detail;
  }
}

export type ReportVisibility = "private" | "workspace";

export interface Report {
  id: string;
  ticker: string;
  date: string;
  time: string;
  visibility?: ReportVisibility;
  tenant_id?: string | null;
  owner_user_id?: string | null;
}

export interface ReportStructure {
  id: string;
  ticker: string;
  has_complete: boolean;
  categories: Record<string, string[]>;
  artifacts: Array<{
    type: string;
    path: string;
    summary?: string | null;
  }>;
}

export interface AnalysisReference {
  analysis_date: string;
  report_path: string;
  full_state_log_path: string;
}

export type TradeReviewType = "entry_review" | "exit_review";

export interface TradeRecord {
  type: "trade_record";
  schema_version: number;
  trade_id: string;
  ticker: string;
  exchange_or_market: string;
  side: string;
  status: string;
  entry_timestamp: string | null;
  entry_price: number | null;
  exit_timestamp: string | null;
  exit_price: number | null;
  size: number | null;
  initial_thesis: string;
  planned_horizon: string;
  stop_loss: number | null;
  take_profit: number | null;
  notes: string;
  analysis_references: AnalysisReference[];
  created_at: string;
  updated_at: string;
}

export interface TradeReview {
  type: "trade_review";
  schema_version: number;
  review_id: string;
  trade_id: string;
  ticker: string;
  review_type: TradeReviewType;
  analysis_date: string;
  analysis_references: AnalysisReference[];
  thesis_assessment: string;
  timing_assessment: string;
  sizing_assessment: string;
  discipline_assessment: string;
  outcome_summary: string;
  improvement_actions: string[];
  ticker_specific_lessons: string[];
  cross_ticker_tags: string[];
  created_at: string;
  updated_at: string;
}

export interface TradeDetail {
  record: TradeRecord;
  reviews: TradeReview[];
}

export interface TradeRecordCreateRequest {
  ticker: string;
  exchange_or_market: string;
  side: string;
  status: string;
  entry_timestamp?: string | null;
  entry_price?: number | null;
  exit_timestamp?: string | null;
  exit_price?: number | null;
  size?: number | null;
  initial_thesis: string;
  planned_horizon: string;
  stop_loss?: number | null;
  take_profit?: number | null;
  notes?: string;
  analysis_references: AnalysisReference[];
}

export interface TradeRecordUpdateRequest {
  ticker?: string;
  exchange_or_market?: string;
  side?: string;
  status?: string;
  entry_timestamp?: string | null;
  entry_price?: number | null;
  exit_timestamp?: string | null;
  exit_price?: number | null;
  size?: number | null;
  initial_thesis?: string;
  planned_horizon?: string;
  stop_loss?: number | null;
  take_profit?: number | null;
  notes?: string;
  analysis_references?: AnalysisReference[];
}

export interface TradeReviewSaveRequest {
  thesis_assessment: string;
  timing_assessment: string;
  sizing_assessment: string;
  discipline_assessment: string;
  outcome_summary: string;
  improvement_actions: string[];
  ticker_specific_lessons: string[];
  cross_ticker_tags: string[];
  analysis_date?: string | null;
  analysis_references?: AnalysisReference[];
}

export interface TradeReviewCreateRequest {
  review_type: TradeReviewType;
  llm_provider: string;
  model: string;
  output_language: string;
  google_thinking_level: string | null;
  openai_reasoning_effort: string | null;
  analysis_date?: string | null;
  analysis_references?: AnalysisReference[];
}

export interface TradeFeedbackEntry {
  trade_id: string;
  ticker: string;
  exchange_or_market: string;
  side: string;
  status: string;
  entry_timestamp: string | null;
  entry_price: number | null;
  exit_timestamp: string | null;
  exit_price: number | null;
  size: number | null;
  initial_thesis: string;
  planned_horizon: string;
  stop_loss: number | null;
  take_profit: number | null;
  review_id: string;
  review_type: TradeReviewType;
  analysis_date: string | null;
  analysis_references: AnalysisReference[];
  thesis_assessment: string;
  timing_assessment: string;
  sizing_assessment: string;
  discipline_assessment: string;
  outcome_summary: string;
  improvement_actions: string[];
  ticker_specific_lessons: string[];
  cross_ticker_tags: string[];
  created_at: string | null;
  updated_at: string | null;
}

export interface TradeFeedbackPayload {
  ticker: string;
  reviews: TradeFeedbackEntry[];
  prompt: string;
}

export interface TaskCreateRequest {
  ticker: string;
  ticker_exchange?: "auto" | "SH" | "SZ" | "BJ" | null;
  analysis_date: string;
  analysts: string[];
  research_depth: number;
  model_profile?: string | null;
  llm_provider?: string | null;
  quick_think_llm?: string | null;
  deep_think_llm?: string | null;
  output_language: string;
  google_thinking_level: string | null;
  openai_reasoning_effort: string | null;
  report_visibility: ReportVisibility;
}

export interface TaskCreateResponse {
  task_id: string;
  status: string;
}

export interface DeleteTaskResponse {
  deleted: boolean;
  task_id: string;
}

export interface CancelTaskResponse {
  canceled: boolean;
  task_id: string;
}

export type TaskStatus =
  | "pending"
  | "queued"
  | "waiting_for_quota"
  | "running"
  | "completed"
  | "failed"
  | "canceled";
export type StageStatus = "not_started" | "processing" | "completed";

export interface ProgressEvent {
  timestamp: string;
  status: TaskStatus;
  stage_status: Record<string, StageStatus>;
  agent_status: Record<string, string>;
  current_agent: string | null;
  message?: string | null;
}

export interface Task {
  id: string;
  owner_user_id?: string | null;
  tenant_id?: string | null;
  ticker: string;
  analysis_date: string;
  analysts: string[];
  request_payload: TaskCreateRequest | null;
  status: TaskStatus;
  latest_progress: ProgressEvent | null;
  report_id: string | null;
  error: string | null;
  created_at?: string | null;
  queued_at?: string | null;
  started_at?: string | null;
  finished_at?: string | null;
  queue_position?: number | null;
  blocked_reason?: string | null;
  blocked_vendor?: string | null;
  blocked_until?: string | null;
  canceled_at?: string | null;
}

export interface SelectOption {
  label: string;
  value: string;
}

export interface ProviderOption extends SelectOption {
  enabled: boolean;
  disabled_reason?: string | null;
}

export interface ModelProfileOption extends SelectOption {
  description: string;
  cost_tier: string;
  enabled: boolean;
  disabled_reason?: string | null;
  default_provider?: string | null;
  default_quick_model?: string | null;
  default_deep_model?: string | null;
  default_quick_label?: string | null;
  default_deep_label?: string | null;
}

export interface ResearchDepthOption {
  label: string;
  value: number;
  description: string;
}

export interface ModelOptions {
  quick: SelectOption[];
  deep: SelectOption[];
}

export interface ConfigOptions {
  providers: ProviderOption[];
  model_profiles: ModelProfileOption[];
  models: Record<string, ModelOptions>;
  analysts: SelectOption[];
  research_depth: ResearchDepthOption[];
  output_languages: SelectOption[];
  defaults: Record<string, never>;
  provider_settings: {
    openai?: { openai_reasoning_effort: SelectOption[] };
    google?: { google_thinking_level: SelectOption[] };
  };
}

export interface ScreenerMarketOption extends SelectOption {
  enabled: boolean;
  disabled_reason?: string | null;
}

export interface ScreenerConfigOptions {
  markets: ScreenerMarketOption[];
  cn_data_sources: Array<{
    label: string;
    value: string;
  }>;
  us_data_sources: Array<{
    label: string;
    value: string;
  }>;
  breakout_types: Array<{
    label: string;
    value: string;
  }>;
  filter_preset_groups: Array<{
    id: string;
    label: string;
    options: Array<{
      label: string;
      value: string;
      condition?: Record<string, unknown>;
      conditions?: Array<Record<string, unknown>>;
    }>;
  }>;
  ranking_profiles: Array<{
    id: string;
    label: string;
    description: string;
    weights: Record<string, number>;
  }>;
  defaults: {
    cn_data_source: string;
    us_data_source: string;
    top_k: number;
    history_cache_policy: string;
    breakout_types: string[];
    filter_preset_selections: Record<string, string>;
    ranking_profile_id: string;
    include_fundamentals: boolean;
    cn_fundamental_source: string;
    us_fundamental_source: string;
  };
}

export interface ScreenTaskCreateRequest {
  markets: string[];
  as_of_date?: string | null;
  top_k: number;
  cn_data_source: string;
  us_data_source: string;
  history_cache_policy?: string;
  breakout_types: string[];
  filter_preset_selections?: Record<string, string>;
  ranking_profile_id?: string | null;
  include_fundamentals?: boolean;
  cn_fundamental_source?: string;
  us_fundamental_source?: string;
}

export interface ScreenerTaskCreateResponse {
  task_id: string;
  status: string;
  run_id?: string;
  cached?: boolean;
}

export interface ScreenerPresetRecord {
  id: string;
  name: string;
  fingerprint?: string;
  config: ScreenTaskCreateRequest;
  created_at: string;
  updated_at: string;
}

export interface DataSyncOhlcvRequest {
  markets: string[];
  as_of_date: string;
  top_k?: number;
  cn_data_source?: string;
  cn_data_source_fallbacks?: string[];
  us_data_source?: string;
  us_data_source_fallbacks?: string[];
  cn_manifest_path?: string | null;
  us_manifest_path?: string | null;
  run_screener_prewarm?: boolean;
}

export interface DataSyncFundamentalsRequest {
  market: string;
  source: string;
  symbols?: string[];
  as_of_date?: string | null;
  data_dir?: string | null;
}

export interface DataSyncTask {
  id: string;
  sync_type: "ohlcv" | "fundamentals" | string;
  request_payload: Record<string, unknown>;
  owner_user_id?: string | null;
  tenant_id?: string | null;
  status: TaskStatus;
  latest_progress: ProgressEvent | null;
  progress_events: ProgressEvent[];
  result?: Record<string, unknown> | null;
  error?: string | null;
  created_at?: string | null;
  queued_at?: string | null;
  started_at?: string | null;
  finished_at?: string | null;
  queue_position?: number | null;
}

export interface ScreenerTask {
  id: string;
  owner_user_id?: string | null;
  tenant_id?: string | null;
  request_payload: ScreenTaskCreateRequest | null;
  status: TaskStatus;
  latest_progress: ProgressEvent | null;
  progress_events: ProgressEvent[];
  run_id: string | null;
  error: string | null;
  created_at?: string | null;
  queued_at?: string | null;
  started_at?: string | null;
  finished_at?: string | null;
  queue_position?: number | null;
  blocked_reason?: string | null;
  blocked_vendor?: string | null;
  blocked_until?: string | null;
  canceled_at?: string | null;
}

export interface ScreenerRunSummary {
  id: string;
  as_of_date: string;
  markets: string[];
  candidate_count: number;
  generated_at: string;
  owner_user_id?: string | null;
  tenant_id?: string | null;
  status?: string;
  snapshot_slot?: "current" | "previous" | null;
  snapshot_available?: boolean;
}

export interface ScreenerRunDetail extends ScreenerRunSummary {
  filtered_count_by_reason: Record<string, number>;
  artifact_paths: Record<string, string>;
  summary?: {
    entered_symbols: string[];
    exited_symbols: string[];
    rank_changed_symbols: string[];
    unchanged: number;
  };
}

export interface ScreenerCandidateRow {
  symbol: string;
  market: string;
  global_rank: number;
  market_rank?: number;
  close?: number | null;
  ma20?: number | null;
  ma60?: number | null;
  ret_20?: number | null;
  ret_60?: number | null;
  rsi?: number | null;
  atr_pct?: number | null;
  avg_amount_20d?: number | null;
  total_score: number;
  base_total_score?: number;
  technical_score?: number | null;
  trend_score: number;
  momentum_score: number;
  pattern_score?: number | null;
  risk_score: number;
  liquidity_score: number;
  fundamental_score?: number | null;
  ranking_profile_id?: string | null;
  score_contributions?: string | null;
  matched_conditions?: string | null;
  matched_condition_details?: string | null;
  breakout_hit?: boolean;
  breakout_type?: string | null;
  breakout_with_volume?: boolean;
  breakout_reason?: string | null;
  breakout_volume_ratio?: number | null;
  breakout_base_bonus?: number;
  breakout_volume_bonus?: number;
  breakout_bonus?: number;
  strategy_tags?: string | null;
  risk_flags?: string | null;
}

export interface TickerHistoryPoint {
  date: string;
  close: number | null;
  open?: number | null;
  high?: number | null;
  low?: number | null;
  volume?: number | null;
}

export interface TickerHistorySeries {
  symbol: string;
  market: string;
  as_of_date: string;
  lookback_days: number;
  start_date: string | null;
  end_date: string | null;
  points: TickerHistoryPoint[];
}

export interface TickerHistoryBatchPayload {
  tickers: Array<{
    symbol: string;
    market?: string | null;
  }>;
  as_of_date?: string | null;
  days?: number;
}

export interface TickerHistoryBatchResponse {
  as_of_date: string;
  lookback_days: number;
  items: TickerHistorySeries[];
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
      detail: {
        detail,
      },
    })
  );
}

function formatApiErrorDetail(detail: unknown, fallback: string): string {
  if (typeof detail === "string" && detail.trim()) {
    return detail;
  }
  if (!detail || typeof detail !== "object") {
    return fallback;
  }

  const payload = detail as Record<string, unknown>;
  const message = typeof payload.message === "string" && payload.message.trim()
    ? payload.message
    : fallback;

  if (payload.code !== "screener_data_not_ready") {
    return message;
  }

  const symbolsMissing = Number(payload.symbols_missing ?? 0);
  const missingPart = symbolsMissing > 0
    ? `Missing or stale symbols: ${symbolsMissing}.`
    : "";
  const examples = Array.isArray(payload.examples)
    ? payload.examples
        .slice(0, 3)
        .map((item) => {
          if (!item || typeof item !== "object") {
            return null;
          }
          const example = item as Record<string, unknown>;
          const market = typeof example.market === "string" ? example.market : "";
          const symbol = typeof example.symbol === "string" ? example.symbol : "";
          const reason = typeof example.reason === "string" ? example.reason : "";
          const label = [market, symbol].filter(Boolean).join(":");
          return label ? `${label}${reason ? ` (${reason})` : ""}` : null;
        })
        .filter(Boolean)
    : [];
  const examplesPart = examples.length > 0 ? `Examples: ${examples.join(", ")}.` : "";
  return [message, missingPart, examplesPart].filter(Boolean).join(" ");
}

async function parseJsonResponse<T>(response: Response): Promise<T> {
  if (!response.ok) {
    const fallback = response.statusText || `${response.status}`;
    let detail: unknown = fallback;
    let message = fallback;

    try {
      const payload = (await response.json()) as { detail?: unknown };
      if (payload.detail !== undefined) {
        detail = payload.detail;
        message = formatApiErrorDetail(payload.detail, fallback);
      }
    } catch {
      // Ignore JSON parse errors and fall back to status text.
    }

    if (response.status === 401) {
      emitAuthRequired(message);
    }

    throw new ApiError(response.status, message, detail);
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

export async function getAuthState(): Promise<AuthState> {
  return requestJson<AuthState>("/api/auth/me", {
    cache: "no-store",
  });
}

export async function login(payload: LoginRequest): Promise<AuthState> {
  return requestJson<AuthState>("/api/auth/login", createJsonRequestInit("POST", payload));
}

export async function logout(): Promise<AuthState> {
  return requestJson<AuthState>("/api/auth/logout", createJsonRequestInit("POST"));
}

export async function changePassword(
  payload: ChangePasswordRequest
): Promise<AuthState> {
  return requestJson<AuthState>(
    "/api/auth/change-password",
    createJsonRequestInit("POST", payload)
  );
}

export async function listAdminUsers(): Promise<AuthUser[]> {
  return requestJson<AuthUser[]>("/api/admin/users", {
    cache: "no-store",
  });
}

export async function listAdminAnalysisLimits(): Promise<AdminAnalysisLimitsResponse> {
  return requestJson<AdminAnalysisLimitsResponse>("/api/admin/analysis-limits", {
    cache: "no-store",
  });
}

export async function updateAdminAnalysisLimits(
  payload: AdminAnalysisLimitsResponse
): Promise<AdminAnalysisLimitsResponse> {
  return requestJson<AdminAnalysisLimitsResponse>(
    "/api/admin/analysis-limits",
    createJsonRequestInit("PUT", payload)
  );
}

export async function listAdminDataSources(): Promise<AdminDataSourceUsageResponse> {
  return requestJson<AdminDataSourceUsageResponse>("/api/admin/data-sources", {
    cache: "no-store",
  });
}

export async function updateAdminDataSource(
  vendor: string,
  payload: AdminDataSourceUpdateRequest
): Promise<AdminDataSourceUpdateResponse> {
  return requestJson<AdminDataSourceUpdateResponse>(
    `/api/admin/data-sources/${vendor}`,
    createJsonRequestInit("PUT", payload)
  );
}

export async function updateAdminDataSourceRoute(
  route: Pick<AdminDataSourceRoute, "module" | "market" | "category">,
  payload: AdminDataSourceRouteUpdateRequest
): Promise<AdminDataSourceRouteUpdateResponse> {
  return requestJson<AdminDataSourceRouteUpdateResponse>(
    `/api/admin/data-source-routes/${route.module}/${route.market}/${route.category}`,
    createJsonRequestInit("PUT", payload)
  );
}

export async function listAdminLLMModels(): Promise<AdminLLMModelsResponse> {
  return requestJson<AdminLLMModelsResponse>("/api/admin/llm-models", {
    cache: "no-store",
  });
}

export async function updateAdminLLMProvider(
  provider: string,
  payload: AdminLLMProviderUpdateRequest
): Promise<{ provider: AdminLLMProvider }> {
  return requestJson<{ provider: AdminLLMProvider }>(
    `/api/admin/llm-models/providers/${provider}`,
    createJsonRequestInit("PUT", payload)
  );
}

export async function updateAdminLLMModel(
  provider: string,
  modelId: string,
  payload: AdminLLMModelUpdateRequest
): Promise<{ model: AdminLLMModel }> {
  return requestJson<{ model: AdminLLMModel }>(
    `/api/admin/llm-models/models/${provider}/${encodeURIComponent(modelId)}`,
    createJsonRequestInit("PUT", payload)
  );
}

export async function updateAdminLLMProfile(
  profileId: string,
  payload: AdminLLMProfileUpdateRequest
): Promise<{ profile: AdminLLMProfile }> {
  return requestJson<{ profile: AdminLLMProfile }>(
    `/api/admin/llm-models/profiles/${profileId}`,
    createJsonRequestInit("PUT", payload)
  );
}

export async function updateAdminLLMProfileRoutes(
  profileId: string,
  payload: AdminLLMProfileRoutesUpdateRequest
): Promise<{ routes: AdminLLMProfileRoute[] }> {
  return requestJson<{ routes: AdminLLMProfileRoute[] }>(
    `/api/admin/llm-models/profiles/${profileId}/routes`,
    createJsonRequestInit("PUT", payload)
  );
}

export async function listAdminTaskQueue(): Promise<AdminTaskQueueResponse> {
  return requestJson<AdminTaskQueueResponse>("/api/admin/task-queue", {
    cache: "no-store",
  });
}

export async function listAdminAuditEvents(
  query: AdminAuditEventsQuery = {}
): Promise<AdminAuditEventsResponse> {
  const searchParams = new URLSearchParams();
  for (const [key, value] of Object.entries(query)) {
    if (value === undefined || value === null || value === "") {
      continue;
    }
    searchParams.set(key, String(value));
  }
  const suffix = searchParams.toString() ? `?${searchParams.toString()}` : "";
  return requestJson<AdminAuditEventsResponse>(`/api/admin/audit-events${suffix}`, {
    cache: "no-store",
  });
}

export async function getAdminUser(userId: string): Promise<AuthUser> {
  return requestJson<AuthUser>(`/api/admin/users/${userId}`, {
    cache: "no-store",
  });
}

export async function createAdminUser(
  payload: AdminUserCreateRequest
): Promise<AuthUser> {
  return requestJson<AuthUser>(
    "/api/admin/users",
    createJsonRequestInit("POST", payload)
  );
}

export async function updateAdminUser(
  userId: string,
  payload: AdminUserUpdateRequest
): Promise<AuthUser> {
  return requestJson<AuthUser>(
    `/api/admin/users/${userId}`,
    createJsonRequestInit("PUT", payload)
  );
}

export async function deleteAdminUser(
  userId: string
): Promise<DeleteAdminUserResponse> {
  return requestJson<DeleteAdminUserResponse>(
    `/api/admin/users/${userId}`,
    createJsonRequestInit("DELETE")
  );
}

export async function resetAdminUserPassword(
  userId: string,
  payload: AdminUserResetPasswordRequest
): Promise<AuthUser> {
  return requestJson<AuthUser>(
    `/api/admin/users/${userId}/reset-password`,
    createJsonRequestInit("POST", payload)
  );
}

export async function resetAdminUserUsage(
  userId: string
): Promise<ResetAdminUserUsageResponse> {
  return requestJson<ResetAdminUserUsageResponse>(
    `/api/admin/users/${userId}/usage/reset`,
    createJsonRequestInit("POST")
  );
}

export async function listReports(): Promise<Report[]> {
  return requestJson<Report[]>("/api/reports", {
    cache: "no-store",
  });
}

export async function getStructure(reportId: string): Promise<ReportStructure> {
  return requestJson<ReportStructure>(`/api/reports/${reportId}/structure`, {
    cache: "no-store",
  });
}

export async function getContent(reportId: string, path: string): Promise<string> {
  const url = new URL(buildApiUrl(`/api/reports/${reportId}/content`));
  url.searchParams.set("path", path);

  const response = await fetch(url.toString(), {
    credentials: "include",
    cache: "no-store",
  });
  const data = await parseJsonResponse<{ content: string }>(response);
  return data.content;
}

export async function listTrades(ticker?: string): Promise<TradeRecord[]> {
  const url = new URL(buildApiUrl("/api/trades"));
  if (ticker) {
    url.searchParams.set("ticker", ticker);
  }

  const response = await fetch(url.toString(), {
    credentials: "include",
    cache: "no-store",
  });
  return parseJsonResponse<TradeRecord[]>(response);
}

export async function createTrade(
  payload: TradeRecordCreateRequest
): Promise<TradeRecord> {
  return requestJson<TradeRecord>("/api/trades", createJsonRequestInit("POST", payload));
}

export async function getTrade(tradeId: string): Promise<TradeDetail> {
  return requestJson<TradeDetail>(`/api/trades/${tradeId}`, {
    cache: "no-store",
  });
}

export async function updateTrade(
  tradeId: string,
  payload: TradeRecordUpdateRequest
): Promise<TradeRecord> {
  return requestJson<TradeRecord>(
    `/api/trades/${tradeId}`,
    createJsonRequestInit("PUT", payload)
  );
}

export async function createTradeReview(
  tradeId: string,
  payload: TradeReviewCreateRequest
): Promise<TradeReview> {
  return requestJson<TradeReview>(
    `/api/trades/${tradeId}/reviews`,
    createJsonRequestInit("POST", payload)
  );
}

export async function saveTradeReview(
  tradeId: string,
  reviewType: TradeReviewType,
  payload: TradeReviewSaveRequest
): Promise<TradeReview> {
  return requestJson<TradeReview>(
    `/api/trades/${tradeId}/reviews/${reviewType}`,
    createJsonRequestInit("PUT", payload)
  );
}

export async function getTickerTradeFeedback(
  ticker: string,
  options: { limit?: number; analysisDate?: string } = {}
): Promise<TradeFeedbackPayload> {
  const url = new URL(buildApiUrl(`/api/trade-feedback/${ticker}`));
  if (typeof options.limit === "number") {
    url.searchParams.set("limit", String(options.limit));
  }
  if (options.analysisDate) {
    url.searchParams.set("analysis_date", options.analysisDate);
  }

  const response = await fetch(url.toString(), {
    credentials: "include",
    cache: "no-store",
  });
  return parseJsonResponse<TradeFeedbackPayload>(response);
}

export async function createTask(
  payload: TaskCreateRequest
): Promise<TaskCreateResponse> {
  return requestJson<TaskCreateResponse>("/api/tasks", createJsonRequestInit("POST", payload));
}

export async function listTasks(): Promise<Task[]> {
  return requestJson<Task[]>("/api/tasks", {
    cache: "no-store",
  });
}

export async function getTask(taskId: string): Promise<Task> {
  return requestJson<Task>(`/api/tasks/${taskId}`, {
    cache: "no-store",
  });
}

export async function deleteTask(taskId: string): Promise<DeleteTaskResponse> {
  return requestJson<DeleteTaskResponse>(`/api/tasks/${taskId}`, {
    method: "DELETE",
    credentials: "include",
  });
}

export async function cancelTask(taskId: string): Promise<CancelTaskResponse> {
  return requestJson<CancelTaskResponse>(`/api/tasks/${taskId}/cancel`, {
    method: "POST",
    credentials: "include",
  });
}

export async function getConfigOptions(): Promise<ConfigOptions> {
  return requestJson<ConfigOptions>("/api/config/options", {
    cache: "no-store",
  });
}

export async function getScreenerConfigOptions(): Promise<ScreenerConfigOptions> {
  return requestJson<ScreenerConfigOptions>("/api/screener/config/options", {
    cache: "no-store",
  });
}

export async function createScreenerTask(
  payload: ScreenTaskCreateRequest
): Promise<ScreenerTaskCreateResponse> {
  return requestJson<ScreenerTaskCreateResponse>(
    "/api/screener/tasks",
    createJsonRequestInit("POST", payload)
  );
}

export async function listScreenerPresets(): Promise<ScreenerPresetRecord[]> {
  return requestJson<ScreenerPresetRecord[]>("/api/screener/presets", {
    cache: "no-store",
  });
}

export async function replaceScreenerPresets(
  presets: ScreenerPresetRecord[]
): Promise<ScreenerPresetRecord[]> {
  return requestJson<ScreenerPresetRecord[]>(
    "/api/screener/presets",
    createJsonRequestInit("PUT", presets)
  );
}

export async function createOhlcvSyncTask(
  payload: DataSyncOhlcvRequest
): Promise<ScreenerTaskCreateResponse> {
  return requestJson<ScreenerTaskCreateResponse>(
    "/api/admin/data-sync/ohlcv",
    createJsonRequestInit("POST", payload)
  );
}

export async function createFundamentalSyncTask(
  payload: DataSyncFundamentalsRequest
): Promise<ScreenerTaskCreateResponse> {
  return requestJson<ScreenerTaskCreateResponse>(
    "/api/admin/data-sync/fundamentals",
    createJsonRequestInit("POST", payload)
  );
}

export async function listDataSyncJobs(): Promise<DataSyncTask[]> {
  return requestJson<DataSyncTask[]>("/api/admin/data-sync/jobs", {
    cache: "no-store",
  });
}

export async function getDataSyncJob(taskId: string): Promise<DataSyncTask> {
  return requestJson<DataSyncTask>(`/api/admin/data-sync/jobs/${taskId}`, {
    cache: "no-store",
  });
}

export async function listScreenerTasks(): Promise<ScreenerTask[]> {
  return requestJson<ScreenerTask[]>("/api/screener/tasks", {
    cache: "no-store",
  });
}

export async function getScreenerTask(taskId: string): Promise<ScreenerTask> {
  return requestJson<ScreenerTask>(`/api/screener/tasks/${taskId}`, {
    cache: "no-store",
  });
}

export async function deleteScreenerTask(taskId: string): Promise<DeleteTaskResponse> {
  return requestJson<DeleteTaskResponse>(`/api/screener/tasks/${taskId}`, {
    method: "DELETE",
    credentials: "include",
  });
}

export async function cancelScreenerTask(
  taskId: string
): Promise<CancelTaskResponse> {
  return requestJson<CancelTaskResponse>(
    `/api/screener/tasks/${taskId}/cancel`,
    {
      method: "POST",
      credentials: "include",
    }
  );
}

export async function listScreenerRuns(): Promise<ScreenerRunSummary[]> {
  return requestJson<ScreenerRunSummary[]>("/api/screener/runs", {
    cache: "no-store",
  });
}

export async function getScreenerRun(runId: string): Promise<ScreenerRunDetail> {
  return requestJson<ScreenerRunDetail>(`/api/screener/runs/${runId}`, {
    cache: "no-store",
  });
}

export async function listScreenerRunCandidates(
  runId: string
): Promise<ScreenerCandidateRow[]> {
  return requestJson<ScreenerCandidateRow[]>(
    `/api/screener/runs/${runId}/candidates`,
    {
      cache: "no-store",
    }
  );
}

export async function getTickerHistory(options: {
  symbol: string;
  market?: string | null;
  asOfDate?: string | null;
  days?: number;
}): Promise<TickerHistorySeries> {
  const url = new URL(buildApiUrl("/api/ticker-history"));
  url.searchParams.set("symbol", options.symbol);
  if (options.market) {
    url.searchParams.set("market", options.market);
  }
  if (options.asOfDate) {
    url.searchParams.set("as_of_date", options.asOfDate);
  }
  if (typeof options.days === "number") {
    url.searchParams.set("days", String(options.days));
  }

  const response = await fetch(url.toString(), {
    credentials: "include",
    cache: "no-store",
  });
  return parseJsonResponse<TickerHistorySeries>(response);
}

export async function getTickerHistoryBatch(
  payload: TickerHistoryBatchPayload
): Promise<TickerHistoryBatchResponse> {
  return requestJson<TickerHistoryBatchResponse>(
    "/api/ticker-history/batch",
    createJsonRequestInit("POST", payload)
  );
}

export function subscribeToTask(
  taskId: string,
  onEvent: (event: ProgressEvent) => void,
  onError?: (error: Error) => void
): () => void {
  const eventSource = new EventSource(buildApiUrl(`/api/tasks/${taskId}/stream`), {
    withCredentials: true,
  });

  eventSource.onmessage = (event) => {
    try {
      const payload = JSON.parse(event.data) as ProgressEvent;
      onEvent(payload);
    } catch (error) {
      onError?.(
        error instanceof Error
          ? error
          : new Error("Unable to parse task stream event")
      );
    }
  };

  eventSource.onerror = () => {
    onError?.(new Error("Task progress stream disconnected"));
    eventSource.close();
  };

  return () => {
    eventSource.close();
  };
}

export function subscribeToScreenerTask(
  taskId: string,
  onEvent: (event: ProgressEvent) => void,
  onError?: (error: Error) => void,
  startCursor = 0
): () => void {
  const url = new URL(buildApiUrl(`/api/screener/tasks/${taskId}/stream`));
  if (startCursor > 0) {
    url.searchParams.set("cursor", String(startCursor));
  }

  const eventSource = new EventSource(url.toString(), {
    withCredentials: true,
  });

  eventSource.onmessage = (event) => {
    try {
      const payload = JSON.parse(event.data) as ProgressEvent;
      onEvent(payload);
    } catch (error) {
      onError?.(
        error instanceof Error
          ? error
          : new Error("Unable to parse screener task stream event")
      );
    }
  };

  eventSource.onerror = () => {
    onError?.(new Error("Screener task progress stream disconnected"));
    eventSource.close();
  };

  return () => {
    eventSource.close();
  };
}
