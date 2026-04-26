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

test("frontend API exposes AI-generated trade review creation endpoint", () => {
  assert.match(source, /interface TradeReviewCreateRequest/);
  assert.match(source, /export async function createTradeReview/);
  assert.match(source, /\/api\/trades\/\$\{tradeId\}\/reviews/);
  assert.match(source, /llm_provider/);
  assert.match(source, /model/);
  assert.match(source, /openai_reasoning_effort/);
  assert.match(source, /google_thinking_level/);
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
  assert.match(source, /export async function deleteTask/);
  assert.match(source, /export async function deleteScreenerTask/);
  assert.match(source, /method:\s*"DELETE"/);
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
