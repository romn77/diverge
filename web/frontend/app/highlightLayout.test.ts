import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import path from "node:path";
import test from "node:test";

const globalsCssPath = path.join(import.meta.dirname, "globals.css");

test("terminal console grid stretches consoles to a shared row height", () => {
  const source = readFileSync(globalsCssPath, "utf8");
  const consoleGridBlock = source.match(/\.terminal-console-grid\s*\{([\s\S]*?)\}/)?.[1] ?? "";
  const consoleBlock = source.match(/\.terminal-console\s*\{([\s\S]*?)\}/)?.[1] ?? "";

  assert.match(consoleGridBlock, /align-items:\s*stretch;/);
  assert.match(consoleBlock, /display:\s*grid;/);
  assert.match(consoleBlock, /grid-template-rows:\s*auto 1fr;/);
  assert.match(consoleBlock, /height:\s*100%;/);
});
