"use client";

import Link from "next/link";
import { startTransition, useEffect, useMemo, useState, type FormEvent } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { useAuth } from "@/components/AuthProvider";
import { DivergeMark } from "@/components/BrandMark";
import { usePreferences } from "@/components/PreferencesProvider";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";

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
      <main className="login-shell login-shell--center px-6 py-10">
        <div className="login-status-card w-full max-w-lg text-center">
          <div className="flex flex-col gap-2 px-6 py-7">
            <p className="login-kicker">
              {t("auth.sessionBootstrap", "Session Bootstrap")}
            </p>
            <div className="login-status-title">
              {t("auth.preparingSignIn", "Preparing secure sign-in")}
            </div>
            <div className="login-status-description">
              {t("auth.checkingSession", "Checking for an existing session.")}
            </div>
          </div>
        </div>
      </main>
    );
  }

  if (authStatus === "error") {
    return (
      <main className="login-shell login-shell--center px-6 py-10">
        <div className="login-status-card w-full max-w-lg text-center">
          <div className="flex flex-col gap-2 px-6 pt-7">
            <p className="login-kicker login-kicker--danger">
              {t("auth.unavailable", "Auth Unavailable")}
            </p>
            <div className="login-status-title">
              {t("auth.unavailableTitle", "Unable to reach the auth service")}
            </div>
            <div className="login-status-description">
              {authError ?? t("auth.verifyFallback", "We couldn't verify your session.")}
            </div>
          </div>
          <div className="flex justify-center px-6 pb-7 pt-5">
            <Button
              type="button"
              variant="secondary"
              className="login-submit"
              onClick={() => void refreshSession()}
            >
              {t("auth.retryBootstrap", "Retry Auth Bootstrap")}
            </Button>
          </div>
        </div>
      </main>
    );
  }

  if (shouldSkipLogin) {
    return (
      <main className="login-shell login-shell--center px-6 py-10">
        <div className="login-status-card w-full max-w-lg text-center">
          <div className="flex flex-col gap-2 px-6 py-7">
            <p className="login-kicker">
              {t("auth.sessionReady", "Session Ready")}
            </p>
            <div className="login-status-title">
              {t("auth.redirectingWorkbench", "Redirecting back to the workbench")}
            </div>
            <div className="login-status-description">
              {t("auth.returningDestination", "Returning to your destination.")}
            </div>
          </div>
        </div>
      </main>
    );
  }

  return (
    <main className="login-shell px-4 py-8 md:px-8">
      <div className="login-card grid w-full max-w-6xl overflow-hidden md:grid-cols-[1.08fr_0.92fr]">
        <section className="login-brand-panel relative overflow-hidden px-6 py-8 md:px-10 md:py-12">
          <div className="relative flex min-h-full items-center justify-center">
            <div className="mx-auto flex w-full max-w-md flex-col items-center text-center">
              <DivergeMark className="login-brand-mark h-44 w-44 md:h-60 md:w-60" />
              <h1 className="login-brand-title font-heading mt-8 text-5xl font-semibold md:text-7xl">
                Diverge
              </h1>
            </div>
          </div>
        </section>

        <section className="login-form-panel px-6 py-8 md:px-10 md:py-12">
          <div className="mx-auto w-full max-w-md">
            <p className="login-kicker">
              {t("auth.login", "Login")}
            </p>
            <h2 className="login-form-title font-heading mt-3 text-3xl font-bold">
              {t("auth.workspaceCredentials", "Workspace credentials")}
            </h2>

            <form className="mt-8 space-y-4" onSubmit={handleSubmit}>
              <label className="block">
                <span className="login-label">
                  {t("auth.email", "Email")}
                </span>
                <Input
                  type="email"
                  autoComplete="email"
                  required
                  value={email}
                  onChange={(event) => setEmail(event.target.value)}
                  className="login-input mt-2"
                  placeholder="analyst@diverge.local"
                />
              </label>

              <label className="block">
                <span className="login-label">
                  {t("auth.password", "Password")}
                </span>
                <Input
                  type="password"
                  autoComplete="current-password"
                  required
                  value={password}
                  onChange={(event) => setPassword(event.target.value)}
                  className="login-input mt-2"
                  placeholder={t("auth.passwordPlaceholder", "Enter your password")}
                />
              </label>

              {formError ? (
                <div
                  className="rounded-[22px] border px-4 py-3 text-sm text-[var(--danger)]"
                  style={{
                    borderColor: "color-mix(in srgb, var(--login-danger) 36%, transparent)",
                    backgroundColor:
                      "color-mix(in srgb, var(--login-danger) 14%, transparent)",
                  }}
                >
                  {formError}
                </div>
              ) : null}

              <Button
                type="submit"
                variant="secondary"
                disabled={isSubmitting}
                className="login-submit w-full"
              >
                {isSubmitting
                  ? t("auth.signingIn", "Signing In")
                  : t("auth.signIn", "Sign In")}
              </Button>
            </form>

            <div className="login-help-card mt-6 px-4 py-4 text-sm">
              {t("auth.accessHelp", "Need access help? Ask your workspace admin.")}
            </div>

            <div className="mt-4 flex justify-end text-sm">
              <Button asChild variant="ghost" size="sm" className="login-back-link h-auto px-0 py-0">
                <Link href="/">{t("auth.backToWorkbench", "Back to workbench")}</Link>
              </Button>
            </div>
          </div>
        </section>
      </div>
    </main>
  );
}
