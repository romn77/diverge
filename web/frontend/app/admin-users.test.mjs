import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import path from "node:path";
import test from "node:test";

const adminUsersPagePath = path.join(import.meta.dirname, "admin", "users", "page.tsx");

test("admin users page wires the backend admin APIs and explicit forbidden handling", () => {
  const source = readFileSync(adminUsersPagePath, "utf8");

  assert.match(source, /listAdminUsers/);
  assert.match(source, /createAdminUser/);
  assert.match(source, /updateAdminUser/);
  assert.match(source, /resetAdminUserPassword/);
  assert.match(source, /deleteAdminUser/);
  assert.match(source, /error instanceof ApiError && error\.status === 403/);
  assert.match(source, /router\.replace\("\/login\?next=\/admin\/users"\)/);
  assert.match(source, /Manage workspace access/);
  assert.match(source, /Create Account/);
  assert.match(source, /Delete User/);
  assert.match(source, /Reset Password/);
});
