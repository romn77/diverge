"use client";

import Link from "next/link";
import { startTransition, useEffect, useMemo, useState, type FormEvent } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { useAuth } from "@/components/AuthProvider";
import { DivergeMark } from "@/components/BrandMark";
import { usePreferences } from "@/components/PreferencesProvider";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
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
      <main className="flex min-h-screen items-center justify-center px-6 py-10">
        <Card className="card-surface w-full max-w-lg text-center">
          <CardHeader>
            <p className="text-[12px] font-semibold uppercase tracking-[0.36em] text-[var(--primary)]">
              Session Bootstrap
            </p>
            <CardTitle>Preparing secure sign-in</CardTitle>
            <CardDescription>
              Checking for an existing session.
            </CardDescription>
          </CardHeader>
        </Card>
      </main>
    );
  }

  if (authStatus === "error") {
    return (
      <main className="flex min-h-screen items-center justify-center px-6 py-10">
        <Card className="card-surface w-full max-w-lg text-center">
          <CardHeader>
            <p className="text-[12px] font-semibold uppercase tracking-[0.36em] text-[var(--danger)]">
              Auth Unavailable
            </p>
            <CardTitle>Unable to reach the auth service</CardTitle>
            <CardDescription>
              {authError ?? "We couldn't verify your session."}
            </CardDescription>
          </CardHeader>
          <CardContent className="flex justify-center pt-0">
            <Button type="button" onClick={() => void refreshSession()}>
              Retry Auth Bootstrap
            </Button>
          </CardContent>
        </Card>
      </main>
    );
  }

  if (shouldSkipLogin) {
    return (
      <main className="flex min-h-screen items-center justify-center px-6 py-10">
        <Card className="card-surface w-full max-w-lg text-center">
          <CardHeader>
            <p className="text-[12px] font-semibold uppercase tracking-[0.36em] text-[var(--primary)]">
              Session Ready
            </p>
            <CardTitle>Redirecting back to the workbench</CardTitle>
            <CardDescription>
              Returning to your destination.
            </CardDescription>
          </CardHeader>
        </Card>
      </main>
    );
  }

  return (
    <main className="flex min-h-screen items-center justify-center px-4 py-8 text-foreground md:px-8">
      <div className="card-surface grid w-full max-w-6xl overflow-hidden rounded-[34px] backdrop-blur-sm md:grid-cols-[1.1fr_0.9fr]">
        <section className="diverge-login-panel relative overflow-hidden border-b border-border px-6 py-8 md:border-b-0 md:border-r md:px-10 md:py-12">
          <div className="relative flex min-h-full items-center justify-center">
            <div className="mx-auto flex w-full max-w-md flex-col items-center text-center">
              <DivergeMark className="h-44 w-44 text-[var(--primary)] md:h-60 md:w-60" />
              <h1 className="font-heading mt-8 text-5xl font-semibold text-foreground md:text-7xl">
                Diverge
              </h1>
            </div>
          </div>
        </section>

        <section className="px-6 py-8 md:px-10 md:py-12">
          <div className="mx-auto w-full max-w-md">
            <p className="text-[12px] font-semibold uppercase tracking-[0.34em] text-muted-foreground">
              Login
            </p>
            <h2 className="font-heading mt-3 text-3xl font-bold tracking-tight text-foreground">
              Workspace credentials
            </h2>
            <p className="mt-3 text-sm leading-6 text-muted-foreground">
              Sign in to continue to your requested page.
            </p>

            <form className="mt-8 space-y-4" onSubmit={handleSubmit}>
              <label className="block">
                <span className="text-[10px] font-semibold uppercase tracking-[0.26em] text-muted-foreground">
                  Email
                </span>
                <Input
                  type="email"
                  autoComplete="email"
                  required
                  value={email}
                  onChange={(event) => setEmail(event.target.value)}
                  className="mt-2"
                  placeholder="analyst@diverge.local"
                />
              </label>

              <label className="block">
                <span className="text-[10px] font-semibold uppercase tracking-[0.26em] text-muted-foreground">
                  Password
                </span>
                <Input
                  type="password"
                  autoComplete="current-password"
                  required
                  value={password}
                  onChange={(event) => setPassword(event.target.value)}
                  className="mt-2"
                  placeholder="Enter your password"
                />
              </label>

              {formError ? (
                <div
                  className="rounded-[22px] border px-4 py-3 text-sm text-[var(--danger)]"
                  style={{
                    borderColor: "color-mix(in srgb, var(--danger) 20%, transparent)",
                    backgroundColor:
                      "color-mix(in srgb, var(--danger) 10%, transparent)",
                  }}
                >
                  {formError}
                </div>
              ) : null}

              <Button type="submit" disabled={isSubmitting} className="w-full">
                {isSubmitting ? "Signing In" : "Sign In"}
              </Button>
            </form>

            <div className="card-surface mt-6 rounded-[24px] border-dashed px-4 py-4 text-sm text-muted-foreground">
              Need access help? Ask your workspace admin.
            </div>

            <div className="mt-4 flex justify-end text-sm text-muted-foreground">
              <Button asChild variant="ghost" size="sm" className="h-auto px-0 py-0 text-[var(--primary)]">
                <Link href="/">Back to workbench</Link>
              </Button>
            </div>
          </div>
        </section>
      </div>
    </main>
  );
}
