"use client";

import { useEffect, useState, type ReactNode } from "react";
import { usePreferences } from "@/components/PreferencesProvider";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import {
  executeTradePlan,
  type TradePlan,
  type TradePlanMutationResponse,
} from "@/lib/api";

interface TradePlanExecuteFormProps {
  isOpen: boolean;
  plan: TradePlan | null;
  onClose: () => void;
  onSaved: (result: TradePlanMutationResponse) => void;
}

export function TradePlanExecuteForm({
  isOpen,
  plan,
  onClose,
  onSaved,
}: TradePlanExecuteFormProps) {
  const { t } = usePreferences();
  const [entryTimestamp, setEntryTimestamp] = useState("");
  const [entryPrice, setEntryPrice] = useState("");
  const [size, setSize] = useState("");
  const [executionNote, setExecutionNote] = useState("");
  const [notes, setNotes] = useState("");
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!isOpen) {
      return;
    }
    setEntryTimestamp(toDateTimeLocalValue(new Date().toISOString()));
    setEntryPrice("");
    setSize("");
    setExecutionNote("");
    setNotes("");
    setSaving(false);
    setError(null);
  }, [isOpen, plan?.plan_id]);

  if (!isOpen || !plan) {
    return null;
  }

  const submitExecution = async () => {
    setSaving(true);
    setError(null);
    try {
      const result = await executeTradePlan(plan.plan_id, {
        entry_timestamp: normalizeRequiredTimestamp(
          entryTimestamp,
          t("tradeRecord.entryTime", "Entry time"),
          t
        ),
        entry_price: parseRequiredNumber(
          entryPrice,
          t("tradeRecord.entryPrice", "Entry price"),
          t
        ),
        size: parseRequiredNumber(size, t("tradeRecord.size", "Size"), t),
        execution_note: executionNote.trim(),
        notes: notes.trim(),
      });
      onSaved(result);
    } catch (submitError) {
      setError(
        submitError instanceof Error
          ? submitError.message
          : t("tradePlan.error.execute", "Unable to execute the trade plan")
      );
    } finally {
      setSaving(false);
    }
  };

  return (
    <Dialog open={isOpen} onOpenChange={(open) => !open && onClose()}>
      <DialogContent
        aria-label={t("tradePlan.executePlan", "Execute Trade Plan")}
        className="modal-panel scrollbar-hidden max-h-[92vh] max-w-3xl overflow-y-auto"
        onMouseDown={(event) => event.stopPropagation()}
      >
        <DialogHeader className="pr-12">
          <p className="text-[11px] font-semibold uppercase tracking-[0.34em] text-[var(--primary)]">
            {plan.display_symbol ?? plan.ticker}
          </p>
          <DialogTitle>{t("tradePlan.executePlan", "Execute Trade Plan")}</DialogTitle>
          <DialogDescription>
            {t(
              "tradePlan.executeDescription",
              "Record the actual entry facts. The saved plan will be snapshotted onto the new trade record."
            )}
          </DialogDescription>
        </DialogHeader>

        <div className="mt-8 grid gap-5">
          <section className="rounded-[28px] border border-border bg-card p-5">
            <p className="text-xs font-semibold uppercase tracking-[0.26em] text-muted-foreground">
              {t("tradePlan.entryCondition", "Entry Condition")}
            </p>
            <p className="mt-3 whitespace-pre-wrap text-sm leading-7 text-foreground">
              {plan.entry_condition}
            </p>
            <div className="mt-4 grid gap-3 md:grid-cols-2">
              <PlanFact
                label={t("tradePlan.positionPlan", "Position Plan")}
                value={plan.position_plan}
              />
              <PlanFact
                label={t("tradePlan.expiresAt", "Expires At")}
                value={formatDateTime(plan.expires_at)}
              />
            </div>
          </section>

          <section className="grid gap-4 md:grid-cols-3">
            <FieldShell label={t("tradeRecord.entryTime", "Entry Time")}>
              <Input
                type="datetime-local"
                value={entryTimestamp}
                onChange={(event) => setEntryTimestamp(event.target.value)}
                className="mt-3"
              />
            </FieldShell>
            <FieldShell label={t("tradeRecord.entryPrice", "Entry Price")}>
              <Input
                type="number"
                inputMode="decimal"
                value={entryPrice}
                onChange={(event) => setEntryPrice(event.target.value)}
                placeholder="420.00"
                className="mt-3"
              />
            </FieldShell>
            <FieldShell label={t("tradeRecord.size", "Size")}>
              <Input
                type="number"
                inputMode="decimal"
                value={size}
                onChange={(event) => setSize(event.target.value)}
                placeholder="10"
                className="mt-3"
              />
            </FieldShell>
          </section>

          <label className="field-shell block rounded-3xl border border-border bg-card p-4">
            <span className="text-xs font-semibold uppercase tracking-[0.24em] text-muted-foreground">
              {t("tradePlan.executionNote", "Execution Note")}
            </span>
            <Textarea
              value={executionNote}
              onChange={(event) => setExecutionNote(event.target.value)}
              rows={5}
              placeholder={t(
                "tradePlan.executionNotePlaceholder",
                "Optional: why execute now, and did the actual entry differ from the plan?"
              )}
              className="mt-3 min-h-[120px]"
            />
          </label>

          <label className="field-shell block rounded-3xl border border-border bg-card p-4">
            <span className="text-xs font-semibold uppercase tracking-[0.24em] text-muted-foreground">
              {t("tradePlan.tradeNotes", "Trade Notes")}
            </span>
            <Textarea
              value={notes}
              onChange={(event) => setNotes(event.target.value)}
              rows={4}
              placeholder={t(
                "tradePlan.tradeNotesPlaceholder",
                "Optional notes copied to the new trade record."
              )}
              className="mt-3 min-h-[100px]"
            />
          </label>

          {error ? (
            <div className="rounded-3xl border border-[var(--danger-border)] bg-[var(--danger-soft)] px-5 py-4 text-sm text-destructive">
              {error}
            </div>
          ) : null}

          <div className="flex flex-wrap items-center justify-end gap-3">
            <Button type="button" variant="secondary" onClick={onClose} disabled={saving}>
              {t("common.cancel", "Cancel")}
            </Button>
            <Button type="button" onClick={() => void submitExecution()} disabled={saving}>
              {saving
                ? t("tradeRecord.saving", "Saving...")
                : t("tradePlan.executePlan", "Execute Trade Plan")}
            </Button>
          </div>
        </div>
      </DialogContent>
    </Dialog>
  );
}

function FieldShell({
  label,
  children,
}: {
  label: string;
  children: ReactNode;
}) {
  return (
    <label className="field-shell block rounded-3xl border border-border bg-card p-4">
      <span className="text-xs font-semibold uppercase tracking-[0.24em] text-muted-foreground">
        {label}
      </span>
      {children}
    </label>
  );
}

function PlanFact({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-2xl border border-border bg-[var(--surface-strong)] px-3 py-3">
      <p className="text-[10px] font-semibold uppercase tracking-[0.22em] text-muted-foreground">
        {label}
      </p>
      <p className="mt-2 text-sm font-semibold text-foreground">{value}</p>
    </div>
  );
}

function normalizeRequiredTimestamp(
  value: string,
  fieldName: string,
  t: ReturnType<typeof usePreferences>["t"]
): string {
  const normalized = value.trim();
  if (!normalized) {
    throw new Error(
      t("common.required", ({ field }) => `${field} is required.`, {
        field: fieldName,
      })
    );
  }
  return toOffsetDateTimeString(parseDateTimeLocalValue(normalized, fieldName, t));
}

function parseRequiredNumber(
  value: string,
  fieldName: string,
  t: ReturnType<typeof usePreferences>["t"]
): number {
  const normalized = value.trim();
  if (!normalized) {
    throw new Error(
      t("common.required", ({ field }) => `${field} is required.`, {
        field: fieldName,
      })
    );
  }
  const parsed = Number(normalized);
  if (!Number.isFinite(parsed)) {
    throw new Error(
      t("common.mustBeNumeric", ({ field }) => `${field} must be numeric.`, {
        field: fieldName,
      })
    );
  }
  return parsed;
}

function toDateTimeLocalValue(value: string | null): string {
  if (!value) {
    return "";
  }
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) {
    return "";
  }
  const local = new Date(parsed.getTime() - parsed.getTimezoneOffset() * 60_000);
  return local.toISOString().slice(0, 16);
}

function parseDateTimeLocalValue(
  value: string,
  fieldName: string,
  t: ReturnType<typeof usePreferences>["t"]
): Date {
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) {
    throw new Error(
      t("common.invalidDateTime", ({ field }) => `${field} is invalid.`, {
        field: fieldName,
      })
    );
  }
  return parsed;
}

function toOffsetDateTimeString(value: Date): string {
  const offsetMinutes = -value.getTimezoneOffset();
  const sign = offsetMinutes >= 0 ? "+" : "-";
  const absoluteMinutes = Math.abs(offsetMinutes);
  const hours = String(Math.floor(absoluteMinutes / 60)).padStart(2, "0");
  const minutes = String(absoluteMinutes % 60).padStart(2, "0");
  const year = value.getFullYear();
  const month = String(value.getMonth() + 1).padStart(2, "0");
  const day = String(value.getDate()).padStart(2, "0");
  const hour = String(value.getHours()).padStart(2, "0");
  const minute = String(value.getMinutes()).padStart(2, "0");
  const second = String(value.getSeconds()).padStart(2, "0");
  return `${year}-${month}-${day}T${hour}:${minute}:${second}${sign}${hours}:${minutes}`;
}

function formatDateTime(value: string): string {
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) {
    return value;
  }
  return new Intl.DateTimeFormat(undefined, {
    dateStyle: "medium",
    timeStyle: "short",
  }).format(parsed);
}
