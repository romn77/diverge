const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

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
  defaults: {
    top_k: number;
    limit_per_market: number;
  };
}

export interface ScreenTaskCreateRequest {
  markets: string[];
  as_of_date: string;
  top_k: number;
  limit_per_market: number | null;
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

async function parseJsonResponse<T>(response: Response): Promise<T> {
  if (!response.ok) {
    let detail = `${response.status}`;

    try {
      const payload = (await response.json()) as { detail?: string };
      if (typeof payload.detail === "string" && payload.detail.trim()) {
        detail = payload.detail;
      }
    } catch {
      // Ignore JSON parse errors and fall back to status text.
    }

    throw new Error(detail);
  }

  return (await response.json()) as T;
}

export async function listReports(): Promise<Report[]> {
  const response = await fetch(`${API_BASE}/api/reports`);
  return parseJsonResponse<Report[]>(response);
}

export async function getStructure(reportId: string): Promise<ReportStructure> {
  const response = await fetch(`${API_BASE}/api/reports/${reportId}/structure`);
  return parseJsonResponse<ReportStructure>(response);
}

export async function getContent(reportId: string, path: string): Promise<string> {
  const url = new URL(`${API_BASE}/api/reports/${reportId}/content`);
  url.searchParams.set("path", path);

  const response = await fetch(url.toString());
  const data = await parseJsonResponse<{ content: string }>(response);
  return data.content;
}

export async function createTask(
  payload: TaskCreateRequest
): Promise<TaskCreateResponse> {
  const response = await fetch(`${API_BASE}/api/tasks`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify(payload),
  });

  return parseJsonResponse<TaskCreateResponse>(response);
}

export async function listTasks(): Promise<Task[]> {
  const response = await fetch(`${API_BASE}/api/tasks`);
  return parseJsonResponse<Task[]>(response);
}

export async function getTask(taskId: string): Promise<Task> {
  const response = await fetch(`${API_BASE}/api/tasks/${taskId}`);
  return parseJsonResponse<Task>(response);
}

export async function getConfigOptions(): Promise<ConfigOptions> {
  const response = await fetch(`${API_BASE}/api/config/options`);
  return parseJsonResponse<ConfigOptions>(response);
}

export async function getScreenerConfigOptions(): Promise<ScreenerConfigOptions> {
  const response = await fetch(`${API_BASE}/api/screener/config/options`);
  return parseJsonResponse<ScreenerConfigOptions>(response);
}

export async function createScreenerTask(
  payload: ScreenTaskCreateRequest
): Promise<ScreenerTaskCreateResponse> {
  const response = await fetch(`${API_BASE}/api/screener/tasks`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify(payload),
  });

  return parseJsonResponse<ScreenerTaskCreateResponse>(response);
}

export async function listScreenerTasks(): Promise<ScreenerTask[]> {
  const response = await fetch(`${API_BASE}/api/screener/tasks`);
  return parseJsonResponse<ScreenerTask[]>(response);
}

export async function getScreenerTask(taskId: string): Promise<ScreenerTask> {
  const response = await fetch(`${API_BASE}/api/screener/tasks/${taskId}`);
  return parseJsonResponse<ScreenerTask>(response);
}

export async function listScreenerRuns(): Promise<ScreenerRunSummary[]> {
  const response = await fetch(`${API_BASE}/api/screener/runs`);
  return parseJsonResponse<ScreenerRunSummary[]>(response);
}

export async function getScreenerRun(runId: string): Promise<ScreenerRunDetail> {
  const response = await fetch(`${API_BASE}/api/screener/runs/${runId}`);
  return parseJsonResponse<ScreenerRunDetail>(response);
}

export async function listScreenerRunCandidates(
  runId: string
): Promise<ScreenerCandidateRow[]> {
  const response = await fetch(`${API_BASE}/api/screener/runs/${runId}/candidates`);
  return parseJsonResponse<ScreenerCandidateRow[]>(response);
}

export function subscribeToTask(
  taskId: string,
  onEvent: (event: ProgressEvent) => void,
  onError?: (error: Error) => void
): () => void {
  const eventSource = new EventSource(`${API_BASE}/api/tasks/${taskId}/stream`);

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
  const eventSource = new EventSource(`${API_BASE}/api/screener/tasks/${taskId}/stream`);

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
