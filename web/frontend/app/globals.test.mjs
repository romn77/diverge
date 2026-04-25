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
  assert.match(source, /html\[data-visual-style="stylful"\]/);
  assert.match(source, /html\[data-theme="light"\]\[data-visual-style="stylful"\]/);
  assert.match(source, /html\[data-theme="dark"\]\[data-visual-style="stylful"\]/);
  assert.match(source, /html\[data-theme="proof"\]/);
  assert.match(source, /html\[data-theme="everforest"\]/);
  assert.match(source, /--button-primary-shadow:/);
  assert.equal(source.includes("backdrop-filter: blur(16px)"), false);
  assert.equal(source.includes(".app-shell::after"), false);
  assert.equal(source.includes("body::before"), false);
  assert.equal(source.includes('"Inter"'), false);
  assert.equal(source.includes('"Noto Sans SC"'), false);
});

test("globals.css keeps markdown typography compact for dense report reading", () => {
  const source = readFileSync(globalsCssPath, "utf8");

  assert.match(source, /line-height:\s*1\.72;/);
  assert.match(source, /\.markdown-content p\s*\{\s*margin:\s*0\.66em 0;/);
  assert.match(source, /\.markdown-content h1\s*\{\s*margin:\s*0 0 0\.55em;/);
  assert.match(source, /\.markdown-content h2\s*\{\s*margin:\s*0\.5em 0 0\.48em;/);
  assert.match(source, /\.markdown-content h3\s*\{\s*margin:\s*1em 0 0\.38em;/);
});

test("globals.css provides a reusable hidden-scrollbar utility for modal panels", () => {
  const source = readFileSync(globalsCssPath, "utf8");

  assert.match(source, /\.scrollbar-hidden\s*\{/);
  assert.match(source, /scrollbar-width:\s*none;/);
  assert.match(source, /-ms-overflow-style:\s*none;/);
  assert.match(source, /\.scrollbar-hidden::\-webkit-scrollbar\s*\{\s*display:\s*none;/);
});

test("globals.css preserves selected pill controls in dark mode", () => {
  const source = readFileSync(globalsCssPath, "utf8");

  assert.match(source, /html\[data-theme="dark"\] \.pill-tab\[data-active="true"\]/);
  assert.match(source, /html\[data-theme="dark"\]\[data-visual-style="stylful"\] \.pill-tab\[data-active="true"\]/);
  assert.match(source, /background:\s*var\(--primary\)/);
  assert.match(source, /color:\s*var\(--primary-foreground\)/);
});

test("globals.css gives primary buttons explicit token colors", () => {
  const source = readFileSync(globalsCssPath, "utf8");

  assert.match(source, /\.button-primary\s*\{/);
  assert.match(source, /border-color:\s*var\(--primary\)/);
  assert.match(source, /background-color:\s*var\(--primary\)/);
  assert.match(source, /color:\s*var\(--primary-foreground\)/);
  assert.match(source, /\.button-primary:hover,\s*[\s\S]*?\.button-primary:active/);
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
    "72",
    "70",
    "68",
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
});
