"use client";

import Link from "next/link";
import {
  startTransition,
  useCallback,
  useEffect,
  useMemo,
  useState,
  type FormEvent,
} from "react";
import { useRouter } from "next/navigation";
import {
  MoreHorizontal,
  RefreshCw,
  Search,
  SlidersHorizontal,
  UserPlus,
} from "lucide-react";
import { useAuth } from "@/components/AuthProvider";
import {
  AdminConsolePage,
  AdminNotice,
  AdminPanel,
} from "@/components/admin/AdminConsolePage";
import { AdminUserSummaryCards } from "@/components/admin/AdminUserSummaryCards";
import { usePreferences } from "@/components/PreferencesProvider";
import { StatusPanel } from "@/components/workbench/StatusPanel";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import {
  Sheet,
  SheetContent,
  SheetDescription,
  SheetFooter,
  SheetHeader,
  SheetTitle,
} from "@/components/ui/sheet";
import {
  ApiError,
  createAdminUser,
  deleteAdminUser,
  listAdminAnalysisLimits,
  listAdminUsers,
  resetAdminUserPassword,
  resetAdminUserUsage,
  updateAdminAnalysisLimits,
  updateAdminUser,
  type AdminAnalysisRoleLimit,
  type AdminUserCreateRequest,
  type AdminUserUpdateRequest,
  type AuthUser,
  type UserRole,
  type UserStatus,
} from "@/lib/api";

const ROLE_OPTIONS: Array<{ label: string; value: UserRole }> = [
  { label: "Admin", value: "admin" },
  { label: "Operator", value: "operator" },
  { label: "Viewer", value: "viewer" },
];

const STATUS_OPTIONS: Array<{ label: string; value: UserStatus }> = [
  { label: "Active", value: "active" },
  { label: "Disabled", value: "disabled" },
];

const USAGE_MODULES = [
  { label: "Analysis", value: "analysis" },
  { label: "Screener", value: "screener" },
  { label: "Assets", value: "assets" },
  { label: "Journal", value: "journal" },
] as const;

function createEmptyRoleLimitDrafts(): Record<UserRole, string> {
  return {
    admin: "",
    operator: "",
    viewer: "",
  };
}

function createEmptyUserForm(): AdminUserCreateRequest {
  return {
    email: "",
    username: "",
    display_name: "",
    password: "",
    role: "viewer",
    status: "active",
    must_change_password: true,
  };
}

function createEditDraft(user: AuthUser): Required<AdminUserUpdateRequest> {
  return {
    username: user.username,
    display_name: user.display_name,
    role: user.role,
    status: user.status,
    must_change_password: user.must_change_password,
  };
}

function createRoleLimitDrafts(
  limits: AdminAnalysisRoleLimit[]
): Record<UserRole, string> {
  const drafts = createEmptyRoleLimitDrafts();
  for (const limit of limits) {
    drafts[limit.role] = limit.weekly_limit === null ? "" : String(limit.weekly_limit);
  }
  return drafts;
}

function sortUsers(users: AuthUser[]): AuthUser[] {
  return [...users].sort((left, right) => {
    const leftTime = Date.parse(left.created_at);
    const rightTime = Date.parse(right.created_at);
    if (Number.isNaN(leftTime) || Number.isNaN(rightTime)) {
      return left.email.localeCompare(right.email);
    }
    return leftTime - rightTime || left.email.localeCompare(right.email);
  });
}

function parseWeeklyLimitDraft(value: string): number | null {
  const trimmed = value.trim();
  if (!trimmed) {
    return null;
  }

  const parsed = Number(trimmed);
  if (!Number.isInteger(parsed) || parsed < 0) {
    throw new Error("Weekly module limits must be whole numbers or blank.");
  }
  return parsed;
}

function formatWeeklyLimit(limit: number | null | undefined): string {
  return limit === null || limit === undefined ? "Unlimited" : `${limit} / week`;
}

function formatAccountSubtitle(user: AuthUser): string {
  return user.username === user.email ? user.email : `${user.username} · ${user.email}`;
}

function getRoleLimit(limits: AdminAnalysisRoleLimit[], role: UserRole): number | null {
  return limits.find((limit) => limit.role === role)?.weekly_limit ?? null;
}

export default function AdminUsersPage() {
  const router = useRouter();
  const { locale } = usePreferences();
  const { authError, authState, authStatus, refreshSession } = useAuth();
  const [users, setUsers] = useState<AuthUser[]>([]);
  const [roleLimits, setRoleLimits] = useState<AdminAnalysisRoleLimit[]>([]);
  const [roleLimitDrafts, setRoleLimitDrafts] = useState<Record<UserRole, string>>(
    createEmptyRoleLimitDrafts
  );
  const [loadingUsers, setLoadingUsers] = useState(true);
  const [pageError, setPageError] = useState<string | null>(null);
  const [notice, setNotice] = useState<{ kind: "success" | "error"; message: string } | null>(
    null
  );
  const [searchQuery, setSearchQuery] = useState("");
  const [isCreateDialogOpen, setIsCreateDialogOpen] = useState(false);
  const [isQuotaDialogOpen, setIsQuotaDialogOpen] = useState(false);
  const [selectedUserId, setSelectedUserId] = useState<string | null>(null);
  const [createForm, setCreateForm] = useState<AdminUserCreateRequest>(
    createEmptyUserForm
  );
  const [editForm, setEditForm] = useState<Required<AdminUserUpdateRequest> | null>(null);
  const [resetPassword, setResetPassword] = useState("");
  const [resetMustChangePassword, setResetMustChangePassword] = useState(true);
  const [isMutating, setIsMutating] = useState(false);
  const [isSavingRoleLimits, setIsSavingRoleLimits] = useState(false);
  const [resettingUsageUserId, setResettingUsageUserId] = useState<string | null>(null);
  const [isForbidden, setIsForbidden] = useState(false);

  const authEnabled = authState?.enabled ?? false;
  const shouldRedirectToLogin =
    authStatus === "ready" && authEnabled && !authState?.authenticated;
  const canLoadUsers =
    authStatus === "ready" &&
    authEnabled &&
    Boolean(authState?.authenticated) &&
    Boolean(authState?.permissions.includes("admin:users"));

  const selectedUser = useMemo(
    () => users.find((user) => user.id === selectedUserId) ?? null,
    [selectedUserId, users]
  );
  const filteredUsers = useMemo(() => {
    if (!searchQuery.trim()) {
      return users;
    }

    const normalizedQuery = searchQuery.trim().toLowerCase();
    return users.filter(
      (user) =>
        user.email.toLowerCase().includes(normalizedQuery) ||
        user.username.toLowerCase().includes(normalizedQuery) ||
        user.display_name.toLowerCase().includes(normalizedQuery) ||
        user.role.toLowerCase().includes(normalizedQuery)
    );
  }, [searchQuery, users]);
  const adminCount = users.filter((user) => user.role === "admin").length;
  const disabledCount = users.filter((user) => user.status === "disabled").length;
  const activeCount = users.filter((user) => user.status === "active").length;
  const selectedUserLimit = selectedUser
    ? getRoleLimit(roleLimits, selectedUser.role)
    : null;

  const handleAuthBoundary = useCallback((error: unknown): boolean => {
    if (error instanceof ApiError && error.status === 401) {
      void refreshSession({ silent: true });
      return true;
    }
    if (error instanceof ApiError && error.status === 403) {
      setIsForbidden(true);
      setLoadingUsers(false);
      return true;
    }
    return false;
  }, [refreshSession]);

  const loadUsers = useCallback(async () => {
    if (!canLoadUsers) {
      return;
    }

    setLoadingUsers(true);
    setPageError(null);
    setIsForbidden(false);

    try {
      const [usersPayload, limitsPayload] = await Promise.all([
        listAdminUsers(),
        listAdminAnalysisLimits(),
      ]);
      const nextUsers = sortUsers(usersPayload);
      setRoleLimits(limitsPayload.limits);
      setRoleLimitDrafts(createRoleLimitDrafts(limitsPayload.limits));
      setUsers(nextUsers);
      setSelectedUserId((current) => {
        if (current && nextUsers.some((user) => user.id === current)) {
          return current;
        }
        return null;
      });
    } catch (error) {
      if (handleAuthBoundary(error)) {
        return;
      }
      setPageError(
        error instanceof Error
          ? error.message
          : "Unable to load admin users right now"
      );
    } finally {
      setLoadingUsers(false);
    }
  }, [canLoadUsers, handleAuthBoundary]);

  useEffect(() => {
    if (!shouldRedirectToLogin) {
      return;
    }

    startTransition(() => {
      router.replace("/login?next=/admin/users");
    });
  }, [router, shouldRedirectToLogin]);

  useEffect(() => {
    if (!canLoadUsers) {
      setLoadingUsers(false);
      return;
    }

    void loadUsers();
  }, [canLoadUsers, loadUsers]);

  useEffect(() => {
    if (!selectedUser) {
      setEditForm(null);
      return;
    }

    setEditForm(createEditDraft(selectedUser));
    setResetPassword("");
    setResetMustChangePassword(true);
  }, [selectedUser]);

  const handleCreateUser = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    setNotice(null);
    setIsMutating(true);

    try {
      const createdUser = await createAdminUser(createForm);
      setUsers((current) => sortUsers([...current, createdUser]));
      setSelectedUserId(null);
      setCreateForm(createEmptyUserForm());
      setIsCreateDialogOpen(false);
      setNotice({
        kind: "success",
        message: `Created ${createdUser.email}`,
      });
    } catch (error) {
      if (handleAuthBoundary(error)) {
        return;
      }
      setNotice({
        kind: "error",
        message: error instanceof Error ? error.message : "Unable to create user",
      });
    } finally {
      setIsMutating(false);
    }
  };

  const handleSaveUser = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (!selectedUser || !editForm) {
      return;
    }

    setNotice(null);
    setIsMutating(true);

    try {
      const updatedUser = await updateAdminUser(selectedUser.id, editForm);
      setUsers((current) =>
        sortUsers(
          current.map((user) => (user.id === updatedUser.id ? updatedUser : user))
        )
      );
      setNotice({
        kind: "success",
        message: `Updated ${updatedUser.email}`,
      });
    } catch (error) {
      if (handleAuthBoundary(error)) {
        return;
      }
      setNotice({
        kind: "error",
        message: error instanceof Error ? error.message : "Unable to update user",
      });
    } finally {
      setIsMutating(false);
    }
  };

  const handleResetPassword = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (!selectedUser) {
      return;
    }

    setNotice(null);
    setIsMutating(true);

    try {
      const updatedUser = await resetAdminUserPassword(selectedUser.id, {
        new_password: resetPassword,
        must_change_password: resetMustChangePassword,
      });
      setUsers((current) =>
        sortUsers(
          current.map((user) => (user.id === updatedUser.id ? updatedUser : user))
        )
      );
      setResetPassword("");
      setNotice({
        kind: "success",
        message: `Reset password for ${updatedUser.email}`,
      });
    } catch (error) {
      if (handleAuthBoundary(error)) {
        return;
      }
      setNotice({
        kind: "error",
        message:
          error instanceof Error ? error.message : "Unable to reset password",
      });
    } finally {
      setIsMutating(false);
    }
  };

  const handleResetUsage = async (user: AuthUser) => {
    setNotice(null);
    setResettingUsageUserId(user.id);

    try {
      const payload = await resetAdminUserUsage(user.id);
      setUsers((current) =>
        current.map((item) =>
          item.id === user.id ? { ...item, usage: payload.usage } : item
        )
      );
      setNotice({
        kind: "success",
        message: `Reset weekly usage for ${user.email}`,
      });
    } catch (error) {
      if (handleAuthBoundary(error)) {
        return;
      }
      setNotice({
        kind: "error",
        message: error instanceof Error ? error.message : "Unable to reset usage",
      });
    } finally {
      setResettingUsageUserId(null);
    }
  };

  const handleDeleteUser = async () => {
    if (!selectedUser) {
      return;
    }
    if (!window.confirm(`Delete ${selectedUser.email}?`)) {
      return;
    }

    setNotice(null);
    setIsMutating(true);

    try {
      await deleteAdminUser(selectedUser.id);
      setUsers((current) => current.filter((user) => user.id !== selectedUser.id));
      setSelectedUserId(null);
      setNotice({
        kind: "success",
        message: `Deleted ${selectedUser.email}`,
      });
    } catch (error) {
      if (handleAuthBoundary(error)) {
        return;
      }
      setNotice({
        kind: "error",
        message: error instanceof Error ? error.message : "Unable to delete user",
      });
    } finally {
      setIsMutating(false);
    }
  };

  const handleSaveAnalysisLimits = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    setNotice(null);
    setIsSavingRoleLimits(true);

    try {
      const nextLimits = ROLE_OPTIONS.map(({ value }) => ({
        role: value,
        weekly_limit: parseWeeklyLimitDraft(roleLimitDrafts[value]),
      }));
      const savedLimits = await updateAdminAnalysisLimits({ limits: nextLimits });
      setRoleLimits(savedLimits.limits);
      setRoleLimitDrafts(createRoleLimitDrafts(savedLimits.limits));
      setNotice({
        kind: "success",
        message: "Updated weekly module limits",
      });
      setIsQuotaDialogOpen(false);
    } catch (error) {
      if (handleAuthBoundary(error)) {
        return;
      }
      setNotice({
        kind: "error",
        message:
          error instanceof Error ? error.message : "Unable to update weekly limits",
      });
    } finally {
      setIsSavingRoleLimits(false);
    }
  };

  if (authStatus === "loading") {
    return (
      <StatusPanel
        eyebrow="Session Bootstrap"
        title="Verifying admin access"
        body="Checking your session."
      />
    );
  }

  if (authStatus === "error") {
    return (
      <StatusPanel
        eyebrow="Auth Unavailable"
        title="Unable to verify admin session"
        tone="danger"
        body={
          authError ?? "We couldn't verify your session."
        }
        action={
          <Button type="button" onClick={() => void refreshSession()}>
            Retry Session Bootstrap
          </Button>
        }
      />
    );
  }

  if (shouldRedirectToLogin) {
    return (
      <StatusPanel
        eyebrow="Login Required"
        title="Redirecting to `/login`"
        body="Sign in to manage users."
      />
    );
  }

  if (!authEnabled) {
    return (
      <StatusPanel
        eyebrow="Auth Disabled"
        title="Admin user management is unavailable"
        tone="muted"
        body="Enable auth to manage users."
        action={
          <Button asChild>
            <Link href="/">Back to Workbench</Link>
          </Button>
        }
      />
    );
  }

  if (isForbidden) {
    return (
      <StatusPanel
        eyebrow="Forbidden"
        title="This session cannot manage users"
        tone="danger"
        body="You do not have permission to manage users."
        action={
          <Button asChild>
            <Link href="/">Back to Workbench</Link>
          </Button>
        }
      />
    );
  }

  return (
    <>
      <AdminConsolePage
        activeTab="users"
        title="Manage workspace access"
        actions={
          <>
                <Button
                  type="button"
                  size="sm"
                  onClick={() => {
                    setCreateForm(createEmptyUserForm());
                    setNotice(null);
                    setIsCreateDialogOpen(true);
                  }}
                >
                  <UserPlus className="size-4" />
                  Create Account
                </Button>
                <Button
                  type="button"
                  variant="secondary"
                  size="sm"
                  onClick={() => {
                    setRoleLimitDrafts(createRoleLimitDrafts(roleLimits));
                    setNotice(null);
                    setIsQuotaDialogOpen(true);
                  }}
                >
                  <SlidersHorizontal className="size-4" />
                  Configure quotas
                </Button>
                <Button
                  type="button"
                  variant="secondary"
                  size="sm"
                  onClick={() => void loadUsers()}
                  disabled={loadingUsers}
                >
                  <RefreshCw className="size-4" />
                  Refresh
                </Button>
          </>
        }
      >
        <AdminUserSummaryCards
          totalUsers={users.length}
          adminCount={adminCount}
          disabledCount={disabledCount}
        />

        {notice ? (
          <AdminNotice tone={notice.kind === "success" ? "success" : "danger"}>
            {notice.message}
          </AdminNotice>
        ) : null}

        <AdminPanel>
            <div className="flex flex-col gap-3 lg:flex-row lg:items-center lg:justify-between">
              <div>
                <p className="text-[10px] font-semibold uppercase tracking-[0.18em] text-slate-500">
                  Directory
                </p>
                <h2 className="mt-1 text-lg font-semibold tracking-tight text-slate-900">
                  Current access roster
                </h2>
              </div>
              <label className="relative block w-full lg:max-w-sm">
                <span className="sr-only">Search users</span>
                <Search className="pointer-events-none absolute left-4 top-1/2 size-4 -translate-y-1/2 text-slate-400" />
                <Input
                  type="search"
                  value={searchQuery}
                  onChange={(event) => setSearchQuery(event.target.value)}
                  placeholder="Search by name, username, email, or role"
                  className="w-full bg-white pl-11"
                />
              </label>
            </div>

            {pageError ? (
              <div className="mt-4 rounded-[12px] border border-[rgba(163,53,53,0.2)] bg-[rgba(163,53,53,0.08)] px-3 py-2 text-xs text-[var(--danger)]">
                {pageError}
              </div>
            ) : null}

            {loadingUsers ? (
              <div className="mt-4 rounded-[12px] border border-[var(--border)] bg-[var(--surface-strong)] px-4 py-6 text-center text-sm text-slate-600">
                Loading admin users...
              </div>
            ) : filteredUsers.length === 0 ? (
              <div className="mt-4 rounded-[12px] border border-dashed border-[var(--border)] bg-[var(--surface-strong)] px-4 py-6 text-center text-sm text-slate-600">
                No users match the current filter.
              </div>
            ) : (
              <div className="mt-4 overflow-hidden rounded-[12px] border border-[var(--border)] bg-white">
                <div className="hidden grid-cols-[minmax(0,1.25fr)_7rem_7rem_minmax(14rem,1fr)_9rem_11rem] gap-3 border-b border-[var(--border)] px-4 py-2 text-[10px] font-semibold uppercase tracking-[0.16em] text-slate-500 lg:grid">
                  <span>User</span>
                  <span>Role</span>
                  <span>Status</span>
                  <span>Usage this week</span>
                  <span>Last Login</span>
                  <span className="text-right">Actions</span>
                </div>
                <div className="divide-y divide-[var(--border)]">
                  {filteredUsers.map((user) => (
                    <div
                      key={user.id}
                      className="grid gap-3 px-4 py-3 transition hover:bg-[var(--surface-strong)] lg:grid-cols-[minmax(0,1.25fr)_7rem_7rem_minmax(14rem,1fr)_9rem_11rem] lg:items-center"
                    >
                      <div className="min-w-0">
                        <div className="flex items-center gap-3">
                          <div className="grid h-9 w-9 shrink-0 place-items-center rounded-xl bg-[var(--surface-strong)] text-xs font-semibold text-[var(--primary-strong)]">
                            {getUserInitials(user.display_name, user.email)}
                          </div>
                          <div className="min-w-0">
                            <p className="truncate text-sm font-semibold text-slate-900">
                              {user.display_name}
                            </p>
                            <p className="truncate text-xs text-slate-500">
                              {formatAccountSubtitle(user)}
                            </p>
                          </div>
                        </div>
                      </div>
                      <Badge variant="secondary" className="w-fit">
                        {user.role}
                      </Badge>
                      <Badge
                        variant={user.status === "active" ? "success" : "destructive"}
                        className="w-fit"
                      >
                        {user.status}
                      </Badge>
                      <UsageSummary user={user} />
                      <span className="text-xs font-medium text-slate-500">
                        {formatDateTime(user.last_login_at, locale)}
                      </span>
                      <div className="flex flex-wrap justify-start gap-2 lg:justify-end">
                        <Button
                          type="button"
                          variant="secondary"
                          size="sm"
                          onClick={() => void handleResetUsage(user)}
                          disabled={resettingUsageUserId === user.id}
                        >
                          <RefreshCw className="size-4" />
                          {resettingUsageUserId === user.id ? "Resetting" : "Reset Usage"}
                        </Button>
                        <Button
                          type="button"
                          variant="outline"
                          size="sm"
                          onClick={() => setSelectedUserId(user.id)}
                        >
                          <MoreHorizontal className="size-4" />
                          Manage
                        </Button>
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            )}
        </AdminPanel>

        <section className="rounded-[12px] border border-dashed border-[var(--border)] bg-[var(--surface-strong)] px-4 py-3 text-xs text-slate-600">
          <div className="flex flex-wrap items-center gap-4">
            <span>Active accounts: {activeCount}</span>
            <span>Admins: {adminCount}</span>
            <span>Disabled: {disabledCount}</span>
            <span>Session owner: {authState?.user?.email ?? "unknown"}</span>
          </div>
        </section>
      </AdminConsolePage>

      <Dialog open={isCreateDialogOpen}
        onOpenChange={(open) => {
          setIsCreateDialogOpen(open);
          if (open) {
            setCreateForm(createEmptyUserForm());
            setNotice(null);
          }
        }}
      >
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Provision a new account</DialogTitle>
            <DialogDescription>
              Create the workspace account first, then assign a role and login status.
            </DialogDescription>
          </DialogHeader>
          <form className="space-y-4" onSubmit={handleCreateUser}>
            <TextField
              label="Email"
              type="email"
              value={createForm.email}
              onChange={(value) =>
                setCreateForm((current) => ({ ...current, email: value }))
              }
            />
            <TextField
              label="Username"
              value={createForm.username ?? ""}
              onChange={(value) =>
                setCreateForm((current) => ({ ...current, username: value }))
              }
              placeholder="Defaults to email"
            />
            <TextField
              label="Display Name"
              value={createForm.display_name}
              onChange={(value) =>
                setCreateForm((current) => ({ ...current, display_name: value }))
              }
            />
            <TextField
              label="Temporary Password"
              type="password"
              value={createForm.password}
              onChange={(value) =>
                setCreateForm((current) => ({ ...current, password: value }))
              }
            />
            <div className="grid gap-4 sm:grid-cols-2">
              <SelectField
                label="Role"
                value={createForm.role}
                options={ROLE_OPTIONS}
                onChange={(value) =>
                  setCreateForm((current) => ({
                    ...current,
                    role: value as UserRole,
                  }))
                }
              />
              <SelectField
                label="Status"
                value={createForm.status}
                options={STATUS_OPTIONS}
                onChange={(value) =>
                  setCreateForm((current) => ({
                    ...current,
                    status: value as UserStatus,
                  }))
                }
              />
            </div>
            <label className="flex items-center gap-3 rounded-[22px] border border-[var(--border)] bg-[var(--surface-strong)] px-4 py-3 text-sm font-medium text-slate-700">
              <input
                type="checkbox"
                checked={createForm.must_change_password}
                onChange={(event) =>
                  setCreateForm((current) => ({
                    ...current,
                    must_change_password: event.target.checked,
                  }))
                }
              />
              Require password change after first login
            </label>
            <DialogFooter>
              <Button type="submit" disabled={isMutating}>
                {isMutating ? "Creating" : "Create User"}
              </Button>
            </DialogFooter>
          </form>
        </DialogContent>
      </Dialog>

      <Dialog open={isQuotaDialogOpen}
        onOpenChange={(open) => {
          setIsQuotaDialogOpen(open);
          if (open) {
            setRoleLimitDrafts(createRoleLimitDrafts(roleLimits));
            setNotice(null);
          }
        }}
      >
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Weekly module limits</DialogTitle>
            <DialogDescription>
              Leave a role blank for unlimited module usage. Use zero to block new
              module actions for that role.
            </DialogDescription>
          </DialogHeader>
          <form className="space-y-4" onSubmit={handleSaveAnalysisLimits}>
            {ROLE_OPTIONS.map((roleOption) => {
              const persistedLimit = getRoleLimit(roleLimits, roleOption.value);
              return (
                <label
                  key={roleOption.value}
                  className="block rounded-[22px] border border-[var(--border)] bg-[var(--surface-strong)] px-4 py-4"
                >
                  <span className="flex items-center justify-between gap-3">
                    <span className="text-sm font-semibold text-slate-900">
                      {roleOption.label}
                    </span>
                    <span className="text-xs font-medium text-slate-500">
                      {formatWeeklyLimit(persistedLimit)}
                    </span>
                  </span>
                  <Input
                    type="number"
                    min={0}
                    step={1}
                    placeholder="Unlimited"
                    value={roleLimitDrafts[roleOption.value]}
                    onChange={(event) =>
                      setRoleLimitDrafts((current) => ({
                        ...current,
                        [roleOption.value]: event.target.value,
                      }))
                    }
                    className="mt-3 bg-white"
                  />
                </label>
              );
            })}
            <DialogFooter>
              <Button type="submit" disabled={isSavingRoleLimits || loadingUsers}>
                {isSavingRoleLimits ? "Saving" : "Save Limits"}
              </Button>
            </DialogFooter>
          </form>
        </DialogContent>
      </Dialog>

      <Sheet open={Boolean(selectedUser)}
        onOpenChange={(open) => {
          if (!open) {
            setSelectedUserId(null);
          }
        }}
      >
        <SheetContent className="overflow-y-auto sm:max-w-xl">
          {selectedUser ? (
            <>
              <SheetHeader>
                <SheetTitle>Manage User</SheetTitle>
                <SheetDescription>
                  {selectedUser.display_name} · {formatAccountSubtitle(selectedUser)}
                </SheetDescription>
              </SheetHeader>
              <div className="mt-4 flex flex-wrap gap-2">
                <Badge variant="secondary">{selectedUser.role}</Badge>
                <Badge
                  variant={selectedUser.status === "active" ? "success" : "destructive"}
                >
                  {selectedUser.status}
                </Badge>
                <Badge variant="secondary">
                  Weekly quota {formatWeeklyLimit(selectedUserLimit)}
                </Badge>
              </div>

              {editForm ? (
                <form className="mt-6 space-y-4" onSubmit={handleSaveUser}>
                  <TextField
                    label="Username"
                    value={editForm.username}
                    onChange={(value) =>
                      setEditForm((current) =>
                        current ? { ...current, username: value } : current
                      )
                    }
                  />
                  <TextField
                    label="Display Name"
                    value={editForm.display_name}
                    onChange={(value) =>
                      setEditForm((current) =>
                        current ? { ...current, display_name: value } : current
                      )
                    }
                  />
                  <div className="grid gap-4 sm:grid-cols-2">
                    <SelectField
                      label="Role"
                      value={editForm.role}
                      options={ROLE_OPTIONS}
                      onChange={(value) =>
                        setEditForm((current) =>
                          current ? { ...current, role: value as UserRole } : current
                        )
                      }
                    />
                    <SelectField
                      label="Status"
                      value={editForm.status}
                      options={STATUS_OPTIONS}
                      onChange={(value) =>
                        setEditForm((current) =>
                          current ? { ...current, status: value as UserStatus } : current
                        )
                      }
                    />
                  </div>
                  <label className="flex items-center gap-3 rounded-[22px] border border-[var(--border)] bg-[var(--surface-strong)] px-4 py-3 text-sm font-medium text-slate-700">
                    <input
                      type="checkbox"
                      checked={editForm.must_change_password}
                      onChange={(event) =>
                        setEditForm((current) =>
                          current
                            ? {
                                ...current,
                                must_change_password: event.target.checked,
                              }
                            : current
                        )
                      }
                    />
                    Force password rotation on next reset
                  </label>
                  <SheetFooter>
                    <Button type="submit" disabled={isMutating}>
                      {isMutating ? "Saving" : "Save User"}
                    </Button>
                  </SheetFooter>
                </form>
              ) : null}

              <form
                className="mt-6 rounded-[28px] border border-[var(--border)] bg-[var(--surface-strong)] p-4"
                onSubmit={handleResetPassword}
              >
                <p className="text-[12px] font-semibold uppercase tracking-[0.28em] text-slate-500">
                  Reset Password
                </p>
                <TextField
                  label="Temporary Password"
                  type="password"
                  value={resetPassword}
                  onChange={setResetPassword}
                />
                <label className="mt-4 flex items-center gap-3 text-sm font-medium text-slate-700">
                  <input
                    type="checkbox"
                    checked={resetMustChangePassword}
                    onChange={(event) =>
                      setResetMustChangePassword(event.target.checked)
                    }
                  />
                  Require password change after reset
                </label>
                <Button
                  type="submit"
                  variant="secondary"
                  disabled={isMutating || !resetPassword.trim()}
                  className="mt-4 bg-[var(--accent)] text-white hover:bg-[var(--accent)] hover:brightness-105"
                >
                  {isMutating ? "Resetting" : "Reset Password"}
                </Button>
              </form>

              <section className="mt-6 rounded-[28px] border border-[var(--border)] bg-[var(--surface-strong)] p-4">
                <div className="flex flex-wrap items-start justify-between gap-3">
                  <div>
                    <p className="text-[12px] font-semibold uppercase tracking-[0.28em] text-slate-500">
                      Usage this week
                    </p>
                    <p className="mt-2 text-sm leading-6 text-slate-600">
                      {selectedUser.usage
                        ? `Week of ${selectedUser.usage.usage_week}`
                        : "No usage recorded for this user yet."}
                    </p>
                  </div>
                  <Button
                    type="button"
                    variant="secondary"
                    disabled={resettingUsageUserId === selectedUser.id}
                    onClick={() => void handleResetUsage(selectedUser)}
                  >
                    {resettingUsageUserId === selectedUser.id
                      ? "Resetting"
                      : "Reset Usage"}
                  </Button>
                </div>
                {selectedUser.usage ? (
                  <div className="mt-4 grid gap-3 sm:grid-cols-2">
                    {Object.entries(selectedUser.usage.modules).map(
                      ([moduleName, usage]) => (
                        <div
                          key={moduleName}
                          className="rounded-[20px] border border-[var(--border)] bg-white/80 px-4 py-3"
                        >
                          <p className="text-xs font-semibold capitalize text-slate-700">
                            {moduleName}
                          </p>
                          <p className="mt-1 text-sm text-slate-500">
                            {usage.used_count} used ·{" "}
                            {formatWeeklyLimit(usage.weekly_limit)}
                          </p>
                        </div>
                      )
                    )}
                  </div>
                ) : null}
              </section>

              <div className="mt-6 rounded-[28px] border border-[rgba(163,53,53,0.18)] bg-[rgba(163,53,53,0.08)] p-4">
                <p className="text-[12px] font-semibold uppercase tracking-[0.28em] text-[var(--danger)]">
                  Destructive Action
                </p>
                <p className="mt-2 text-sm leading-6 text-slate-600">
                  Deleting a user also revokes their active sessions. The backend
                  protects the last active admin account.
                </p>
                <Button
                  type="button"
                  variant="outline"
                  disabled={isMutating}
                  onClick={() => void handleDeleteUser()}
                  className="mt-4 border-[var(--danger)] text-[var(--danger)] hover:bg-[rgba(163,53,53,0.06)] hover:text-[var(--danger)]"
                >
                  {isMutating ? "Deleting" : "Delete User"}
                </Button>
              </div>
            </>
          ) : null}
        </SheetContent>
      </Sheet>
    </>
  );
}

function TextField({
  label,
  placeholder,
  type = "text",
  value,
  onChange,
}: {
  label: string;
  placeholder?: string;
  type?: string;
  value: string;
  onChange: (value: string) => void;
}) {
  return (
    <label className="block">
      <span className="text-[10px] font-semibold uppercase tracking-[0.26em] text-slate-500">
        {label}
      </span>
      <Input
        type={type}
        placeholder={placeholder}
        value={value}
        onChange={(event) => onChange(event.target.value)}
        className="mt-2 bg-white"
      />
    </label>
  );
}

function SelectField({
  label,
  value,
  options,
  onChange,
}: {
  label: string;
  value: string;
  options: Array<{ label: string; value: string }>;
  onChange: (value: string) => void;
}) {
  return (
    <label className="block">
      <span className="text-[10px] font-semibold uppercase tracking-[0.26em] text-slate-500">
        {label}
      </span>
      <Select value={value} onValueChange={onChange}>
        <SelectTrigger className="mt-2 bg-white">
          <SelectValue placeholder={label} />
        </SelectTrigger>
        <SelectContent>
        {options.map((option) => (
          <SelectItem key={option.value} value={option.value}>
            {option.label}
          </SelectItem>
        ))}
        </SelectContent>
      </Select>
    </label>
  );
}

function UsageSummary({ user }: { user: AuthUser }) {
  if (!user.usage) {
    return (
      <span className="text-xs font-medium text-slate-500">
        No usage yet
      </span>
    );
  }

  return (
    <div className="grid gap-1 text-xs text-slate-600 sm:grid-cols-2 lg:grid-cols-2">
      {USAGE_MODULES.map((module) => {
        const usage = user.usage?.modules[module.value];
        const usedCount = usage?.used_count ?? 0;
        const limit = usage?.weekly_limit ?? user.usage?.weekly_limit ?? null;
        return (
          <span
            key={module.value}
            className="flex items-center justify-between gap-2 rounded-full bg-[var(--surface-strong)] px-2.5 py-1"
          >
            <span className="font-medium">{module.label}</span>
            <span className="text-slate-500">
              {usedCount}/{limit === null ? "unlimited" : limit}
            </span>
          </span>
        );
      })}
    </div>
  );
}

function getUserInitials(displayName: string, email: string): string {
  const source = displayName.trim() || email.trim();
  if (!source) {
    return "DV";
  }

  const words = source.split(/\s+/).filter(Boolean);
  if (words.length >= 2) {
    return `${words[0][0]}${words[1][0]}`.toUpperCase();
  }

  return source.slice(0, 2).toUpperCase();
}

function formatDateTime(value: string | null, locale: string): string {
  if (!value) {
    return "Never";
  }

  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) {
    return value;
  }

  return new Intl.DateTimeFormat(locale, {
    year: "numeric",
    month: "short",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  }).format(parsed);
}
