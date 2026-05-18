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
  assert.match(source, /generateTradeReview/);
  assert.match(source, /listTradePlans/);
  assert.match(source, /deleteTradePlan/);
  assert.match(source, /TradePlanQueue/);
  assert.match(source, /TradePlanForm/);
  assert.match(source, /TradePlanExecuteForm/);
  assert.match(source, /\[selectedTradeId,\s*setSelectedTradeId\]/);
  assert.match(source, /\[tradeDetail,\s*setTradeDetail\]/);
  assert.match(source, /\[feedback,\s*setFeedback\]/);
  assert.match(source, /\[tradePlans,\s*setTradePlans\]/);
  assert.match(source, /\[tickerFilter,\s*setTickerFilter\]/);
  assert.match(source, /\[statusFilter,\s*setStatusFilter\]/);
  assert.match(source, /\[timeWindow,\s*setTimeWindow\]/);
  assert.match(source, /\[reviewTab,\s*setReviewTab\]/);
  assert.match(source, /Trade Journal/);
  assert.match(source, /Trade Plan Queue/);
  assert.match(source, /Snapshot references only, not copied report content/);
  assert.match(source, /Distinguish entry_review and exit_review on the same trade_id/);
  assert.match(source, /tradeTickerGroups/);
  assert.match(source, /expandedTickerGroups/);
  assert.match(source, /Collapse trade history/);
  assert.match(source, /sameTickerFeedbackReviews/);
  assert.doesNotMatch(source, /Same-Ticker Feedback/);
  assert.doesNotMatch(source, /Prompt Preview/);
  assert.match(source, /<TradeRecordForm/);
  assert.match(source, /<TradeReviewForm/);
  assert.match(source, /onGenerateReview/);
});

test("TradeJournal runs AI review generation outside the modal and shows pending state in the review panel", () => {
  const source = readFileSync(componentPath, "utf8");

  assert.match(source, /\[pendingReviewGeneration,\s*setPendingReviewGeneration\]/);
  assert.match(source, /handleGenerateReviewRequested/);
  assert.match(source, /setEditingReviewType\(null\);/);
  assert.match(source, /void generateTradeReview\(record\.trade_id, reviewType, payload\)/);
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

test("TradeJournal tolerates legacy trade records with missing display fields", () => {
  const source = readFileSync(componentPath, "utf8");

  assert.match(source, /function formatMarketLabel/);
  assert.match(source, /function formatTradeMarketExchangeLabel/);
  assert.match(source, /function normalizeMarketForHistory/);
  assert.match(source, /function formatStrategyTags/);
  assert.doesNotMatch(source, /record\.market\.toUpperCase\(\)/);
  assert.doesNotMatch(source, /tradeDetail\.record\.market\.toUpperCase\(\)/);
  assert.doesNotMatch(source, /tradeDetail\.record\.strategy_tags\.join\(", "\)/);
});

test("TradeJournal keeps trade history metadata inside each record card", () => {
  const source = readFileSync(componentPath, "utf8");

  assert.match(
    source,
    /choice-card h-auto w-full flex-col items-stretch justify-start overflow-hidden rounded-\[24px\] p-4 text-left whitespace-normal/
  );
  assert.match(source, /className="choice-pill md:hidden"/);
  assert.match(source, /className="choice-card h-auto w-full flex-col gap-1 rounded-2xl/);
  assert.match(source, /<div className="mt-4 grid w-full gap-3 sm:grid-cols-2">/);
});

test("TradeJournal groups history by ticker and supports a collapsed ticker rail", () => {
  const source = readFileSync(componentPath, "utf8");

  assert.match(source, /interface TradeTickerGroup/);
  assert.match(source, /compareTradesNewestFirst/);
  assert.match(source, /activityDateValue\(group\.latestTrade\)/);
  assert.match(source, /PanelLeftClose/);
  assert.match(source, /PanelLeftOpen/);
  assert.match(source, /compactTickerLabel/);
  assert.match(source, /journal\.tradeCount/);
  assert.match(source, /\[historyPaneWidth,\s*setHistoryPaneWidth\]/);
  assert.match(source, /journal\.resizeHistory/);
});

test("TradeJournal lets the journal workspace fill the available browser width", () => {
  const source = readFileSync(componentPath, "utf8");

  assert.match(source, /<div className="workbench-content-frame flex flex-col gap-6">/);
  assert.match(source, /--journal-history-width/);
  assert.match(source, /xl:\[grid-template-columns:minmax\(5\.5rem,var\(--journal-history-width\)\)_minmax\(0,1fr\)\]/);
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

test("TradeJournal formats generated review text into readable assessment lines", () => {
  const source = readFileSync(componentPath, "utf8");

  assert.match(source, /function formatReviewTextSegments/);
  assert.match(source, /const REVIEW_TEXT_LABELS/);
  assert.match(source, /const REVIEW_TEXT_MARKER_ALIASES/);
  assert.match(source, /Verdict: \{ zh: "判断", en: "Verdict" \}/);
  assert.match(source, /Evidence: \["Evidence", "依据", "证据"\]/);
  assert.match(source, /Remediation: \["Remediation", "修复要求", "改进要求"\]/);
  assert.match(source, /function prettifyReviewText/);
  assert.match(source, /take_profit_or_reward_target: \{/);
  assert.match(source, /\[\^A-Za-z0-9_\]/);
  assert.match(source, /function getReviewTextLanguage/);
  assert.match(source, /function getReviewTextMarker/);
  assert.match(source, /\.split\(\/\\s\*\\\|\\s\*\//);
  assert.match(source, /function splitReviewTextByMarkers/);
  assert.match(source, /\[:：\]/);
  assert.match(source, /"Cannot conclude"/);
  assert.match(source, /marker === "Cannot conclude"/);
  assert.match(source, /segments\.map\(\(segment, index\) =>/);
  assert.doesNotMatch(source, /segment\.label[\s\S]{0,260}rounded-full/);
  assert.doesNotMatch(source, /"Cannot conclude": "待确认"/);
  assert.doesNotMatch(source, /待确认/);
});

test("TradeJournal presents review follow-ups as action-first notes instead of three equal tag columns", () => {
  const source = readFileSync(componentPath, "utf8");

  assert.match(source, /<ReviewFollowupPanel/);
  assert.match(source, /function ReviewFollowupPanel/);
  assert.match(source, /lg:grid-cols-\[minmax\(0,1\.25fr\)_minmax\(0,0\.75fr\)\]/);
  assert.match(source, /function ReviewListItems/);
  assert.doesNotMatch(source.slice(0, source.indexOf("import { usePreferences }")), /CheckCircle2|Lightbulb|Tags/);
  assert.doesNotMatch(source, /md:grid-cols-3">\s*<TagCard/s);
});
