import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import path from "node:path";
import test from "node:test";

const sidebarPath = path.join(import.meta.dirname, "Sidebar.tsx");

test("Sidebar implements grouped workbench navigation for research, portfolio, and operations", () => {
  const source = readFileSync(sidebarPath, "utf8");

  assert.match(source, /import Link from "next\/link"/);
  assert.match(source, /from "@\/components\/ui\/button"/);
  assert.match(source, /from "@\/components\/ui\/sheet"/);
  assert.match(source, /SheetContent/);
  assert.match(source, /usePathname/);
  assert.match(source, /useWorkbench/);
  assert.match(source, /buildHomeHref/);
  assert.match(source, /buildAssetsHref/);
  assert.match(source, /buildMarketBriefHref/);
  assert.match(source, /buildScreenerHref/);
  assert.match(source, /buildJournalHref/);
  assert.match(source, /buildActivityHref/);
  assert.doesNotMatch(source, /sidebar\.brandSubline/);
  assert.doesNotMatch(source, /t\("sidebar\.create", "New"\)/);
  assert.match(source, /SidebarSection title=\{t\("sidebar\.section\.research", "Research"\)\}/);
  assert.match(source, /SidebarSection title=\{t\("sidebar\.section\.portfolio", "Portfolio"\)\}/);
  assert.match(source, /SidebarSectionHeading title=\{t\("sidebar\.section\.operations", "Operations"\)\} muted/);
  assert.match(source, /mt-auto mb-4 w-full border-t border-\[var\(--border\)\] pt-3/);
  assert.match(source, /mt-auto mb-4 border-t border-\[var\(--border\)\] pt-2\.5/);
  assert.match(source, /t\("sidebar\.nav\.analysis", "Analysis"\)/);
  assert.match(source, /t\("sidebar\.nav\.marketBrief", "Market Brief"\)/);
  assert.match(source, /t\("sidebar\.nav\.screener", "Screener"\)/);
  assert.match(source, /t\("sidebar\.nav\.assets", "Assets"\)/);
  assert.match(source, /t\("sidebar\.nav\.journal", "Journal"\)/);
  assert.match(source, /t\("sidebar\.nav\.activity", "Activity"\)/);
  assert.match(source, /t\("sidebar\.meta\.analysis", "Reports and search"\)/);
  assert.match(source, /t\("sidebar\.meta\.marketBrief", "Daily market briefs"\)/);
  assert.match(source, /t\("sidebar\.meta\.screener", "Runs and candidates"\)/);
  assert.match(source, /t\("sidebar\.meta\.assets", "Ledger and exposure"\)/);
  assert.match(source, /t\("sidebar\.meta\.journal", "Trade review"\)/);
  assert.match(source, /t\("sidebar\.noActiveWork", "No active background work"\)/);
  assert.match(source, /activeOpportunityTasks/);
  assert.match(source, /canAccessAssetsWorkspace/);
  assert.match(source, /pathname\.startsWith\("\/opportunity-tasks\/"\)/);
  assert.doesNotMatch(source, /CreateMenu/);
  assert.match(source, /const isMobileDrawerOpen = isMobileViewport && isOpen/);
  assert.match(source, /const isDesktopRail = !isMobileViewport && isDesktopCollapsed/);
  assert.match(source, /document\.body\.style\.overflow/);
  assert.match(source, /event\.key !== "Escape"/);
  assert.doesNotMatch(source, /createButtonRef/);
  assert.doesNotMatch(source, /createMenuRef/);
  assert.doesNotMatch(source, /isCreateMenuOpen/);
  assert.match(source, /window\.matchMedia\("\(max-width: 767px\)"\)/);
  assert.match(source, /Collapse sidebar/);
  assert.match(source, /Expand sidebar/);
  assert.match(source, /pathname === "\/" \|\| pathname\.startsWith\("\/reports\/"\)/);
  assert.match(source, /pathname === buildMarketBriefHref\(\) \|\| pathname\.startsWith\("\/market-briefs\/"\)/);
  assert.match(source, /pathname === buildAssetsHref\(\) \|\| pathname\.startsWith\("\/assets\/"\)/);
  assert.match(source, /pathname === buildActivityHref\(\)/);
});

test("Sidebar treats the asset workspace as an optional portfolio utility", () => {
  const source = readFileSync(sidebarPath, "utf8");

  assert.match(source, /canAccessAssetsWorkspace \? \(/);
  assert.match(source, /href=\{buildAssetsHref\(\)\}/);
  assert.match(source, /t\("sidebar\.meta\.assets", "Ledger and exposure"\)/);
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

test("Sidebar preserves grouped structure in collapsed rail and renders an in-header desktop toggle", () => {
  const source = readFileSync(sidebarPath, "utf8");

  assert.match(source, /const desktopShellClasses = \[/);
  assert.match(source, /hidden md:block md:shrink-0/);
  assert.match(source, /md:fixed md:left-0 md:top-0 md:z-\[var\(--z-sidebar\)\] md:flex md:h-\[100svh\]/);
  assert.match(source, /md:py-0/);
  assert.match(source, /md:h-\[var\(--workbench-topbar-height\)\]/);
  assert.doesNotMatch(source, /md:min-h-\[4\.25rem\]/);
  assert.match(source, /const desktopToggleClasses = \[/);
  assert.match(source, /hidden h-8 w-8 items-center justify-center rounded-full border border-\[var\(--border\)\] bg-\[var\(--surface\)\]/);
  assert.match(source, /shadow-\[var\(--button-secondary-shadow\)\] transition active:translate-y-px motion-reduce:active:translate-y-0/);
  assert.match(source, /hover:border-\[var\(--border-strong\)\] hover:bg-\[var\(--surface-hover\)\] hover:text-\[var\(--primary\)\] md:inline-flex/);
  assert.match(source, /isDesktopRail \? "" : "ml-auto"/);
  assert.match(source, /aria-expanded=\{!isDesktopRail\}/);
  assert.match(source, /flex flex-col items-center gap-2 md:py-3/);
  assert.match(source, /h-16 flex items-center md:h-\[var\(--workbench-topbar-height\)\]/);
  assert.match(source, /viewBox="0 0 16 16"/);
  assert.match(source, /d="M9\.5 3\.5 5 8l4\.5 4\.5"/);
  assert.match(source, /d="M13 3\.5 8\.5 8 13 12\.5"/);
  assert.match(source, /my-1\.5 flex justify-center/);
  assert.match(source, /h-px w-6 bg-\[var\(--divider-soft\)\]/);
  assert.match(source, /sidebar-nav-link/);
  assert.match(source, /sidebar-rail-link/);
  assert.match(source, /data-active=\{active\}/);
  assert.match(source, /bg-\[var\(--surface\)\] text-\[var\(--text\)\]/);
  assert.doesNotMatch(source, /bg-\[var\(--primary-soft\)\] text-\[var\(--primary-strong\)\]/);
  assert.doesNotMatch(source, /DesktopUtilityControl/);
  assert.doesNotMatch(source, /desktopToggleWrapperClasses/);
  assert.doesNotMatch(source, /pointer-events-none fixed top-1\/2 z-\[var\(--z-toast\)\]/);
  assert.doesNotMatch(source, /rounded-full border border-\[rgba\(28,56,83,0\.12\)\] bg-white\/72/);
  assert.doesNotMatch(source, />\s*Rail\s*</);
  assert.doesNotMatch(source, /sidebar\.collapseShort/);
  assert.doesNotMatch(source, /sidebar\.expandShort/);
});
