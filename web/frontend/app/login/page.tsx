"use client";

import Link from "next/link";
import { startTransition, useEffect, useMemo, useState, type FormEvent } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { useAuth } from "@/components/AuthProvider";
import { usePreferences } from "@/components/PreferencesProvider";

function resolveNextPath(value: string | null): string {
  if (!value || !value.startsWith("/") || value.startsWith("//")) {
    return "/";
  }
  return value;
}

export default function LoginPage() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const { t } = usePreferences();
  const { authError, authState, authStatus, login, refreshSession } = useAuth();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [formError, setFormError] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);

  const nextPath = useMemo(
    () => resolveNextPath(searchParams.get("next")),
    [searchParams]
  );
  const shouldSkipLogin =
    authStatus === "ready" && (!authState?.enabled || authState.authenticated);

  useEffect(() => {
    if (!shouldSkipLogin) {
      return;
    }

    startTransition(() => {
      router.replace(nextPath);
    });
  }, [nextPath, router, shouldSkipLogin]);

  const handleSubmit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    setFormError(null);
    setIsSubmitting(true);

    try {
      await login({
        email,
        password,
      });
      startTransition(() => {
        router.replace(nextPath);
      });
    } catch (error) {
      setFormError(
        error instanceof Error
          ? error.message
          : t("auth.loginError", "Unable to sign in right now")
      );
    } finally {
      setIsSubmitting(false);
    }
  };

  if (authStatus === "loading") {
    return (
      <main className="flex min-h-screen items-center justify-center px-6 py-10">
        <div className="card-surface w-full max-w-lg rounded-[32px] px-8 py-10 text-center">
          <p className="text-[12px] font-semibold uppercase tracking-[0.36em] text-[var(--primary)]">
            Session Bootstrap
          </p>
          <h1 className="font-heading mt-4 text-3xl font-bold tracking-tight text-slate-900">
            Preparing secure sign-in
          </h1>
          <p className="mt-3 text-sm leading-6 text-slate-600">
            TradingAgents is checking whether a valid session cookie already exists.
          </p>
        </div>
      </main>
    );
  }

  if (authStatus === "error") {
    return (
      <main className="flex min-h-screen items-center justify-center px-6 py-10">
        <div className="card-surface w-full max-w-lg rounded-[32px] px-8 py-10 text-center">
          <p className="text-[12px] font-semibold uppercase tracking-[0.36em] text-[var(--danger)]">
            Auth Unavailable
          </p>
          <h1 className="font-heading mt-4 text-3xl font-bold tracking-tight text-slate-900">
            Unable to reach the auth service
          </h1>
          <p className="mt-3 text-sm leading-6 text-slate-600">
            {authError ??
              "The login page could not read /api/auth/me, so sign-in is temporarily paused."}
          </p>
          <button
            type="button"
            className="interactive-button focus-ring mt-6 rounded-full border border-[var(--primary)] bg-[var(--primary)] px-5 py-3 text-xs font-semibold uppercase tracking-[0.22em] text-white"
            onClick={() => void refreshSession()}
          >
            Retry Auth Bootstrap
          </button>
        </div>
      </main>
    );
  }

  if (shouldSkipLogin) {
    return (
      <main className="flex min-h-screen items-center justify-center px-6 py-10">
        <div className="card-surface w-full max-w-lg rounded-[32px] px-8 py-10 text-center">
          <p className="text-[12px] font-semibold uppercase tracking-[0.36em] text-[var(--primary)]">
            Session Ready
          </p>
          <h1 className="font-heading mt-4 text-3xl font-bold tracking-tight text-slate-900">
            Redirecting back to the workbench
          </h1>
          <p className="mt-3 text-sm leading-6 text-slate-600">
            A valid session is already present, so TradingAgents is returning to the
            requested destination.
          </p>
        </div>
      </main>
    );
  }

  return (
    <main className="flex min-h-screen items-center justify-center px-4 py-8 md:px-8">
      <div className="grid w-full max-w-6xl overflow-hidden rounded-[34px] border border-[var(--border)] bg-[rgba(255,252,246,0.92)] shadow-[0_28px_70px_rgba(18,28,41,0.12)] md:grid-cols-[1.1fr_0.9fr]">
        <section className="relative overflow-hidden border-b border-[var(--border)] px-6 py-8 md:border-b-0 md:border-r md:px-10 md:py-12">
          <div className="absolute inset-x-0 top-0 h-40 bg-[radial-gradient(circle_at_top_left,rgba(182,90,43,0.22),transparent_62%)]" />
          <div className="relative">
            <p className="text-[12px] font-semibold uppercase tracking-[0.4em] text-[var(--primary)]">
              TradingAgents
            </p>
            <h1 className="font-heading mt-4 max-w-xl text-4xl font-bold tracking-tight text-slate-900 md:text-5xl">
              Return to the research workbench
            </h1>
            <p className="mt-4 max-w-xl text-sm leading-7 text-slate-600">
              Use your workspace account to reopen saved reports, watch active
              research tasks, review screener pools, and continue the trade journal
              without losing context.
            </p>

            <div className="mt-8 grid gap-4 sm:grid-cols-2">
              <div className="rounded-[24px] border border-[var(--border)] bg-white/82 p-4">
                <p className="text-[10px] font-semibold uppercase tracking-[0.28em] text-slate-500">
                  After Sign In
                </p>
                <p className="mt-3 text-sm font-semibold text-slate-900">
                  Jump straight back into reports, live queues, screener results, and
                  the trade journal.
                </p>
              </div>
              <div className="rounded-[24px] border border-[var(--border)] bg-white/82 p-4">
                <p className="text-[10px] font-semibold uppercase tracking-[0.28em] text-slate-500">
                  Workspace Support
                </p>
                <p className="mt-3 text-sm font-semibold text-slate-900">
                  If you need a new account or a reset, your workspace admin can help
                  from the access console.
                </p>
              </div>
            </div>

            <div className="mt-8 rounded-[28px] border border-[var(--border)] bg-[var(--surface-strong)] p-5">
              <p className="text-[10px] font-semibold uppercase tracking-[0.28em] text-slate-500">
                Next Destination
              </p>
              <p className="mt-3 text-sm font-semibold text-slate-900">{nextPath}</p>
              <p className="mt-2 text-sm leading-6 text-slate-600">
                TradingAgents preserves the requested route so successful sign-in lands
                back where the session was blocked.
              </p>
            </div>
          </div>
        </section>

        <section className="px-6 py-8 md:px-10 md:py-12">
          <div className="mx-auto w-full max-w-md">
            <p className="text-[12px] font-semibold uppercase tracking-[0.34em] text-slate-500">
              Login
            </p>
            <h2 className="font-heading mt-3 text-3xl font-bold tracking-tight text-slate-900">
              Workspace credentials
            </h2>
            <p className="mt-3 text-sm leading-6 text-slate-600">
              Sign in with the email and password assigned to you so TradingAgents can
              reopen the destination you were trying to reach.
            </p>

            <form className="mt-8 space-y-4" onSubmit={handleSubmit}>
              <label className="block">
                <span className="text-[10px] font-semibold uppercase tracking-[0.26em] text-slate-500">
                  Email
                </span>
                <input
                  type="email"
                  autoComplete="email"
                  required
                  value={email}
                  onChange={(event) => setEmail(event.target.value)}
                  className="focus-ring mt-2 w-full rounded-[22px] border border-[var(--border-strong)] bg-white px-4 py-3 text-sm font-medium text-slate-900"
                  placeholder="analyst@tradingagents.local"
                />
              </label>

              <label className="block">
                <span className="text-[10px] font-semibold uppercase tracking-[0.26em] text-slate-500">
                  Password
                </span>
                <input
                  type="password"
                  autoComplete="current-password"
                  required
                  value={password}
                  onChange={(event) => setPassword(event.target.value)}
                  className="focus-ring mt-2 w-full rounded-[22px] border border-[var(--border-strong)] bg-white px-4 py-3 text-sm font-medium text-slate-900"
                  placeholder="Enter your password"
                />
              </label>

              {formError ? (
                <div className="rounded-[22px] border border-[rgba(163,53,53,0.2)] bg-[rgba(163,53,53,0.08)] px-4 py-3 text-sm text-[var(--danger)]">
                  {formError}
                </div>
              ) : null}

              <button
                type="submit"
                disabled={isSubmitting}
                className="interactive-button focus-ring w-full rounded-full border border-[var(--primary)] bg-[var(--primary)] px-5 py-3 text-xs font-semibold uppercase tracking-[0.24em] text-white disabled:cursor-not-allowed disabled:opacity-70"
              >
                {isSubmitting ? "Signing In" : "Sign In"}
              </button>
            </form>

            <div className="mt-6 rounded-[24px] border border-dashed border-[var(--border)] bg-[var(--surface-strong)] px-4 py-4 text-sm text-slate-600">
              Need a reset or a new account? Contact your workspace admin. They can
              manage access after signing in through{" "}
              <code className="rounded bg-white px-1.5 py-0.5 text-[12px] font-semibold text-slate-800">
                /admin/users
              </code>
              .
            </div>

            <div className="mt-4 flex items-center justify-between text-sm text-slate-500">
              <span>Protected by backend session cookies.</span>
              <Link href="/" className="font-semibold text-[var(--primary)]">
                Back to workbench
              </Link>
            </div>
          </div>
        </section>
      </div>
    </main>
  );
}
