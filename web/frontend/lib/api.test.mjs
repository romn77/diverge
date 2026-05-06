import assert from "node:assert/strict";
import fs from "node:fs";
import path from "node:path";
import test from "node:test";

const source = fs.readFileSync(path.join("lib", "api.ts"), "utf8");

test("api client remains configurable for Vercel or separate backend deployments", () => {
  assert.match(source, /NEXT_PUBLIC_API_BASE_URL/);
  assert.doesNotMatch(source, /window\.location\.origin/);
  assert.doesNotMatch(source, /\/api\/healthz["'`]/);
});

test("frontend API exposes market resolution and AI-generated trade review endpoints", () => {
  assert.match(source, /interface MarketResolution/);
  assert.match(source, /export async function resolveMarketSymbol/);
  assert.match(source, /\/api\/market-resolution/);
  assert.match(source, /interface TradeReviewGenerateRequest/);
  assert.match(source, /export async function generateTradeReview/);
  assert.match(source, /\/api\/trades\/\$\{tradeId\}\/reviews\/\$\{reviewType\}\/generate/);
});

test("screener task stream resumes from a cursor instead of replaying all events", () => {
  assert.match(source, /progress_events:\s*ProgressEvent\[\]/);
  assert.match(source, /startCursor\s*=\s*0/);
  assert.match(source, /url\.searchParams\.set\("cursor", String\(startCursor\)\)/);
  assert.match(source, /new EventSource\(url\.toString\(\)/);
});

test("screener API types include US market data source selection", () => {
  assert.match(source, /us_data_sources:\s*Array/);
  assert.match(source, /us_data_source:\s*string/);
});

test("task APIs rely on automatic analysis data routing and expose failed task deletion", () => {
  assert.doesNotMatch(source, /market_data_sources:\s*SelectOption\[\]/);
  assert.doesNotMatch(source, /market_data_source:\s*string/);
  assert.match(source, /export type ReportVisibility = "private" \| "workspace"/);
  assert.match(source, /visibility\?:\s*ReportVisibility/);
  assert.match(source, /owner_user_id\?:\s*string \| null/);
  assert.match(source, /report_visibility:\s*ReportVisibility/);
  assert.match(source, /export async function deleteTask/);
  assert.match(source, /export async function deleteScreenerTask/);
  assert.match(source, /method:\s*"DELETE"/);
});

test("screener run summaries carry owner scope for workspace list badges", () => {
  assert.match(source, /interface ScreenerRunSummary/);
  assert.match(source, /owner_user_id\?:\s*string \| null/);
  assert.match(source, /tenant_id\?:\s*string \| null/);
  assert.match(source, /interface ScreenerPresetRecord/);
  assert.match(source, /export async function listScreenerPresets/);
  assert.match(source, /export async function replaceScreenerPresets/);
  assert.match(source, /\/api\/screener\/presets/);
});

test("task APIs expose Redis queue statuses, scheduling metadata, and cancel endpoints", () => {
  assert.match(source, /waiting_for_quota/);
  assert.match(source, /queue_position\?:\s*number \| null/);
  assert.match(source, /blocked_vendor\?:\s*string \| null/);
  assert.match(source, /blocked_until\?:\s*string \| null/);
  assert.match(source, /canceled_at\?:\s*string \| null/);
  assert.match(source, /export async function cancelTask/);
  assert.match(source, /export async function cancelScreenerTask/);
  assert.match(source, /\/api\/tasks\/\$\{taskId\}\/cancel/);
  assert.match(source, /\/api\/screener\/tasks\/\$\{taskId\}\/cancel/);
});

test("admin APIs expose data-source usage and configuration controls", () => {
  assert.match(source, /AdminDataSourceUsageResponse/);
  assert.match(source, /AdminDataSourceRoute/);
  assert.match(source, /AdminDataSourceUpdateRequest/);
  assert.match(source, /AdminDataSourceRouteUpdateRequest/);
  assert.match(source, /listAdminDataSources/);
  assert.match(source, /updateAdminDataSource/);
  assert.match(source, /updateAdminDataSourceRoute/);
  assert.match(source, /\/api\/admin\/data-sources/);
  assert.match(source, /\/api\/admin\/data-source-routes\/\$\{route\.module\}/);
});

test("admin APIs expose LLM model configuration controls without key values", () => {
  assert.match(source, /AdminLLMModelsResponse/);
  assert.match(source, /AdminLLMProvider/);
  assert.match(source, /key_status:\s*"configured" \| "missing"/);
  assert.match(source, /api_key_env:\s*string \| null/);
  assert.match(source, /listAdminLLMModels/);
  assert.match(source, /updateAdminLLMProvider/);
  assert.match(source, /updateAdminLLMModel/);
  assert.match(source, /updateAdminLLMProfileRoutes/);
  assert.match(source, /\/api\/admin\/llm-models/);
});

test("admin APIs expose the read-only task queue snapshot", () => {
  assert.match(source, /AdminTaskQueueResponse/);
  assert.match(source, /AdminTaskQueueItem/);
  assert.match(source, /kind:\s*"analysis" \| "screener" \| "data_sync"/);
  assert.match(source, /listAdminTaskQueue/);
  assert.match(source, /\/api\/admin\/task-queue/);
});

test("admin APIs expose tenant-scoped audit events with filters", () => {
  assert.match(source, /AdminAuditEvent/);
  assert.match(source, /AdminAuditEventsResponse/);
  assert.match(source, /AdminAuditEventsQuery/);
  assert.match(source, /listAdminAuditEvents/);
  assert.match(source, /\/api\/admin\/audit-events/);
  assert.match(source, /created_from/);
  assert.match(source, /created_to/);
  assert.match(source, /actor_user_id/);
});
