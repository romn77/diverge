import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import path from "node:path";
import test from "node:test";

const reportViewerPath = path.join(import.meta.dirname, "ReportViewer.tsx");

test("ReportViewer uses sticky headers with pressed-state navigation buttons", () => {
  const source = readFileSync(reportViewerPath, "utf8");

  assert.match(source, /from "@\/components\/ui\/badge"/);
  assert.match(source, /from "@\/components\/ui\/button"/);
  assert.match(source, /from "@\/components\/ui\/card"/);
  assert.match(source, /from "@\/components\/ui\/tabs"/);
  assert.match(source, /<Tabs/);
  assert.match(source, /<Card/);
  assert.match(source, /<Badge/);
  assert.match(source, /sticky top-0/);
  assert.match(source, /overflow-x-auto/);
  assert.match(source, /onValueChange=\{handleTabChange\}/);
  assert.match(source, /<TabsTrigger value="complete"/);
  assert.equal(source.includes("top-[5.75rem]"), false);
  assert.equal(source.includes("top-[6.5rem]"), false);
  assert.equal(source.includes('role="tablist"'), false);
});

test("ReportViewer lets the reading surface use the full content column", () => {
  const source = readFileSync(reportViewerPath, "utf8");

  assert.equal(source.includes("max-w-[1080px]"), false);
  assert.equal(source.includes("max-w-[76rem]"), false);
  assert.equal(source.includes("max-w-[1260px]"), false);
  assert.equal(source.includes("reader-frame"), false);
  assert.equal(source.includes("md:h-screen"), false);
  assert.equal(source.includes("overflow-y-auto"), false);
  assert.equal(source.includes('className="h-full overflow-y-auto"'), false);
});

test("ReportViewer decorates reports with valuation-aware highlights without injecting thesis tracker", () => {
  const source = readFileSync(reportViewerPath, "utf8");

  assert.match(source, /injectValuationMetricsIntoHighlights/);
  assert.match(source, /extractDcfApplicabilityMetrics/);
  assert.match(source, /extractDcfScenarioMetrics/);
  assert.match(source, /"DCF Scenario Summary"/);
  assert.match(source, /"DCF Applicability"/);
  assert.doesNotMatch(source, /buildThesisSummaryMarkdown/);
  assert.doesNotMatch(source, /artifacts\?\.find\(\(artifact\) => artifact\.type === "thesis"\)/);
  assert.doesNotMatch(source, /thesisArtifact/);
  assert.doesNotMatch(source, /selectedFile === "fundamentals"/);
  assert.doesNotMatch(source, /selectedFile === "manager"/);
});

test("ReportViewer pairs the ticker price panel with the header summary before the sticky tab rail", () => {
  const source = readFileSync(reportViewerPath, "utf8");

  assert.match(source, /Reading Overview/);
  assert.match(source, /Available tracks/);
  assert.match(source, /Source files/);
  assert.match(source, /SummaryMetric/);
  assert.match(source, /TickerPricePanel/);
  assert.match(source, /Price Trend/);
  assert.match(source, /embedded/);
  assert.match(source, /xl:grid-cols-\[minmax\(0,3fr\)_minmax\(0,7fr\)\]/);
  assert.doesNotMatch(source, /xl:grid-cols-2/);
  assert.doesNotMatch(source, /sm:grid-cols-3/);

  const headerIndex = source.indexOf("<header>");
  const panelIndex = source.indexOf("<TickerPricePanel");
  const stickyIndex = source.indexOf('className="sticky top-0');
  assert.notEqual(headerIndex, -1);
  assert.notEqual(panelIndex, -1);
  assert.notEqual(stickyIndex, -1);
  assert.ok(
    headerIndex < panelIndex,
    "header summary should render before the price panel in the hero row"
  );
  assert.ok(
    panelIndex < stickyIndex,
    "price panel should render beside the header before the sticky tab rail"
  );
});

test("ReportViewer promotes a dedicated summary tab instead of a right-side summary rail", () => {
  const source = readFileSync(reportViewerPath, "utf8");

  assert.match(source, /const SUMMARY_TAB_KEY = "summary"/);
  assert.match(source, /setSelectedTab\(SUMMARY_TAB_KEY\)/);
  assert.match(source, /selectedTab === SUMMARY_TAB_KEY/);
  assert.match(source, /SummaryPanel/);
  assert.match(source, /report\.summary/);
  assert.match(source, /TabsTrigger/);
  assert.doesNotMatch(source, /<aside className="viewer-meta-card"/);
});
