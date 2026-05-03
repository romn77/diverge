import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import path from "node:path";
import test from "node:test";

const adminUsersPagePath = path.join(import.meta.dirname, "admin", "users", "page.tsx");
const adminConsolePagePath = path.join(
  import.meta.dirname,
  "..",
  "components",
  "admin",
  "AdminConsolePage.tsx"
);

test("admin users page wires the backend admin APIs and explicit forbidden handling", () => {
  const source = `${readFileSync(adminUsersPagePath, "utf8")}\n${readFileSync(adminConsolePagePath, "utf8")}`;

  assert.match(source, /from "@\/components\/ui\/button"/);
  assert.match(source, /AdminConsolePage/);
  assert.match(source, /AdminPanel/);
  assert.match(source, /AdminNotice/);
  assert.match(source, /from "@\/components\/ui\/input"/);
  assert.match(source, /from "@\/components\/ui\/select"/);
  assert.match(source, /from "@\/components\/ui\/dialog"/);
  assert.match(source, /from "@\/components\/ui\/sheet"/);
  assert.match(source, /AdminUserSummaryCards/);
  assert.match(source, /<Button/);
  assert.match(source, /listAdminUsers/);
  assert.match(source, /listAdminAnalysisLimits/);
  assert.match(source, /createAdminUser/);
  assert.match(source, /updateAdminUser/);
  assert.match(source, /updateAdminAnalysisLimits/);
  assert.match(source, /resetAdminUserPassword/);
  assert.match(source, /resetAdminUserUsage/);
  assert.match(source, /deleteAdminUser/);
  assert.match(source, /error instanceof ApiError && error\.status === 403/);
  assert.match(source, /router\.replace\("\/login\?next=\/admin\/users"\)/);
  assert.match(source, /Manage workspace access/);
  assert.match(source, /User Management/);
  assert.match(source, /Data Sources/);
  assert.match(source, /activeTab="users"/);
  assert.match(source, /Weekly module limits/);
  assert.match(source, /Usage this week/);
  assert.match(source, /Reset Usage/);
  assert.match(source, /Create Account/);
  assert.match(source, /Delete User/);
  assert.match(source, /Reset Password/);
});

test("admin users page keeps creation, quota, and selected-user editing in overlays", () => {
  const source = readFileSync(adminUsersPagePath, "utf8");

  assert.match(source, /isCreateDialogOpen/);
  assert.match(source, /isQuotaDialogOpen/);
  assert.match(source, /<Dialog open=\{isCreateDialogOpen\}/);
  assert.match(source, /<Dialog open=\{isQuotaDialogOpen\}/);
  assert.match(source, /<Sheet open=\{Boolean\(selectedUser\)\}/);
  assert.match(source, /Manage User/);
  assert.match(source, /Configure quotas/);
  assert.doesNotMatch(source, /xl:grid-cols-\[1\.12fr_0\.88fr\]/);
});
