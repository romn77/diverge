import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import path from "node:path";
import test from "node:test";

const componentPath = path.join(import.meta.dirname, "TradeJournal.tsx");

test("TradeJournal wires the manual trade history and review workflow to backend endpoints", () => {
  const source = readFileSync(componentPath, "utf8");

  assert.match(source, /listTrades/);
  assert.match(source, /getTrade/);
  assert.match(source, /getTickerTradeFeedback/);
  assert.match(source, /\[selectedTradeId,\s*setSelectedTradeId\]/);
  assert.match(source, /\[tradeDetail,\s*setTradeDetail\]/);
  assert.match(source, /\[feedback,\s*setFeedback\]/);
  assert.match(source, /\[tickerFilter,\s*setTickerFilter\]/);
  assert.match(source, /\[statusFilter,\s*setStatusFilter\]/);
  assert.match(source, /\[timeWindow,\s*setTimeWindow\]/);
  assert.match(source, /\[reviewTab,\s*setReviewTab\]/);
  assert.match(source, /Manual Trade Journal MVP/);
  assert.match(source, /Snapshot references only, not copied report content/);
  assert.match(source, /Distinguish entry_review and exit_review on the same trade_id/);
  assert.match(source, /Future analyses will read this saved review context/);
  assert.match(source, /Prompt Preview/);
  assert.match(source, /<TradeRecordForm/);
  assert.match(source, /<TradeReviewForm/);
});

test("TradeJournal exposes history filters and manual-only language rather than account automation", () => {
  const source = readFileSync(componentPath, "utf8");

  assert.match(source, /Filter by Ticker or Trade ID/);
  assert.match(source, /Time Window/);
  assert.match(source, /Status/);
  assert.match(source, /New Manual Trade/);
  assert.match(source, /This surface is intentionally manual\./);
  assert.match(source, /hand-entered trade/);
  assert.match(source, /snapshot references instead of full copied reports/);
});
