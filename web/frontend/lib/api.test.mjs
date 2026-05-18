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

test("auth API types expose username login while preserving email identity", () => {
  assert.match(source, /interface AuthUser[\s\S]*username:\s*string/);
  assert.match(source, /interface LoginRequest[\s\S]*account:\s*string/);
  assert.match(source, /interface AdminUserCreateRequest[\s\S]*username\?:\s*string/);
  assert.match(source, /interface AdminUserUpdateRequest[\s\S]*username\?:\s*string/);
});

test("frontend API exposes market resolution and AI-generated trade review endpoints", () => {
  assert.match(source, /interface MarketResolution/);
  assert.match(source, /export async function resolveMarketSymbol/);
  assert.match(source, /\/api\/market-resolution/);
  assert.match(source, /interface TradeReviewGenerateRequest/);
  assert.match(source, /export async function generateTradeReview/);
  assert.match(source, /\/api\/trades\/\$\{tradeId\}\/reviews\/\$\{reviewType\}\/generate/);
});

test("frontend API exposes the 7-day market brief index", () => {
  assert.match(source, /interface MarketBriefSummary/);
  assert.match(source, /interface MarketBriefIndexResponse/);
  assert.match(source, /export async function listMarketBriefs/);
  assert.doesNotMatch(source, /export async function createMarketBriefTask/);
  assert.doesNotMatch(source, /export async function listMarketBriefTasks/);
  assert.doesNotMatch(source, /export async function getMarketBriefTask/);
  assert.doesNotMatch(source, /export function subscribeToMarketBriefTask/);
  assert.match(source, /\/api\/market-briefs/);
  assert.match(source, /latest:\s*MarketBriefSummary \| null/);
  assert.match(source, /briefs:\s*MarketBriefSummary\[\]/);
});

test("journal APIs normalize legacy trade payloads before components receive them", () => {
  assert.match(source, /function normalizeTradeRecord\(value: unknown\): TradeRecord/);
  assert.match(source, /strategy_tags: normalizeStringArray\(record\.strategy_tags\)/);
  assert.match(
    source,
    /analysis_references: normalizeAnalysisReferences\(record\.analysis_references\)/
  );
  assert.match(source, /plan_execution: stringValue\(record\.plan_execution\)/);
  assert.match(source, /function normalizeTradeReview\(value: unknown/);
  assert.match(source, /improvement_actions: normalizeStringArray/);
  assert.match(source, /function normalizeTradeDetail\(value: unknown\): TradeDetail/);
  assert.match(source, /execution_note: stringValue\(record\.execution_note\)/);
  assert.match(source, /originating_plan_id: nullableStringValue\(record\.originating_plan_id\)/);
  assert.match(
    source,
    /originating_plan_snapshot: normalizeTradePlanSnapshot\(\s*record\.originating_plan_snapshot\s*\)/
  );
  assert.match(source, /return Array\.isArray\(data\) \? data\.map\(normalizeTradeRecord\) : \[\]/);
  assert.match(source, /return normalizeTradeDetail\(data\)/);
  assert.match(source, /return normalizeTradeReview\(data\)/);
});

test("trade plan APIs expose typed CRUD, execution, link, and payload normalization", () => {
  const tradeCreateRequest = source.match(/export interface TradeRecordCreateRequest \{[\s\S]*?\n\}/)?.[0] ?? "";
  const tradeUpdateRequest = source.match(/export interface TradeRecordUpdateRequest \{[\s\S]*?\n\}/)?.[0] ?? "";
  assert.match(source, /export interface TradePlan/);
  assert.match(source, /export interface TradePlanSnapshot/);
  assert.match(source, /export interface TradePlanCreateRequest/);
  assert.match(source, /export interface TradePlanUpdateRequest/);
  assert.match(source, /export interface TradePlanExecuteRequest/);
  assert.match(source, /export interface TradePlanLinkRequest/);
  assert.match(source, /function normalizeTradePlan\(value: unknown\): TradePlan/);
  assert.match(source, /function normalizeTradePlanSnapshot\(value: unknown\): TradePlanSnapshot \| null/);
  assert.match(source, /strategy_tags: normalizeStringArray\(plan\.strategy_tags\)/);
  assert.match(
    source,
    /analysis_references: normalizeAnalysisReferences\(plan\.analysis_references\)/
  );
  assert.match(source, /export async function listTradePlans/);
  assert.match(source, /export async function createTradePlan/);
  assert.match(source, /export async function getTradePlan/);
  assert.match(source, /export async function updateTradePlan/);
  assert.match(source, /export async function deleteTradePlan/);
  assert.match(source, /export async function executeTradePlan/);
  assert.match(source, /export async function linkTradeToPlan/);
  assert.match(source, /\/api\/trade-plans/);
  assert.match(source, /\/api\/trade-plans\/\$\{planId\}/);
  assert.match(source, /\/api\/trade-plans\/\$\{planId\}\/execute/);
  assert.match(source, /\/api\/trades\/\$\{tradeId\}\/link-plan/);
  assert.doesNotMatch(tradeCreateRequest, /originating_plan_id/);
  assert.doesNotMatch(tradeUpdateRequest, /originating_plan_id/);
  assert.doesNotMatch(tradeCreateRequest, /originating_plan_snapshot/);
  assert.doesNotMatch(tradeUpdateRequest, /originating_plan_snapshot/);
  assert.doesNotMatch(tradeCreateRequest, /execution_note/);
  assert.doesNotMatch(tradeUpdateRequest, /execution_note/);
});

test("screener task stream resumes from a cursor instead of replaying all events", () => {
  assert.match(source, /progress_events:\s*ProgressEvent\[\]/);
  assert.match(source, /startCursor\s*=\s*0/);
  assert.match(source, /url\.searchParams\.set\("cursor", String\(startCursor\)\)/);
  assert.match(source, /new EventSource\(url\.toString\(\)/);
});

test("opportunity task API exposes task polling, cancellation, and resumable streams", () => {
  assert.match(source, /export interface OpportunityTask/);
  assert.match(source, /export async function listOpportunityTasks/);
  assert.match(source, /export async function getOpportunityTask/);
  assert.match(source, /export async function cancelOpportunityTask/);
  assert.match(source, /export function subscribeToOpportunityTask/);
  assert.match(source, /\/api\/opportunities\/tasks/);
  assert.match(source, /\/api\/opportunities\/tasks\/\$\{taskId\}\/stream/);
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
  assert.match(source, /visibility_admin_override\?:\s*boolean/);
  assert.match(source, /owner_user_id\?:\s*string \| null/);
  assert.match(source, /report_visibility:\s*ReportVisibility/);
  assert.match(source, /export async function updateReportVisibility/);
  assert.match(source, /interface DeleteReportResponse/);
  assert.match(source, /export async function deleteReport/);
  assert.match(source, /\/api\/reports\/\$\{reportId\}/);
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
  assert.match(source, /cancel_requested_at\?:\s*string \| null/);
  assert.match(source, /canceled_at\?:\s*string \| null/);
  assert.match(source, /export async function cancelTask/);
  assert.match(source, /export async function cancelScreenerTask/);
  assert.match(source, /export async function cancelDataSyncJob/);
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

test("admin APIs expose search quota controls", () => {
  assert.match(source, /AdminSearchQuotaProvider/);
  assert.match(source, /AdminSearchQuotaResponse/);
  assert.match(source, /AdminSearchProviderUpdateRequest/);
  assert.match(source, /getAdminSearchQuota/);
  assert.match(source, /updateAdminSearchGlobal/);
  assert.match(source, /updateAdminSearchProvider/);
  assert.match(source, /reactivateAdminSearchProvider/);
  assert.match(source, /resetAdminSearchProviderUsage/);
  assert.match(source, /\/api\/admin\/search-quota/);
  assert.match(source, /\/api\/admin\/search-quota\/providers\/\$\{provider\}\/reactivate/);
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

test("admin APIs expose the task queue snapshot and stale queue cleanup", () => {
  assert.match(source, /AdminTaskQueueResponse/);
  assert.match(source, /AdminTaskQueueItem/);
  assert.match(source, /kind:\s*"analysis" \| "screener" \| "data_sync"/);
  assert.match(source, /runtime_present:\s*boolean/);
  assert.match(source, /stale:\s*boolean/);
  assert.match(source, /listAdminTaskQueue/);
  assert.match(source, /deleteAdminTaskQueueItem/);
  assert.match(source, /\/api\/admin\/task-queue/);
  assert.match(source, /\/api\/admin\/task-queue\/\$\{kind\}\/\$\{taskId\}/);
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
