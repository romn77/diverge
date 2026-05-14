import type { ReactNode } from "react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";

type StatusPanelTone = "primary" | "danger" | "muted";

interface StatusPanelProps {
  eyebrow: string;
  title: string;
  body: ReactNode;
  action?: ReactNode;
  tone?: StatusPanelTone;
}

const toneClass: Record<StatusPanelTone, string> = {
  primary: "text-[var(--primary)]",
  danger: "text-[var(--danger)]",
  muted: "text-muted-foreground",
};

export function StatusPanel({
  eyebrow,
  title,
  body,
  action,
  tone = "primary",
}: StatusPanelProps) {
  return (
    <main className="flex min-h-dvh items-center justify-center px-6 py-10">
      <Card className="w-full max-w-xl text-center">
        <CardHeader>
          <p
            className={`text-[12px] font-semibold uppercase tracking-[0.36em] ${toneClass[tone]}`}
          >
            {eyebrow}
          </p>
          <CardTitle>{title}</CardTitle>
          <p className="mt-3 text-sm leading-6 text-muted-foreground">{body}</p>
        </CardHeader>
        {action ? (
          <CardContent className="flex justify-center pt-0">{action}</CardContent>
        ) : null}
      </Card>
    </main>
  );
}
