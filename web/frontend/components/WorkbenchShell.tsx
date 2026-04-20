"use client";

import {
  createContext,
  startTransition,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from "react";
import { usePathname, useRouter, useSearchParams } from "next/navigation";
import { NewAnalysisForm } from "@/components/NewAnalysisForm";
import { NewScreenerForm } from "@/components/NewScreenerForm";
import { Sidebar } from "@/components/Sidebar";
import { useWorkbench } from "@/components/WorkbenchProvider";
import { WorkspaceAccountMenu } from "@/components/WorkspaceAccountMenu";
import {
  buildLoginHref,
  buildScreenerTaskHref,
  buildTaskHref,
} from "@/lib/workbenchRoutes";

interface WorkbenchChromeContextValue {
  openAnalysisDialog: () => void;
  openScreenerDialog: () => void;
}

const WorkbenchChromeContext = createContext<WorkbenchChromeContextValue | null>(null);

export function WorkbenchShell({ children }: { children: ReactNode }) {
  const router = useRouter();
  const pathname = usePathname();
  const searchParams = useSearchParams();
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
    }),
    [newAnalysisDisabled, newScreenerDisabled]
  );

  useEffect(() => {
    if (!shouldRedirectToLogin) {
      return;
    }

    startTransition(() => {
      router.replace(buildLoginHref(nextPath));
    });
  }, [nextPath, router, shouldRedirectToLogin]);

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
        eyebrow="Session Bootstrap"
        title="Preparing the workbench"
        body="TradingAgents is checking the current session before loading reports, tasks, and screeners."
      />
    );
  }

  if (authStatus === "error") {
    return (
      <StatusPanel
        eyebrow="Workbench Unavailable"
        title="We could not reach the auth boundary"
        body={
          authError ??
          "The frontend could not read /api/auth/me, so protected workbench navigation is paused."
        }
        actionLabel="Retry Session Bootstrap"
        onAction={() => void refreshSession()}
      />
    );
  }

  if (shouldRedirectToLogin) {
    return (
      <StatusPanel
        eyebrow="Login Required"
        title="Redirecting to sign in"
        body="This workbench is protected in the current environment, so TradingAgents is routing this session through the login page."
      />
    );
  }

  return (
    <WorkbenchChromeContext.Provider value={chromeValue}>
      <div className="app-shell relative min-h-screen bg-[var(--bg)] md:flex md:items-stretch">
        <div
          className="min-h-screen flex-1"
          inert={activeDialog !== null ? true : undefined}
          aria-hidden={activeDialog !== null}
        >
          <WorkspaceAccountMenu
            authEnabled={authEnabled}
            authUser={authState?.user ?? null}
            canManageUsers={canManageUsers}
            loggingOut={isLoggingOut}
            onLogout={handleLogout}
            onOpenSidebar={() => setIsSidebarOpen(true)}
            selectedOutputLanguage={defaultOutputLanguage}
            onOutputLanguageChange={(value) => setDefaultOutputLanguage(value)}
          />

          <div className="flex min-h-screen md:items-stretch">
            <Sidebar
              isOpen={isSidebarOpen}
              onClose={() => setIsSidebarOpen(false)}
              onNewAnalysis={() => {
                chromeValue.openAnalysisDialog();
                setIsSidebarOpen(false);
              }}
              onNewScreener={() => {
                chromeValue.openScreenerDialog();
                setIsSidebarOpen(false);
              }}
            />

            <div className="flex min-w-0 flex-1 flex-col">
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
            void refreshScreenerRuns();
            void refreshScreenerTasks();
            startTransition(() => {
              router.push(buildScreenerTaskHref(taskId));
            });
          }}
        />
      </div>
    </WorkbenchChromeContext.Provider>
  );
}

export function useWorkbenchChrome() {
  const context = useContext(WorkbenchChromeContext);
  if (!context) {
    throw new Error("useWorkbenchChrome must be used within WorkbenchShell.");
  }
  return context;
}

function StatusPanel({
  eyebrow,
  title,
  body,
  actionLabel,
  onAction,
}: {
  eyebrow: string;
  title: string;
  body: string;
  actionLabel?: string;
  onAction?: () => void;
}) {
  return (
    <main className="flex min-h-screen items-center justify-center px-6 py-10">
      <div className="card-surface w-full max-w-xl rounded-[32px] px-8 py-10 text-center">
        <p className="text-[12px] font-semibold uppercase tracking-[0.36em] text-[var(--primary)]">
          {eyebrow}
        </p>
        <h1 className="font-heading mt-4 text-3xl font-bold tracking-tight text-slate-900">
          {title}
        </h1>
        <p className="mt-3 text-sm leading-6 text-slate-600">{body}</p>
        {actionLabel && onAction ? (
          <button
            type="button"
            className="interactive-button focus-ring mt-6 rounded-full border border-[var(--primary)] bg-[var(--primary)] px-5 py-3 text-xs font-semibold uppercase tracking-[0.22em] text-white"
            onClick={onAction}
          >
            {actionLabel}
          </button>
        ) : null}
      </div>
    </main>
  );
}
