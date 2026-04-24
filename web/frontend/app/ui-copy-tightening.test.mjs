import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import path from "node:path";
import test from "node:test";

const loginPagePath = path.join(import.meta.dirname, "login", "page.tsx");
const shellPath = path.join(import.meta.dirname, "..", "components", "WorkbenchShell.tsx");
const adminUsersPagePath = path.join(import.meta.dirname, "admin", "users", "page.tsx");
const preferencesPath = path.join(
  import.meta.dirname,
  "..",
  "lib",
  "uiPreferences.ts"
);

test("top-level workbench copy stays short and action-oriented", () => {
  const loginSource = readFileSync(loginPagePath, "utf8");
  const shellSource = readFileSync(shellPath, "utf8");
  const adminSource = readFileSync(adminUsersPagePath, "utf8");
  const preferencesSource = readFileSync(preferencesPath, "utf8");

  assert.doesNotMatch(
    loginSource,
    /Use your workspace account to reopen saved reports, watch active[\s\S]*without losing context\./
  );
  assert.doesNotMatch(loginSource, /Protected by backend session cookies\./);
  assert.match(loginSource, /Sign in to continue to your requested page\./);
  assert.match(loginSource, /Need access help\? Ask your workspace admin\./);

  assert.doesNotMatch(
    shellSource,
    /TradingAgents is checking the current session before loading reports, tasks, and screeners\./
  );
  assert.doesNotMatch(
    shellSource,
    /This workbench is protected in the current environment, so TradingAgents is routing this session through the login page\./
  );
  assert.match(shellSource, /Checking your session\./);
  assert.match(shellSource, /Sign in to continue\./);

  assert.doesNotMatch(
    adminSource,
    /The backend returned `403 Insufficient permissions`, so this screen stays read-only and does not guess around RBAC\./
  );
  assert.doesNotMatch(
    adminSource,
    /The backend has auth turned off in this environment, so `\/api\/admin\/users` cannot be used until auth is enabled\./
  );
  assert.match(adminSource, /You do not have permission to manage users\./);
  assert.match(adminSource, /Enable auth to manage users\./);

  assert.doesNotMatch(
    preferencesSource,
    /TradingAgents 正在检查当前会话，然后加载报告、任务和筛选结果。/
  );
  assert.doesNotMatch(
    preferencesSource,
    /发起新的筛选任务、回看排序候选池，并让筛选工作区与报告浏览保持分离。/
  );
  assert.doesNotMatch(
    preferencesSource,
    /跟踪账户、当前持仓、手动资产和按市值计量的敞口，沉淀到 PostgreSQL 台账中，供组合经理在分析任务中复用。/
  );
  assert.match(preferencesSource, /"workbench\.preparingBody":\s*"正在检查会话。"/);
  assert.match(preferencesSource, /"analysis\.description":\s*"选择 ticker 和参数后开始分析。"/);
  assert.match(preferencesSource, /"screenerDashboard\.description":\s*"发起筛选并查看候选池。"/);
  assert.match(preferencesSource, /"activity\.description":\s*"集中查看分析和筛选任务。"/);
  assert.match(preferencesSource, /"assets\.description":\s*"查看账户、持仓和资产敞口。"/);
});
