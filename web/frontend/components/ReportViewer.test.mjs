import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import path from "node:path";
import test from "node:test";

const reportViewerPath = path.join(import.meta.dirname, "ReportViewer.tsx");

test("ReportViewer uses sticky headers with pressed-state navigation buttons", () => {
  const source = readFileSync(reportViewerPath, "utf8");

  assert.match(source, /sticky top-0/);
  assert.match(source, /overflow-x-auto/);
  assert.match(source, /aria-pressed=\{selectedTab === "complete"\}/);
  assert.equal(source.includes("top-[5.75rem]"), false);
  assert.equal(source.includes("top-[6.5rem]"), false);
  assert.equal(source.includes('role="tablist"'), false);
  assert.equal(source.includes('role="tab"'), false);
});

test("ReportViewer lets the reading surface use the full content column", () => {
  const source = readFileSync(reportViewerPath, "utf8");

  assert.equal(source.includes("max-w-[1080px]"), false);
  assert.equal(source.includes("max-w-[76rem]"), false);
  assert.equal(source.includes("max-w-[1260px]"), false);
  assert.equal(source.includes("reader-frame"), false);
  assert.equal(source.includes("p-3 md:h-screen md:overflow-hidden md:p-4 lg:p-5"), false);
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

test("ReportViewer surfaces route-level overview cards and artifact context for faster scanning", () => {
  const source = readFileSync(reportViewerPath, "utf8");

  assert.match(source, /Reading Overview/);
  assert.match(source, /Available tracks/);
  assert.match(source, /Source files/);
  assert.match(source, /Reference artifacts/);
  assert.match(source, /Available Tracks/);
  assert.match(source, /Artifact Summary/);
  assert.match(source, /SummaryMetric/);
  assert.match(source, /ArtifactPill/);
  assert.match(source, /TickerPricePanel/);
  assert.match(source, /Price Trend/);
});
