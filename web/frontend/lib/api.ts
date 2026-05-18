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
  | "opportunity:read"
  | "opportunity:run"
  | "opportunity:write"
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
  username: string;
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
  account: string;
  password: string;
}

export interface ChangePasswordRequest {
  current_password: string;
  new_password: string;
}

export interface AdminUserCreateRequest {
  email: string;
  username?: string;
  display_name: string;
  password: string;
  role: UserRole;
  status: UserStatus;
  must_change_password: boolean;
}

export interface AdminUserUpdateRequest {
  username?: string;
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

export type AdminSearchProviderName = "brave" | "tavily" | "bocha";

export interface AdminSearchQuotaGlobal {
  enabled: boolean;
  disabled_until: string | null;
  disabled_reason: string | null;
  updated_at: string | null;
}

export interface AdminSearchQuotaProvider {
  provider: AdminSearchProviderName;
  label: string;
  enabled: boolean;
  key_status: "configured" | "missing";
  monthly_free_quota: number;
  monthly_hard_cap: number;
  used_this_month: number;
  remaining_to_hard_cap: number;
  hard_cap_reached: boolean;
  success_count: number;
  failure_count: number;
  disabled_until: string | null;
  disabled_reason: string | null;
  last_error: string | null;
  last_called_at: string | null;
  updated_at: string | null;
}

export interface AdminSearchQuotaResponse {
  month: string;
  global: AdminSearchQuotaGlobal;
  providers: AdminSearchQuotaProvider[];
}

export interface AdminSearchGlobalUpdateRequest {
  enabled: boolean;
}

export interface AdminSearchProviderUpdateRequest {
  enabled?: boolean;
  monthly_free_quota?: number | null;
  monthly_hard_cap?: number | null;
}

export interface AdminSearchProviderUpdateResponse {
  provider: AdminSearchQuotaProvider;
}

export interface AdminSearchGlobalUpdateResponse {
  global: AdminSearchQuotaGlobal;
}

export interface AdminSearchProviderUsageResetResponse {
  provider: AdminSearchQuotaProvider;
  reset_count: number;
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

export interface AdminLLMModuleSetting {
  module: string;
  label: string;
  description: string;
  enabled: boolean;
  model_profile: string;
  output_language: string;
  custom_provider: string | null;
  custom_model: string | null;
  openai_reasoning_effort: string | null;
  google_thinking_level: string | null;
}

export interface AdminLLMUiSetting {
  setting_key: string;
  label: string;
  description: string;
  enabled: boolean;
}

export interface AdminLLMModelsResponse {
  date: string;
  providers: AdminLLMProvider[];
  models: AdminLLMModel[];
  profiles: AdminLLMProfile[];
  module_settings: AdminLLMModuleSetting[];
  ui_settings: AdminLLMUiSetting[];
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

export interface AdminLLMModuleSettingUpdateRequest {
  enabled: boolean;
  model_profile: string;
  output_language: string;
  custom_provider?: string | null;
  custom_model?: string | null;
  openai_reasoning_effort: string | null;
  google_thinking_level: string | null;
}

export interface AdminLLMUiSettingUpdateRequest {
  enabled: boolean;
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
  runtime_present: boolean;
  stale: boolean;
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

export interface DeleteAdminTaskQueueItemResponse {
  deleted: boolean;
  kind: AdminTaskQueueItem["kind"];
  task_id: string;
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

export interface DeleteReportResponse {
  deleted: boolean;
  report_id: string;
  storage_path: string;
  deleted_storage_keys: number;
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
  visibility_updated_by_user_id?: string | null;
  visibility_updated_at?: string | null;
  visibility_admin_override?: boolean;
  tenant_id?: string | null;
  owner_user_id?: string | null;
}

export interface ReportStructure {
  id: string;
  ticker: string;
  visibility?: ReportVisibility;
  visibility_updated_by_user_id?: string | null;
  visibility_updated_at?: string | null;
  visibility_admin_override?: boolean;
  tenant_id?: string | null;
  owner_user_id?: string | null;
  has_complete: boolean;
  categories: Record<string, string[]>;
  artifacts: Array<{
    type: string;
    path: string;
    summary?: string | null;
  }>;
}

export interface MarketBriefSummary {
  type: "premarket_brief";
  report_id: string | null;
  brief_id: string;
  date: string;
  time: string | null;
  title: string;
  summary: string | null;
  markets: string[];
  trading_day: string | null;
  generated_at: string | null;
  information_cutoff_at: string | null;
  data_quality_level: string | null;
  main_themes: string[];
  risks: string[];
  opening_validation_signals: string[];
  quality_warnings: string[];
  source_count: number;
  artifact_path: string;
  provider?: string | null;
  source_path?: string | null;
}

export interface MarketBriefIndexResponse {
  retention_days: number;
  today: string;
  cutoff_date: string;
  latest: MarketBriefSummary | null;
  briefs: MarketBriefSummary[];
}

export interface AnalysisReference {
  analysis_date: string;
  report_path: string;
  full_state_log_path: string;
}

export type TradeReviewType = "entry_review" | "exit_review";
export type MarketResolutionMarket = "cn" | "us" | "unknown";
export type MarketResolutionAssetType = "equity" | "etf" | "unknown";
export type MarketResolutionConfidence = "high" | "medium" | "low" | "manual";
export type MarketResolutionSource = "manifest" | "rule" | "manual" | "unknown";

export interface MarketResolution {
  raw_symbol: string;
  canonical_symbol: string;
  display_symbol: string;
  market: MarketResolutionMarket;
  exchange: string | null;
  asset_type: MarketResolutionAssetType;
  confidence: MarketResolutionConfidence;
  source: MarketResolutionSource;
  warnings: string[];
}

export interface TradeDerivedMetrics {
  realized_return_pct: number | null;
  pnl_amount: number | null;
  r_multiple: number | null;
  holding_period_hours: number | null;
}

export type TradePlanStatus = "planned" | "executed" | "expired";
export type TradePlanSource = "manual" | "analysis_prefill";

export interface TradePlan {
  type: "trade_plan";
  schema_version: number;
  plan_id: string;
  raw_symbol: string;
  ticker: string;
  canonical_symbol: string;
  display_symbol: string;
  market?: MarketResolutionMarket | null;
  exchange: string | null;
  asset_type: MarketResolutionAssetType;
  market_resolution: MarketResolution;
  exchange_or_market: string;
  side: string;
  status: TradePlanStatus;
  status_reason: string;
  source: TradePlanSource;
  strategy_tags: string[];
  entry_condition: string;
  thesis: string;
  invalidation_condition: string;
  risk_rule: string;
  reward_target: string;
  position_plan: string;
  planned_horizon: string;
  stop_loss: number | null;
  take_profit: number | null;
  expires_at: string;
  notes: string;
  analysis_references: AnalysisReference[];
  linked_trade_id: string;
  created_at: string;
  updated_at: string;
}

export interface TradePlanSnapshot
  extends Omit<
    TradePlan,
    "type" | "status" | "status_reason" | "notes" | "linked_trade_id"
  > {
  type: "trade_plan_snapshot";
  snapshotted_at: string;
}

export interface TradeRecord {
  type: "trade_record";
  schema_version: number;
  trade_id: string;
  raw_symbol: string;
  ticker: string;
  canonical_symbol: string;
  display_symbol: string;
  market?: MarketResolutionMarket | null;
  exchange: string | null;
  asset_type: MarketResolutionAssetType;
  market_resolution: MarketResolution;
  exchange_or_market: string;
  side: string;
  status: string;
  entry_timestamp: string | null;
  entry_price: number | null;
  exit_timestamp: string | null;
  exit_price: number | null;
  size: number | null;
  strategy_tags: string[];
  entry_reason: string;
  invalidation_condition: string;
  initial_thesis: string;
  planned_horizon: string;
  stop_loss: number | null;
  take_profit: number | null;
  exit_reason: string;
  plan_execution: string;
  execution_note: string;
  originating_plan_id: string | null;
  originating_plan_snapshot: TradePlanSnapshot | null;
  notes: string;
  analysis_references: AnalysisReference[];
  derived_metrics?: TradeDerivedMetrics;
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
  raw_symbol: string;
  side?: string;
  entry_timestamp: string;
  entry_price: number;
  size: number;
  strategy_tags: string[];
  entry_reason: string;
  invalidation_condition: string;
  planned_horizon?: string;
  stop_loss?: number | null;
  take_profit?: number | null;
  exit_timestamp?: string | null;
  exit_price?: number | null;
  exit_reason?: string;
  plan_execution?: string;
  initial_thesis?: string;
  notes?: string;
  market_resolution?: MarketResolution | null;
  analysis_references: AnalysisReference[];
}

export interface TradeRecordUpdateRequest {
  raw_symbol?: string;
  side?: string;
  entry_timestamp?: string | null;
  entry_price?: number | null;
  size?: number | null;
  strategy_tags?: string[];
  entry_reason?: string;
  invalidation_condition?: string;
  planned_horizon?: string;
  stop_loss?: number | null;
  take_profit?: number | null;
  exit_timestamp?: string | null;
  exit_price?: number | null;
  exit_reason?: string;
  plan_execution?: string;
  initial_thesis?: string;
  notes?: string;
  market_resolution?: MarketResolution | null;
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

export interface TradeReviewGenerateRequest {
  analysis_date?: string | null;
  analysis_references?: AnalysisReference[];
  output_language?: string;
}

export interface TradeFeedbackEntry {
  trade_id: string;
  ticker: string;
  exchange_or_market: string;
  raw_symbol: string | null;
  canonical_symbol: string | null;
  display_symbol: string | null;
  market: MarketResolutionMarket | null;
  exchange: string | null;
  asset_type: MarketResolutionAssetType | null;
  market_resolution: MarketResolution | null;
  side: string;
  status: string;
  entry_timestamp: string | null;
  entry_price: number | null;
  exit_timestamp: string | null;
  exit_price: number | null;
  size: number | null;
  strategy_tags: string[];
  entry_reason: string | null;
  invalidation_condition: string | null;
  exit_reason: string | null;
  plan_execution: string | null;
  execution_note: string | null;
  originating_plan_id: string | null;
  originating_plan_snapshot: TradePlanSnapshot | null;
  initial_thesis: string;
  planned_horizon: string;
  stop_loss: number | null;
  take_profit: number | null;
  derived_metrics?: TradeDerivedMetrics;
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

export interface TradePlanCreateRequest {
  raw_symbol: string;
  side?: string;
  source?: TradePlanSource;
  strategy_tags: string[];
  entry_condition: string;
  thesis: string;
  invalidation_condition: string;
  risk_rule: string;
  reward_target: string;
  position_plan: string;
  planned_horizon?: string;
  stop_loss?: number | null;
  take_profit?: number | null;
  expires_at: string;
  notes?: string;
  market_resolution?: MarketResolution | null;
  analysis_references?: AnalysisReference[];
}

export interface TradePlanUpdateRequest {
  raw_symbol?: string;
  side?: string;
  source?: TradePlanSource;
  strategy_tags?: string[];
  entry_condition?: string;
  thesis?: string;
  invalidation_condition?: string;
  risk_rule?: string;
  reward_target?: string;
  position_plan?: string;
  planned_horizon?: string;
  stop_loss?: number | null;
  take_profit?: number | null;
  expires_at?: string;
  notes?: string;
  market_resolution?: MarketResolution | null;
  analysis_references?: AnalysisReference[];
}

export interface TradePlanExecuteRequest {
  entry_timestamp: string;
  entry_price: number;
  size: number;
  notes?: string;
  execution_note?: string;
}

export interface TradePlanLinkRequest {
  plan_id: string;
  execution_note?: string;
}

export interface TradePlanMutationResponse {
  plan: TradePlan;
  record: TradeRecord;
}

export interface DeleteTradePlanResponse {
  deleted: boolean;
  plan_id: string;
}

export interface TradePlanQuery {
  ticker?: string;
  status?: TradePlanStatus | null;
}

export interface TaskCreateRequest {
  ticker: string;
  ticker_exchange?: "auto" | "SH" | "SZ" | "BJ" | null;
  analysis_date?: string | null;
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
  warnings?: Array<Record<string, string>>;
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
  cancel_requested_at?: string | null;
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
  ui_settings?: Record<string, boolean>;
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



export interface OpportunityRunSummary {
  run_id: string;
  status: string;
  trade_date: string;
  market: string;
  candidate_count: number;
  generated_at?: string | null;
  artifact_manifest?: Record<string, string>;
}

export interface MarketPulse {
  trade_date: string;
  market: string;
  market_regime: string;
  summary: string;
  top_themes: string[];
  risk_notes: string[];
  data_quality_notes: string[];
}

export interface ThemeRadarItem {
  theme_id: string;
  theme_name: string;
  hot_score: number;
  capital_score: number;
  momentum_score?: number;
  breadth_score?: number;
  catalyst_score?: number;
  stage: string;
  leaders: string[];
  watch_symbols: string[];
  backtest_summary?: BacktestSnapshotSummary | null;
  risk_flags?: string[];
}

export interface ThemeRadarResponse {
  trade_date: string;
  market: string;
  themes: ThemeRadarItem[];
}

export interface OpportunityCandidate {
  symbol: string;
  name?: string | null;
  market?: string | null;
  theme_id?: string | null;
  theme_name?: string | null;
  candidate_type: string;
  stock_score: number;
  theme_hot_score?: number | null;
  capital_score?: number | null;
  technical_score?: number | null;
  catalyst_score?: number | null;
  backtest_signal?: string | null;
  recommended_next_step?: string | null;
  reason: string;
  risk_flags: string[];
  data_quality_flags: Array<Record<string, unknown>>;
  backtest_summary?: BacktestSnapshotSummary | null;
}

export interface CandidatePoolResponse {
  trade_date: string;
  market: string;
  strategy_ids: string[];
  candidates: OpportunityCandidate[];
}

export interface OpportunityEvent {
  event_id: string;
  trade_date: string;
  scope: string;
  event_type: string;
  symbol?: string;
  theme_id?: string | null;
  score?: number | null;
  evidence?: string[];
  source_run_id?: string;
  next_step?: string;
}

export interface WatchlistItem {
  id?: string;
  symbol: string;
  market?: string;
  name?: string | null;
  theme_id?: string | null;
  status: string;
  reason?: string | null;
  source_run_id?: string | null;
  metadata?: Record<string, unknown>;
}

export interface BacktestSnapshotSummary {
  strategy_id?: string;
  run_id?: string;
  engine?: string;
  status?: string;
  sample_size?: number;
  holding_periods?: Record<string, {
    sample_size?: number;
    win_rate?: number;
    avg_return?: number;
    median_return?: number;
    max_adverse_excursion_median?: number | null;
  }>;
  risk_notes?: string[];
  data_quality_notes?: string[];
}

export interface OpportunityRunRequest {
  trade_date?: string | null;
  market?: string;
  strategy_ids?: string[];
  factor_snapshot_path?: string | null;
  price_history_path?: string | null;
  cost_model_id?: string | null;
  force?: boolean;
}

export interface OpportunityTaskCreateResponse {
  task_id: string;
  status: string;
  run_id?: string;
  cached?: boolean;
}

export interface OpportunityTask {
  id: string;
  request_payload: OpportunityRunRequest | null;
  owner_user_id?: string | null;
  tenant_id?: string | null;
  status: TaskStatus;
  latest_progress: ProgressEvent | null;
  progress_events: ProgressEvent[];
  result?: {
    run_id?: string | null;
    status?: string | null;
    cached?: boolean;
    candidate_count?: number | null;
    run_dir?: string | null;
  } | null;
  error?: string | null;
  created_at?: string | null;
  queued_at?: string | null;
  started_at?: string | null;
  finished_at?: string | null;
  queue_position?: number | null;
  cancel_requested_at?: string | null;
  canceled_at?: string | null;
}

export interface CandidateAnalyzeRequest {
  run_id?: string | null;
  analysis_date?: string | null;
  output_language?: string | null;
  model_profile?: string | null;
  opportunity_context?: Record<string, unknown> | null;
  report_visibility?: "private" | "workspace";
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
  cancel_requested_at?: string | null;
  canceled_at?: string | null;
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
  cancel_requested_at?: string | null;
  canceled_at?: string | null;
}

export interface JournalReviewTask {
  id: string;
  kind: "journal_review" | string;
  owner_user_id?: string | null;
  tenant_id?: string | null;
  request_payload: {
    trigger?: string;
    trade_id?: string | null;
    ticker?: string | null;
    review_types?: TradeReviewType[];
  } | null;
  status: TaskStatus;
  latest_progress: ProgressEvent | null;
  progress_events: ProgressEvent[];
  result?: {
    trade_id?: string | null;
    ticker?: string | null;
    review_types?: TradeReviewType[];
    generated_count?: number;
    generated_review_types?: Array<string | null>;
    skipped?: boolean;
    reason?: string;
    failures?: Array<{ review_type?: string; error?: string }>;
  } | null;
  error?: string | null;
  created_at?: string | null;
  queued_at?: string | null;
  started_at?: string | null;
  finished_at?: string | null;
  updated_at?: string | null;
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
  name?: string | null;
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

function isRecord(value: unknown): value is Record<string, unknown> {
  return value !== null && typeof value === "object" && !Array.isArray(value);
}

function stringValue(value: unknown, fallback = ""): string {
  return typeof value === "string" ? value : fallback;
}

function nullableStringValue(value: unknown): string | null {
  return typeof value === "string" && value.length > 0 ? value : null;
}

function nullableNumberValue(value: unknown): number | null {
  return typeof value === "number" && Number.isFinite(value) ? value : null;
}

function normalizeStringArray(value: unknown): string[] {
  if (!Array.isArray(value)) {
    return [];
  }
  return value
    .map((item) => (typeof item === "string" ? item.trim() : ""))
    .filter((item) => item.length > 0);
}

function normalizeAnalysisReferences(value: unknown): AnalysisReference[] {
  if (!Array.isArray(value)) {
    return [];
  }

  return value
    .map((item) => {
      if (!isRecord(item)) {
        return null;
      }
      const reference = {
        analysis_date: stringValue(item.analysis_date),
        report_path: stringValue(item.report_path),
        full_state_log_path: stringValue(item.full_state_log_path),
      };
      return reference.analysis_date ||
        reference.report_path ||
        reference.full_state_log_path
        ? reference
        : null;
    })
    .filter((item): item is AnalysisReference => item !== null);
}

function normalizeMarketValue(value: unknown): MarketResolutionMarket {
  return value === "cn" || value === "us" || value === "unknown" ? value : "unknown";
}

function normalizeAssetTypeValue(value: unknown): MarketResolutionAssetType {
  return value === "equity" || value === "etf" || value === "unknown"
    ? value
    : "unknown";
}

function normalizeMarketResolutionSource(value: unknown): MarketResolutionSource {
  return value === "manifest" ||
    value === "rule" ||
    value === "manual" ||
    value === "unknown"
    ? value
    : "unknown";
}

function normalizeMarketResolutionConfidence(
  value: unknown
): MarketResolutionConfidence {
  return value === "high" ||
    value === "medium" ||
    value === "low" ||
    value === "manual"
    ? value
    : "low";
}

function normalizeMarketResolution(
  value: unknown,
  fallback: Pick<
    MarketResolution,
    "raw_symbol" | "canonical_symbol" | "display_symbol" | "market" | "exchange" | "asset_type"
  >
): MarketResolution {
  const source = isRecord(value) ? value : {};
  return {
    raw_symbol: stringValue(source.raw_symbol, fallback.raw_symbol),
    canonical_symbol: stringValue(source.canonical_symbol, fallback.canonical_symbol),
    display_symbol: stringValue(source.display_symbol, fallback.display_symbol),
    market: normalizeMarketValue(source.market ?? fallback.market),
    exchange: nullableStringValue(source.exchange) ?? fallback.exchange,
    asset_type: normalizeAssetTypeValue(source.asset_type ?? fallback.asset_type),
    confidence: normalizeMarketResolutionConfidence(source.confidence),
    source: normalizeMarketResolutionSource(source.source),
    warnings: normalizeStringArray(source.warnings),
  };
}

function normalizeTradePlanStatus(value: unknown): TradePlanStatus {
  return value === "executed" || value === "expired" ? value : "planned";
}

function normalizeTradePlanSource(value: unknown): TradePlanSource {
  return value === "analysis_prefill" ? "analysis_prefill" : "manual";
}

function normalizeTradePlanBase(value: unknown): TradePlan {
  const plan = isRecord(value) ? value : {};
  const rawSymbol = stringValue(plan.raw_symbol, stringValue(plan.ticker, "UNKNOWN"));
  const ticker = stringValue(
    plan.ticker,
    stringValue(plan.canonical_symbol, rawSymbol)
  ).toUpperCase();
  const canonicalSymbol = stringValue(plan.canonical_symbol, ticker).toUpperCase();
  const displaySymbol = stringValue(plan.display_symbol, canonicalSymbol);
  const market = normalizeMarketValue(plan.market);
  const exchange = nullableStringValue(plan.exchange);
  const assetType = normalizeAssetTypeValue(plan.asset_type);
  const exchangeOrMarket = stringValue(
    plan.exchange_or_market,
    exchange ?? market
  );

  return {
    type: "trade_plan",
    schema_version:
      typeof plan.schema_version === "number" && Number.isFinite(plan.schema_version)
        ? plan.schema_version
        : 1,
    plan_id: stringValue(plan.plan_id),
    raw_symbol: rawSymbol,
    ticker,
    canonical_symbol: canonicalSymbol,
    display_symbol: displaySymbol,
    market,
    exchange,
    asset_type: assetType,
    market_resolution: normalizeMarketResolution(plan.market_resolution, {
      raw_symbol: rawSymbol,
      canonical_symbol: canonicalSymbol,
      display_symbol: displaySymbol,
      market,
      exchange,
      asset_type: assetType,
    }),
    exchange_or_market: exchangeOrMarket,
    side: stringValue(plan.side, "unknown"),
    status: normalizeTradePlanStatus(plan.status),
    status_reason: stringValue(plan.status_reason),
    source: normalizeTradePlanSource(plan.source),
    strategy_tags: normalizeStringArray(plan.strategy_tags),
    entry_condition: stringValue(plan.entry_condition),
    thesis: stringValue(plan.thesis),
    invalidation_condition: stringValue(plan.invalidation_condition),
    risk_rule: stringValue(plan.risk_rule),
    reward_target: stringValue(plan.reward_target),
    position_plan: stringValue(plan.position_plan),
    planned_horizon: stringValue(plan.planned_horizon),
    stop_loss: nullableNumberValue(plan.stop_loss),
    take_profit: nullableNumberValue(plan.take_profit),
    expires_at: stringValue(plan.expires_at),
    notes: stringValue(plan.notes),
    analysis_references: normalizeAnalysisReferences(plan.analysis_references),
    linked_trade_id: stringValue(plan.linked_trade_id),
    created_at: stringValue(plan.created_at),
    updated_at: stringValue(plan.updated_at),
  };
}

function normalizeTradePlan(value: unknown): TradePlan {
  return normalizeTradePlanBase(value);
}

function normalizeTradePlanSnapshot(value: unknown): TradePlanSnapshot | null {
  if (!isRecord(value)) {
    return null;
  }
  const plan = normalizeTradePlanBase(value);
  return {
    ...plan,
    type: "trade_plan_snapshot",
    snapshotted_at: stringValue(value.snapshotted_at),
  };
}

function normalizeTradeRecord(value: unknown): TradeRecord {
  const record = isRecord(value) ? value : {};
  const rawSymbol = stringValue(record.raw_symbol, stringValue(record.ticker, "UNKNOWN"));
  const ticker = stringValue(
    record.ticker,
    stringValue(record.canonical_symbol, rawSymbol)
  ).toUpperCase();
  const canonicalSymbol = stringValue(record.canonical_symbol, ticker).toUpperCase();
  const displaySymbol = stringValue(record.display_symbol, canonicalSymbol);
  const market = normalizeMarketValue(record.market);
  const exchange = nullableStringValue(record.exchange);
  const assetType = normalizeAssetTypeValue(record.asset_type);
  const exchangeOrMarket = stringValue(
    record.exchange_or_market,
    exchange ?? market
  );

  return {
    type: "trade_record",
    schema_version:
      typeof record.schema_version === "number" && Number.isFinite(record.schema_version)
        ? record.schema_version
        : 1,
    trade_id: stringValue(record.trade_id, `${ticker}-legacy`),
    raw_symbol: rawSymbol,
    ticker,
    canonical_symbol: canonicalSymbol,
    display_symbol: displaySymbol,
    market,
    exchange,
    asset_type: assetType,
    market_resolution: normalizeMarketResolution(record.market_resolution, {
      raw_symbol: rawSymbol,
      canonical_symbol: canonicalSymbol,
      display_symbol: displaySymbol,
      market,
      exchange,
      asset_type: assetType,
    }),
    exchange_or_market: exchangeOrMarket,
    side: stringValue(record.side, "unknown"),
    status: stringValue(record.status, "unknown"),
    entry_timestamp: nullableStringValue(record.entry_timestamp),
    entry_price: nullableNumberValue(record.entry_price),
    exit_timestamp: nullableStringValue(record.exit_timestamp),
    exit_price: nullableNumberValue(record.exit_price),
    size: nullableNumberValue(record.size),
    strategy_tags: normalizeStringArray(record.strategy_tags),
    entry_reason: stringValue(record.entry_reason),
    invalidation_condition: stringValue(record.invalidation_condition),
    initial_thesis: stringValue(record.initial_thesis),
    planned_horizon: stringValue(record.planned_horizon),
    stop_loss: nullableNumberValue(record.stop_loss),
    take_profit: nullableNumberValue(record.take_profit),
    exit_reason: stringValue(record.exit_reason),
    plan_execution: stringValue(record.plan_execution),
    execution_note: stringValue(record.execution_note),
    originating_plan_id: nullableStringValue(record.originating_plan_id),
    originating_plan_snapshot: normalizeTradePlanSnapshot(
      record.originating_plan_snapshot
    ),
    notes: stringValue(record.notes),
    analysis_references: normalizeAnalysisReferences(record.analysis_references),
    derived_metrics: isRecord(record.derived_metrics)
      ? {
          realized_return_pct: nullableNumberValue(
            record.derived_metrics.realized_return_pct
          ),
          pnl_amount: nullableNumberValue(record.derived_metrics.pnl_amount),
          r_multiple: nullableNumberValue(record.derived_metrics.r_multiple),
          holding_period_hours: nullableNumberValue(
            record.derived_metrics.holding_period_hours
          ),
        }
      : undefined,
    created_at: stringValue(record.created_at),
    updated_at: stringValue(record.updated_at),
  };
}

function normalizeTradeReviewType(value: unknown): TradeReviewType {
  return value === "exit_review" ? "exit_review" : "entry_review";
}

function normalizeTradeReview(value: unknown, fallbackRecord?: TradeRecord): TradeReview {
  const review = isRecord(value) ? value : {};
  const reviewType = normalizeTradeReviewType(review.review_type);
  const tradeId = stringValue(review.trade_id, fallbackRecord?.trade_id ?? "UNKNOWN");
  const ticker = stringValue(review.ticker, fallbackRecord?.ticker ?? "UNKNOWN");

  return {
    type: "trade_review",
    schema_version:
      typeof review.schema_version === "number" && Number.isFinite(review.schema_version)
        ? review.schema_version
        : 1,
    review_id: stringValue(review.review_id, `${tradeId}-${reviewType}`),
    trade_id: tradeId,
    ticker,
    review_type: reviewType,
    analysis_date: stringValue(review.analysis_date),
    analysis_references: normalizeAnalysisReferences(review.analysis_references),
    thesis_assessment: stringValue(review.thesis_assessment),
    timing_assessment: stringValue(review.timing_assessment),
    sizing_assessment: stringValue(review.sizing_assessment),
    discipline_assessment: stringValue(review.discipline_assessment),
    outcome_summary: stringValue(review.outcome_summary),
    improvement_actions: normalizeStringArray(review.improvement_actions),
    ticker_specific_lessons: normalizeStringArray(review.ticker_specific_lessons),
    cross_ticker_tags: normalizeStringArray(review.cross_ticker_tags),
    created_at: stringValue(review.created_at),
    updated_at: stringValue(review.updated_at),
  };
}

function normalizeTradeDetail(value: unknown): TradeDetail {
  const detail = isRecord(value) ? value : {};
  const record = normalizeTradeRecord(detail.record);
  const reviews = Array.isArray(detail.reviews)
    ? detail.reviews.map((review) => normalizeTradeReview(review, record))
    : [];
  return { record, reviews };
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

export async function getAdminSearchQuota(): Promise<AdminSearchQuotaResponse> {
  return requestJson<AdminSearchQuotaResponse>("/api/admin/search-quota", {
    cache: "no-store",
  });
}

export async function updateAdminSearchGlobal(
  payload: AdminSearchGlobalUpdateRequest
): Promise<AdminSearchGlobalUpdateResponse> {
  return requestJson<AdminSearchGlobalUpdateResponse>(
    "/api/admin/search-quota/global",
    createJsonRequestInit("PUT", payload)
  );
}

export async function updateAdminSearchProvider(
  provider: AdminSearchProviderName,
  payload: AdminSearchProviderUpdateRequest
): Promise<AdminSearchProviderUpdateResponse> {
  return requestJson<AdminSearchProviderUpdateResponse>(
    `/api/admin/search-quota/providers/${provider}`,
    createJsonRequestInit("PUT", payload)
  );
}

export async function reactivateAdminSearchProvider(
  provider: AdminSearchProviderName
): Promise<AdminSearchProviderUpdateResponse> {
  return requestJson<AdminSearchProviderUpdateResponse>(
    `/api/admin/search-quota/providers/${provider}/reactivate`,
    createJsonRequestInit("POST")
  );
}

export async function resetAdminSearchProviderUsage(
  provider: AdminSearchProviderName
): Promise<AdminSearchProviderUsageResetResponse> {
  return requestJson<AdminSearchProviderUsageResetResponse>(
    `/api/admin/search-quota/providers/${provider}/usage/reset`,
    createJsonRequestInit("POST")
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

export async function updateAdminLLMModuleSetting(
  module: string,
  payload: AdminLLMModuleSettingUpdateRequest
): Promise<{ setting: AdminLLMModuleSetting }> {
  return requestJson<{ setting: AdminLLMModuleSetting }>(
    `/api/admin/llm-models/module-settings/${module}`,
    createJsonRequestInit("PUT", payload)
  );
}

export async function updateAdminLLMUiSetting(
  settingKey: string,
  payload: AdminLLMUiSettingUpdateRequest
): Promise<{ setting: AdminLLMUiSetting }> {
  return requestJson<{ setting: AdminLLMUiSetting }>(
    `/api/admin/llm-models/ui-settings/${settingKey}`,
    createJsonRequestInit("PUT", payload)
  );
}

export async function listAdminTaskQueue(): Promise<AdminTaskQueueResponse> {
  return requestJson<AdminTaskQueueResponse>("/api/admin/task-queue", {
    cache: "no-store",
  });
}

export async function deleteAdminTaskQueueItem(
  kind: AdminTaskQueueItem["kind"],
  taskId: string
): Promise<DeleteAdminTaskQueueItemResponse> {
  return requestJson<DeleteAdminTaskQueueItemResponse>(
    `/api/admin/task-queue/${kind}/${taskId}`,
    {
      method: "DELETE",
      credentials: "include",
    }
  );
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

export async function listMarketBriefs(): Promise<MarketBriefIndexResponse> {
  return requestJson<MarketBriefIndexResponse>("/api/market-briefs", {
    cache: "no-store",
  });
}

export async function getStructure(reportId: string): Promise<ReportStructure> {
  return requestJson<ReportStructure>(`/api/reports/${reportId}/structure`, {
    cache: "no-store",
  });
}

export async function updateReportVisibility(
  reportId: string,
  visibility: ReportVisibility
): Promise<Report> {
  return requestJson<Report>(
    `/api/reports/${reportId}/visibility`,
    createJsonRequestInit("PATCH", { visibility })
  );
}

export async function deleteReport(reportId: string): Promise<DeleteReportResponse> {
  return requestJson<DeleteReportResponse>(
    `/api/reports/${reportId}`,
    createJsonRequestInit("DELETE")
  );
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
  const data = await parseJsonResponse<unknown>(response);
  return Array.isArray(data) ? data.map(normalizeTradeRecord) : [];
}

export async function listTradePlans(
  query: TradePlanQuery = {}
): Promise<TradePlan[]> {
  const url = new URL(buildApiUrl("/api/trade-plans"));
  if (query.ticker) {
    url.searchParams.set("ticker", query.ticker);
  }
  if (query.status !== undefined) {
    url.searchParams.set("status", query.status ?? "");
  }

  const response = await fetch(url.toString(), {
    credentials: "include",
    cache: "no-store",
  });
  const data = await parseJsonResponse<unknown>(response);
  return Array.isArray(data) ? data.map(normalizeTradePlan) : [];
}

export async function resolveMarketSymbol(
  symbol: string,
  overrides?: {
    manual_market?: MarketResolutionMarket | null;
    manual_exchange?: string | null;
    manual_asset_type?: MarketResolutionAssetType | null;
  }
): Promise<MarketResolution> {
  const url = new URL(buildApiUrl("/api/market-resolution"));
  url.searchParams.set("symbol", symbol);
  if (overrides?.manual_market) {
    url.searchParams.set("manual_market", overrides.manual_market);
  }
  if (overrides?.manual_exchange) {
    url.searchParams.set("manual_exchange", overrides.manual_exchange);
  }
  if (overrides?.manual_asset_type) {
    url.searchParams.set("manual_asset_type", overrides.manual_asset_type);
  }

  const response = await fetch(url.toString(), {
    credentials: "include",
    cache: "no-store",
  });
  return parseJsonResponse<MarketResolution>(response);
}

export async function createTrade(
  payload: TradeRecordCreateRequest
): Promise<TradeRecord> {
  const data = await requestJson<unknown>(
    "/api/trades",
    createJsonRequestInit("POST", payload)
  );
  return normalizeTradeRecord(data);
}

export async function createTradePlan(
  payload: TradePlanCreateRequest
): Promise<TradePlan> {
  const data = await requestJson<unknown>(
    "/api/trade-plans",
    createJsonRequestInit("POST", payload)
  );
  return normalizeTradePlan(data);
}

export async function getTradePlan(planId: string): Promise<TradePlan> {
  const data = await requestJson<unknown>(`/api/trade-plans/${planId}`, {
    cache: "no-store",
  });
  return normalizeTradePlan(data);
}

export async function updateTradePlan(
  planId: string,
  payload: TradePlanUpdateRequest
): Promise<TradePlan> {
  const data = await requestJson<unknown>(
    `/api/trade-plans/${planId}`,
    createJsonRequestInit("PUT", payload)
  );
  return normalizeTradePlan(data);
}

export async function deleteTradePlan(
  planId: string
): Promise<DeleteTradePlanResponse> {
  return requestJson<DeleteTradePlanResponse>(
    `/api/trade-plans/${planId}`,
    createJsonRequestInit("DELETE")
  );
}

export async function executeTradePlan(
  planId: string,
  payload: TradePlanExecuteRequest
): Promise<TradePlanMutationResponse> {
  const data = await requestJson<unknown>(
    `/api/trade-plans/${planId}/execute`,
    createJsonRequestInit("POST", payload)
  );
  const response = isRecord(data) ? data : {};
  return {
    plan: normalizeTradePlan(response.plan),
    record: normalizeTradeRecord(response.record),
  };
}

export async function linkTradeToPlan(
  tradeId: string,
  payload: TradePlanLinkRequest
): Promise<TradePlanMutationResponse> {
  const data = await requestJson<unknown>(
    `/api/trades/${tradeId}/link-plan`,
    createJsonRequestInit("POST", payload)
  );
  const response = isRecord(data) ? data : {};
  return {
    plan: normalizeTradePlan(response.plan),
    record: normalizeTradeRecord(response.record),
  };
}

export async function getTrade(tradeId: string): Promise<TradeDetail> {
  const data = await requestJson<unknown>(`/api/trades/${tradeId}`, {
    cache: "no-store",
  });
  return normalizeTradeDetail(data);
}

export async function updateTrade(
  tradeId: string,
  payload: TradeRecordUpdateRequest
): Promise<TradeRecord> {
  const data = await requestJson<unknown>(
    `/api/trades/${tradeId}`,
    createJsonRequestInit("PUT", payload)
  );
  return normalizeTradeRecord(data);
}

export async function generateTradeReview(
  tradeId: string,
  reviewType: TradeReviewType,
  payload: TradeReviewGenerateRequest
): Promise<TradeReview> {
  const data = await requestJson<unknown>(
    `/api/trades/${tradeId}/reviews/${reviewType}/generate`,
    createJsonRequestInit("POST", payload)
  );
  return normalizeTradeReview(data);
}

export async function saveTradeReview(
  tradeId: string,
  reviewType: TradeReviewType,
  payload: TradeReviewSaveRequest
): Promise<TradeReview> {
  const data = await requestJson<unknown>(
    `/api/trades/${tradeId}/reviews/${reviewType}`,
    createJsonRequestInit("PUT", payload)
  );
  return normalizeTradeReview(data);
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

export async function cancelDataSyncJob(
  taskId: string
): Promise<CancelTaskResponse> {
  return requestJson<CancelTaskResponse>(
    `/api/admin/data-sync/jobs/${taskId}/cancel`,
    {
      method: "POST",
      credentials: "include",
    }
  );
}

export async function listScreenerTasks(): Promise<ScreenerTask[]> {
  return requestJson<ScreenerTask[]>("/api/screener/tasks", {
    cache: "no-store",
  });
}

export async function listJournalReviewTasks(): Promise<JournalReviewTask[]> {
  return requestJson<JournalReviewTask[]>("/api/journal/review-tasks", {
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


export async function listOpportunityRuns(): Promise<OpportunityRunSummary[]> {
  return requestJson<OpportunityRunSummary[]>("/api/opportunities/runs", {
    cache: "no-store",
  });
}

export async function getOpportunityRun(runId: string): Promise<OpportunityRunSummary> {
  return requestJson<OpportunityRunSummary>(`/api/opportunities/runs/${runId}`, {
    cache: "no-store",
  });
}

export async function getOpportunityMarketPulse(runId: string): Promise<MarketPulse> {
  return requestJson<MarketPulse>(`/api/opportunities/runs/${runId}/market-pulse`, { cache: "no-store" });
}

export async function getOpportunityThemes(runId: string): Promise<ThemeRadarResponse> {
  return requestJson<ThemeRadarResponse>(`/api/opportunities/runs/${runId}/themes`, { cache: "no-store" });
}

export async function getOpportunityCandidates(runId: string): Promise<CandidatePoolResponse> {
  return requestJson<CandidatePoolResponse>(`/api/opportunities/runs/${runId}/candidates`, { cache: "no-store" });
}

export async function getOpportunityEvents(runId: string): Promise<OpportunityEvent[]> {
  return requestJson<OpportunityEvent[]>(`/api/opportunities/runs/${runId}/events`, { cache: "no-store" });
}

export async function listOpportunityTasks(): Promise<OpportunityTask[]> {
  return requestJson<OpportunityTask[]>("/api/opportunities/tasks", {
    cache: "no-store",
  });
}

export async function getOpportunityTask(taskId: string): Promise<OpportunityTask> {
  return requestJson<OpportunityTask>(`/api/opportunities/tasks/${taskId}`, {
    cache: "no-store",
  });
}

export async function cancelOpportunityTask(
  taskId: string
): Promise<CancelTaskResponse> {
  return requestJson<CancelTaskResponse>(
    `/api/opportunities/tasks/${taskId}/cancel`,
    {
      method: "POST",
      credentials: "include",
    }
  );
}

export async function listOpportunityWatchlist(): Promise<WatchlistItem[]> {
  return requestJson<WatchlistItem[]>("/api/opportunities/watchlist", { cache: "no-store" });
}

export async function addOpportunityWatchlistItem(payload: WatchlistItem): Promise<{ id: string; symbol: string; status: string }> {
  return requestJson<{ id: string; symbol: string; status: string }>("/api/opportunities/watchlist", createJsonRequestInit("POST", payload));
}

export async function deleteOpportunityWatchlistItem(symbol: string): Promise<{ deleted: boolean; symbol: string }> {
  return requestJson<{ deleted: boolean; symbol: string }>(`/api/opportunities/watchlist/${encodeURIComponent(symbol)}`, {
    method: "DELETE",
    credentials: "include",
  });
}

export async function createOpportunityRun(payload: OpportunityRunRequest): Promise<OpportunityTaskCreateResponse> {
  return requestJson<OpportunityTaskCreateResponse>("/api/opportunities/run", createJsonRequestInit("POST", payload));
}

export function subscribeToOpportunityTask(
  taskId: string,
  onEvent: (event: ProgressEvent) => void,
  onError?: (error: Error) => void,
  startCursor = 0
): () => void {
  const url = new URL(buildApiUrl(`/api/opportunities/tasks/${taskId}/stream`));
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
          : new Error("Unable to parse opportunity task stream event")
      );
    }
  };

  eventSource.onerror = () => {
    onError?.(new Error("Opportunity task progress stream disconnected"));
    eventSource.close();
  };

  return () => {
    eventSource.close();
  };
}


export async function analyzeOpportunityCandidate(
  symbol: string,
  payload: CandidateAnalyzeRequest = {}
): Promise<{ task_id: string; status: string; report_id?: string }> {
  return requestJson<{ task_id: string; status: string; report_id?: string }>(
    `/api/opportunities/candidates/${encodeURIComponent(symbol)}/analyze`,
    createJsonRequestInit("POST", payload)
  );
}
