# Anthropic Financial Services Skills Adoption v3.0 Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

> **Supersedes:** `docs/plans/002-fundamental-analysis-dcf.md`

**Goal:** Adapt the highest-fit skills from Anthropic's `financial-services-plugins` repository into Diverge as native Python tools, prompts, and report outputs without introducing a Claude plugin runtime dependency.

**Architecture:** Implement this in three waves. Wave 1 ports `dcf-model` and `comps-analysis` into a native valuation package and the existing fundamentals analyst. Wave 2 ports equity-research workflows such as `earnings-analysis` and `earnings-preview` into the existing research/report flow. Wave 3 adds persistent research artifacts inspired by `thesis-tracker` and `catalyst-calendar`, while preserving the current LangGraph graph shape and markdown-first report contract.

**Tech Stack:** Python 3.10+, LangGraph, LangChain, pytest, FastAPI, Next.js, markdown/json-highlights, existing vendor routing via `yfinance`, `alpha_vantage`, `akshare`, and `tushare`.

---

## Source scope

This plan selectively adopts ideas from the following Anthropic skill families:

- `financial-analysis/dcf-model`
- `financial-analysis/comps-analysis`
- `equity-research/earnings-analysis`
- `equity-research/earnings-preview`
- `equity-research/thesis-tracker`
- `equity-research/catalyst-calendar`

This plan explicitly does **not** try to import Anthropic's plugin runtime, MCP connector layer, Office/PowerPoint workflows, investment-banking skills, or wealth-management skills into the first implementation pass.

## Adoption decision

### Adopt now

- `dcf-model`
- `comps-analysis`
- `earnings-analysis`
- `earnings-preview`
- `thesis-tracker`

### Defer

- `catalyst-calendar`
- `sector-overview`
- `model-update`
- `3-statement-model`

### Do not port in this project phase

- `investment-banking/*`
- `wealth-management/*`
- Excel / PowerPoint oriented financial-analysis skills
- partner-built skills that require proprietary MCP connectors

## Constraints

- Keep the existing `market`, `social`, `news`, and `fundamentals` analyst graph topology intact for the first milestone.
- Preserve `fundamentals_report`, `news_report`, and other markdown report fields consumed downstream.
- Reuse `diverge.dataflows.interface` instead of adding direct provider calls inside analysts.
- Prefer structured calculation modules plus markdown formatters over adding new agent roles immediately.
- Add tests before introducing each calculation or output contract change.

## DCF and fundamentals architecture baseline

This section folds in the key decisions from the previous standalone DCF plan so that this v3.0 document is the only source of truth.

### Current repository baseline

- Diverge already has a `fundamentals` analyst and should not add a parallel analyst role for valuation.
- Existing fundamental data enters through `diverge.dataflows.interface` and its vendor routing layer.
- Existing downstream consumers expect markdown report fields such as `fundamentals_report`.
- The current web product is a report/task UI, not a dedicated interactive valuation workbench.

### DCF design rules

- Keep DCF, ratios, multiples, and sensitivity as pure calculation modules that do not depend on LLMs.
- Keep vendor-specific parsing out of analyst nodes and out of valuation functions.
- Feed valuation logic with normalized schema objects rather than raw provider payloads.
- Keep first-phase outputs markdown-first and compatible with the current report pipeline.
- Defer MCP, spreadsheet-native workflows, and standalone valuation APIs until the native valuation core is stable.

### Required valuation package shape

The first Wave 1 implementation should converge on this internal package:

```text
diverge/
├── valuation/
│   ├── __init__.py
│   ├── schemas.py
│   ├── dcf.py
│   ├── ratios.py
│   ├── multiples.py
│   ├── sensitivity.py
│   └── formatter.py
```

### Module responsibilities

#### `schemas.py`

- define normalized statement and market snapshot objects
- allow partial / missing values where real vendor data is incomplete
- represent reporting period, currency, report date, and market context

#### `dcf.py`

- project future FCF from historical inputs
- discount forecast cash flows
- compute terminal value
- bridge enterprise value to equity value
- compute per-share value
- reject invalid assumptions such as `wacc <= terminal_growth_rate`

#### `ratios.py`

- calculate grouped liquidity, profitability, leverage, efficiency, and cash flow quality ratios
- protect all ratio calculations against zero or missing denominators
- use explicit accounting-field provenance

#### `multiples.py`

- support first-pass single-name outputs for `P/E`, `P/B`, `EV/EBITDA`, `EV/Sales`, and `FCF Yield`
- treat peer comps as a later extension, not a Wave 1 requirement

#### `sensitivity.py`

- run DCF sensitivity outside the base DCF function
- avoid recursive self-calls from the main DCF calculation path

#### `formatter.py`

- render valuation outputs as markdown sections and tables
- emit report-friendly summaries and `json-highlights` compatible structures

### Output contract

Wave 1 must keep the current markdown report contract intact:

- continue writing `fundamentals_report: str`
- include DCF summary, multiples summary, assumptions, and sensitivity summary in the report body
- keep structured payloads optional and additive, not required for downstream graph nodes
- if structured artifacts are persisted, save them alongside reports rather than replacing report text

### Data source strategy

- Keep using the current vendor routing system in Wave 1
- Normalize `yfinance`, `alpha_vantage`, `tushare`, and `akshare` outputs into common valuation schemas
- Treat Financial Modeling Prep and other new providers as optional future enhancements, not prerequisites

## Task 1: Create the native valuation package for Anthropic financial-analysis skill adoption

**Files:**
- Create: `diverge/valuation/__init__.py`
- Create: `diverge/valuation/schemas.py`
- Create: `diverge/valuation/dcf.py`
- Create: `diverge/valuation/multiples.py`
- Create: `diverge/valuation/sensitivity.py`
- Create: `tests/valuation/test_dcf.py`
- Create: `tests/valuation/test_multiples.py`

**Step 1: Write the failing tests**

Create `tests/valuation/test_dcf.py` and `tests/valuation/test_multiples.py` with cases for:

- valid DCF base calculation
- invalid `wacc <= terminal_growth_rate`
- missing shares outstanding
- EV to equity value conversion with net debt
- multiple calculation with missing denominators

**Step 2: Run tests to verify they fail**

Run: `pytest tests/valuation/test_dcf.py tests/valuation/test_multiples.py -q`

Expected: FAIL because the new valuation package does not exist yet.

**Step 3: Write minimal implementation**

Implement:

- dataclasses / typed models for normalized valuation input
- a pure `calculate_dcf(...)` function
- a pure `calculate_multiples(...)` function
- a separate sensitivity helper instead of recursive DCF self-calls

**Step 4: Run tests to verify they pass**

Run: `pytest tests/valuation/test_dcf.py tests/valuation/test_multiples.py -q`

Expected: PASS

**Step 5: Commit**

```bash
git add diverge/valuation tests/valuation
git commit -m "feat: add native valuation package for skill adoption"
```

## Task 2: Add a normalization layer that converts current vendor outputs into valuation-ready inputs

**Files:**
- Create: `diverge/dataflows/fundamentals_normalizer.py`
- Modify: `diverge/dataflows/interface.py`
- Create: `tests/dataflows/test_fundamentals_normalizer.py`
- Modify: `tests/dataflows/test_interface_routing.py`

**Step 1: Write the failing test**

Create `tests/dataflows/test_fundamentals_normalizer.py` with cases for:

- Alpha Vantage style statement payload normalization
- yfinance style statement payload normalization
- CN vendor payload normalization with missing fields
- explicit error messages for non-normalizable payloads

**Step 2: Run test to verify it fails**

Run: `pytest tests/dataflows/test_fundamentals_normalizer.py tests/dataflows/test_interface_routing.py -q`

Expected: FAIL because the normalization layer and routing hook do not exist yet.

**Step 3: Write minimal implementation**

Implement a normalization helper that:

- accepts raw vendor strings / dict-like outputs
- extracts the minimum fields required by DCF and multiples
- tags market, currency, report frequency, and report date
- returns a valuation-ready schema object

Do not replace existing routing behavior. Add this as a downstream adapter only.

**Step 4: Run tests to verify it passes**

Run: `pytest tests/dataflows/test_fundamentals_normalizer.py tests/dataflows/test_interface_routing.py -q`

Expected: PASS

**Step 5: Commit**

```bash
git add diverge/dataflows tests/dataflows
git commit -m "feat: add fundamentals normalization for valuation workflows"
```

## Task 3: Integrate `dcf-model` and `comps-analysis` into the existing fundamentals analyst

**Files:**
- Modify: `diverge/agents/analysts/fundamentals_analyst.py`
- Create: `diverge/valuation/formatter.py`
- Modify: `diverge/agents/utils/fundamental_data_tools.py`
- Create: `tests/agents/test_fundamentals_prompt_highlights.py`
- Modify: `tests/agents/test_prompt_highlights_runtime.py`

**Step 1: Write the failing test**

Create `tests/agents/test_fundamentals_prompt_highlights.py` with assertions that a fundamentals report now contains:

- DCF summary section
- multiples summary section
- assumptions section
- unchanged `json-highlights` fence category of `fundamentals`

**Step 2: Run test to verify it fails**

Run: `pytest tests/agents/test_fundamentals_prompt_highlights.py tests/agents/test_prompt_highlights_runtime.py -q`

Expected: FAIL because the report formatter does not yet include valuation sections.

**Step 3: Write minimal implementation**

Implement a formatter that converts valuation outputs into markdown blocks and insert those blocks into the fundamentals analyst flow after tool retrieval and normalization.

Do not change the state field name from `fundamentals_report`.

**Step 4: Run test to verify it passes**

Run: `pytest tests/agents/test_fundamentals_prompt_highlights.py tests/agents/test_prompt_highlights_runtime.py -q`

Expected: PASS

**Step 5: Commit**

```bash
git add diverge/agents diverge/valuation tests/agents
git commit -m "feat: integrate valuation skills into fundamentals analyst"
```

## Task 4: Port `earnings-analysis` and `earnings-preview` into the current research flow without adding a new graph branch

**Files:**
- Create: `diverge/research/__init__.py`
- Create: `diverge/research/earnings.py`
- Modify: `diverge/agents/analysts/news_analyst.py`
- Modify: `diverge/agents/analysts/fundamentals_analyst.py`
- Create: `tests/agents/test_earnings_workflow_prompts.py`

**Step 1: Write the failing test**

Create `tests/agents/test_earnings_workflow_prompts.py` with cases for:

- earnings preview mode prompt structure
- post-earnings analysis mode prompt structure
- fallback behavior when no earnings-specific event data is available

**Step 2: Run test to verify it fails**

Run: `pytest tests/agents/test_earnings_workflow_prompts.py -q`

Expected: FAIL because the earnings research helper does not exist yet.

**Step 3: Write minimal implementation**

Implement a small earnings research helper that:

- detects whether the current context is preview vs post-earnings
- injects the correct prompt framing into existing analyst workflows
- produces markdown sections that fit into current report outputs

Do not add a fifth analyst node in the first pass.

**Step 4: Run test to verify it passes**

Run: `pytest tests/agents/test_earnings_workflow_prompts.py -q`

Expected: PASS

**Step 5: Commit**

```bash
git add diverge/research diverge/agents tests/agents
git commit -m "feat: add earnings preview and analysis workflows"
```

## Task 5: Add thesis tracking inspired by Anthropic's `thesis-tracker`

**Files:**
- Create: `diverge/research/thesis_tracker.py`
- Modify: `diverge/runner.py`
- Modify: `web/backend/main.py`
- Create: `tests/agents/test_thesis_tracker.py`
- Create: `tests/web/test_thesis_artifact_listing.py`

**Step 1: Write the failing test**

Create tests that assert:

- a thesis artifact can be created from a completed report
- thesis artifact serialization does not break existing report saving
- web backend can expose the saved artifact path or metadata if present

**Step 2: Run test to verify it fails**

Run: `pytest tests/agents/test_thesis_tracker.py tests/web/test_thesis_artifact_listing.py -q`

Expected: FAIL because the tracker and artifact exposure do not exist yet.

**Step 3: Write minimal implementation**

Implement thesis tracking as a saved artifact alongside report output, not as a new required state field for every graph node.

The tracker should capture:

- thesis summary
- supporting evidence
- invalidation signals
- next catalysts

**Step 4: Run test to verify it passes**

Run: `pytest tests/agents/test_thesis_tracker.py tests/web/test_thesis_artifact_listing.py -q`

Expected: PASS

**Step 5: Commit**

```bash
git add diverge/research diverge/runner.py web/backend/main.py tests/agents tests/web
git commit -m "feat: add thesis tracking artifacts for research flows"
```

## Task 6: Surface the new structured skill outputs in the existing web viewer

**Files:**
- Modify: `web/frontend/lib/highlightTerminal.ts`
- Modify: `web/frontend/components/HighlightCards.tsx`
- Modify: `web/frontend/components/ReportViewer.tsx`
- Create: `web/frontend/lib/highlightTerminalSkillAdoption.test.ts`
- Modify: `web/frontend/components/HighlightCards.test.ts`

**Step 1: Write the failing test**

Add tests for:

- valuation-oriented fundamentals highlight rendering
- thesis artifact summary rendering when present
- graceful fallback when the new sections are absent

**Step 2: Run test to verify it fails**

Run: `cd web/frontend && npm test`

Expected: FAIL because the frontend parsers and cards do not understand the new sections yet.

**Step 3: Write minimal implementation**

Update the viewer and highlight parsing so that:

- existing reports still render unchanged
- new valuation sections show up as richer fundamentals cards
- thesis summaries are visible without requiring a new route

**Step 4: Run test to verify it passes**

Run: `cd web/frontend && npm test`

Expected: PASS

**Step 5: Commit**

```bash
git add web/frontend
git commit -m "feat: surface adopted skill outputs in report viewer"
```

## Task 7: Run an end-to-end validation pass for the selected skill adoption set

**Files:**
- Modify: `docs/plans/002-fundamental-analysis-dcf.md`
- Create: `tests/integration/test_skill_adoption_flow.py`
- Modify: `tests/web/test_runner.py`

**Step 1: Write the failing test**

Create an integration test that verifies a representative ticker flow can:

- fetch existing fundamentals data
- normalize it
- generate valuation sections
- produce a stable fundamentals report
- save compatible report artifacts

**Step 2: Run test to verify it fails**

Run: `pytest tests/integration/test_skill_adoption_flow.py tests/web/test_runner.py -q`

Expected: FAIL before the integration is complete.

**Step 3: Write minimal implementation**

Patch integration gaps only. Do not broaden scope to catalyst calendars, new analyst nodes, or MCP support during this step.

**Step 4: Run the verification suite**

Run: `pytest tests/valuation tests/dataflows tests/agents tests/integration tests/web -q`

Expected: PASS

Run: `cd web/frontend && npm test`

Expected: PASS

**Step 5: Commit**

```bash
git add docs/plans tests
git commit -m "test: verify anthropic skill adoption flow end-to-end"
```

## Rollout notes

- Roll out Wave 1 before touching earnings workflows.
- Ship thesis tracking as an optional artifact, not a required graph state key.
- Keep `catalyst-calendar` as a follow-up after thesis tracking proves useful.
- Do not start MCP or partner-built connector work inside this plan.

## Definition of done

- `dcf-model` and `comps-analysis` ideas exist as native Diverge valuation modules.
- fundamentals reports contain structured valuation summaries without breaking downstream consumers.
- earnings preview and post-earnings analysis have reusable prompt/workflow helpers.
- thesis tracking exists as an optional report artifact.
- web viewer can render the new valuation-oriented highlights.
- the full Python and frontend verification suite passes.
