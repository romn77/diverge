import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import path from "node:path";
import test from "node:test";

const formPath = path.join(import.meta.dirname, "NewAnalysisForm.tsx");

test("NewAnalysisForm is driven by backend config options and task creation callbacks", () => {
  const source = readFileSync(formPath, "utf8");

  assert.match(source, /getConfigOptions/);
  assert.match(source, /createTask/);
  assert.match(source, /onTaskCreated:\s*\(taskId:\s*string\)/);
  assert.match(source, /defaultOutputLanguage:\s*string \| null/);
  assert.match(source, /from "@\/components\/ui\/button"/);
  assert.match(source, /from "@\/components\/ui\/dialog"/);
  assert.match(source, /from "@\/components\/ui\/input"/);
  assert.match(source, /from "@\/components\/ui\/select"/);
  assert.match(source, /<Button/);
  assert.match(source, /DialogContent/);
  assert.match(source, /Ticker/);
  assert.match(source, /Research Depth/i);
  assert.match(source, /Model Profile/i);
  assert.match(source, /LLM Provider/i);
  assert.match(source, /Output Language/i);
  assert.match(source, /aria-label=\{t\("analysis\.dialog", "New analysis"\)\}/);
  assert.doesNotMatch(source, /AccessibleDialog/);
  assert.doesNotMatch(source, /<button/);
});

test("NewAnalysisForm hides providers without configured credentials", () => {
  const source = readFileSync(formPath, "utf8");

  assert.match(source, /provider\.enabled/);
  assert.match(source, /enabledProviderOptions/);
  assert.match(source, /filter\(\(provider\) => provider\.enabled\)/);
  assert.match(source, /enabledProviderOptions\.map/);
  assert.doesNotMatch(source, /disabled=\{!provider\.enabled\}/);
  assert.doesNotMatch(source, /analysis\.disabledProvider/);
  assert.match(source, /providerUnavailableLabel/);
  assert.match(source, /analysis\.providerHint/);
  assert.match(source, /API key/i);
});

test("NewAnalysisForm defaults to model profiles and keeps provider selection in custom mode", () => {
  const source = readFileSync(formPath, "utf8");

  assert.match(source, /model_profiles/);
  assert.match(source, /buildModelProfileSelection/);
  assert.match(source, /model_profile:\s*"custom"/);
  assert.match(source, /isCustomModelProfile/);
  assert.match(source, /selectedProvider === "openai"/);
});

test("NewAnalysisForm defaults to the full analyst set instead of truncating to two", () => {
  const source = readFileSync(formPath, "utf8");

  assert.doesNotMatch(source, /analysts:\s*configOptions\.analysts\.slice\(0,\s*2\)/);
  assert.match(source, /analysts:\s*configOptions\.analysts\.map\(\(option\)\s*=>\s*option\.value\)/);
});

test("NewAnalysisForm lets users choose private or workspace report visibility", () => {
  const source = readFileSync(formPath, "utf8");

  assert.match(source, /report_visibility:\s*"workspace"/);
  assert.match(source, /analysis\.reportVisibility/);
  assert.match(source, /analysis\.reportVisibilityHint/);
  assert.match(source, /analysis\.visibility\.private/);
  assert.match(source, /analysis\.visibility\.workspace/);
  assert.match(source, /value=\{formState\.report_visibility\}/);
  assert.match(source, /report_visibility:\s*value as ReportVisibility/);
});

test("NewAnalysisForm lets users choose automatic or explicit CN exchange labels", () => {
  const source = readFileSync(formPath, "utf8");

  assert.match(source, /ticker_exchange:\s*"auto"/);
  assert.match(source, /analysis\.tickerExchange/);
  assert.match(source, /analysis\.tickerExchangeHint/);
  assert.match(source, /value=\{formState\.ticker_exchange \?\? "auto"\}/);
  assert.match(source, /ticker_exchange:\s*value as TaskCreateRequest\["ticker_exchange"\]/);
  assert.match(source, /<SelectItem value="auto">/);
  assert.match(source, /<SelectItem value="SH">/);
  assert.match(source, /<SelectItem value="SZ">/);
  assert.match(source, /<SelectItem value="BJ">/);
});

test("NewAnalysisForm lets the backend resolve the latest ready analysis date", () => {
  const source = readFileSync(formPath, "utf8");

  assert.doesNotMatch(source, /from "@\/lib\/localDate"/);
  assert.match(source, /analysis_date:\s*null/);
  assert.doesNotMatch(source, /analysis\.analysisDate/);
  assert.doesNotMatch(source, /type="date"/);
  assert.doesNotMatch(source, /new Date\(\)\.toISOString\(\)\.slice\(0,\s*10\)/);
});

test("NewAnalysisForm relies on automatic market data routing instead of a user selector", () => {
  const source = readFileSync(formPath, "utf8");

  assert.doesNotMatch(source, /market_data_source/);
  assert.doesNotMatch(source, /configOptions\.market_data_sources/);
  assert.doesNotMatch(source, /analysis\.marketDataSource/);
  assert.doesNotMatch(source, /analysis\.marketDataSourceHint/);
});

test("NewAnalysisForm preserves an open draft when the sidebar language default changes", () => {
  const source = readFileSync(formPath, "utf8");

  assert.match(source, /formState === null/);
  assert.match(source, /defaultOutputLanguageRef/);
  assert.match(source, /defaultOutputLanguageRef\.current = defaultOutputLanguage/);
  assert.match(source, /setFormState\(buildInitialFormState\(configOptions,\s*defaultOutputLanguageRef\.current\)\)/);
  assert.match(source, /setFormState\(null\)/);
  assert.match(source, /option\.value === defaultOutputLanguage/);
  assert.match(source, /\}, \[configOptions, formState, isOpen\]\);/);
  assert.doesNotMatch(
    source,
    /\}, \[configOptions, defaultOutputLanguage, formState, isOpen\]\);/
  );
});

test("NewAnalysisForm keeps tall dialog content inside an internal scroll container", () => {
  const source = readFileSync(formPath, "utf8");

  assert.match(source, /max-h-\[92vh\]/);
  assert.match(source, /overflow-y-auto/);
  assert.match(source, /scrollbar-hidden/);
  assert.match(source, /className="modal-panel scrollbar-hidden max-h-\[92vh\] max-w-3xl overflow-y-auto"/);
});

test("NewAnalysisForm keeps research depth descriptions contained within each option", () => {
  const source = readFileSync(formPath, "utf8");

  assert.match(
    source,
    /className=\{`h-auto w-full flex-col items-stretch justify-start overflow-hidden rounded-\[24px\] p-4 text-left whitespace-normal/
  );
  assert.match(source, /<p className="min-w-0 text-sm font-semibold">/);
  assert.match(source, /<p className="mt-2 min-w-0 break-words text-xs leading-5">/);
});
