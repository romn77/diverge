import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import path from "node:path";
import test from "node:test";

const sidebarPath = path.join(import.meta.dirname, "Sidebar.tsx");

test("Sidebar implements the research rail with one create surface, three primary destinations, and activity utility", () => {
  const source = readFileSync(sidebarPath, "utf8");

  assert.match(source, /import Link from "next\/link"/);
  assert.match(source, /usePathname/);
  assert.match(source, /useWorkbench/);
  assert.match(source, /buildHomeHref/);
  assert.match(source, /buildScreenerHref/);
  assert.match(source, /buildJournalHref/);
  assert.match(source, /buildActivityHref/);
  assert.match(source, /Research Workbench/);
  assert.match(source, /\+ New/);
  assert.match(source, /New Analysis/);
  assert.match(source, /New Screener/);
  assert.match(source, /Analysis/);
  assert.match(source, /Screener/);
  assert.match(source, /Journal/);
  assert.match(source, /Activity/);
  assert.match(source, /Reports and search/);
  assert.match(source, /Runs and candidates/);
  assert.match(source, /Trade review/);
  assert.match(source, /No active background work/);
  assert.match(source, /role="menu"/);
  assert.match(source, /aria-haspopup="menu"/);
  assert.match(source, /role=\{isMobileDrawerOpen \? "dialog" : undefined\}/);
  assert.match(source, /const isMobileDrawerOpen = isMobileViewport && isOpen/);
  assert.match(source, /const isDesktopRail = !isMobileViewport && isDesktopCollapsed/);
  assert.match(source, /document\.body\.style\.overflow/);
  assert.match(source, /event\.key !== "Escape"/);
  assert.match(source, /createButtonRef\.current\?\.focus/);
  assert.match(source, /window\.matchMedia\("\(max-width: 767px\)"\)/);
  assert.match(source, /Collapse sidebar/);
  assert.match(source, /Expand sidebar/);
  assert.match(source, /pathname === "\/" \|\| pathname\.startsWith\("\/reports\/"\)/);
  assert.match(source, /pathname === buildActivityHref\(\)/);
});

test("Sidebar no longer renders browse-heavy report and screener modules inline", () => {
  const source = readFileSync(sidebarPath, "utf8");

  assert.doesNotMatch(source, /Recent Reports/);
  assert.doesNotMatch(source, /Recent Screeners/);
  assert.doesNotMatch(source, /All tickers/i);
  assert.doesNotMatch(source, /Filter reports from home/);
  assert.doesNotMatch(source, /Open results/);
  assert.doesNotMatch(source, /type="search"/);
  assert.doesNotMatch(source, /router\.(push|replace)/);
  assert.doesNotMatch(source, /useSearchParams/);
  assert.doesNotMatch(source, /searchQuery/);
});

test("Sidebar keeps the compact chevron-only collapse toggle for desktop rail mode", () => {
  const source = readFileSync(sidebarPath, "utf8");

  assert.match(source, /rounded-xl p-2 text-slate-500/);
  assert.match(source, /viewBox="0 0 16 16"/);
  assert.match(source, /d="M9\.5 3\.5 5 8l4\.5 4\.5"/);
  assert.match(source, /d="M13 3\.5 8\.5 8 13 12\.5"/);
  assert.doesNotMatch(source, /sidebar\.collapseShort/);
  assert.doesNotMatch(source, /sidebar\.expandShort/);
});
