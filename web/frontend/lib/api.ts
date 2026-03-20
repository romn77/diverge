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
