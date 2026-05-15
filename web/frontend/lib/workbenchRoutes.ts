const HOME_PATH = "/";
const LOGIN_PATH = "/login";

function resolveNextPath(nextPath: string | null | undefined): string {
  if (!nextPath || !nextPath.startsWith("/") || nextPath.startsWith("//")) {
    return HOME_PATH;
  }

  return nextPath;
}

export function buildHomeHref(query?: string | null): string {
  const normalizedQuery = query?.trim() ?? "";
  if (!normalizedQuery) {
    return HOME_PATH;
  }

  const searchParams = new URLSearchParams({ q: normalizedQuery });
  return `${HOME_PATH}?${searchParams.toString()}`;
}

export function buildJournalHref(): string {
  return "/journal";
}

export function buildAssetsHref(): string {
  return "/assets";
}

export function buildActivityHref(): string {
  return "/activity";
}

export function buildOpportunitiesHref(runId?: string | null): string {
  if (!runId) {
    return "/opportunities";
  }
  const searchParams = new URLSearchParams({ runId });
  return `/opportunities?${searchParams.toString()}`;
}

export function buildLoginHref(nextPath?: string | null): string {
  const searchParams = new URLSearchParams({
    next: resolveNextPath(nextPath),
  });
  return `${LOGIN_PATH}?${searchParams.toString()}`;
}

export function buildReportHref(reportId: string): string {
  return `/reports/${encodeURIComponent(reportId)}`;
}

export function buildTaskHref(taskId: string): string {
  return `/tasks/${encodeURIComponent(taskId)}`;
}

export function buildScreenerHref(runId?: string | null): string {
  if (!runId) {
    return "/screeners";
  }

  const searchParams = new URLSearchParams({ runId });
  return `/screeners?${searchParams.toString()}`;
}

export function buildScreenerRunHref(runId: string): string {
  return buildScreenerHref(runId);
}

export function buildScreenerTaskHref(taskId: string): string {
  return `/screener-tasks/${encodeURIComponent(taskId)}`;
}
