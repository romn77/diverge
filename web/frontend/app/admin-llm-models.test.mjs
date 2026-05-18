import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import path from "node:path";
import test from "node:test";

const adminLLMModelsPagePath = path.join(
  import.meta.dirname,
  "admin",
  "llm-models",
  "page.tsx"
);

test("admin LLM models page makes module defaults a concrete global model picker", () => {
  const source = readFileSync(adminLLMModelsPagePath, "utf8");

  assert.match(source, /function ModuleSettingCard/);
  assert.doesNotMatch(source, /market_brief/);
  assert.doesNotMatch(source, /Enable Market Brief agent generation/);
  assert.doesNotMatch(source, /Brief Model/);
  assert.doesNotMatch(source, /No enabled brief models/);
  assert.doesNotMatch(source, /Save Market Brief Model/);
  assert.match(source, /LLM Provider/);
  assert.match(source, /Output Language/);
  assert.match(source, /Review Model/);
  assert.match(source, /model_profile:\s*"custom"/);
  assert.match(source, /Save Global Module Default/);
  assert.match(source, /OpenAI Reasoning Effort/);
  assert.match(source, /Google Thinking Level/);
  assert.match(source, /MODULE_OUTPUT_LANGUAGE_OPTIONS/);
  assert.match(source, /OPENAI_REASONING_OPTIONS/);
  assert.match(source, /GOOGLE_THINKING_OPTIONS/);
  assert.match(source, /ui_settings/);
  assert.match(source, /updateAdminLLMUiSetting/);
  assert.match(source, /saveUiSetting/);
  assert.match(source, /<Select value=\{value\} onValueChange=\{onChange\}>/);
  assert.match(source, /Only providers with configured API keys are shown/);
  assert.doesNotMatch(source, /Model Profile/);
  assert.doesNotMatch(source, /CUSTOM_PROFILE_ID/);
  assert.doesNotMatch(source, /h-auto min-h-\[116px\] w-full flex-col/);
});
