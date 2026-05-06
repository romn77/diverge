"use client";

import { useEffect, useState } from "react";
import { usePreferences } from "@/components/PreferencesProvider";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Textarea } from "@/components/ui/textarea";
import { updateTrade, type TradeRecord } from "@/lib/api";

interface CloseTradeFormProps {
  isOpen: boolean;
  record: TradeRecord | null;
  onClose: () => void;
  onSaved: (record: TradeRecord) => void;
}

const PLAN_EXECUTIONS = [
  "followed_plan",
  "partially_followed",
  "deviated_with_reason",
  "deviated_emotionally",
];

export function CloseTradeForm({
  isOpen,
  record,
  onClose,
  onSaved,
}: CloseTradeFormProps) {
  const { t } = usePreferences();
  const [exitTimestamp, setExitTimestamp] = useState("");
  const [exitPrice, setExitPrice] = useState("");
  const [exitReason, setExitReason] = useState("");
  const [planExecution, setPlanExecution] = useState("followed_plan");
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!isOpen) {
      return;
    }
    setExitTimestamp(toDateTimeLocalValue(record?.exit_timestamp ?? null));
    setExitPrice(toInputNumber(record?.exit_price ?? null));
    setExitReason(record?.exit_reason ?? "");
    setPlanExecution(
      record?.plan_execution && !["unknown", "not_applicable"].includes(record.plan_execution)
        ? record.plan_execution
        : "followed_plan"
    );
    setSaving(false);
    setError(null);
  }, [isOpen, record]);

  if (!isOpen || !record) {
    return null;
  }

  const submitClose = async () => {
    setSaving(true);
    setError(null);
    try {
      const normalizedExitTimestamp = normalizeRequiredTimestamp(
        exitTimestamp,
        t("tradeRecord.exitTime", "Exit time"),
        record.exit_timestamp
      );
      const normalizedExitPrice = parseRequiredNumber(
        exitPrice,
        t("tradeRecord.exitPrice", "Exit price")
      );
      const normalizedExitReason = requireText(
        exitReason,
        t("tradeRecord.exitReason", "Exit reason")
      );
      const saved = await updateTrade(record.trade_id, {
        exit_timestamp: normalizedExitTimestamp,
        exit_price: normalizedExitPrice,
        exit_reason: normalizedExitReason,
        plan_execution: planExecution,
      });
      onSaved(saved);
    } catch (submitError) {
      setError(
        submitError instanceof Error
          ? submitError.message
          : t("tradeRecord.error.save", "Unable to save the trade record")
      );
    } finally {
      setSaving(false);
    }
  };

  return (
    <Dialog open={isOpen} onOpenChange={(open) => !open && onClose()}>
      <DialogContent
        aria-label={t("journal.closeTrade", "Close Trade")}
        className="modal-panel scrollbar-hidden max-h-[92vh] max-w-3xl overflow-y-auto"
        onMouseDown={(event) => event.stopPropagation()}
      >
        <DialogHeader className="pr-12">
          <p className="text-[11px] font-semibold uppercase tracking-[0.34em] text-[var(--primary)]">
            {record.display_symbol ?? record.ticker}
          </p>
          <DialogTitle>{t("journal.closeTrade", "Close Trade")}</DialogTitle>
          <DialogDescription>
            {t(
              "tradeRecord.closeDescription",
              "Record the exit facts and whether the exit followed the original plan."
            )}
          </DialogDescription>
        </DialogHeader>

        <div className="mt-8 grid gap-5">
          <section className="grid gap-4 md:grid-cols-2">
            <label className="field-shell block rounded-3xl border border-[var(--border)] bg-white/90 p-4">
              <span className="text-xs font-semibold uppercase tracking-[0.24em] text-slate-500">
                {t("tradeRecord.exitTime", "Exit Time")}
              </span>
              <input
                type="datetime-local"
                value={exitTimestamp}
                onChange={(event) => setExitTimestamp(event.target.value)}
                className="focus-ring mt-3 w-full rounded-2xl border border-[var(--border)] bg-[var(--surface-strong)] px-4 py-3 text-sm font-medium text-slate-800"
              />
            </label>
            <label className="field-shell block rounded-3xl border border-[var(--border)] bg-white/90 p-4">
              <span className="text-xs font-semibold uppercase tracking-[0.24em] text-slate-500">
                {t("tradeRecord.exitPrice", "Exit Price")}
              </span>
              <input
                type="number"
                inputMode="decimal"
                value={exitPrice}
                onChange={(event) => setExitPrice(event.target.value)}
                placeholder="436.50"
                className="focus-ring mt-3 w-full rounded-2xl border border-[var(--border)] bg-[var(--surface-strong)] px-4 py-3 text-sm font-medium text-slate-800"
              />
            </label>
          </section>

          <label className="field-shell block rounded-3xl border border-[var(--border)] bg-white/90 p-4">
            <span className="text-xs font-semibold uppercase tracking-[0.24em] text-slate-500">
              {t("tradeRecord.planExecution", "Plan Execution")}
            </span>
            <Select value={planExecution} onValueChange={setPlanExecution}>
              <SelectTrigger className="mt-3 border-[var(--border)] bg-[var(--surface-strong)] text-slate-800">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                {PLAN_EXECUTIONS.map((value) => (
                  <SelectItem key={value} value={value}>
                    {value.replaceAll("_", " ")}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </label>

          <label className="field-shell block rounded-3xl border border-[var(--border)] bg-white/90 p-4">
            <span className="text-xs font-semibold uppercase tracking-[0.24em] text-slate-500">
              {t("tradeRecord.exitReason", "Exit Reason")}
            </span>
            <Textarea
              value={exitReason}
              onChange={(event) => setExitReason(event.target.value)}
              rows={6}
              placeholder={t(
                "tradeRecord.exitReasonPlaceholder",
                "Why exit now, and was the exit plan-based, evidence-based, or emotional?"
              )}
              className="mt-3 min-h-[160px] border-[var(--border)] bg-[var(--surface-strong)] text-slate-800"
            />
          </label>

          {error ? (
            <div className="rounded-3xl border border-rose-200 bg-rose-50 px-5 py-4 text-sm text-rose-700">
              {error}
            </div>
          ) : null}

          <div className="flex flex-wrap items-center justify-end gap-3">
            <Button type="button" variant="secondary" onClick={onClose} disabled={saving}>
              {t("common.cancel", "Cancel")}
            </Button>
            <Button type="button" onClick={() => void submitClose()} disabled={saving}>
              {saving ? t("tradeRecord.saving", "Saving...") : t("journal.closeTrade", "Close Trade")}
            </Button>
          </div>
        </div>
      </DialogContent>
    </Dialog>
  );
}

function requireText(value: string, fieldName: string): string {
  const normalized = value.trim();
  if (!normalized) {
    throw new Error(`${fieldName} is required.`);
  }
  return normalized;
}

function parseRequiredNumber(value: string, fieldName: string): number {
  const normalized = value.trim();
  if (!normalized) {
    throw new Error(`${fieldName} is required.`);
  }
  const parsed = Number(normalized);
  if (!Number.isFinite(parsed)) {
    throw new Error(`${fieldName} must be numeric.`);
  }
  return parsed;
}

function normalizeRequiredTimestamp(
  value: string,
  fieldName: string,
  originalValue: string | null
): string {
  const normalized = value.trim();
  if (!normalized) {
    throw new Error(`${fieldName} is required.`);
  }
  if (originalValue && normalized === toDateTimeLocalValue(originalValue)) {
    return originalValue;
  }
  return toOffsetDateTimeString(parseDateTimeLocalValue(normalized, fieldName));
}

function toDateTimeLocalValue(value: string | null): string {
  if (!value) {
    return "";
  }
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) {
    const fallback = value.match(/^(\d{4}-\d{2}-\d{2}T\d{2}:\d{2})/);
    return fallback ? fallback[1] : "";
  }
  return formatDateTimeLocalValue(parsed);
}

function toInputNumber(value: number | null): string {
  return typeof value === "number" ? String(value) : "";
}

function parseDateTimeLocalValue(value: string, fieldName: string): Date {
  const match = value.match(/^(\d{4})-(\d{2})-(\d{2})T(\d{2}):(\d{2})$/);
  if (!match) {
    throw new Error(`${fieldName} must use YYYY-MM-DDTHH:MM format.`);
  }
  const parsed = new Date(
    Number(match[1]),
    Number(match[2]) - 1,
    Number(match[3]),
    Number(match[4]),
    Number(match[5]),
    0,
    0
  );
  if (Number.isNaN(parsed.getTime())) {
    throw new Error(`${fieldName} must be a valid date and time.`);
  }
  return parsed;
}

function formatDateTimeLocalValue(value: Date): string {
  return `${value.getFullYear()}-${padDateTimePart(value.getMonth() + 1)}-${padDateTimePart(value.getDate())}T${padDateTimePart(value.getHours())}:${padDateTimePart(value.getMinutes())}`;
}

function toOffsetDateTimeString(value: Date): string {
  const timezoneOffsetMinutes = -value.getTimezoneOffset();
  const sign = timezoneOffsetMinutes >= 0 ? "+" : "-";
  const absoluteOffsetMinutes = Math.abs(timezoneOffsetMinutes);
  const offsetHours = Math.floor(absoluteOffsetMinutes / 60);
  const offsetMinutes = absoluteOffsetMinutes % 60;
  return `${formatDateTimeLocalValue(value)}:00${sign}${padDateTimePart(offsetHours)}:${padDateTimePart(offsetMinutes)}`;
}

function padDateTimePart(value: number): string {
  return String(value).padStart(2, "0");
}
