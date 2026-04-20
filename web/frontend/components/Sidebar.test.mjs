import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import path from "node:path";
import test from "node:test";

const sidebarPath = path.join(import.meta.dirname, "Sidebar.tsx");

test("Sidebar is route-aware and exposes link-based workbench navigation", () => {
  const source = readFileSync(sidebarPath, "utf8");

  assert.match(source, /import Link from "next\/link"/);
  assert.match(source, /usePathname/);
  assert.match(source, /useSearchParams/);
  assert.match(source, /useWorkbench/);
  assert.match(source, /buildHomeHref/);
  assert.match(source, /buildReportHref/);
  assert.match(source, /buildTaskHref/);
  assert.match(source, /buildScreenerTaskHref/);
  assert.match(source, /buildScreenerRunHref/);
  assert.match(source, /buildJournalHref/);
  assert.match(source, /searchQuery/);
  assert.match(source, /router\.(push|replace)/);
  assert.match(source, /isOpen:\s*boolean/);
  assert.match(source, /onClose:\s*\(\)\s*=>\s*void/);
  assert.match(source, /Recent Reports/);
  assert.match(source, /New Analysis/);
  assert.match(source, /New Screener/);
  assert.match(source, /Trade Journal/);
  assert.match(source, /Task Queue/);
  assert.match(source, /Recent Screeners/);
  assert.match(source, /Filter reports from home/);
  assert.match(source, /type="search"/);
  assert.match(source, /type="submit"/);
  assert.match(source, /document\.body\.style\.overflow/);
  assert.match(source, /event\.key === "Escape"/);
  assert.match(source, /searchInputRef\.current\?\.focus/);
  assert.match(source, /window\.matchMedia\("\(max-width: 767px\)"\)/);
  assert.match(source, /const isMobileDrawerOpen = isMobileViewport && isOpen/);
  assert.match(source, /const isDesktopRail = !isMobileViewport && isDesktopCollapsed/);
  assert.match(source, /const \[isDesktopCollapsed,\s*setIsDesktopCollapsed\] = useState\(false\)/);
  assert.match(source, /const \[isRecentReportsOpen,\s*setIsRecentReportsOpen\] = useState\(true\)/);
  assert.match(source, /const \[isAllTickersOpen,\s*setIsAllTickersOpen\] = useState\(false\)/);
  assert.match(source, /Collapse sidebar/);
  assert.match(source, /Expand sidebar/);
  assert.match(source, /group-focus-within:opacity-100/);
  assert.match(source, /aria-controls="recent-reports-panel"/);
  assert.match(source, /aria-controls="all-tickers-panel"/);
  assert.match(source, /\{isRecentReportsOpen && \(/);
  assert.match(source, /\{isAllTickersOpen && \(/);
  assert.match(source, /role=\{isMobileDrawerOpen \? "dialog" : undefined\}/);
  assert.match(source, /\{isMobileDrawerOpen && \(/);
  assert.match(source, /fixed left-0 top-0 bottom-0/);
  assert.match(source, /"hidden -translate-x-full px-4 md:flex md:translate-x-0"/);
  assert.equal(source.includes("&gt;"), false);
  assert.match(source, /href=\{buildJournalHref\(\)\}/);
  assert.match(source, /href=\{buildHomeHref\(searchQuery\)\}/);
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

test("Sidebar uses a compact chevron-only toggle for desktop collapse instead of a text pill", () => {
  const source = readFileSync(sidebarPath, "utf8");

  assert.match(source, /rounded-xl p-2 text-slate-500/);
  assert.match(source, /viewBox="0 0 16 16"/);
  assert.match(source, /d="M9\.5 3\.5 5 8l4\.5 4\.5"/);
  assert.match(source, /d="M13 3\.5 8\.5 8 13 12\.5"/);
  assert.doesNotMatch(source, /sidebar\.collapseShort/);
  assert.doesNotMatch(source, /sidebar\.expandShort/);
});

test("Sidebar opens settings in a lightweight anchored popover from a compact gear trigger", () => {
  const source = readFileSync(sidebarPath, "utf8");

  assert.doesNotMatch(source, /aria-haspopup="dialog"/);
  assert.doesNotMatch(source, /sidebar-settings-dialog/);
  assert.doesNotMatch(source, /fixed z-\[90\] w-\[20rem\]/);
  assert.doesNotMatch(source, /Loading settings\.\.\./);
});

test("Sidebar exposes a hover-revealed task detail trigger with a read-only form preview", () => {
  const source = readFileSync(sidebarPath, "utf8");

  assert.doesNotMatch(source, /Request details/);
  assert.doesNotMatch(source, /Task Request Snapshot/);
  assert.doesNotMatch(source, /quick_think_llm/);
  assert.doesNotMatch(source, /deep_think_llm/);
});
