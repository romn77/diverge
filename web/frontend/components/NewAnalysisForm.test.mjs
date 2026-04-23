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
  assert.match(source, /LLM Provider/i);
  assert.match(source, /Output Language/i);
  assert.match(source, /aria-label=\{t\("analysis\.dialog", "New analysis"\)\}/);
  assert.doesNotMatch(source, /AccessibleDialog/);
  assert.doesNotMatch(source, /<button/);
});

test("NewAnalysisForm disables providers without configured credentials", () => {
  const source = readFileSync(formPath, "utf8");

  assert.match(source, /provider\.enabled/);
  assert.match(source, /disabled=\{!provider\.enabled\}/);
  assert.match(source, /providerUnavailableLabel/);
  assert.match(source, /analysis\.disabledProvider/);
  assert.match(source, /analysis\.providerHint/);
  assert.match(source, /API key/i);
});

test("NewAnalysisForm defaults to the full analyst set instead of truncating to two", () => {
  const source = readFileSync(formPath, "utf8");

  assert.doesNotMatch(source, /analysts:\s*configOptions\.analysts\.slice\(0,\s*2\)/);
  assert.match(source, /analysts:\s*configOptions\.analysts\.map\(\(option\)\s*=>\s*option\.value\)/);
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
