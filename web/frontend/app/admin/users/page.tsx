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
import { useAuth } from "@/components/AuthProvider";
import { usePreferences } from "@/components/PreferencesProvider";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import {
  ApiError,
  createAdminUser,
  deleteAdminUser,
  listAdminUsers,
  resetAdminUserPassword,
  updateAdminUser,
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

function createEmptyUserForm(): AdminUserCreateRequest {
  return {
    email: "",
    display_name: "",
    password: "",
    role: "viewer",
    status: "active",
    must_change_password: true,
  };
}

function createEditDraft(user: AuthUser): Required<AdminUserUpdateRequest> {
  return {
    display_name: user.display_name,
    role: user.role,
    status: user.status,
    must_change_password: user.must_change_password,
  };
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

export default function AdminUsersPage() {
  const router = useRouter();
  const { locale } = usePreferences();
  const { authError, authState, authStatus, refreshSession } = useAuth();
  const [users, setUsers] = useState<AuthUser[]>([]);
  const [loadingUsers, setLoadingUsers] = useState(true);
  const [pageError, setPageError] = useState<string | null>(null);
  const [notice, setNotice] = useState<{ kind: "success" | "error"; message: string } | null>(
    null
  );
  const [searchQuery, setSearchQuery] = useState("");
  const [selectedUserId, setSelectedUserId] = useState<string | null>(null);
  const [createForm, setCreateForm] = useState<AdminUserCreateRequest>(
    createEmptyUserForm
  );
  const [editForm, setEditForm] = useState<Required<AdminUserUpdateRequest> | null>(null);
  const [resetPassword, setResetPassword] = useState("");
  const [resetMustChangePassword, setResetMustChangePassword] = useState(true);
  const [isMutating, setIsMutating] = useState(false);
  const [isForbidden, setIsForbidden] = useState(false);

  const authEnabled = authState?.enabled ?? false;
  const shouldRedirectToLogin =
    authStatus === "ready" && authEnabled && !authState?.authenticated;
  const canLoadUsers =
    authStatus === "ready" && authEnabled && Boolean(authState?.authenticated);

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
        user.display_name.toLowerCase().includes(normalizedQuery) ||
        user.role.toLowerCase().includes(normalizedQuery)
    );
  }, [searchQuery, users]);
  const adminCount = users.filter((user) => user.role === "admin").length;
  const disabledCount = users.filter((user) => user.status === "disabled").length;
  const activeCount = users.filter((user) => user.status === "active").length;

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
      const nextUsers = sortUsers(await listAdminUsers());
      setUsers(nextUsers);
      setSelectedUserId((current) => {
        if (current && nextUsers.some((user) => user.id === current)) {
          return current;
        }
        return nextUsers[0]?.id ?? null;
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
      setSelectedUserId(createdUser.id);
      setCreateForm(createEmptyUserForm());
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

  if (authStatus === "loading") {
    return (
      <main className="flex min-h-screen items-center justify-center px-6 py-10">
        <Card className="w-full max-w-xl text-center">
          <CardHeader>
          <p className="text-[12px] font-semibold uppercase tracking-[0.36em] text-[var(--primary)]">
            Session Bootstrap
          </p>
          <CardTitle>
            Verifying admin access
          </CardTitle>
          <p className="mt-3 text-sm leading-6 text-slate-600">
            TradingAgents is checking the current session before loading admin APIs.
          </p>
          </CardHeader>
        </Card>
      </main>
    );
  }

  if (authStatus === "error") {
    return (
      <main className="flex min-h-screen items-center justify-center px-6 py-10">
        <Card className="w-full max-w-xl text-center">
          <CardHeader>
          <p className="text-[12px] font-semibold uppercase tracking-[0.36em] text-[var(--danger)]">
            Auth Unavailable
          </p>
          <CardTitle>
            Unable to verify admin session
          </CardTitle>
          <p className="mt-3 text-sm leading-6 text-slate-600">
            {authError ??
              "The admin console could not load /api/auth/me, so user management is paused."}
          </p>
          </CardHeader>
          <CardContent className="flex justify-center pt-0">
            <Button type="button" onClick={() => void refreshSession()}>
              Retry Session Bootstrap
            </Button>
          </CardContent>
        </Card>
      </main>
    );
  }

  if (shouldRedirectToLogin) {
    return (
      <main className="flex min-h-screen items-center justify-center px-6 py-10">
        <Card className="w-full max-w-xl text-center">
          <CardHeader>
          <p className="text-[12px] font-semibold uppercase tracking-[0.36em] text-[var(--primary)]">
            Login Required
          </p>
          <CardTitle>
            Redirecting to `/login`
          </CardTitle>
          <p className="mt-3 text-sm leading-6 text-slate-600">
            The admin console is protected, so unauthenticated sessions are routed
            back through the sign-in page.
          </p>
          </CardHeader>
        </Card>
      </main>
    );
  }

  if (!authEnabled) {
    return (
      <main className="flex min-h-screen items-center justify-center px-6 py-10">
        <Card className="w-full max-w-xl text-center">
          <CardHeader>
          <p className="text-[12px] font-semibold uppercase tracking-[0.36em] text-slate-500">
            Auth Disabled
          </p>
          <CardTitle>
            Admin user management is unavailable
          </CardTitle>
          <p className="mt-3 text-sm leading-6 text-slate-600">
            The backend has auth turned off in this environment, so `/api/admin/users`
            cannot be used until auth is enabled.
          </p>
          </CardHeader>
          <CardContent className="flex justify-center pt-0">
            <Button asChild>
              <Link href="/">Back to Workbench</Link>
            </Button>
          </CardContent>
        </Card>
      </main>
    );
  }

  if (isForbidden) {
    return (
      <main className="flex min-h-screen items-center justify-center px-6 py-10">
        <Card className="w-full max-w-xl text-center">
          <CardHeader>
          <p className="text-[12px] font-semibold uppercase tracking-[0.36em] text-[var(--danger)]">
            Forbidden
          </p>
          <CardTitle>
            This session cannot manage users
          </CardTitle>
          <p className="mt-3 text-sm leading-6 text-slate-600">
            The backend returned `403 Insufficient permissions`, so this screen stays
            read-only and does not guess around RBAC.
          </p>
          </CardHeader>
          <CardContent className="flex justify-center pt-0">
            <Button asChild>
              <Link href="/">Back to Workbench</Link>
            </Button>
          </CardContent>
        </Card>
      </main>
    );
  }

  return (
    <main className="px-4 py-6 md:px-7 lg:px-9">
      <div className="mx-auto max-w-7xl space-y-6">
        <Card className="rounded-[30px]">
          <CardContent className="px-6 py-7 md:px-8">
          <div className="flex flex-col gap-6 lg:flex-row lg:items-end lg:justify-between">
            <div className="max-w-3xl">
              <Link
                href="/"
                className="text-[12px] font-semibold uppercase tracking-[0.32em] text-[var(--primary)]"
              >
                Back to Workbench
              </Link>
              <h1 className="font-heading mt-4 text-3xl font-bold tracking-tight text-slate-900 md:text-4xl">
                Manage workspace access
              </h1>
              <p className="mt-3 text-sm leading-7 text-slate-600">
                Add accounts, change who can operate the workspace, and handle resets
                without leaving the admin console.
              </p>
            </div>
            <div className="flex flex-wrap gap-3">
              <Button
                type="button"
                onClick={() => {
                  setSelectedUserId(null);
                  setCreateForm(createEmptyUserForm());
                  setNotice(null);
                }}
              >
                Create Account
              </Button>
              <Button
                type="button"
                variant="secondary"
                onClick={() => void loadUsers()}
                disabled={loadingUsers}
              >
                Refresh
              </Button>
            </div>
          </div>

          <div className="mt-6 grid gap-4 md:grid-cols-3">
            <SummaryCard label="Total Users" value={users.length} />
            <SummaryCard label="Active Admins" value={adminCount} accent />
            <SummaryCard label="Disabled Accounts" value={disabledCount} muted />
          </div>
          </CardContent>
        </Card>

        {notice ? (
          <div
            className={`rounded-[24px] border px-4 py-3 text-sm ${
              notice.kind === "success"
                ? "border-[rgba(46,118,83,0.18)] bg-[rgba(46,118,83,0.08)] text-[var(--success)]"
                : "border-[rgba(163,53,53,0.2)] bg-[rgba(163,53,53,0.08)] text-[var(--danger)]"
            }`}
          >
            {notice.message}
          </div>
        ) : null}

        <div className="grid gap-6 xl:grid-cols-[1.12fr_0.88fr]">
          <Card className="rounded-[30px]">
            <CardContent className="px-6 py-6">
            <div className="flex flex-col gap-4 md:flex-row md:items-center md:justify-between">
              <div>
                  <p className="text-[12px] font-semibold uppercase tracking-[0.3em] text-slate-500">
                    Directory
                  </p>
                  <h2 className="mt-2 text-2xl font-semibold tracking-tight text-slate-900">
                    Current access roster
                  </h2>
                </div>
              <label className="block w-full md:max-w-xs">
                <span className="sr-only">Search users</span>
                <Input
                  type="search"
                  value={searchQuery}
                  onChange={(event) => setSearchQuery(event.target.value)}
                  placeholder="Search by name, email, or role"
                  className="w-full bg-white"
                />
              </label>
            </div>

            {pageError ? (
              <div className="mt-6 rounded-[24px] border border-[rgba(163,53,53,0.2)] bg-[rgba(163,53,53,0.08)] px-4 py-4 text-sm text-[var(--danger)]">
                {pageError}
              </div>
            ) : null}

            {loadingUsers ? (
              <div className="mt-6 rounded-[24px] border border-[var(--border)] bg-[var(--surface-strong)] px-5 py-8 text-center text-sm text-slate-600">
                Loading admin users...
              </div>
            ) : filteredUsers.length === 0 ? (
              <div className="mt-6 rounded-[24px] border border-dashed border-[var(--border)] bg-[var(--surface-strong)] px-5 py-8 text-center text-sm text-slate-600">
                No users match the current filter.
              </div>
            ) : (
              <div className="mt-6 overflow-hidden rounded-[28px] border border-[var(--border)] bg-white">
                <div className="hidden grid-cols-[minmax(0,1.2fr)_9rem_8rem_9rem] gap-4 border-b border-[var(--border)] px-5 py-3 text-[11px] font-semibold uppercase tracking-[0.28em] text-slate-500 md:grid">
                  <span>User</span>
                  <span>Role</span>
                  <span>Status</span>
                  <span>Last Login</span>
                </div>
                <div className="divide-y divide-[var(--border)]">
                  {filteredUsers.map((user) => {
                    const isSelected = user.id === selectedUserId;
                    return (
                      <button
                        key={user.id}
                        type="button"
                        onClick={() => setSelectedUserId(user.id)}
                        className={`grid w-full gap-3 px-5 py-4 text-left transition md:grid-cols-[minmax(0,1.2fr)_9rem_8rem_9rem] md:items-center ${
                          isSelected
                            ? "bg-[var(--primary-soft)]"
                            : "hover:bg-[var(--surface-strong)]"
                        }`}
                      >
                        <div className="min-w-0">
                          <div className="flex items-center gap-3">
                            <div className="grid h-11 w-11 shrink-0 place-items-center rounded-2xl bg-[var(--surface-strong)] text-sm font-semibold text-[var(--primary-strong)]">
                              {getUserInitials(user.display_name, user.email)}
                            </div>
                            <div className="min-w-0">
                              <p className="truncate text-sm font-semibold text-slate-900">
                                {user.display_name}
                              </p>
                              <p className="truncate text-xs text-slate-500">
                                {user.email}
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
                        <span className="text-xs font-medium text-slate-500">
                          {formatDateTime(user.last_login_at, locale)}
                        </span>
                      </button>
                    );
                  })}
                </div>
              </div>
            )}
            </CardContent>
          </Card>

          <Card className="rounded-[30px]">
            <CardContent className="px-6 py-6">
            {selectedUser ? (
              <>
                <div className="flex items-start justify-between gap-4">
                  <div>
                    <p className="text-[12px] font-semibold uppercase tracking-[0.3em] text-slate-500">
                      Selected User
                    </p>
                    <h2 className="mt-2 text-2xl font-semibold tracking-tight text-slate-900">
                      {selectedUser.display_name}
                    </h2>
                    <p className="mt-2 text-sm text-slate-500">{selectedUser.email}</p>
                  </div>
                  <Badge variant="secondary">
                    {selectedUser.role}
                  </Badge>
                </div>

                {editForm ? (
                  <form className="mt-6 space-y-4" onSubmit={handleSaveUser}>
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
                    <Button type="submit" disabled={isMutating}>
                      {isMutating ? "Saving" : "Save User"}
                    </Button>
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
            ) : (
              <>
                <p className="text-[12px] font-semibold uppercase tracking-[0.3em] text-slate-500">
                  Create User
                </p>
                <h2 className="mt-2 text-2xl font-semibold tracking-tight text-slate-900">
                  Provision a new account
                </h2>
                <p className="mt-3 text-sm leading-6 text-slate-600">
                  Create the workspace account first, then decide whether this person
                  should administer, operate, or only view TradingAgents.
                </p>

                <form className="mt-6 space-y-4" onSubmit={handleCreateUser}>
                  <TextField
                    label="Email"
                    type="email"
                    value={createForm.email}
                    onChange={(value) =>
                      setCreateForm((current) => ({ ...current, email: value }))
                    }
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
                  <Button type="submit" disabled={isMutating}>
                    {isMutating ? "Creating" : "Create User"}
                  </Button>
                </form>
              </>
            )}
            </CardContent>
          </Card>
        </div>

        <section className="rounded-[24px] border border-dashed border-[var(--border)] bg-[var(--surface-strong)] px-5 py-4 text-sm text-slate-600">
          <div className="flex flex-wrap items-center gap-4">
            <span>Active accounts: {activeCount}</span>
            <span>Admins: {adminCount}</span>
            <span>Disabled: {disabledCount}</span>
            <span>Session owner: {authState?.user?.email ?? "unknown"}</span>
          </div>
        </section>
      </div>
    </main>
  );
}

function SummaryCard({
  label,
  value,
  accent = false,
  muted = false,
}: {
  label: string;
  value: number;
  accent?: boolean;
  muted?: boolean;
}) {
  const textClass = accent
    ? "text-[var(--primary-strong)]"
    : muted
      ? "text-slate-600"
      : "text-slate-900";

  return (
    <Card className="rounded-[24px] bg-white/82">
      <CardContent className="p-5">
      <p className="text-[11px] font-semibold uppercase tracking-[0.28em] text-slate-500">
        {label}
      </p>
      <p className={`mt-3 text-3xl font-semibold tracking-tight ${textClass}`}>{value}</p>
      </CardContent>
    </Card>
  );
}

function TextField({
  label,
  type = "text",
  value,
  onChange,
}: {
  label: string;
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

function getUserInitials(displayName: string, email: string): string {
  const source = displayName.trim() || email.trim();
  if (!source) {
    return "TA";
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
