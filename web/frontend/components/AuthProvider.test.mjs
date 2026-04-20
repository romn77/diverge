import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import path from "node:path";
import test from "node:test";

const authProviderPath = path.join(import.meta.dirname, "AuthProvider.tsx");

test("AuthProvider bootstraps session state and listens for auth-required events", () => {
  const source = readFileSync(authProviderPath, "utf8");

  assert.match(source, /getAuthState/);
  assert.match(source, /AUTH_REQUIRED_EVENT/);
  assert.match(source, /window\.addEventListener\(AUTH_REQUIRED_EVENT, handleAuthRequired\)/);
  assert.match(source, /loginRequest/);
  assert.match(source, /logoutRequest/);
  assert.match(source, /changePasswordRequest/);
  assert.match(source, /authStatus/);
  assert.match(source, /refreshSession/);
  assert.match(source, /useAuth must be used within an AuthProvider/);
});
