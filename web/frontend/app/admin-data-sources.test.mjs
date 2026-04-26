import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import path from "node:path";
import test from "node:test";

const adminDataSourcesPagePath = path.join(
  import.meta.dirname,
  "admin",
  "data-sources",
  "page.tsx"
);

test("admin data sources page exposes vendor usage and enablement controls", () => {
  const source = readFileSync(adminDataSourcesPagePath, "utf8");

  assert.match(source, /listAdminDataSources/);
  assert.match(source, /updateAdminDataSource/);
  assert.match(source, /updateAdminDataSourceRoute/);
  assert.match(source, /Data Source Usage/);
  assert.match(source, /Routing Policies/);
  assert.match(source, /href="\/admin\/users"/);
  assert.match(source, /User Management/);
  assert.match(source, /Alpha Vantage/);
  assert.match(source, /Daily limit/);
  assert.match(source, /Hourly limit/);
  assert.match(source, /Used today/);
  assert.match(source, /Used this hour/);
  assert.match(source, /Analysis/);
  assert.match(source, /Screener/);
  assert.match(source, /Trade Journal/);
  assert.match(source, /Core Stock APIs/);
  assert.match(source, /enabled/);
  assert.match(source, /disabled/);
  assert.match(source, /router\.replace\("\/login\?next=\/admin\/data-sources"\)/);
});
