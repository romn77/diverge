import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import path from "node:path";
import test from "node:test";

const globalsCssPath = path.join(import.meta.dirname, "globals.css");

test("globals.css defines the simplified workbench surfaces and removes glass grid treatments", () => {
  const source = readFileSync(globalsCssPath, "utf8");

  assert.match(source, /--surface-page:/);
  assert.match(source, /--surface-panel:/);
  assert.match(source, /--surface-elevated:/);
  assert.match(source, /--text-xs:/);
  assert.match(source, /--workbench-topbar-height:\s*4rem;/);
  assert.match(source, /--workbench-topbar-height:\s*4\.25rem;/);
  assert.match(source, /html\[data-visual-style="stylful"\]/);
  assert.match(source, /html\[data-theme="light"\]\[data-visual-style="stylful"\]/);
  assert.match(source, /html\[data-theme="dark"\]\[data-visual-style="stylful"\]/);
  assert.match(source, /html\[data-theme="proof"\]/);
  assert.match(source, /html\[data-theme="everforest"\]/);
  assert.match(source, /--button-primary-shadow:/);
  assert.match(source, /--success-soft:/);
  assert.match(source, /--danger-border:/);
  assert.match(source, /--surface-translucent:/);
  assert.match(source, /--control-chip-bg:/);
  assert.match(source, /--overlay-scrim:/);
  assert.match(source, /--field-shadow:/);
  assert.match(source, /--modal-shadow:/);
  assert.match(source, /\.button-count-chip\s*\{/);
  assert.match(source, /\.button-count-chip\s*\{[\s\S]*?height:\s*1rem;/);
  assert.match(source, /\.button-count-chip\s*\{[\s\S]*?line-height:\s*1;/);
  assert.equal(source.includes("backdrop-filter: blur(16px)"), false);
  assert.equal(source.includes(".app-shell::after"), false);
  assert.equal(source.includes("body::before"), false);
  assert.equal(source.includes('"Inter"'), false);
  assert.equal(source.includes('"Noto Sans SC"'), false);
});

test("globals.css locks the workbench topbar to the shared chrome height", () => {
  const source = readFileSync(globalsCssPath, "utf8");

  assert.match(source, /\.workbench-topbar\s*\{[\s\S]*?height:\s*var\(--workbench-topbar-height\);/);
  assert.match(source, /\.workbench-topbar\s*\{[\s\S]*?min-height:\s*var\(--workbench-topbar-height\);/);
  assert.match(source, /\.workbench-topbar\s*\{[\s\S]*?padding:\s*0 1rem;/);
  assert.match(source, /\.workbench-topbar-secondary,\s*[\s\S]*?\.workbench-topbar-new\s*\{[\s\S]*?height:\s*2rem;/);
  assert.match(source, /\.workbench-topbar-secondary\s*\{[\s\S]*?box-shadow:\s*var\(--button-secondary-shadow\);/);
  assert.match(source, /\.workbench-topbar-secondary:hover\s*\{[\s\S]*?border-color:\s*var\(--accent-border\);/);
  assert.match(source, /\.workbench-account-menu-frame\s*\{[\s\S]*?box-shadow:\s*var\(--button-secondary-shadow\);/);
  assert.doesNotMatch(source, /\.workbench-account-menu \.inline-flex/);
  assert.match(source, /@media \(min-width: 768px\)\s*\{[\s\S]*?:root\s*\{[\s\S]*?--workbench-topbar-height:\s*4\.25rem;/);
  assert.doesNotMatch(source, /\.workbench-topbar\s*\{[\s\S]*?padding:\s*0\.7rem 1rem;/);
});

test("globals.css keeps markdown typography compact for dense report reading", () => {
  const source = readFileSync(globalsCssPath, "utf8");

  assert.match(source, /line-height:\s*1\.72;/);
  assert.match(source, /overflow-wrap:\s*anywhere;/);
  assert.match(source, /\.report-reading-frame\s*\{[\s\S]*?overflow-x:\s*hidden;/);
  assert.match(source, /\.markdown-content p\s*\{\s*margin:\s*0\.66em 0;/);
  assert.match(source, /\.markdown-content h1\s*\{\s*margin:\s*0 0 0\.55em;/);
  assert.match(source, /\.markdown-content h2\s*\{\s*margin:\s*0\.5em 0 0\.48em;/);
  assert.match(source, /\.markdown-content h3\s*\{\s*margin:\s*1em 0 0\.38em;/);
  assert.match(source, /\.markdown-content pre\s*\{[\s\S]*?max-width:\s*100%;/);
  assert.match(source, /\.markdown-content > \[role="region"\]\s*\{[\s\S]*?max-width:\s*100%;/);
  assert.match(source, /\.markdown-content table\s*\{[\s\S]*?min-width:\s*100%;/);
  assert.match(source, /\.markdown-content table\s*\{[\s\S]*?max-width:\s*100%;/);
  assert.match(source, /\.markdown-content table\s*\{[\s\S]*?table-layout:\s*fixed;/);
  assert.equal(source.includes("min-width: max-content"), false);
});

test("globals.css provides a reusable hidden-scrollbar utility for modal panels", () => {
  const source = readFileSync(globalsCssPath, "utf8");

  assert.match(source, /\.scrollbar-hidden\s*\{/);
  assert.match(source, /scrollbar-width:\s*none;/);
  assert.match(source, /-ms-overflow-style:\s*none;/);
  assert.match(source, /\.scrollbar-hidden::\-webkit-scrollbar\s*\{\s*display:\s*none;/);
});

test("globals.css provides a responsive capped workbench content frame", () => {
  const source = readFileSync(globalsCssPath, "utf8");

  assert.match(source, /\.workbench-content-frame\s*\{/);
  assert.match(source, /width:\s*min\(100%, 96rem\);/);
  assert.match(source, /margin-inline:\s*0 auto;/);
});

test("globals.css keeps the page background stable across long scrolling pages", () => {
  const source = readFileSync(globalsCssPath, "utf8");

  assert.match(source, /html,\s*body\s*\{\s*min-height:\s*100%;/);
  assert.doesNotMatch(source, /html,\s*body\s*\{\s*height:\s*100%;/);
  assert.match(source, /html\s*\{\s*scrollbar-gutter:\s*stable both-edges;/);
  assert.match(source, /body\s*\{[\s\S]*?background-color:\s*var\(--body-gradient-end\);/);
  assert.match(source, /body\s*\{[\s\S]*?background-image:\s*linear-gradient\(180deg, var\(--body-gradient-start\) 0%, var\(--body-gradient-end\) 100%\);/);
  assert.match(source, /body\s*\{[\s\S]*?background-attachment:\s*fixed;/);
  assert.match(source, /body\s*\{[\s\S]*?background-repeat:\s*no-repeat;/);
  assert.match(source, /html\[data-visual-style="stylful"\] body\s*\{[\s\S]*?background-attachment:\s*fixed, fixed, fixed;/);
  assert.match(source, /html\[data-theme="dark"\]\[data-visual-style="stylful"\] body\s*\{[\s\S]*?background-attachment:\s*fixed, fixed, fixed;/);
});

test("globals.css keeps analysis pages on the shared workbench content width", () => {
  const source = readFileSync(globalsCssPath, "utf8");

  assert.doesNotMatch(source, /\.analysis-density-page \.workbench-content-frame\s*\{/);
  assert.match(source, /width:\s*min\(100%, 96rem\);/);
  assert.match(source, /\.analysis-overview-title\s*\{[\s\S]*?font-size:\s*2rem;/);
  assert.match(source, /\.analysis-overview-metric \.metric-card-value\s*\{[\s\S]*?font-size:\s*1\.55rem;/);
  assert.match(source, /\.analysis-reports-title\s*\{[\s\S]*?font-size:\s*1\.55rem;/);
  assert.match(source, /\.analysis-report-list\s*\{[\s\S]*?border-radius:\s*10px;/);
  assert.match(source, /\.analysis-report-group\s*\{[\s\S]*?border-top:\s*1px solid color-mix/);
  assert.doesNotMatch(source, /\.analysis-report-group\s*\{[^}]*box-shadow:/);
  assert.match(source, /\.analysis-report-list-head\s*\{/);
  assert.match(source, /\.analysis-report-list-head\s*\{[\s\S]*?font-weight:\s*650;/);
  assert.match(source, /\.analysis-report-list-head\s*\{[\s\S]*?letter-spacing:\s*0;/);
  assert.match(source, /\.analysis-report-list-head\s*\{[\s\S]*?text-transform:\s*none;/);
  assert.match(source, /\.analysis-report-grid\s*\{/);
  assert.match(source, /\.analysis-report-ticker\s*\{[\s\S]*?color:\s*color-mix\(in srgb, var\(--text\) 88%, var\(--muted\) 12%\);/);
  assert.match(source, /\.analysis-report-ticker\s*\{[\s\S]*?font-size:\s*0\.86rem;/);
  assert.match(source, /\.analysis-report-ticker\s*\{[\s\S]*?font-weight:\s*600;/);
  assert.match(source, /\.analysis-report-id\s*\{[\s\S]*?font-family:\s*inherit;/);
  assert.match(source, /\.analysis-report-id\s*\{[\s\S]*?font-weight:\s*600;/);
  assert.match(source, /\.analysis-report-date-cell\s*\{[\s\S]*?font-family:\s*inherit;/);
  assert.match(source, /\.analysis-report-date-cell\s*\{[\s\S]*?font-variant-numeric:\s*tabular-nums;/);
  assert.match(source, /\.analysis-report-group-header\s*\{[\s\S]*?padding:\s*0\.65rem 0\.85rem;/);
  assert.match(source, /\.analysis-report-children\s*\{[\s\S]*?gap:\s*0;/);
  assert.match(source, /\.analysis-report-row\s*\{[\s\S]*?padding:\s*0\.55rem 0\.85rem;/);
  assert.match(source, /\.analysis-report-child-row::before/);
});

test("globals.css preserves selected pill controls in dark mode", () => {
  const source = readFileSync(globalsCssPath, "utf8");

  assert.match(source, /\.pill-tab,\s*[\s\S]*?\.choice-pill\s*\{/);
  assert.match(source, /\.choice-card\s*\{/);
  assert.match(source, /\.pill-tab\[data-active="true"\],\s*[\s\S]*?\.pill-tab\[data-state="active"\]/);
  assert.match(source, /\.pill-tab\[data-active="true"\]::after,\s*[\s\S]*?\.pill-tab\[data-state="active"\]::after/);
  assert.match(source, /\.choice-card\[data-active="true"\]::after/);
  assert.match(source, /\.sidebar-report-card\[data-active="true"\]::before/);
  assert.match(source, /\.sidebar-nav-link\[data-active="true"\]::before/);
  assert.match(source, /\.sidebar-rail-link\[data-active="true"\]::before/);
  assert.match(source, /html\[data-theme="dark"\] \.pill-tab\[data-active="true"\]/);
  assert.match(source, /html\[data-theme="dark"\]\[data-visual-style="stylful"\] \.pill-tab\[data-active="true"\],/);
  assert.match(source, /\.pill-tab\[data-active="true"\],\s*[\s\S]*?background:\s*var\(--surface\)/);
  assert.match(source, /\.choice-card\[data-active="true"\]\s*\{[\s\S]*?background:\s*var\(--surface\)/);
  assert.match(source, /\.sidebar-report-card\[data-active="true"\],\s*[\s\S]*?\.sidebar-history-card\[data-active="true"\]\s*\{[\s\S]*?background:\s*var\(--surface\);/);
  assert.match(source, /html\[data-visual-style="stylful"\] \.sidebar-report-card\[data-active="true"\],[\s\S]*?background:\s*var\(--surface\);/);
});

test("globals.css keeps primary buttons as highlighted surfaces instead of inverse fills", () => {
  const source = readFileSync(globalsCssPath, "utf8");

  assert.match(source, /\.button-primary\s*\{/);
  assert.match(source, /border-color:\s*color-mix\(in srgb, var\(--primary\)/);
  assert.match(source, /background-color:\s*var\(--surface\)/);
  assert.match(source, /color:\s*var\(--text\)/);
  assert.match(source, /\.button-primary::after/);
  assert.match(source, /\.workbench-topbar-new::after/);
  assert.match(source, /\.button-primary:hover,\s*[\s\S]*?\.button-primary:active/);
  assert.doesNotMatch(source, /\.button-primary\s*\{[^}]*?background-color:\s*var\(--primary\)/);
  assert.doesNotMatch(source, /\.workbench-topbar-new\s*\{[^}]*?background:\s*var\(--primary\)/);
});

test("globals.css maps every in-use white alpha surface to a dark surface", () => {
  const source = readFileSync(globalsCssPath, "utf8");
  const requiredAlphaClasses = [
    "95",
    "92",
    "90",
    "88",
    "85",
    "82",
    "80",
    "78",
    "76",
    "75",
    "72",
    "70",
    "68",
    "58",
    "50",
    "42",
  ];

  assert.match(source, /html\[data-theme="dark"\] \.bg-white,/);
  assert.match(source, /html\[data-theme="everforest"\] \.bg-white,/);

  for (const alpha of requiredAlphaClasses) {
    assert.match(
      source,
      new RegExp(`html\\[data-theme="dark"\\] \\.bg-white\\\\/${alpha}`),
      `expected bg-white/${alpha} to be covered in dark mode`
    );
    assert.match(
      source,
      new RegExp(`html\\[data-theme="everforest"\\] \\.bg-white\\\\/${alpha}`),
      `expected bg-white/${alpha} to be covered in everforest mode`
    );
  }
});

test("globals.css maps every in-use slate text shade to theme text in dark surfaces", () => {
  const source = readFileSync(globalsCssPath, "utf8");
  const requiredTextClasses = [
    "950",
    "900",
    "800",
    "700",
    "600",
    "500",
    "400",
    "300",
  ];

  for (const shade of requiredTextClasses) {
    assert.match(
      source,
      new RegExp(`html\\[data-theme="dark"\\] \\.text-slate-${shade}`),
      `expected text-slate-${shade} to be covered in dark mode`
    );
    assert.match(
      source,
      new RegExp(`html\\[data-theme="everforest"\\] \\.text-slate-${shade}`),
      `expected text-slate-${shade} to be covered in everforest mode`
    );
  }
});

test("globals.css keeps report, chart, and form surfaces theme-token driven", () => {
  const source = readFileSync(globalsCssPath, "utf8");

  for (const token of [
    "--report-panel-bg:",
    "--report-summary-bg:",
    "--report-tab-bg:",
    "--chart-panel-bg:",
    "--chart-svg-bg:",
    "--chart-line:",
  ]) {
    assert.match(source, new RegExp(token));
  }

  for (const selector of [
    ".report-panel",
    ".report-tab-rail",
    ".report-summary-card",
    ".ticker-price-panel",
    ".ticker-chart-shell",
    ".field-shell",
  ]) {
    assert.match(source, new RegExp(selector.replace(".", "\\.")));
  }

  assert.match(source, /\.report-panel\s*\{\s*background:\s*var\(--report-panel-bg\);/);
  assert.match(source, /\.ticker-price-panel\s*\{\s*background:\s*var\(--chart-panel-bg\);/);
  assert.match(source, /\.field-shell\s*\{\s*border-color:\s*var\(--border\);\s*background:\s*var\(--surface\);/);
  assert.match(source, /\.workbench-topbar\s*\{[\s\S]*?color-mix\(in srgb, var\(--surface\) 92%, transparent\)/);
  assert.match(source, /\.analysis-report-list\s*\{[\s\S]*?background:\s*var\(--surface\);/);
});
