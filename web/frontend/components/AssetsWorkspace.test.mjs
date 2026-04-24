import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import path from "node:path";
import test from "node:test";

const componentPath = path.join(import.meta.dirname, "AssetsWorkspace.tsx");

test("AssetsWorkspace uses the shared UI primitives for its asset editor dialog and controls", () => {
  const source = readFileSync(componentPath, "utf8");

  assert.match(source, /from "@\/components\/ui\/badge"/);
  assert.match(source, /from "@\/components\/ui\/button"/);
  assert.match(source, /from "@\/components\/ui\/card"/);
  assert.match(source, /from "@\/components\/ui\/dialog"/);
  assert.match(source, /from "@\/components\/ui\/input"/);
  assert.match(source, /from "@\/components\/ui\/table"/);
  assert.match(source, /from "@\/components\/ui\/textarea"/);
  assert.match(source, /usePreferences/);
  assert.match(source, /<Input/);
  assert.match(source, /<Button/);
  assert.match(source, /<Card/);
  assert.match(source, /<Table/);
  assert.match(source, /<Badge/);
  assert.match(source, /DialogContent/);
  assert.doesNotMatch(source, /AccessibleDialog/);
  assert.doesNotMatch(source, /<button/);
  assert.doesNotMatch(source, /<input/);
  assert.match(source, /baseCurrency/);
  assert.match(source, /createAssetPosition/);
  assert.match(source, /updateAssetPosition/);
  assert.match(source, /t\("assets\.title", "Portfolio ledger"\)/);
  assert.match(source, /t\("assets\.addAsset", "Add Asset"\)/);
  assert.match(source, /t\("assets\.ledgerTable", "Ledger Table"\)/);
});

test("AssetsWorkspace gives hero actions stable wide touch targets", () => {
  const source = readFileSync(componentPath, "utf8");

  assert.match(source, /HERO_ACTION_BUTTON_CLASS/);
  assert.match(source, /HERO_CURRENCY_CONTROL_CLASS/);
  assert.match(source, /h-14/);
  assert.match(source, /min-w-\[9\.75rem\]/);
  assert.match(source, /min-w-\[10\.5rem\]/);
});
