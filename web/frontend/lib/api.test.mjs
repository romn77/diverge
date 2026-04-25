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
