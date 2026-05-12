import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import path from "node:path";
import test from "node:test";

const reportViewerPath = path.join(import.meta.dirname, "ReportViewer.tsx");

test("ReportViewer uses sticky headers with pressed-state navigation buttons", () => {
  const source = readFileSync(reportViewerPath, "utf8");

  assert.match(source, /from "@\/components\/ui\/button"/);
  assert.match(source, /from "@\/components\/ui\/card"/);
  assert.match(source, /from "@\/components\/ui\/tabs"/);
  assert.match(source, /<Tabs/);
  assert.match(source, /<Card/);
  assert.match(source, /sticky top-0/);
  assert.match(source, /overflow-x-auto/);
  assert.match(source, /onValueChange=\{handleTabChange\}/);
  assert.match(source, /<TabsTrigger value="complete"/);
  assert.equal(source.includes("top-[5.75rem]"), false);
  assert.equal(source.includes("top-[6.5rem]"), false);
  assert.equal(source.includes('role="tablist"'), false);
});

test("ReportViewer uses the shared workbench width frame for report pages", () => {
  const source = readFileSync(reportViewerPath, "utf8");

  assert.match(source, /analysis-density-page workbench-page-shell/);
  assert.match(source, /className="workbench-content-frame"/);
  assert.match(source, /className="viewer-frame min-w-0 w-full"/);
  assert.match(source, /report-reading-frame/);
  assert.match(source, /min-w-0 w-full max-w-full/);
  assert.match(source, /TabsList className="scrollbar-none flex min-w-0 w-full max-w-full/);
  assert.doesNotMatch(source, /viewer-frame mx-auto min-w-0 w-full max-w-full/);
  assert.equal(source.includes("max-w-none"), false);
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
  assert.match(source, /ReportOverviewCompanion/);
  assert.match(source, /report-overview-companion/);
  assert.match(source, /TickerPricePanel/);
  assert.match(source, /Price Trend/);
  assert.match(source, /embedded/);
  assert.match(source, /xl:grid-cols-\[minmax\(0,3fr\)_minmax\(0,7fr\)\]/);
  assert.doesNotMatch(source, /xl:grid-cols-2/);
  assert.doesNotMatch(source, /sm:grid-cols-3/);

  const headerIndex = source.indexOf("<header>");
  const panelIndex = source.indexOf("<ReportOverviewCompanion");
  const tickerPanelIndex = source.indexOf("<TickerPricePanel");
  const stickyIndex = source.indexOf('className="sticky top-0');
  assert.notEqual(headerIndex, -1);
  assert.notEqual(panelIndex, -1);
  assert.notEqual(tickerPanelIndex, -1);
  assert.notEqual(stickyIndex, -1);
  assert.ok(
    headerIndex < panelIndex,
    "header summary should render before the price panel in the hero row"
  );
  assert.ok(
    panelIndex < stickyIndex,
    "price panel should render beside the header before the sticky tab rail"
  );
  assert.ok(
    tickerPanelIndex > panelIndex,
    "overview companion should own the ticker price panel rendering"
  );
});

test("ReportViewer localizes report hierarchy file labels consistently", () => {
  const source = readFileSync(reportViewerPath, "utf8");

  assert.match(source, /function localizeFileLabel/);
  assert.match(source, /t\(`report\.file\.\$\{file\}`/);
  assert.match(source, /const selectedFileLabel = selectedFile \? localizeFileLabel\(selectedFile, t\) : null/);
  assert.match(source, /\{localizeFileLabel\(file, t\)\}/);
  assert.doesNotMatch(source, /\{FILE_LABELS\[file\] \|\| file\}/);
});

test("ReportViewer lets the top overview panel collapse above the report body", () => {
  const source = readFileSync(reportViewerPath, "utf8");

  assert.match(source, /isOverviewCollapsed/);
  assert.match(source, /setIsOverviewCollapsed/);
  assert.match(source, /report\.collapseOverview/);
  assert.match(source, /report\.expandOverview/);
  assert.match(source, /aria-expanded=\{!isOverviewCollapsed\}/);
  assert.match(source, /title=\{overviewToggleLabel\}/);
  assert.match(source, /ChevronUp/);
  assert.match(source, /ChevronDown/);
  assert.match(source, /collapsedOverviewSummary/);
  assert.match(source, /!\s*isOverviewCollapsed && \(/);
});

test("ReportViewer exposes authorized report visibility changes", () => {
  const source = readFileSync(reportViewerPath, "utf8");

  assert.match(source, /updateReportVisibility/);
  assert.match(source, /type ReportVisibility/);
  assert.match(source, /canUpdateVisibility/);
  assert.match(source, /visibility_admin_override/);
  assert.match(source, /home\.visibility\.change/);
  assert.match(source, /role="switch"/);
  assert.match(source, /aria-checked=\{isWorkspaceVisible\}/);
  assert.match(source, /report-visibility-switch/);
  assert.match(source, /onClick=\{\(\) => void handleVisibilityChange\(nextVisibility\)\}/);
  assert.doesNotMatch(source, /<select/);
  assert.doesNotMatch(source, /<option value="workspace"/);
});

test("ReportViewer loads and renders decision_card artifacts before complete markdown", () => {
  const source = readFileSync(reportViewerPath, "utf8");

  assert.match(source, /fetchDecisionCard/);
  assert.match(source, /fetchDecisionDelta/);
  assert.match(source, /artifact\.type\.toLowerCase\(\) === "decision_card"/);
  assert.match(source, /artifact\.type\.toLowerCase\(\) === "decision_delta"/);
  assert.match(source, /<DecisionCardView card=\{decisionCard\} delta=\{decisionDelta\}/);
  assert.match(source, /<DecisionCardSkeleton/);
  assert.match(source, /decision-raw-details/);
  assert.match(source, /formatDecisionCardJson\(decisionCard, decisionDelta\)/);
  assert.match(source, /decisionCard \|\| isDecisionCardLoading \? "off" : "single"/);
});

test("ReportViewer keeps tab changes smooth by caching report content instead of blanking the body", () => {
  const source = readFileSync(reportViewerPath, "utf8");
  const handleStart = source.indexOf("const handleTabChange = useCallback");
  const handleEnd = source.indexOf("if (!structure)", handleStart);
  const handleBlock = source.slice(handleStart, handleEnd);
  const fileClickStart = source.indexOf("onClick={() => {");
  const fileClickEnd = source.indexOf("setSelectedFile(file);", fileClickStart);
  const fileClickBlock = source.slice(fileClickStart, fileClickEnd);

  assert.match(source, /contentCacheRef/);
  assert.match(source, /new Map<string, string>\(\)/);
  assert.match(source, /contentCacheRef\.current\.get\(path\)/);
  assert.match(source, /contentCacheRef\.current\.set\(path, decoratedContent\)/);
  assert.match(source, /startTransition\(\(\) => \{/);
  assert.match(source, /const ReportOverviewCompanion = memo/);
  assert.doesNotMatch(handleBlock, /setContent\(""\)/);
  assert.doesNotMatch(fileClickBlock, /setContent\(""\)/);
});

test("ReportViewer keeps the summary body free of unresolved signal badges", () => {
  const source = readFileSync(reportViewerPath, "utf8");

  assert.doesNotMatch(source, /viewer-signal-badge/);
  assert.doesNotMatch(source, /finalSignal/);
  assert.doesNotMatch(source, /finalConfidence/);
  assert.doesNotMatch(source, /report\.pending/);
  assert.doesNotMatch(source, /parseHighlights/);
  assert.doesNotMatch(source, /<Badge/);
});

test("ReportViewer promotes a dedicated summary tab instead of a right-side summary rail", () => {
  const source = readFileSync(reportViewerPath, "utf8");

  assert.match(source, /const SUMMARY_TAB_KEY = "summary"/);
  assert.match(source, /setSelectedTab\(SUMMARY_TAB_KEY\)/);
  assert.match(source, /selectedTab === SUMMARY_TAB_KEY/);
  assert.match(source, /SummaryPanel/);
  assert.match(source, /artifact\.type\.toLowerCase\(\) === "summary"/);
  assert.doesNotMatch(source, /artifact\.type\.toLowerCase\(\) === "thesis"/);
  assert.doesNotMatch(source, /report\.summaryFallback/);
  assert.match(source, /TabsTrigger/);
  assert.doesNotMatch(source, /<aside className="viewer-meta-card"/);
});
