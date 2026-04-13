import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import path from "node:path";
import test from "node:test";

const sidebarPath = path.join(import.meta.dirname, "Sidebar.tsx");

test("Sidebar is prop-driven and exposes the redesigned navigation affordances", () => {
  const source = readFileSync(sidebarPath, "utf8");

  assert.equal(source.includes("listReports"), false);
  assert.match(source, /reports:\s*Report\[]/);
  assert.match(source, /loading:\s*boolean/);
  assert.match(source, /error:\s*string \| null/);
  assert.match(source, /selectedTradeJournal:\s*boolean/);
  assert.match(source, /searchQuery:\s*string/);
  assert.match(source, /onSearchQueryChange:\s*\(value:\s*string\)/);
  assert.match(source, /onNewAnalysis:\s*\(\)\s*=>\s*void/);
  assert.match(source, /onNewScreener:\s*\(\)\s*=>\s*void/);
  assert.match(source, /onSelectTradeJournal:\s*\(\)\s*=>\s*void/);
  assert.match(source, /taskQueue:\s*Task\[]/);
  assert.match(source, /screenerRuns:\s*ScreenerRunSummary\[]/);
  assert.match(source, /screenerTaskQueue:\s*ScreenerTask\[]/);
  assert.match(source, /activeTaskId:\s*string \| null/);
  assert.match(source, /activeScreenerTaskId:\s*string \| null/);
  assert.match(source, /onSelectTask:\s*\(taskId:\s*string\)/);
  assert.match(source, /onSelectScreenerTask:\s*\(taskId:\s*string\)/);
  assert.match(source, /onSelectScreenerRun:\s*\(runId:\s*string\)/);
  assert.match(source, /newAnalysisDisabled:\s*boolean/);
  assert.match(source, /newScreenerDisabled:\s*boolean/);
  assert.match(source, /isOpen:\s*boolean/);
  assert.match(source, /onClose:\s*\(\)\s*=>\s*void/);
  assert.match(source, /Recent Reports/);
  assert.match(source, /New Analysis/);
  assert.match(source, /New Screener/);
  assert.match(source, /Trade Journal/);
  assert.match(source, /Task Queue/);
  assert.match(source, /Recent Screeners/);
  assert.doesNotMatch(source, /Return to Queue/);
  assert.doesNotMatch(source, /canReturnToQueue/);
  assert.doesNotMatch(source, /onReturnToQueue/);
  assert.match(source, /disabled=\{newAnalysisDisabled\}/);
  assert.match(source, /disabled=\{newScreenerDisabled\}/);
  assert.match(source, /data-active=\{selectedTradeJournal\}/);
  assert.match(source, /Filter by ticker or report ID/);
  assert.match(source, /document\.body\.style\.overflow/);
  assert.match(source, /event\.key === "Escape"/);
  assert.match(source, /searchInputRef\.current\?\.focus/);
  assert.match(source, /window\.matchMedia\("\(max-width: 767px\)"\)/);
  assert.match(source, /const isMobileDrawerOpen = isMobileViewport && isOpen/);
  assert.match(source, /const \[isRecentReportsOpen,\s*setIsRecentReportsOpen\] = useState\(true\)/);
  assert.match(source, /const \[isAllTickersOpen,\s*setIsAllTickersOpen\] = useState\(false\)/);
  assert.match(source, /aria-controls="recent-reports-panel"/);
  assert.match(source, /aria-controls="all-tickers-panel"/);
  assert.match(source, /\{isRecentReportsOpen && \(/);
  assert.match(source, /\{isAllTickersOpen && \(/);
  assert.match(source, /role=\{isMobileDrawerOpen \? "dialog" : undefined\}/);
  assert.match(source, /\{isMobileDrawerOpen && \(/);
  assert.match(source, /"hidden md:flex -translate-x-full md:translate-x-0"/);
  assert.equal(source.includes("&gt;"), false);
});

test("Sidebar keeps the launch CTA and task cards visually compact", () => {
  const source = readFileSync(sidebarPath, "utf8");

  assert.match(source, /rounded-\[22px\] border px-4 py-2\.5/);
  assert.match(source, /block text-\[10px\] font-semibold uppercase tracking-\[0\.22em\]/);
  assert.match(source, /mt-1 block text-\[13px\] font-semibold/);
  assert.match(source, /rounded-2xl px-3 py-2\.5 text-left transition/);
  assert.match(source, /border border-transparent bg-white text-slate-700 hover:bg-white/);
  assert.match(source, /text-\[13px\] font-semibold/);
  assert.match(source, /text-\[10px\] uppercase tracking-\[0\.22em\]/);
  assert.match(source, /rounded-full px-2 py-0\.5 text-\[10px\]/);
});

test("Sidebar exposes a hover-revealed task detail trigger with a read-only form preview", () => {
  const source = readFileSync(sidebarPath, "utf8");

  assert.doesNotMatch(source, /Request details/);
  assert.doesNotMatch(source, /Task Request Snapshot/);
  assert.doesNotMatch(source, /quick_think_llm/);
  assert.doesNotMatch(source, /deep_think_llm/);
});
