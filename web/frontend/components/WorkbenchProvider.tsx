"use client";

import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from "react";
import { useAuth } from "@/components/AuthProvider";
import {
  ApiError,
  listJournalReviewTasks,
  listOpportunityTasks,
  listReports,
  listScreenerRuns,
  listScreenerTasks,
  listTasks,
  type JournalReviewTask,
  type OpportunityTask,
  type Report,
  type Permission,
  type ScreenerRunSummary,
  type ScreenerTask,
  type Task,
  type TaskStatus,
} from "@/lib/api";

interface WorkbenchContextValue {
  authEnabled: boolean;
  authError: string | null;
  authState: ReturnType<typeof useAuth>["authState"];
  authStatus: ReturnType<typeof useAuth>["authStatus"];
  canAccessWorkbench: boolean;
  canManageUsers: boolean;
  loadingReports: boolean;
  reports: Report[];
  reportsError: string | null;
  recentReports: Report[];
  recentTickers: string[];
  refreshReports: () => Promise<void>;
  refreshJournalReviewTasks: () => Promise<void>;
  refreshOpportunityTasks: () => Promise<void>;
  refreshScreenerRuns: () => Promise<void>;
  refreshScreenerTasks: () => Promise<void>;
  refreshSession: ReturnType<typeof useAuth>["refreshSession"];
  refreshTasks: () => Promise<void>;
  reportsByTicker: Array<{ ticker: string; reports: Report[] }>;
  journalReviewTasks: JournalReviewTask[];
  opportunityTasks: OpportunityTask[];
  screenerRuns: ScreenerRunSummary[];
  screenerTasks: ScreenerTask[];
  tasks: Task[];
  activeTasks: Task[];
  activeJournalReviewTasks: JournalReviewTask[];
  activeOpportunityTasks: OpportunityTask[];
  activeScreenerTasks: ScreenerTask[];
  newAnalysisDisabled: boolean;
  newScreenerDisabled: boolean;
  canAccessOpportunityRadar: boolean;
  logout: ReturnType<typeof useAuth>["logout"];
}

const WorkbenchContext = createContext<WorkbenchContextValue | null>(null);

const POLL_INTERVAL_MS = 3000;
const ACTIVE_TASK_STATUSES = new Set<TaskStatus>([
  "pending",
  "queued",
  "waiting_for_quota",
  "running",
]);

function hasActiveTaskStatus(task: { status: TaskStatus }): boolean {
  return ACTIVE_TASK_STATUSES.has(task.status);
}

function hasPermission(
  authState: ReturnType<typeof useAuth>["authState"],
  permission: Permission
): boolean {
  if (!authState?.enabled) {
    return true;
  }
  return Boolean(authState.permissions.includes(permission));
}

function dedupeScreenerRuns(runs: ScreenerRunSummary[]): ScreenerRunSummary[] {
  const uniqueRuns = new Map<string, ScreenerRunSummary>();
  for (const run of runs) {
    if (!uniqueRuns.has(run.id)) {
      uniqueRuns.set(run.id, run);
    }
  }
  return Array.from(uniqueRuns.values());
}

export function WorkbenchProvider({ children }: { children: ReactNode }) {
  const {
    authError,
    authState,
    authStatus,
    logout,
    refreshSession,
  } = useAuth();
  const [reports, setReports] = useState<Report[]>([]);
  const [screenerRuns, setScreenerRuns] = useState<ScreenerRunSummary[]>([]);
  const [tasks, setTasks] = useState<Task[]>([]);
  const [screenerTasks, setScreenerTasks] = useState<ScreenerTask[]>([]);
  const [opportunityTasks, setOpportunityTasks] = useState<OpportunityTask[]>([]);
  const [journalReviewTasks, setJournalReviewTasks] = useState<JournalReviewTask[]>([]);
  const [loadingReports, setLoadingReports] = useState(true);
  const [reportsError, setReportsError] = useState<string | null>(null);

  const authEnabled = authState?.enabled ?? false;
  const canAccessWorkbench =
    authStatus === "ready" && (!authEnabled || Boolean(authState?.authenticated));
  const canManageUsers = hasPermission(authState, "admin:users");
  const canCreateAnalysis = hasPermission(authState, "analysis:create");
  const canCreateScreener = hasPermission(authState, "screener:create");
  const canReadOpportunity = hasPermission(authState, "opportunity:read");
  const canAccessOpportunityRadar = canAccessWorkbench && canReadOpportunity;

  const handleProtectedError = useCallback(
    (error: unknown): boolean => {
      if (error instanceof ApiError && error.status === 401) {
        void refreshSession({ silent: true });
        return true;
      }
      return false;
    },
    [refreshSession]
  );

  const refreshReports = useCallback(async () => {
    if (!canAccessWorkbench) {
      setLoadingReports(false);
      return;
    }

    setLoadingReports(true);
    setReportsError(null);

    try {
      setReports(await listReports());
    } catch (error) {
      if (handleProtectedError(error)) {
        return;
      }
      setReportsError(error instanceof Error ? error.message : "Unable to load reports");
    } finally {
      setLoadingReports(false);
    }
  }, [canAccessWorkbench, handleProtectedError]);

  const refreshTasks = useCallback(async () => {
    if (!canAccessWorkbench) {
      return;
    }

    try {
      setTasks(await listTasks());
    } catch (error) {
      if (handleProtectedError(error)) {
        return;
      }
    }
  }, [canAccessWorkbench, handleProtectedError]);

  const refreshScreenerRuns = useCallback(async () => {
    if (!canAccessWorkbench) {
      return;
    }

    try {
      setScreenerRuns(dedupeScreenerRuns(await listScreenerRuns()));
    } catch (error) {
      if (handleProtectedError(error)) {
        return;
      }
    }
  }, [canAccessWorkbench, handleProtectedError]);

  const refreshScreenerTasks = useCallback(async () => {
    if (!canAccessWorkbench) {
      return;
    }

    try {
      setScreenerTasks(await listScreenerTasks());
    } catch (error) {
      if (handleProtectedError(error)) {
        return;
      }
    }
  }, [canAccessWorkbench, handleProtectedError]);

  const refreshOpportunityTasks = useCallback(async () => {
    if (!canAccessOpportunityRadar) {
      return;
    }

    try {
      setOpportunityTasks(await listOpportunityTasks());
    } catch (error) {
      if (handleProtectedError(error)) {
        return;
      }
    }
  }, [canAccessOpportunityRadar, handleProtectedError]);

  const refreshJournalReviewTasks = useCallback(async () => {
    if (!canAccessWorkbench) {
      return;
    }

    try {
      setJournalReviewTasks(await listJournalReviewTasks());
    } catch (error) {
      if (handleProtectedError(error)) {
        return;
      }
    }
  }, [canAccessWorkbench, handleProtectedError]);

  const hasActiveTasks = useMemo(() => tasks.some(hasActiveTaskStatus), [tasks]);
  const hasActiveScreenerTasks = useMemo(
    () => screenerTasks.some(hasActiveTaskStatus),
    [screenerTasks]
  );
  const hasActiveOpportunityTasks = useMemo(
    () => opportunityTasks.some(hasActiveTaskStatus),
    [opportunityTasks]
  );
  const hasActiveJournalReviewTasks = useMemo(
    () => journalReviewTasks.some(hasActiveTaskStatus),
    [journalReviewTasks]
  );

  useEffect(() => {
    if (canAccessWorkbench) {
      void refreshReports();
      return;
    }

    setReports([]);
    setLoadingReports(authStatus === "loading");
    setReportsError(null);
  }, [authStatus, canAccessWorkbench, refreshReports]);

  useEffect(() => {
    if (canAccessWorkbench) {
      void refreshScreenerRuns();
      return;
    }

    setScreenerRuns([]);
  }, [canAccessWorkbench, refreshScreenerRuns]);

  useEffect(() => {
    if (!canAccessWorkbench) {
      setTasks([]);
      return;
    }

    void refreshTasks();
    if (!hasActiveTasks) {
      return;
    }

    const intervalId = window.setInterval(() => {
      void refreshTasks();
    }, POLL_INTERVAL_MS);

    return () => {
      window.clearInterval(intervalId);
    };
  }, [canAccessWorkbench, hasActiveTasks, refreshTasks]);

  useEffect(() => {
    if (!canAccessWorkbench) {
      setScreenerTasks([]);
      return;
    }

    void refreshScreenerTasks();
    if (!hasActiveScreenerTasks) {
      return;
    }

    const intervalId = window.setInterval(() => {
      void refreshScreenerTasks();
    }, POLL_INTERVAL_MS);

    return () => {
      window.clearInterval(intervalId);
    };
  }, [canAccessWorkbench, hasActiveScreenerTasks, refreshScreenerTasks]);

  useEffect(() => {
    if (!canAccessOpportunityRadar) {
      setOpportunityTasks([]);
      return;
    }

    void refreshOpportunityTasks();
    if (!hasActiveOpportunityTasks) {
      return;
    }

    const intervalId = window.setInterval(() => {
      void refreshOpportunityTasks();
    }, POLL_INTERVAL_MS);

    return () => {
      window.clearInterval(intervalId);
    };
  }, [canAccessOpportunityRadar, hasActiveOpportunityTasks, refreshOpportunityTasks]);

  useEffect(() => {
    if (!canAccessWorkbench) {
      setJournalReviewTasks([]);
      return;
    }

    void refreshJournalReviewTasks();
    if (!hasActiveJournalReviewTasks) {
      return;
    }

    const intervalId = window.setInterval(() => {
      void refreshJournalReviewTasks();
    }, POLL_INTERVAL_MS);

    return () => {
      window.clearInterval(intervalId);
    };
  }, [canAccessWorkbench, hasActiveJournalReviewTasks, refreshJournalReviewTasks]);

  const sortedReports = useMemo(() => {
    return [...reports].sort(
      (left, right) => parseReportTimestamp(right) - parseReportTimestamp(left)
    );
  }, [reports]);

  const reportsByTicker = useMemo(() => {
    const grouped = sortedReports.reduce<Map<string, Report[]>>((acc, report) => {
      const existing = acc.get(report.ticker) ?? [];
      existing.push(report);
      acc.set(report.ticker, existing);
      return acc;
    }, new Map());

    return Array.from(grouped.entries()).map(([ticker, tickerReports]) => ({
      ticker,
      reports: tickerReports,
    }));
  }, [sortedReports]);

  const recentReports = useMemo(() => sortedReports.slice(0, 5), [sortedReports]);
  const recentTickers = useMemo(() => {
    const seen = new Set<string>();
    const tickers: string[] = [];

    for (const report of sortedReports) {
      if (seen.has(report.ticker)) {
        continue;
      }

      seen.add(report.ticker);
      tickers.push(report.ticker);

      if (tickers.length === 6) {
        break;
      }
    }

    return tickers;
  }, [sortedReports]);

  const activeTasks = useMemo(
    () => tasks.filter(hasActiveTaskStatus),
    [tasks]
  );
  const activeJournalReviewTasks = useMemo(
    () => journalReviewTasks.filter(hasActiveTaskStatus),
    [journalReviewTasks]
  );
  const activeOpportunityTasks = useMemo(
    () => opportunityTasks.filter(hasActiveTaskStatus),
    [opportunityTasks]
  );
  const activeScreenerTasks = useMemo(
    () => screenerTasks.filter(hasActiveTaskStatus),
    [screenerTasks]
  );

  const value = useMemo<WorkbenchContextValue>(
    () => ({
      activeJournalReviewTasks,
      activeOpportunityTasks,
      activeScreenerTasks,
      activeTasks,
      authEnabled,
      authError,
      authState,
      authStatus,
      canAccessWorkbench,
      canAccessOpportunityRadar,
      canManageUsers,
      loadingReports,
      logout,
      journalReviewTasks,
      opportunityTasks,
      newAnalysisDisabled: !canCreateAnalysis,
      newScreenerDisabled: !canCreateScreener,
      recentReports,
      recentTickers,
      refreshJournalReviewTasks,
      refreshOpportunityTasks,
      refreshReports,
      refreshScreenerRuns,
      refreshScreenerTasks,
      refreshSession,
      refreshTasks,
      reports,
      reportsByTicker,
      reportsError,
      screenerRuns,
      screenerTasks,
      tasks,
    }),
    [
      activeScreenerTasks,
      activeJournalReviewTasks,
      activeOpportunityTasks,
      activeTasks,
      authEnabled,
      authError,
      authState,
      authStatus,
      canAccessOpportunityRadar,
      canAccessWorkbench,
      canCreateAnalysis,
      canCreateScreener,
      canManageUsers,
      loadingReports,
      logout,
      journalReviewTasks,
      opportunityTasks,
      recentReports,
      recentTickers,
      refreshJournalReviewTasks,
      refreshOpportunityTasks,
      refreshReports,
      refreshScreenerRuns,
      refreshScreenerTasks,
      refreshSession,
      refreshTasks,
      reports,
      reportsByTicker,
      reportsError,
      screenerRuns,
      screenerTasks,
      tasks,
    ]
  );

  return <WorkbenchContext.Provider value={value}>{children}</WorkbenchContext.Provider>;
}

export function useWorkbench() {
  const context = useContext(WorkbenchContext);
  if (!context) {
    throw new Error("useWorkbench must be used within a WorkbenchProvider.");
  }
  return context;
}

function parseReportTimestamp(report: Report): number {
  if (report.date) {
    const isoLike = `${report.date}T${report.time ?? "00:00:00"}`;
    const parsed = Date.parse(isoLike);
    if (!Number.isNaN(parsed)) {
      return parsed;
    }
  }

  const fallback = Date.parse(report.id);
  if (!Number.isNaN(fallback)) {
    return fallback;
  }

  return Number.NEGATIVE_INFINITY;
}
