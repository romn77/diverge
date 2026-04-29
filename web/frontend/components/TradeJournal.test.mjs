import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import path from "node:path";
import test from "node:test";

const componentPath = path.join(import.meta.dirname, "TradeJournal.tsx");

test("TradeJournal wires the manual trade history and review workflow to backend endpoints", () => {
  const source = readFileSync(componentPath, "utf8");

  assert.match(source, /from "@\/components\/ui\/badge"/);
  assert.match(source, /from "@\/components\/ui\/button"/);
  assert.match(source, /from "@\/components\/ui\/card"/);
  assert.match(source, /from "@\/components\/ui\/input"/);
  assert.match(source, /from "@\/components\/ui\/select"/);
  assert.match(source, /from "@\/components\/ui\/tabs"/);
  assert.match(source, /<Button/);
  assert.match(source, /<Select/);
  assert.match(source, /<Card/);
  assert.match(source, /<Input/);
  assert.match(source, /<Tabs/);
  assert.doesNotMatch(source, /<button/);
  assert.doesNotMatch(source, /<input/);
  assert.doesNotMatch(source, /<select/);
  assert.match(source, /listTrades/);
  assert.match(source, /getTrade/);
  assert.match(source, /getTickerTradeFeedback/);
  assert.match(source, /createTradeReview/);
  assert.match(source, /\[selectedTradeId,\s*setSelectedTradeId\]/);
  assert.match(source, /\[tradeDetail,\s*setTradeDetail\]/);
  assert.match(source, /\[feedback,\s*setFeedback\]/);
  assert.match(source, /\[tickerFilter,\s*setTickerFilter\]/);
  assert.match(source, /\[statusFilter,\s*setStatusFilter\]/);
  assert.match(source, /\[timeWindow,\s*setTimeWindow\]/);
  assert.match(source, /\[reviewTab,\s*setReviewTab\]/);
  assert.match(source, /Trade Journal/);
  assert.match(source, /Snapshot references only, not copied report content/);
  assert.match(source, /Distinguish entry_review and exit_review on the same trade_id/);
  assert.match(source, /Future analyses will read this saved review context/);
  assert.match(source, /Prompt Preview/);
  assert.match(source, /<TradeRecordForm/);
  assert.match(source, /<TradeReviewForm/);
  assert.match(source, /onGenerateReview/);
});

test("TradeJournal runs AI review generation outside the modal and shows pending state in the review panel", () => {
  const source = readFileSync(componentPath, "utf8");

  assert.match(source, /\[pendingReviewGeneration,\s*setPendingReviewGeneration\]/);
  assert.match(source, /handleGenerateReviewRequested/);
  assert.match(source, /setEditingReviewType\(null\);/);
  assert.match(source, /void createTradeReview\(record\.trade_id, payload\)/);
  assert.match(source, /activeReviewGeneration/);
  assert.match(source, /Generating AI review/);
  assert.match(source, /This review is being generated in the background/);
});

test("TradeJournal exposes history filters and manual-only language rather than account automation", () => {
  const source = readFileSync(componentPath, "utf8");

  assert.match(source, /Filter by Ticker or Trade ID/);
  assert.match(source, /Time Window/);
  assert.match(source, /Status/);
  assert.match(source, /Record Trade/);
  assert.match(source, /<Select/);
  assert.doesNotMatch(source, /This surface is intentionally manual\./);
});

test("TradeJournal adds health and review overview blocks so a selected trade is easier to assess", () => {
  const source = readFileSync(componentPath, "utf8");

  assert.match(source, /Trade Health/);
  assert.match(source, /Review Coverage/);
  assert.match(source, /Feedback Loop/);
  assert.match(source, /TickerPricePanel/);
  assert.match(source, /Price Trend/);
  assert.match(source, /DetailMetric/);
  assert.match(source, /selectionSummaryCards/);
  assert.match(source, /reviewCoverageLabel/);
});

test("TradeJournal keeps trade history metadata inside each record card", () => {
  const source = readFileSync(componentPath, "utf8");

  assert.match(
    source,
    /className=\{`h-auto w-full flex-col items-stretch justify-start overflow-hidden rounded-\[26px\] p-4 text-left whitespace-normal/
  );
  assert.match(source, /<div className="mt-4 grid w-full gap-3 sm:grid-cols-2">/);
});

test("TradeJournal lets the journal workspace fill the available browser width", () => {
  const source = readFileSync(componentPath, "utf8");

  assert.match(source, /<div className="workbench-content-frame flex flex-col gap-6">/);
  assert.match(source, /xl:grid-cols-\[minmax\(0,0\.95fr\)_minmax\(0,2\.05fr\)\]/);
  assert.doesNotMatch(source, /mx-auto flex w-full max-w-7xl/);
  assert.doesNotMatch(source, /max-w-none/);
  assert.doesNotMatch(source, /minmax\(320px,360px\)/);
});

test("TradeJournal localizes open and closed trade status labels", () => {
  const source = readFileSync(componentPath, "utf8");

  assert.match(source, /normalized === "open" \|\| normalized === "closed" \|\| normalized === "close"/);
  assert.match(source, /const statusKey = normalized === "close" \? "closed" : normalized/);
  assert.match(source, /t\(`trade\.status\.\$\{statusKey\}`, value\)/);
});
