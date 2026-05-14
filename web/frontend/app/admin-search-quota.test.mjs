import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import path from "node:path";
import test from "node:test";

const pagePath = path.join(
  import.meta.dirname,
  "admin",
  "search-quota",
  "page.tsx"
);
const adminConsolePagePath = path.join(
  import.meta.dirname,
  "..",
  "components",
  "admin",
  "AdminConsolePage.tsx"
);

test("admin search quota page exposes quota controls without key values", () => {
  const source = `${readFileSync(pagePath, "utf8")}\n${readFileSync(adminConsolePagePath, "utf8")}`;

  assert.match(source, /Search Quota/);
  assert.match(source, /activeTab="search-quota"/);
  assert.match(source, /getAdminSearchQuota/);
  assert.match(source, /updateAdminSearchGlobal/);
  assert.match(source, /updateAdminSearchProvider/);
  assert.match(source, /reactivateAdminSearchProvider/);
  assert.match(source, /resetAdminSearchProviderUsage/);
  assert.match(source, /Global Web Search/);
  assert.match(source, /Key status/);
  assert.match(source, /Used this month/);
  assert.match(source, /Remaining to hard cap/);
  assert.match(source, /Monthly free quota/);
  assert.match(source, /Monthly hard cap/);
  assert.match(source, /Reactivate/);
  assert.match(source, /Reset usage/);
  assert.match(source, /admin:settings/);
  assert.match(source, /router\.replace\("\/login\?next=\/admin\/search-quota"\)/);
  assert.doesNotMatch(source, /BRAVE_SEARCH_API_KEY/);
  assert.doesNotMatch(source, /TAVILY_API_KEY/);
  assert.doesNotMatch(source, /BOCHA_API_KEY/);
});

test("admin console includes search quota tab", () => {
  const source = readFileSync(adminConsolePagePath, "utf8");

  assert.match(source, /\|\s*"search-quota"/);
  assert.match(source, /label:\s*"Search Quota"/);
  assert.match(source, /href:\s*"\/admin\/search-quota"/);
});
