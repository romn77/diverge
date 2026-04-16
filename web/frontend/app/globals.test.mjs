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
