"use client";

import {
  Menu,
  Plus,
  Search,
} from "lucide-react";
import {
  createContext,
  startTransition,
  useContext,
  useEffect,
  useMemo,
  useState,
  type FormEvent,
  type ReactNode,
} from "react";
import { usePathname, useRouter, useSearchParams } from "next/navigation";
import { NewAnalysisForm } from "@/components/NewAnalysisForm";
import { NewScreenerForm } from "@/components/NewScreenerForm";
import { usePreferences } from "@/components/PreferencesProvider";
import { Sidebar } from "@/components/Sidebar";
import { useWorkbench } from "@/components/WorkbenchProvider";
import { WorkspaceAccountMenu } from "@/components/WorkspaceAccountMenu";
import { StatusPanel } from "@/components/workbench/StatusPanel";
import {
  buildLoginHref,
  buildHomeHref,
  buildScreenerTaskHref,
  buildTaskHref,
} from "@/lib/workbenchRoutes";

interface WorkbenchChromeContextValue {
  openAnalysisDialog: () => void;
  openScreenerDialog: () => void;
  setTopbarActions: (actions: ReactNode | null) => void;
}

interface WorkbenchPageChrome {
  title: string;
}

const WorkbenchChromeContext = createContext<WorkbenchChromeContextValue | null>(null);

export function WorkbenchShell({ children }: { children: ReactNode }) {
  const router = useRouter();
  const pathname = usePathname();
  const searchParams = useSearchParams();
  const { t } = usePreferences();
  const {
    authEnabled,
    authError,
    authState,
    authStatus,
    canManageUsers,
    newAnalysisDisabled,
    newScreenerDisabled,
    logout,
    refreshScreenerRuns,
    refreshScreenerTasks,
    refreshSession,
    refreshTasks,
  } = useWorkbench();
  const [isLoggingOut, setIsLoggingOut] = useState(false);
  const [isSidebarOpen, setIsSidebarOpen] = useState(false);
  const [activeDialog, setActiveDialog] = useState<"analysis" | "screener" | null>(
    null
  );
  const [topbarSearchQuery, setTopbarSearchQuery] = useState("");
  const [topbarActions, setTopbarActions] = useState<ReactNode | null>(null);
  const [defaultOutputLanguage, setDefaultOutputLanguage] = useState<string | null>(
    null
  );

  const nextPath = (() => {
    const query = searchParams.toString();
    return query ? `${pathname}?${query}` : pathname;
  })();
  const shouldRedirectToLogin =
    authStatus === "ready" && authEnabled && !authState?.authenticated;
  const chromeValue = useMemo<WorkbenchChromeContextValue>(
    () => ({
      openAnalysisDialog: () => {
        if (newAnalysisDisabled) {
          return;
        }
        setActiveDialog("analysis");
      },
      openScreenerDialog: () => {
        if (newScreenerDisabled) {
          return;
        }
        setActiveDialog("screener");
      },
      setTopbarActions,
    }),
    [newAnalysisDisabled, newScreenerDisabled]
  );
  const pageChrome = useMemo(
    () => getWorkbenchPageChrome(pathname, t),
    [pathname, t]
  );

  useEffect(() => {
    if (!shouldRedirectToLogin) {
      return;
    }

    startTransition(() => {
      router.replace(buildLoginHref(nextPath));
    });
  }, [nextPath, router, shouldRedirectToLogin]);

  useEffect(() => {
    const rawQuery = searchParams.get("q") ?? "";
    setTopbarSearchQuery(pathname === "/" ? rawQuery : "");
  }, [pathname, searchParams]);

  const handleTopbarSearch = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    const nextQuery = topbarSearchQuery.trim();

    startTransition(() => {
      router.push(buildHomeHref(nextQuery));
    });
  };
  const showTopbarSearch = pathname === "/";
  const resolvedTopbarActions =
    topbarActions ??
    (pathname === "/" ? (
      <button
        type="button"
        className="workbench-topbar-new"
        onClick={chromeValue.openAnalysisDialog}
        disabled={newAnalysisDisabled}
      >
        <Plus className="size-4" aria-hidden />
        <span>{t("home.launchAnalysis", "New Analysis")}</span>
      </button>
    ) : null);

  const handleLogout = async () => {
    setIsLoggingOut(true);

    try {
      await logout();
      startTransition(() => {
        router.replace(buildLoginHref("/"));
      });
    } finally {
      setIsLoggingOut(false);
    }
  };

  if (authStatus === "loading") {
    return (
      <StatusPanel
        eyebrow={t("workbench.sessionBootstrap", "Session Bootstrap")}
        title={t("workbench.preparingTitle", "Preparing the workbench")}
        body={t(
          "workbench.preparingBody",
          "Checking your session."
        )}
      />
    );
  }

  if (authStatus === "error") {
    return (
      <StatusPanel
        eyebrow={t("workbench.unavailable", "Workbench Unavailable")}
        title={t("workbench.authBoundaryTitle", "We could not reach the auth boundary")}
        body={
          authError ??
          t(
            "workbench.authBoundaryBody",
            "We couldn't verify your session."
          )
        }
        action={
          <button
            type="button"
            className="interactive-button focus-ring rounded-full border border-[var(--primary)] bg-[var(--primary)] px-5 py-3 text-xs font-semibold uppercase tracking-[0.22em] text-white"
            onClick={() => void refreshSession()}
          >
            {t("workbench.retrySession", "Retry Session Bootstrap")}
          </button>
        }
      />
    );
  }

  if (shouldRedirectToLogin) {
    return (
      <StatusPanel
        eyebrow={t("workbench.loginRequired", "Login Required")}
        title={t("workbench.loginRequiredTitle", "Redirecting to sign in")}
        body={t(
          "workbench.loginRequiredBody",
          "Sign in to continue."
        )}
      />
    );
  }

  return (
    <WorkbenchChromeContext.Provider value={chromeValue}>
      <div className="app-shell relative min-h-dvh overflow-x-hidden bg-transparent md:flex md:items-stretch">
        <div
          className="min-h-dvh min-w-0 flex-1 overflow-x-hidden"
          inert={activeDialog !== null ? true : undefined}
          aria-hidden={activeDialog !== null}
        >
          <div className="flex min-h-dvh min-w-0 max-w-full md:items-stretch">
            <Sidebar
              isOpen={isSidebarOpen}
              onClose={() => setIsSidebarOpen(false)}
            />

            <div className="flex min-w-0 max-w-full flex-1 flex-col overflow-x-hidden">
              <header className="workbench-topbar">
                <div className="flex min-w-0 items-center gap-3">
                  <button
                    type="button"
                    className="workbench-topbar-menu md:hidden"
                    aria-label={t("common.menu", "Menu")}
                    onClick={() => setIsSidebarOpen(true)}
                  >
                    <Menu className="size-4" aria-hidden />
                  </button>
                  <div className="min-w-0">
                    <h1 className="workbench-topbar-title">{pageChrome.title}</h1>
                  </div>
                </div>
                {showTopbarSearch ? (
                  <form
                    className="workbench-topbar-search"
                    role="search"
                    onSubmit={handleTopbarSearch}
                  >
                    <Search className="size-4" aria-hidden />
                    <input
                      type="search"
                      value={topbarSearchQuery}
                      onChange={(event) => setTopbarSearchQuery(event.target.value)}
                      placeholder={t("home.searchPlaceholderShort", "Ticker or report id")}
                      aria-label={t("home.searchLabel", "Search reports")}
                    />
                    <kbd aria-hidden="true">/</kbd>
                  </form>
                ) : null}
                {resolvedTopbarActions ? (
                  <div className="workbench-topbar-actions">{resolvedTopbarActions}</div>
                ) : null}
                <WorkspaceAccountMenu
                  authEnabled={authEnabled}
                  authUser={authState?.user ?? null}
                  canManageUsers={canManageUsers}
                  loggingOut={isLoggingOut}
                  onLogout={handleLogout}
                  selectedOutputLanguage={defaultOutputLanguage}
                  onOutputLanguageChange={(value) => setDefaultOutputLanguage(value)}
                />
              </header>
              {children}
            </div>
          </div>
        </div>

        <NewAnalysisForm
          isOpen={activeDialog === "analysis"}
          onClose={() => setActiveDialog(null)}
          defaultOutputLanguage={defaultOutputLanguage}
          onTaskCreated={(taskId) => {
            setActiveDialog(null);
            void refreshTasks();
            startTransition(() => {
              router.push(buildTaskHref(taskId));
            });
          }}
        />

        <NewScreenerForm
          isOpen={activeDialog === "screener"}
          onClose={() => setActiveDialog(null)}
          onTaskCreated={(taskId) => {
            setActiveDialog(null);
            startTransition(() => {
              router.push(buildScreenerTaskHref(taskId));
            });
            void refreshScreenerTasks();
            void refreshScreenerRuns();
          }}
        />
      </div>
    </WorkbenchChromeContext.Provider>
  );
}

function getWorkbenchPageChrome(
  pathname: string,
  t: ReturnType<typeof usePreferences>["t"]
): WorkbenchPageChrome {
  if (pathname.startsWith("/screeners")) {
    return {
      title: t("screenerDashboard.title", "Candidate Workspace"),
    };
  }

  if (pathname.startsWith("/assets")) {
    return {
      title: t("assets.title", "Portfolio ledger"),
    };
  }

  if (pathname.startsWith("/journal")) {
    return {
      title: t("journal.shortTitle", "Trade Journal"),
    };
  }

  if (pathname.startsWith("/activity")) {
    return {
      title: t("activity.title", "Background work"),
    };
  }

  if (pathname.startsWith("/reports")) {
    return {
      title: t("workbench.reportViewer", "Research Report"),
    };
  }

  if (pathname.startsWith("/tasks") || pathname.startsWith("/screener-tasks")) {
    return {
      title: t("workbench.taskProgress", "Task Progress"),
    };
  }

  return {
    title: t("home.analysisWorkspace", "Analysis workspace"),
  };
}

export function useWorkbenchChrome() {
  const context = useContext(WorkbenchChromeContext);
  if (!context) {
    throw new Error("useWorkbenchChrome must be used within WorkbenchShell.");
  }
  return context;
}
