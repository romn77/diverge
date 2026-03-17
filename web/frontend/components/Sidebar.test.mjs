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
  assert.match(source, /searchQuery:\s*string/);
  assert.match(source, /onSearchQueryChange:\s*\(value:\s*string\)/);
  assert.match(source, /isOpen:\s*boolean/);
  assert.match(source, /onClose:\s*\(\)\s*=>\s*void/);
  assert.match(source, /Recent Reports/);
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
