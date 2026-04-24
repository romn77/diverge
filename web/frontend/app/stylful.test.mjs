import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import path from "node:path";
import test from "node:test";

const stylfulCssPath = path.join(import.meta.dirname, "stylful.css");

test("stylful.css implements a skillshare-style playful visual system", () => {
  const source = readFileSync(stylfulCssPath, "utf8");

  assert.match(source, /--radius-wobble-card:/);
  assert.match(source, /--stylful-active:\s*var\(--primary-soft\)/);
  assert.match(source, /html\[data-theme="everforest"\]\[data-visual-style="stylful"\]/);
  assert.match(source, /radial-gradient\(var\(--stylful-dot\) 0\.8px, transparent 0\.8px\)/);
  assert.match(source, /\.card-surface[\s\S]*?border:\s*2px solid var\(--stylful-pencil\)/);
  assert.match(source, /\.card-surface[\s\S]*?border-radius:\s*var\(--radius-wobble-card\)/);
  assert.match(source, /\.sidebar-surface[\s\S]*?border-right:\s*2px dashed var\(--stylful-pencil-light\)/);
  assert.match(source, /\.summary-panel::before/);
  assert.equal(source.includes("body::before"), false);
});
