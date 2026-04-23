import assert from "node:assert/strict";
import { existsSync, readFileSync } from "node:fs";
import path from "node:path";
import test from "node:test";

const frontendRoot = path.join(import.meta.dirname, "..");
const componentsJsonPath = path.join(frontendRoot, "components.json");
const utilsPath = path.join(frontendRoot, "lib", "utils.ts");
const uiRoot = path.join(frontendRoot, "components", "ui");

test("frontend declares a shadcn-compatible component registry and utility layer", () => {
  assert.ok(existsSync(componentsJsonPath), "expected components.json to exist");
  assert.ok(existsSync(utilsPath), "expected lib/utils.ts to exist");

  const componentsJson = readFileSync(componentsJsonPath, "utf8");
  const utilsSource = readFileSync(utilsPath, "utf8");

  assert.match(componentsJson, /"style"\s*:/);
  assert.match(componentsJson, /"tailwind"\s*:/);
  assert.match(componentsJson, /"css"\s*:\s*"app\/globals\.css"/);
  assert.match(componentsJson, /"components"\s*:\s*"@\/components"/);
  assert.match(utilsSource, /clsx/);
  assert.match(utilsSource, /tailwind-merge/);
  assert.match(utilsSource, /export function cn/);
});

test("frontend exposes the first-wave shadcn-style UI primitives under components/ui", () => {
  const requiredFiles = [
    "badge.tsx",
    "button.tsx",
    "card.tsx",
    "dialog.tsx",
    "dropdown-menu.tsx",
    "input.tsx",
    "scroll-area.tsx",
    "select.tsx",
    "sheet.tsx",
    "skeleton.tsx",
    "table.tsx",
    "tabs.tsx",
    "textarea.tsx",
  ];

  for (const fileName of requiredFiles) {
    assert.ok(existsSync(path.join(uiRoot, fileName)), `expected ${fileName} to exist`);
  }

  const buttonSource = readFileSync(path.join(uiRoot, "button.tsx"), "utf8");
  const dialogSource = readFileSync(path.join(uiRoot, "dialog.tsx"), "utf8");
  const selectSource = readFileSync(path.join(uiRoot, "select.tsx"), "utf8");

  assert.match(buttonSource, /class-variance-authority/);
  assert.match(buttonSource, /@radix-ui\/react-slot/);
  assert.match(buttonSource, /export \{ Button, buttonVariants \}/);
  assert.match(dialogSource, /@radix-ui\/react-dialog/);
  assert.match(dialogSource, /DialogContent/);
  assert.match(selectSource, /@radix-ui\/react-select/);
  assert.match(selectSource, /SelectTrigger/);
});
