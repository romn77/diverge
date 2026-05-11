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

test("admin LLM models page gives module defaults the analysis-style model picker", () => {
  const source = readFileSync(adminLLMModelsPagePath, "utf8");

  assert.match(source, /function ModuleSettingCard/);
  assert.match(source, /Model Profile/);
  assert.match(source, /CUSTOM_PROFILE_ID/);
  assert.match(source, /h-auto min-h-\[116px\] w-full flex-col/);
  assert.match(source, /LLM Provider/);
  assert.match(source, /Output Language/);
  assert.match(source, /Review Model/);
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
  assert.doesNotMatch(source, /<select[\s\S]{0,400}Model Profile/);
});
