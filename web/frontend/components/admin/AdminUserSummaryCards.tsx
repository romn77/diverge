import { AdminMetricCard, AdminMetricGrid } from "@/components/admin/AdminConsolePage";

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
    <AdminMetricGrid>
      <AdminMetricCard label="Total Users" value={totalUsers} />
      <AdminMetricCard
        label="Active Accounts"
        value={totalUsers - disabledCount}
      />
      <AdminMetricCard
        label="Active Admins"
        value={adminCount}
      />
      <AdminMetricCard
        label="Disabled Accounts"
        value={disabledCount}
      />
    </AdminMetricGrid>
  );
}
