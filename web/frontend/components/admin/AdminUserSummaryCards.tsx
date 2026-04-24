import { MetricCard } from "@/components/workbench/MetricCard";

interface AdminUserSummaryCardsProps {
  totalUsers: number;
  adminCount: number;
  disabledCount: number;
}

export function AdminUserSummaryCards({
  totalUsers,
  adminCount,
  disabledCount,
}: AdminUserSummaryCardsProps) {
  return (
    <div className="mt-6 grid gap-4 md:grid-cols-3">
      <MetricCard label="Total Users" value={`${totalUsers}`} className="bg-white/82" />
      <MetricCard
        label="Active Admins"
        value={`${adminCount}`}
        className="bg-white/82"
        valueClassName="text-[var(--primary-strong)]"
      />
      <MetricCard
        label="Disabled Accounts"
        value={`${disabledCount}`}
        className="bg-white/82"
        valueClassName="text-slate-600"
      />
    </div>
  );
}
