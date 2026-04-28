import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import path from "node:path";
import test from "node:test";

const componentPath = path.join(import.meta.dirname, "HomeDashboard.tsx");

test("HomeDashboard is analysis-focused and keeps browse modules in page content", () => {
  const source = readFileSync(componentPath, "utf8");

  assert.match(source, /from "@\/components\/ui\/badge"/);
  assert.match(source, /from "@\/components\/ui\/button"/);
  assert.match(source, /from "@\/components\/ui\/card"/);
  assert.match(source, /from "@\/components\/ui\/input"/);
  assert.match(source, /usePreferences/);
  assert.match(source, /<Card/);
  assert.match(source, /<Input/);
  assert.match(source, /<Badge/);
  assert.match(source, /buildActivityHref/);
  assert.match(source, /t\("home\.searchLabel", "Search reports"\)/);
  assert.match(source, /t\("home\.recentTickers", "Tracked Tickers"\)/);
  assert.match(source, /home\.metric\.trackedTickersMeta/);
  assert.doesNotMatch(source, /home\.coverageSnapshot/);
  assert.doesNotMatch(source, /home\.coverageMap/);
  assert.match(source, /t\("home\.launchAnalysis", "New Analysis"\)/);
  assert.doesNotMatch(source, /Launch Screener/);
  assert.doesNotMatch(source, /Open Trade Journal/);
  assert.doesNotMatch(source, /buildScreenerRunHref/);
  assert.doesNotMatch(source, /QueueCard/);
});

test("HomeDashboard hero actions share a unified CTA base style across button and link elements", () => {
  const source = readFileSync(componentPath, "utf8");

  assert.match(source, /<Button/);
  assert.match(source, /asChild/);
  assert.match(source, /variant="secondary"/);
  assert.match(source, /home\.searchLabel/);
});

test("HomeDashboard keeps the page title stable while search changes the results section", () => {
  const source = readFileSync(componentPath, "utf8");

  assert.match(source, /t\("home\.analysisWorkspace", "Analysis workspace"\)/);
  assert.match(source, /t\("home\.matchingReportCount"/);
  assert.doesNotMatch(source, /home\.searchResultsTitle/);
  assert.doesNotMatch(source, /const heroTitle/);
});

test("HomeDashboard uses the shared responsive workbench width frame", () => {
  const source = readFileSync(componentPath, "utf8");

  assert.match(source, /className="workbench-content-frame space-y-6"/);
  assert.doesNotMatch(source, /max-w-6xl/);
});

test("HomeDashboard distinguishes private and workspace shared reports", () => {
  const source = readFileSync(componentPath, "utf8");

  assert.match(source, /type ReportScopeFilter = "all" \| "mine" \| "workspace"/);
  assert.match(source, /isOwnedReport/);
  assert.match(source, /return report\.owner_user_id === currentUserId/);
  assert.match(source, /return report\.visibility === "workspace"/);
  assert.match(source, /home\.scope\.all/);
  assert.match(source, /home\.scope\.mine/);
  assert.match(source, /home\.scope\.workspace/);
  assert.match(source, /home\.visibility\.private/);
  assert.match(source, /home\.visibility\.workspace/);
  assert.doesNotMatch(source, /isWorkspaceSharedReport/);
  assert.doesNotMatch(source, /home\.visibility\.workspaceOwned/);
});

test("HomeDashboard scopes counts and report results to the current search query", () => {
  const source = readFileSync(componentPath, "utf8");

  assert.match(source, /function matchesReportQuery/);
  assert.match(source, /const searchMatchedReports = useMemo/);
  assert.match(source, /reportScopeCounts[\s\S]*searchMatchedReports/);
  assert.match(source, /const scopedReports = useMemo/);
  assert.match(source, /const trackedTickers = useMemo/);
  assert.match(source, /for \(const report of scopedReports\)/);
  assert.match(source, /const matchingReports = scopedReports/);
  assert.doesNotMatch(source, /latestScopedReport/);
  assert.doesNotMatch(source, /snapshotSearchBody/);
});
