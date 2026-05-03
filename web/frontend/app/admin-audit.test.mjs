import assert from "node:assert/strict";
import { existsSync, readFileSync } from "node:fs";
import path from "node:path";
import test from "node:test";

const adminAuditPagePath = path.join(
  import.meta.dirname,
  "admin",
  "audit",
  "page.tsx"
);
const adminUsersPagePath = path.join(import.meta.dirname, "admin", "users", "page.tsx");
const adminDataSourcesPagePath = path.join(
  import.meta.dirname,
  "admin",
  "data-sources",
  "page.tsx"
);
const adminTaskQueuePagePath = path.join(
  import.meta.dirname,
  "admin",
  "task-queue",
  "page.tsx"
);
const adminConsolePagePath = path.join(
  import.meta.dirname,
  "..",
  "components",
  "admin",
  "AdminConsolePage.tsx"
);

test("admin audit page renders filterable tenant audit events", () => {
  assert.equal(existsSync(adminAuditPagePath), true);
  const source = readFileSync(adminAuditPagePath, "utf8");

  assert.match(source, /listAdminAuditEvents/);
  assert.match(source, /Admin Audit/);
  assert.match(source, /Audit Log/);
  assert.match(source, /actionFilter/);
  assert.match(source, /resourceTypeFilter/);
  assert.match(source, /actorUserIdFilter/);
  assert.match(source, /createdFromFilter/);
  assert.match(source, /createdToFilter/);
  assert.match(source, /limitFilter/);
  assert.match(source, /AuditEventTable/);
  assert.match(source, /<Table/);
  assert.match(source, /Metadata/);
  assert.match(source, /metadata/);
  assert.match(source, /ip_address/);
  assert.match(source, /user_agent/);
  assert.match(source, /router\.replace\("\/login\?next=\/admin\/audit"\)/);
  assert.match(source, /You do not have permission to inspect audit events\./);
});

test("admin pages expose audit log navigation", () => {
  for (const filePath of [
    adminUsersPagePath,
    adminDataSourcesPagePath,
    adminTaskQueuePagePath,
  ]) {
    const source = readFileSync(filePath, "utf8");
    assert.match(source, /AdminConsolePage/);
  }

  const shellSource = readFileSync(adminConsolePagePath, "utf8");
  assert.match(shellSource, /Audit Log/);
  assert.match(shellSource, /href: "\/admin\/audit"/);
  assert.match(shellSource, /href: "\/admin\/users"/);
  assert.match(shellSource, /href: "\/admin\/data-sources"/);
  assert.match(shellSource, /href: "\/admin\/llm-models"/);
  assert.match(shellSource, /href: "\/admin\/task-queue"/);
});
