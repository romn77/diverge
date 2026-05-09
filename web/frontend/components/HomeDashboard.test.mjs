import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import path from "node:path";
import test from "node:test";

const componentPath = path.join(import.meta.dirname, "HomeDashboard.tsx");

test("HomeDashboard is analysis-focused and keeps browse modules in page content", () => {
  const source = readFileSync(componentPath, "utf8");

  assert.match(source, /from "@\/components\/ui\/badge"/);
  assert.match(source, /from "@\/components\/ui\/button"/);
  assert.match(source, /from "@\/components\/ui\/input"/);
  assert.match(source, /from "@\/components\/workbench\/PageHeader"/);
  assert.match(source, /usePreferences/);
  assert.match(source, /<PageHeader/);
  assert.match(source, /<Input/);
  assert.match(source, /<Badge/);
  assert.match(source, /t\("home\.searchLabel", "Search reports"\)/);
  assert.match(source, /t\("home\.recentTickers", "Tracked Tickers"\)/);
  assert.match(source, /home\.metric\.trackedTickersMeta/);
  assert.match(source, /home\.metric\.reportLibrarySecondary/);
  assert.match(source, /home\.metric\.trackedTickersSecondary/);
  assert.match(source, /home\.metric\.activeResearchSecondary/);
  assert.match(source, /trendValue/);
  assert.match(source, /trendDirection=\{activeTasks\.length > 0 \? "up" : "neutral"\}/);
  assert.doesNotMatch(source, /home\.coverageSnapshot/);
  assert.doesNotMatch(source, /home\.coverageMap/);
  assert.doesNotMatch(source, /t\("home\.launchAnalysis", "New Analysis"\)/);
  assert.doesNotMatch(source, /buildActivityHref/);
  assert.doesNotMatch(source, /Launch Screener/);
  assert.doesNotMatch(source, /Open Trade Journal/);
  assert.doesNotMatch(source, /buildScreenerRunHref/);
  assert.doesNotMatch(source, /QueueCard/);
});

test("HomeDashboard leaves global actions to the workbench topbar", () => {
  const source = readFileSync(componentPath, "utf8");

  assert.match(source, /<Button/);
  assert.match(source, /home\.searchLabel/);
  assert.doesNotMatch(source, /useWorkbenchChrome/);
  assert.doesNotMatch(source, /openAnalysisDialog/);
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

  assert.match(source, /className="workbench-content-frame space-y-5"/);
  assert.doesNotMatch(source, /max-w-6xl/);
});

test("HomeDashboard applies denser analysis-only spacing", () => {
  const source = readFileSync(componentPath, "utf8");

  assert.match(source, /analysis-density-page/);
  assert.match(source, /workbench-page-shell/);
  assert.match(source, /<PageHeader/);
  assert.match(source, /analysis-overview-metric/);
  assert.match(source, /analysis-report-section/);
  assert.match(source, /analysis-report-row/);
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

test("HomeDashboard groups visible reports by ticker with collapsible children", () => {
  const source = readFileSync(componentPath, "utf8");

  assert.match(source, /interface ReportTickerGroup/);
  assert.match(source, /function groupReportsByTicker/);
  assert.match(source, /const visibleReports = useMemo\(\(\) => matchingReports\.slice\(0, 8\)/);
  assert.match(source, /const reportTickerGroups = useMemo/);
  assert.match(source, /expandedTickerGroups/);
  assert.match(source, /aria-expanded=\{isExpanded\}/);
  assert.match(source, /analysis-report-group-header/);
  assert.match(source, /analysis-report-children/);
  assert.match(source, /home\.reportGroupCount/);
});
