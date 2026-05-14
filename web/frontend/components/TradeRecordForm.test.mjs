import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import path from "node:path";
import test from "node:test";

const componentPath = path.join(import.meta.dirname, "TradeRecordForm.tsx");

test("TradeRecordForm keeps the manual trade payload aligned with backend schema fields", () => {
  const source = readFileSync(componentPath, "utf8");

  assert.match(source, /from "@\/components\/ui\/button"/);
  assert.match(source, /from "@\/components\/ui\/dialog"/);
  assert.match(source, /from "@\/components\/ui\/input"/);
  assert.match(source, /from "@\/components\/ui\/select"/);
  assert.match(source, /from "@\/components\/ui\/textarea"/);
  assert.match(source, /DialogContent/);
  assert.doesNotMatch(source, /role="dialog"/);
  assert.match(source, /createTrade/);
  assert.match(source, /updateTrade/);
  assert.match(source, /resolveMarketSymbol/);
  assert.match(source, /raw_symbol:\s*string/);
  assert.match(source, /strategy_tags:\s*string\[]/);
  assert.match(source, /entry_reason:\s*string/);
  assert.match(source, /invalidation_condition:\s*string/);
  assert.match(source, /entry_timestamp:\s*string/);
  assert.match(source, /planned_horizon:\s*string/);
  assert.match(source, /analysis_references:\s*AnalysisReference\[]/);
  assert.match(source, /Capture the setup, trigger, invalidation, and risk plan/);
  assert.match(source, /Market Resolution/);
  assert.match(source, /Strategy Tags/);
  assert.match(source, /Add Blank Reference/);
});

test("TradeRecordForm derives report and full-state-log paths from the MAY-8 contract", () => {
  const source = readFileSync(componentPath, "utf8");

  assert.match(source, /buildReferenceFromReport/);
  assert.match(source, /data\/reports\/\$?\{?report\.id\}?\/complete_report\.md/);
  assert.match(source, /full_state_log_path:\s*""/);
  assert.match(source, /normalizeAnalysisReferences/);
  assert.match(source, /tradeRecord\.error\.snapshotIncomplete/);
  assert.match(source, /!analysisDate \|\| !reportPath/);
});

test("TradeRecordForm preserves offset-aware timestamps through the datetime-local editor", () => {
  const source = readFileSync(componentPath, "utf8");

  assert.match(source, /normalizeRequiredTimestamp/);
  assert.match(source, /toOffsetDateTimeString/);
  assert.match(source, /getTimezoneOffset/);
  assert.equal(source.includes('return value.replace("Z", "").slice(0, 16);'), false);
});

test("TradeRecordForm hides native scrollbar chrome while keeping internal modal scrolling", () => {
  const source = readFileSync(componentPath, "utf8");

  assert.match(source, /max-h-\[92vh\]/);
  assert.match(source, /overflow-y-auto/);
  assert.match(source, /scrollbar-hidden/);
});

test("TradeRecordForm keeps market and status out of the primary manual fields", () => {
  const source = readFileSync(componentPath, "utf8");

  assert.doesNotMatch(source, /status:\s*string/);
  assert.doesNotMatch(source, /exchange_or_market:\s*string/);
  assert.match(source, /market_override/);
  assert.match(source, /record\?\.market_resolution\?\.source === "manual" && record\.market/);
  assert.match(source, /source: "manual"/);
});
