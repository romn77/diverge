# 2026-05-22 Architecture Deepening Review Plan

This plan saves the architecture review from May 22, 2026 so the findings do
not live only in the temporary HTML report.

Temporary visual report:
`/tmp/architecture-review-20260522T111815+0800.html`

## Scope

Review Diverge Workbench for modules whose interface is shallow, where callers
must know too much of the implementation, and where a deeper module would
improve locality and leverage.

This is not an implementation plan yet. The next step is to pick one candidate
and run the grilling loop before proposing an interface.

## Domain And ADR Context

- Domain vocabulary: `docs/plans/CONTEXT.md`
- ADR context: `docs/adr/0001-journal-plans-use-existing-storage.md`

ADR-0001 says Trade Plans belong inside the Journal workflow and use the
existing file-backed Journal artifact pattern with database metadata when auth
is enabled. Candidates below should deepen that pattern, not replace it with a
plan-only database model.

## Top Recommendation

### Deepen Trade Plan Execution

**Recommendation strength:** Strong

**Files involved:**

- `web/backend/services/trades.py`
- `diverge/trade_plans.py`
- `diverge/trade_feedback.py`
- `web/backend/trade_entries.py`
- `web/backend/trade_plan_entries.py`
- `web/frontend/components/TradeRecordForm.tsx`
- `tests/test_trade_plans.py`

**Problem:**

The domain operation "Trade Plan becomes Trade Record" is one Journal workflow,
but the implementation is a caller protocol. The caller has to know the order:
validate plan link, build execution payload, create or update the Trade Record,
capture the Trade Plan Snapshot, mark the Trade Plan executed, sync two
metadata indexes, and maybe trigger Trade Reviews.

**Deepening direction:**

Concentrate that lifecycle in one Journal module. Keep the file-backed Journal
artifact pattern from ADR-0001, but move execution ordering, snapshot
immutability, one-plan-one-record checks, expiry checks, metadata sync, and
review triggering behind one seam.

**Benefits:**

- Locality: lifecycle rules concentrate in one module.
- Locality: snapshot immutability bugs are fixed once.
- Leverage: backend routes and tests cross one interface.
- Test surface: Trade Plan execution becomes testable as a workflow, not a
  sequence of helper calls.

**First grilling questions:**

- What is the exact domain operation name: "execute Trade Plan", "link Trade
  Plan", or a combined "materialize Trade Plan into Trade Record" concept?
- Should retroactive linking and direct execution share the same module, or
  share only internal implementation?
- Which side effects are part of the operation: metadata sync, audit event
  recording, automatic Trade Review generation, or only artifact mutation?
- What must remain outside the module because it belongs to route permissions,
  usage limits, or user-facing request handling?
- Which tests should become the public test surface for this module?

## Other Candidates To Revisit

### Deepen Journal Storage And Index Locality

**Recommendation strength:** Strong

**Files involved:**

- `web/backend/services/trades.py`
- `web/backend/trade_entries.py`
- `web/backend/trade_plan_entries.py`
- `diverge/trade_feedback.py`
- `diverge/trade_plans.py`
- `tests/web/test_trade_owner_scoping_backend.py`

**Problem:**

The storage seam is real but shallow. Callers still know file layout, owner and
tenant scoping, index projection, expiry materialization, stale metadata, and
review-count sync.

**Deepening direction:**

Create a deeper Journal storage module that owns artifact reads and writes,
status materialization, and projected database metadata. Keep file and database
adapters local to the module.

**ADR note:**

This aligns with ADR-0001 if it preserves file-backed Journal artifacts. A
DB-only rewrite would contradict ADR-0001.

### Collapse Factor-Snapshot Strategy Execution

**Recommendation strength:** Strong

**Files involved:**

- `diverge/screener/strategy_pipeline.py`
- `diverge/opportunity/radar.py`
- `diverge/screener/strategy_config.py`
- `diverge/screener/dsl.py`
- `diverge/screener/scoring.py`
- `diverge/screener/signal_builder.py`

**Problem:**

Screener strategy mode and Opportunity Radar duplicate strategy execution over
factor snapshots: normalization, condition-tree evaluation, weighted scoring,
ranking, candidate typing, matched rules, top-k selection, and signal events.

**Deepening direction:**

Make "strategy over factor snapshot" a deep module. Screener and Opportunity
Radar would become adapters around the same behavior, while artifact writing
stays local to each workflow.

### Deepen The Task Runtime Module

**Recommendation strength:** Worth exploring

**Files involved:**

- `web/backend/runtime/task_lifecycle.py`
- `web/backend/runtime/task_store.py`
- `web/backend/runtime/analysis_tasks.py`
- `web/backend/runtime/screener_tasks.py`
- `web/backend/runtime/data_sync_tasks.py`
- `web/backend/runtime/opportunity_tasks.py`
- `web/backend/runtime/backtest_tasks.py`
- `tests/web/test_task_lifecycle.py`

**Problem:**

The task lifecycle interface is shallow. Each task kind still assembles local
versus Redis storage, locks, event append, cancellation, quota waiting, and
job-record projection.

**Deepening direction:**

Let a deeper task runtime module own storage mode, state transitions, event
replay, delayed queue handling, and job-record side effects. Task kinds should
provide only their domain execution implementation and progress vocabulary.

### Deepen Data-Source Route Execution

**Recommendation strength:** Worth exploring

**Files involved:**

- `diverge/dataflows/interface.py`
- `diverge/dataflows/routes.py`
- `diverge/dataflows/vendor_usage.py`
- `web/backend/data_sources.py`
- `tests/dataflows/test_interface_routing.py`
- `tests/dataflows/test_router_executor_decoupling.py`
- `tests/dataflows/test_vendor_usage.py`

**Problem:**

Data-source routing has leverage, but the interface is still
implementation-shaped. Tests patch global vendor maps, route policy, database
fallback state, method argument schema, and quota details.

**Deepening direction:**

Put policy, adapter registry, symbol normalization, quota acquisition, fallback
error handling, and legacy error mapping behind a deeper route-execution
module.

### Make Plan Execution Assessment A Saved Concept

**Recommendation strength:** Worth exploring

**Files involved:**

- `docs/plans/CONTEXT.md`
- `diverge/trade_feedback.py`
- `web/backend/schemas/trades.py`
- `web/frontend/lib/api.ts`
- `web/frontend/components/TradeReviewForm.tsx`
- `tests/test_trade_feedback.py`

**Problem:**

CONTEXT says every Trade Review should include a Plan Execution Assessment, but
the saved interface only guarantees generic review strings. The invariant lives
mostly in prompt text and UI copy.

**Deepening direction:**

Move Plan Execution Assessment into the Trade Review module so AI-generated
reviews, manual saves, and consumers share one domain invariant.

## Deferred Candidates

These were real but less urgent than the candidates above:

- Report storage and metadata publication could become a deeper artifact module.
- Opportunity artifacts are stringly and could use named artifact access.
- `ScreenRunConfig` is deep for preset screening, but shallow when strategy mode
  fields are mixed into the same interface.

## Next Step

Pick one candidate for the grilling loop. Recommended first candidate:
**Deepen Trade Plan execution**.

The grilling loop should decide module naming, what lives behind the seam, which
side effects are inside the operation, and which tests define the interface.
