# TradingAgents v3 Next-Priority Roadmap

**Date:** 2026-03-20  
**Supersedes:** This document does not replace [2026-03-19-anthropic-financial-services-skills-adoption-v3.0.md](/home/ron/TradingAgents/docs/plans/2026-03-19-anthropic-financial-services-skills-adoption-v3.0.md). It defines the next execution order after the first v3 adoption tranche was completed.

## Current Baseline

The first v3 adoption tranche is already in place:

- native valuation package (`dcf`, `multiples`, `sensitivity`, formatter)
- fundamentals normalization layer
- valuation sections embedded into `fundamentals_report`
- earnings preview/review prompt helpers in existing analysts
- thesis tracking artifact persistence
- report viewer support for valuation-oriented fundamentals displays
- end-to-end Python and frontend verification coverage for the implemented tranche

The next phase should prioritize **productizing and stabilizing the embedded capabilities** before broadening scope into larger financial workflows.

## Scope

### In

- **Asset-type classification and DCF applicability**
  Reason: the current system can attempt DCF on ETFs or fund-like symbols such as `SPY`, producing technically correct but user-hostile output. This is the highest-value quality fix because it improves trust in every fundamentals report.

- **State and schema propagation for v3 metadata**
  Reason: the next tranche needs `instrument_type`, valuation applicability, and earnings context to move through the same report pipeline cleanly. That requires explicit propagation through normalized schemas, task payloads, and graph state rather than leaving these as implicit ad hoc fields. This also fixes an existing technical-debt pattern where `earnings_event` is currently accessed opportunistically by analysts without being formally declared in graph state.

- **Earnings input and event-context activation**
  Reason: earnings preview/review logic exists, but the current web path does not provide structured earnings event inputs. This leaves part of the v3 feature set inaccessible from the product.

- **Catalyst artifact layer**
  Reason: `catalyst-calendar` was explicitly deferred in v3 but is architecturally adjacent to the already implemented `thesis-tracker`. It can be added as an optional artifact without changing graph topology.

- **UI/testing polish for v3 entry points**
  Reason: recent issues were caused by integration gaps rather than algorithmic complexity: missing request payloads, misleading fallbacks, default analyst selection, and frontend API contract drift. The next phase should lock down these user-facing seams.

- **A documented validation matrix**
  Reason: v3 behavior depends on ticker type and analyst selection. Without a stable testing matrix, valid functionality can appear broken simply because the wrong instrument or analyst set was selected.

### Out

- **A new analyst node or graph branch**
  Reason: the current architecture decision is still sound. The main gaps are in capability activation, data eligibility, and UX, not in agent topology.

- **MCP/plugin runtime or connector-heavy workflows**
  Reason: they would expand operational scope and reintroduce external runtime complexity that v3 intentionally avoided.

- **Investment banking and wealth management skill families**
  Reason: they are outside the current TradingAgents core product loop and would dilute focus away from the report/research workflow already in progress.

- **Full 3-statement or model-update port**
  Reason: those require a richer and more reliable financial schema than the current first-pass valuation core. Doing them now would compound normalization complexity too early.

## Priority Roadmap

### P0: Productize The Current v3 Core

**Goal:** make the already-embedded functionality trustworthy in daily usage.

**Why first:** these are the issues most likely to be encountered immediately by real users.

#### Work items

- Extend normalized valuation schemas and graph state with explicit v3 metadata:
  - `instrument_type`
  - `valuation_applicability`
  - `valuation_applicability_reason`
  - earnings context fields or a structured `earnings_context`
  - Explicitly formalize the currently implicit `earnings_event` path by updating:
    - `tradingagents/agents/utils/agent_states.py`
    - `tradingagents/graph/propagation.py`
    - backend task/request flow that feeds graph execution
- Add instrument classification to normalized fundamentals inputs, including a first-pass distinction between operating companies and fund/ETF-style instruments.
  - Recommended classification strategy: ticker-pattern heuristics plus vendor metadata, with `yfinance` `quoteType` or equivalent vendor fields used when available.
  - Classification should happen during normalization, where raw vendor payloads are still available.
  - `instrument_type` should live on `ValuationInput` rather than on per-period financial snapshots.
- Gate DCF by valuation eligibility and render a deliberate “DCF not applicable” section for ETFs/funds instead of showing the current technical missing-FCF message.
  - Also remove the current silent-omission risk in the higher-level valuation injection path so non-DCF valuation failures do not disappear without explanation.
  - Replace the current bare `except Exception` valuation fallback in `tradingagents/agents/analysts/fundamentals_analyst.py` with classification-aware handling:
    - inapplicable assets render `DCF Not Applicable`
    - applicable assets with incomplete inputs render a data-insufficiency explanation
    - unexpected failures remain observable rather than being silently swallowed
- Surface asset-type and valuation-eligibility metadata in the fundamentals viewer so users can tell whether DCF was applied, skipped, or only multiples were shown.
  - Viewer behavior should be explicit:
    - show a visible `DCF Not Applicable` badge or status treatment
    - conditionally hide raw DCF tables when DCF is not applicable
    - continue rendering multiples and non-DCF fundamentals context
- Treat `tradingagents/agents/utils/fundamental_data_tools.py` as a critical integration target because `get_valuation_ready_fundamentals()` is the main call site that feeds the valuation pipeline from analysts.
- Ensure task request snapshots always reflect real form selections and avoid misleading fallback values for older or partial tasks.
- Keep the web defaults aligned with v3 validation goals, especially analyst selection and report path visibility.

#### Acceptance criteria

- `SPY`/ETF-like runs no longer produce raw DCF-missing-data errors in the fundamentals report.
- `SPY`/ETF-like runs show explicit DCF-inapplicability messaging instead of a technical missing-FCF message.
- Operating-company runs such as `AAPL` or `MSFT` still produce DCF + multiples when data is available.
- Viewer clearly communicates valuation applicability.
- Task detail UI shows consistent request state for new and legacy tasks.

### P1a: Activate Earnings Workflows End-To-End

**Goal:** expose the v3 earnings logic as a real product feature instead of a test-only capability.

**Why second:** the core helper logic exists, but users currently cannot drive it cleanly from the main workflow.

#### Work items

- Extend the task request contract to allow structured earnings inputs from the web UI.
  - This must be decomposed across:
    - backend request model (`TaskCreatePayload`)
    - frontend form and client types
    - persisted task snapshot payloads
    - graph state / `AgentState`
    - analyst prompt inputs
- Support two paths: manual earnings-event entry and auto-derived earnings context when vendor data is available.
- Add explicit UI risk controls for earnings entry:
  - use progressive disclosure
  - only show earnings-specific fields once earnings mode is enabled or an earnings date is entered
  - keep the default form understandable for non-earnings runs
- Add explicit earnings smoke tests for preview mode, review mode, and general fallback mode.

#### Acceptance criteria

- A user can launch a task with explicit earnings context from the UI.
- The report clearly indicates preview vs review vs general mode.

### P1b: Add Catalyst Artifacts And Viewer Support

**Goal:** turn the deferred catalyst-calendar idea into a lightweight artifact layer that complements thesis tracking.

**Why after P1a:** earnings without catalysts is already useful; catalysts without a stable earnings/context path is much less valuable.

#### Work items

- Define a catalyst artifact schema sized for an extractive first pass, with at least:
  - `ticker`
  - `generated_at`
  - `upcoming_events`
  - `description`
  - `source_section`
  - `raw_text`
  - optional `inferred_date`
- Decide data acquisition mode explicitly:
  - extractive first pass from existing report/news context
  - optional later enrichment from new data sources
- Persist catalyst artifacts beside thesis artifacts without adding required graph state keys.
- Surface upcoming/report-recap catalyst data in report viewer cards and markdown summaries.
- Add explicit catalyst artifact tests and viewer tests.

#### Acceptance criteria

- Catalyst data is persisted as an optional artifact and displayed without requiring a new route.
- The first pass works even when catalyst extraction is purely report-derived.

### P2: Broaden Valuation And Research Depth

**Goal:** extend coverage after the current v3 baseline is stable and well-activated.

**Why third:** these are useful, but they are less urgent than fixing applicability and activation gaps.

#### Work items

- Add `ratios.py` and grouped accounting-ratio sections promised by the original architecture.
  - Initial groups should be explicit:
    - liquidity
    - profitability
    - leverage
    - efficiency
    - cash-flow quality
- Expand from single-name multiples to first-pass peer comps.
- Add a constrained `sector-overview` workflow if it can remain report-first and reuse the current graph shape.
- Revisit `model-update` only after normalized financial input coverage is materially richer.

#### Acceptance criteria

- Fundamentals reports can show ratios and richer comparative context without breaking `fundamentals_report`.
- Peer comps remain optional and degrade gracefully when peer data is unavailable.
- No new graph branch is required to realize the added depth.

## Recommended Execution Order

1. Ship instrument classification and DCF gating.
2. In the same deliverable, propagate those fields through schemas, graph state, and task/report payloads.
3. In the same deliverable, add valuation applicability metadata to viewer/report output.
4. Expose earnings event inputs in the task contract, graph state, and web form.
5. Add catalyst artifact generation and viewer rendering.
6. Expand ratios and peer comps only after the above are stable.

## Validation Matrix

Use the following matrix for manual and automated smoke checks.

### Valuation applicability

- `AAPL` or `MSFT` with `news + fundamentals`
  Expected: DCF + multiples + thesis artifact.

- `SPY` or `QQQ` with `fundamentals`
  Expected: DCF skipped as not applicable; a visible applicability badge/status is present; raw DCF tables are hidden; multiples/fallback narrative still valid.

### Earnings workflows

- Preview case: operating company + future `earnings_date`
  Expected: earnings preview framing in both prompt and report.

- Review case: operating company + past `earnings_date` with reported fields
  Expected: post-earnings review framing in both prompt and report.

- General case: no earnings payload
  Expected: explicit general fallback section, no fabricated earnings narrative.

### Viewer/artifacts

- Completed run with fundamentals + news
  Expected: valuation-enhanced fundamentals cards and visible thesis artifact summary.

- Completed run with catalyst artifact
  Expected: thesis and catalyst summaries both visible without route expansion.

## Verification Commands

Python:

```bash
pytest tests/valuation tests/dataflows tests/agents tests/integration tests/web -q
```

Frontend:

```bash
cd web/frontend && npm test
cd web/frontend && npm run build
```

## Suggested Next Implementation Plan

If implementation starts immediately, the next concrete build sequence should be:

1. `instrument_type` and `valuation_applicability` in schemas/normalizer
2. explicit propagation of those fields, plus formal `earnings_event` support, through graph state and task/report payloads
3. DCF skip logic and ETF/fund report messaging through `fundamental_data_tools.py`, `fundamentals_analyst.py`, and viewer rendering
4. task contract extension for earnings event inputs
5. catalyst artifact persistence and viewer support
6. ratios and peer comps as the first expansion after stabilization
