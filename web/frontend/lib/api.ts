const API_BASE =
  process.env.NEXT_PUBLIC_API_BASE_URL ||
  process.env.NEXT_PUBLIC_API_URL ||
  "http://localhost:8000";

export const AUTH_REQUIRED_EVENT = "tradingagents:auth-required";

export type AuthMode = "disabled" | "optional" | "required";
export type UserRole = "admin" | "operator" | "viewer";
export type UserStatus = "active" | "disabled";

export interface AuthUser {
  id: string;
  email: string;
  display_name: string;
  role: UserRole;
  status: UserStatus;
  must_change_password: boolean;
  last_login_at: string | null;
  created_at: string;
  updated_at: string;
}

export interface AuthState {
  enabled: boolean;
  mode: AuthMode;
  authenticated: boolean;
  user: AuthUser | null;
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

export interface DeleteAdminUserResponse {
  deleted: boolean;
  user_id: string;
}

export class ApiError extends Error {
  status: number;

  constructor(status: number, detail: string) {
    super(detail);
    this.name = "ApiError";
    this.status = status;
  }
}

export interface Report {
  id: string;
  ticker: string;
  date: string;
  time: string;
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
  analysis_date: string;
  analysts: string[];
  research_depth: number;
  llm_provider: string;
  quick_think_llm: string;
  deep_think_llm: string;
  output_language: string;
  google_thinking_level: string | null;
  openai_reasoning_effort: string | null;
}

export interface TaskCreateResponse {
  task_id: string;
  status: string;
}

export type TaskStatus = "pending" | "running" | "completed" | "failed";
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
  ticker: string;
  analysis_date: string;
  analysts: string[];
  request_payload: TaskCreateRequest | null;
  status: TaskStatus;
  latest_progress: ProgressEvent | null;
  report_id: string | null;
  error: string | null;
}

export interface SelectOption {
  label: string;
  value: string;
}

export interface ProviderOption extends SelectOption {
  enabled: boolean;
  disabled_reason?: string | null;
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
  models: Record<string, ModelOptions>;
  analysts: SelectOption[];
  research_depth: ResearchDepthOption[];
  output_languages: SelectOption[];
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
  defaults: {
    cn_data_source: string;
    top_k: number;
  };
}

export interface ScreenTaskCreateRequest {
  markets: string[];
  as_of_date: string;
  top_k: number;
  cn_data_source: string;
}

export interface ScreenerTaskCreateResponse {
  task_id: string;
  status: string;
}

export interface ScreenerTask {
  id: string;
  request_payload: ScreenTaskCreateRequest | null;
  status: TaskStatus;
  latest_progress: ProgressEvent | null;
  run_id: string | null;
  error: string | null;
}

export interface ScreenerRunSummary {
  id: string;
  as_of_date: string;
  markets: string[];
  candidate_count: number;
  generated_at: string;
}

export interface ScreenerRunDetail extends ScreenerRunSummary {
  filtered_count_by_reason: Record<string, number>;
  artifact_paths: Record<string, string>;
}

export interface ScreenerCandidateRow {
  symbol: string;
  market: string;
  global_rank: number;
  market_rank?: number;
  total_score: number;
  trend_score: number;
  momentum_score: number;
  risk_score: number;
  liquidity_score: number;
  strategy_tags: string;
  risk_flags: string;
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

async function parseJsonResponse<T>(response: Response): Promise<T> {
  if (!response.ok) {
    let detail = response.statusText || `${response.status}`;

    try {
      const payload = (await response.json()) as { detail?: string };
      if (typeof payload.detail === "string" && payload.detail.trim()) {
        detail = payload.detail;
      }
    } catch {
      // Ignore JSON parse errors and fall back to status text.
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
  onError?: (error: Error) => void
): () => void {
  const eventSource = new EventSource(
    buildApiUrl(`/api/screener/tasks/${taskId}/stream`),
    {
      withCredentials: true,
    }
  );

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
