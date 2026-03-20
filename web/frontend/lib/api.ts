/**
 * TradingAgents Report Viewer API Client
 * Simple fetch wrappers for the 3 read-only endpoints.
 */

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

/**
 * Report listing response.
 */
export interface Report {
  id: string;
  ticker: string;
  date: string;
  time: string;
}

/**
 * Report structure response (actual files present).
 */
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

/**
 * List all available reports sorted by date descending.
 */
export async function listReports(): Promise<Report[]> {
  const res = await fetch(`${API_BASE}/api/reports`);
  if (!res.ok) {
    throw new Error(`Failed to list reports: ${res.status}`);
  }
  return res.json();
}

/**
 * Get the structure (file listing) for a specific report.
 */
export async function getStructure(reportId: string): Promise<ReportStructure> {
  const res = await fetch(`${API_BASE}/api/reports/${reportId}/structure`);
  if (!res.ok) {
    throw new Error(`Failed to get structure for report ${reportId}: ${res.status}`);
  }
  return res.json();
}

/**
 * Get the content of a file within a report.
 * path: relative path within the report, e.g. "complete_report.md" or "1_analysts/market.md"
 */
export async function getContent(
  reportId: string,
  path: string
): Promise<string> {
  const url = new URL(`${API_BASE}/api/reports/${reportId}/content`);
  url.searchParams.set("path", path);
  
  const res = await fetch(url.toString());
  if (!res.ok) {
    throw new Error(
      `Failed to get content from ${reportId}/${path}: ${res.status}`
    );
  }
  
  const data = await res.json();
  return data.content;
}
