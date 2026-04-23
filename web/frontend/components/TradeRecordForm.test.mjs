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
  assert.match(source, /ticker:\s*string/);
  assert.match(source, /exchange_or_market:\s*string/);
  assert.match(source, /entry_timestamp:\s*string/);
  assert.match(source, /exit_timestamp:\s*string/);
  assert.match(source, /initial_thesis:\s*string/);
  assert.match(source, /planned_horizon:\s*string/);
  assert.match(source, /analysis_references:\s*AnalysisReference\[]/);
  assert.match(source, /Capture a hand-entered trade record for the manual review\./);
  assert.match(source, /Bind analysis snapshots instead of copying full reports/);
  assert.match(source, /Quick add from reports/);
  assert.match(source, /Add Blank Reference/);
});

test("TradeRecordForm derives report and full-state-log paths from the MAY-8 contract", () => {
  const source = readFileSync(componentPath, "utf8");

  assert.match(source, /buildReferenceFromReport/);
  assert.match(source, /data\/reports\/\$?\{?report\.id\}?\/complete_report\.md/);
  assert.match(source, /data\/eval_results\/\$?\{?report\.ticker\}?\/TradingAgentsStrategy_logs\/full_states_log_/);
  assert.match(source, /normalizeAnalysisReferences/);
  assert.match(source, /Snapshot reference \${index \+ 1} is incomplete\./);
});

test("TradeRecordForm preserves offset-aware timestamps through the datetime-local editor", () => {
  const source = readFileSync(componentPath, "utf8");

  assert.match(source, /normalizeOptionalTimestamp/);
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
