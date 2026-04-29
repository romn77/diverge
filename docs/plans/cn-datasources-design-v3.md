# CN Data Sources Integration V3 (akshare + tushare)

## TL;DR
> **Summary**: Add CN-market data support by extending the existing vendor routing architecture (not replacing it), preserving all current tool interfaces while introducing market-aware symbol resolution and semantic fallback.
> **Deliverables**:
> - Market-aware router layer in `diverge/dataflows/interface.py`
> - New CN vendor adapters for `akshare` and `tushare`
> - Unified vendor error taxonomy + fallback policy
> - Config precedence preserved (`tool_vendors > market_overrides > data_vendors > available vendors`)
> - Test matrix for symbol detection, routing, fallback, config merge, and end-to-end CLI flow
> **Effort**: Large
> **Parallel**: YES - 2 waves
> **Critical Path**: Task 1 → Task 3 → Task 4 → Task 6 → Task 9 → Task 10

## Context
### Original Request
User asked to review `docs/plans/2026-03-10-cn-datasources-design.md` and then requested: “整理成v3版本”.

### Interview Summary
- Keep current architecture contracts stable.
- Produce a corrected v3 that is implementation-ready.
- Preserve current tool signatures and avoid breaking current US flow.

### Metis Review (gaps addressed)
- Add explicit handling for legacy vendor string errors (not only exceptions) so fallback actually triggers.
- Resolve config shallow-merge risk before introducing nested `market_overrides` behavior.
- Make `METHOD_ARG_SCHEMA` and symbol detection fully test-backed to avoid signature-drift coupling.
- Clarify `VendorAuthError` and `VendorDataEmptyError` policy (skip/abort rules) per method class.

## Work Objectives
### Core Objective
Deliver a backward-compatible CN datasource integration architecture that supports `akshare` and `tushare` under the existing `route_to_vendor` model with deterministic routing and robust fallback.

### Deliverables
- Router enhancements (`METHOD_ARG_SCHEMA`, `resolve_market_and_symbol`, `build_vendor_chain`, semantic fallback).
- CN utilities (`cn_market_utils`) and vendor error classes (`vendor_errors`).
- New CN vendor adapters and registration in `VENDOR_METHODS`.
- Indicator path correction to avoid hardwired yfinance dependence when CN vendors are selected.
- Contract/routing/fallback/config/e2e tests and docs updates.

### Definition of Done (verifiable conditions with commands)
- `pytest tests/dataflows -q` passes with new routing and fallback tests.
- `pytest tests/integration -q` passes for method contract and symbol routing coverage.
- `python -m cli.main` can run a CN ticker path without router exceptions when config points to CN vendors.
- `python - <<'PY'\nfrom diverge.dataflows.interface import route_to_vendor\nprint(type(route_to_vendor('get_global_news','2024-06-01',7,3)).__name__)\nPY` prints `str`.

### Must Have
- No breaking changes to signatures in:
  - `diverge/agents/utils/core_stock_tools.py`
  - `diverge/agents/utils/technical_indicators_tools.py`
  - `diverge/agents/utils/fundamental_data_tools.py`
  - `diverge/agents/utils/news_data_tools.py`
- Router precedence preserved and documented.
- CN ticker normalization supports at least: `600519`, `sh600519`, `600519.SH`, `SZ000001`.
- Non-ticker method (`get_global_news`) bypasses ticker market detection logic.

### Must NOT Have (guardrails, AI slop patterns, scope boundaries)
- Must NOT create parallel routing subsystem outside `route_to_vendor`.
- Must NOT introduce `cn_*` tool categories.
- Must NOT silently swallow auth/data-empty errors without policy.
- Must NOT change output contract away from `str` for existing tool methods.
- Must NOT rely on implicit `args[0]` ticker guessing.

## Verification Strategy
> ZERO HUMAN INTERVENTION — all verification is agent-executed.
- Test decision: tests-after + pytest (existing repo style)
- QA policy: Every task includes agent-run happy + edge/failure scenario.
- Evidence: `.sisyphus/evidence/task-{N}-{slug}.{ext}`

## Execution Strategy
### Parallel Execution Waves
> Target: 5-8 tasks per wave. <3 per wave (except final) = under-splitting.

Wave 1 (Foundation and contracts): Tasks 1, 2, 3, 4, 5
Wave 2 (Integration and validation): Tasks 6, 7, 8, 9, 10

### Dependency Matrix (full, all tasks)
| Task | Blocks | Blocked By |
|---|---|---|
| 1 | 4, 9 | - |
| 2 | 4, 6, 9 | - |
| 3 | 4, 9 | - |
| 4 | 6, 7, 8, 9, 10 | 1,2,3 |
| 5 | 6, 7 | 2 |
| 6 | 7, 8, 9, 10 | 4,5 |
| 7 | 9,10 | 4,6 |
| 8 | 9,10 | 4,6 |
| 9 | 10 | 4,6,7,8 |
| 10 | - | 4,6,7,8,9 |

### Agent Dispatch Summary (wave → task count → categories)
- Wave 1 → 5 tasks → deep / unspecified-high / quick
- Wave 2 → 5 tasks → unspecified-high / deep / writing

## TODOs
> Implementation + Test = ONE task. Never separate.
> EVERY task MUST have: Agent Profile + Parallelization + QA Scenarios.

- [ ] 1. Introduce unified vendor error semantics and legacy error adapter

  **What to do**: Create `diverge/dataflows/vendor_errors.py` with `VendorRetryableError`, `VendorAuthError`, `VendorNotSupportedError`, `VendorDataEmptyError`. Add routing-level adapter utility (same module or `interface.py` private helper) that maps legacy vendor return strings like `"Error ..."` / `"No data found ..."` into typed exceptions before fallback evaluation.
  **Must NOT do**: Do not change public tool signatures or return type contract (`str`).

  **Recommended Agent Profile**:
  - Category: `unspecified-high` — Reason: Cross-cutting behavior change with compatibility risk.
  - Skills: [`software-architecture`] — preserve boundary and error semantics.
  - Omitted: [`frontend-patterns`] — not relevant to backend routing.

  **Parallelization**: Can Parallel: YES | Wave 1 | Blocks: 4,9 | Blocked By: none

  **References** (executor has NO interview context — be exhaustive):
  - Pattern: `diverge/dataflows/interface.py:133-161` — current fallback loop and vendor call flow.
  - Pattern: `diverge/dataflows/alpha_vantage_common.py:38-78` — existing typed exception precedent.
  - API/Type: `diverge/agents/utils/core_stock_tools.py:22` — downstream expects string returns from routed tools.

  **Acceptance Criteria** (agent-executable only):
  - [ ] `python - <<'PY'\nfrom diverge.dataflows import interface\nassert hasattr(interface, 'route_to_vendor')\nprint('ok')\nPY` succeeds.
  - [ ] Unit tests include string-error mapping coverage for at least one legacy vendor failure string.

  **QA Scenarios** (MANDATORY — task incomplete without these):
  ```
  Scenario: Legacy error string triggers fallback path
    Tool: Bash
    Steps: Run `pytest tests/dataflows/test_vendor_error_mapping.py -q`
    Expected: Test proves error string converts to typed error and fallback decision branch executes
    Evidence: .sisyphus/evidence/task-1-vendor-errors.log

  Scenario: Non-error string remains pass-through
    Tool: Bash
    Steps: Run `pytest tests/dataflows/test_vendor_error_mapping.py::test_non_error_string_passthrough -q`
    Expected: Returns original payload string; no exception remap
    Evidence: .sisyphus/evidence/task-1-vendor-errors-edge.log
  ```

  **Commit**: YES | Message: `feat(dataflows): add vendor error taxonomy and legacy error adapter` | Files: `diverge/dataflows/vendor_errors.py`, `diverge/dataflows/interface.py`, `tests/dataflows/test_vendor_error_mapping.py`

- [ ] 2. Add CN market symbol normalization and method argument schema contract

  **What to do**: Create `diverge/dataflows/cn_market_utils.py` with explicit parser for `600519`, `sh600519`, `600519.SH`, `SZ000001`; implement deterministic `detect_market` rules and normalization map (`akshare`, `tushare`). Define `METHOD_ARG_SCHEMA` in `interface.py` and ensure no-ticker methods are explicitly marked. Market resolution rule must be exact: (a) if `config.market` is `cn`/`us`, force that market, (b) if `config.market == 'auto'` and symbol matches CN parser, use `cn`, (c) otherwise use `us`, (d) no-ticker methods use `global`.
  **Must NOT do**: Do not infer market by loose substring heuristics or unsafe string stripping like `lstrip('SH')`.

  **Recommended Agent Profile**:
  - Category: `deep` — Reason: Ambiguous symbol edge-cases require deterministic design.
  - Skills: [`software-architecture`] — keep parser rules explicit and testable.
  - Omitted: [`api-design`] — no external API contract changes.

  **Parallelization**: Can Parallel: YES | Wave 1 | Blocks: 4,6,9 | Blocked By: none

  **References** (executor has NO interview context — be exhaustive):
  - Pattern: `docs/plans/2026-03-10-cn-datasources-design.md:74-90` — intended `METHOD_ARG_SCHEMA` and resolver behavior.
  - API/Type: `diverge/agents/utils/news_data_tools.py:39` — `get_global_news` has no ticker and must bypass ticker detection.
  - Pattern: `diverge/agents/utils/fundamental_data_tools.py:20-77` — ticker-bearing methods and argument positions.

  **Acceptance Criteria** (agent-executable only):
  - [ ] Parser tests pass for all accepted symbol variants and canonical outputs.
  - [ ] `get_global_news` route path test confirms market resolution does not inspect ticker.

  **QA Scenarios** (MANDATORY — task incomplete without these):
  ```
  Scenario: CN symbol variants normalize deterministically
    Tool: Bash
    Steps: Run `pytest tests/dataflows/test_cn_market_utils.py -q`
    Expected: All listed input variants map to expected canonical + vendor-specific format
    Evidence: .sisyphus/evidence/task-2-cn-symbols.log

  Scenario: Ambiguous/unknown symbol handled explicitly
    Tool: Bash
    Steps: Run `pytest tests/dataflows/test_cn_market_utils.py::test_unknown_symbol_policy -q`
    Expected: Returns configured fallback market behavior (documented, deterministic)
    Evidence: .sisyphus/evidence/task-2-cn-symbols-edge.log
  ```

  **Commit**: YES | Message: `feat(router): add cn symbol normalization and method arg schema` | Files: `diverge/dataflows/cn_market_utils.py`, `diverge/dataflows/interface.py`, `tests/dataflows/test_cn_market_utils.py`

- [ ] 3. Extend config safely with deep-merge semantics and market overrides

  **What to do**: Update `diverge/default_config.py` with `market`, `market_overrides`, `tushare_token`. Update `diverge/dataflows/config.py` so `set_config()` deep-merges nested dictionaries (instead of shallow replace) to preserve defaults and partial override behavior.
  **Must NOT do**: Do not break existing callers that pass partial `data_vendors` / `tool_vendors` configs.

  **Recommended Agent Profile**:
  - Category: `unspecified-high` — Reason: Global config behavior change affects all dataflows.
  - Skills: [`software-architecture`] — ensure compatibility and deterministic precedence.
  - Omitted: [`backend-patterns`] — not needed beyond configuration layer.

  **Parallelization**: Can Parallel: YES | Wave 1 | Blocks: 4,9 | Blocked By: none

  **References** (executor has NO interview context — be exhaustive):
  - Pattern: `diverge/default_config.py:25-34` — existing vendor config shape.
  - Pattern: `diverge/dataflows/config.py:15-21` — current shallow `.update()` implementation.
  - API/Type: `diverge/graph/trading_graph.py:60` — global config injection path (`set_config`).

  **Acceptance Criteria** (agent-executable only):
  - [ ] Deep-merge test verifies partial nested override does not erase sibling defaults.
  - [ ] Existing minimal config initialization path still works without market-specific keys.

  **QA Scenarios** (MANDATORY — task incomplete without these):
  ```
  Scenario: Partial nested override preserves defaults
    Tool: Bash
    Steps: Run `pytest tests/dataflows/test_config_merge.py::test_market_override_deep_merge -q`
    Expected: `us`/other category entries remain after applying partial `cn` override
    Evidence: .sisyphus/evidence/task-3-config-merge.log

  Scenario: Backward compatibility with old config payload
    Tool: Bash
    Steps: Run `pytest tests/dataflows/test_config_merge.py::test_legacy_config_payload_still_valid -q`
    Expected: No key errors; routing config still resolves
    Evidence: .sisyphus/evidence/task-3-config-merge-edge.log
  ```

  **Commit**: YES | Message: `feat(config): add market overrides with safe deep-merge` | Files: `diverge/default_config.py`, `diverge/dataflows/config.py`, `tests/dataflows/test_config_merge.py`

- [ ] 4. Refactor router with deterministic precedence and semantic fallback policy

  **What to do**: Implement `resolve_market_and_symbol()` and `build_vendor_chain()` in `interface.py`. Enforce precedence order: `tool_vendors` > `market_overrides[market][category]` > `data_vendors[category]` > method-available vendors. Apply semantic fallback policy table exactly as: `VendorRetryableError -> try next vendor`; `VendorNotSupportedError -> try next vendor`; `VendorAuthError -> skip current vendor, continue next`; `VendorDataEmptyError -> try next vendor`; after chain exhausted, raise runtime error with attempted vendor list.
  **Must NOT do**: Do not remove current category/tool routing concepts; extend them.

  **Recommended Agent Profile**:
  - Category: `deep` — Reason: Core routing behavior with multiple coupled conditions.
  - Skills: [`software-architecture`, `api-design`] — deterministic dispatch policy.
  - Omitted: [`frontend-patterns`] — irrelevant.

  **Parallelization**: Can Parallel: NO | Wave 1 | Blocks: 6,7,8,9,10 | Blocked By: 1,2,3

  **References** (executor has NO interview context — be exhaustive):
  - Pattern: `diverge/dataflows/interface.py:118-131` — current vendor selection behavior.
  - Pattern: `diverge/dataflows/interface.py:133-161` — current call/fallback loop.
  - Pattern: `docs/plans/2026-03-10-cn-datasources-design.md:91-103` — target fallback semantics.

  **Acceptance Criteria** (agent-executable only):
  - [ ] Routing tests confirm precedence order exactly as specified.
  - [ ] Exception-policy tests confirm per-error fallback/abort behavior.

  **QA Scenarios** (MANDATORY — task incomplete without these):
  ```
  Scenario: Precedence chain behaves deterministically
    Tool: Bash
    Steps: Run `pytest tests/dataflows/test_router_precedence.py -q`
    Expected: `tool_vendors` override wins over market/category defaults in all covered methods
    Evidence: .sisyphus/evidence/task-4-router-precedence.log

  Scenario: Auth error skips/aborts per policy table
    Tool: Bash
    Steps: Run `pytest tests/dataflows/test_router_fallback_policy.py::test_auth_error_policy -q`
    Expected: Behavior matches documented policy table exactly
    Evidence: .sisyphus/evidence/task-4-router-policy-edge.log
  ```

  **Commit**: YES | Message: `feat(router): add market-aware dispatch and semantic fallback` | Files: `diverge/dataflows/interface.py`, `tests/dataflows/test_router_precedence.py`, `tests/dataflows/test_router_fallback_policy.py`

- [ ] 5. Add minimal CN vendor adapters (consolidated modules first)

  **What to do**: Implement consolidated vendor modules first: `diverge/dataflows/akshare.py` and `diverge/dataflows/tushare.py` covering phase-1 methods (`get_stock_data`, `get_fundamentals`, `get_balance_sheet`, `get_cashflow`, `get_income_statement`). Keep dispatcher API aligned with `VENDOR_METHODS` expectations.
  **Must NOT do**: Do not split into 12 files in first pass; avoid scope bloat until core route is stable.

  **Recommended Agent Profile**:
  - Category: `unspecified-high` — Reason: Multiple external integrations + compatibility constraints.
  - Skills: [`software-architecture`, `backend-patterns`] — robust adapters with minimal surface.
  - Omitted: [`frontend-patterns`] — irrelevant.

  **Parallelization**: Can Parallel: YES | Wave 1 | Blocks: 6,7 | Blocked By: 2

  **References** (executor has NO interview context — be exhaustive):
  - Pattern: `diverge/dataflows/alpha_vantage.py` — vendor dispatcher-style export pattern.
  - Pattern: `diverge/dataflows/y_finance.py:8-47,295-463` — existing method return style (`str`, readable header + content).
  - External: `https://tushare.pro/document/1?doc_id=40` — token/init requirements.

  **Acceptance Criteria** (agent-executable only):
  - [ ] New modules expose callable functions matching router method signatures.
  - [ ] Missing token path raises/returns mapped auth error for tushare adapter.

  **QA Scenarios** (MANDATORY — task incomplete without these):
  ```
  Scenario: Tushare adapter token-required behavior
    Tool: Bash
    Steps: Run `pytest tests/dataflows/test_tushare_adapter.py::test_missing_token_policy -q`
    Expected: Emits mapped auth error path matching router policy
    Evidence: .sisyphus/evidence/task-5-vendor-adapters.log

  Scenario: Akshare adapter returns formatted string payload
    Tool: Bash
    Steps: Run `pytest tests/dataflows/test_akshare_adapter.py::test_stock_data_returns_string -q`
    Expected: Type is `str`, content non-empty for mocked vendor response
    Evidence: .sisyphus/evidence/task-5-vendor-adapters-edge.log
  ```

  **Commit**: YES | Message: `feat(dataflows): add akshare and tushare base adapters` | Files: `diverge/dataflows/akshare.py`, `diverge/dataflows/tushare.py`, `tests/dataflows/test_akshare_adapter.py`, `tests/dataflows/test_tushare_adapter.py`

- [ ] 6. Register CN vendors in interface mappings and availability checks

  **What to do**: Update `VENDOR_LIST` and `VENDOR_METHODS` in `interface.py` to include `akshare` and `tushare` for supported methods. Ensure `build_vendor_chain()` intersects configured chain with method-supported vendors to avoid invalid vendor selection.
  **Must NOT do**: Do not register unsupported methods blindly (e.g., news/insider before adapter exists).

  **Recommended Agent Profile**:
  - Category: `quick` — Reason: Mapping-focused change with clear expected shape.
  - Skills: [`software-architecture`] — keep registry consistent with policy.
  - Omitted: [`backend-patterns`] — unnecessary for mapping-only updates.

  **Parallelization**: Can Parallel: NO | Wave 2 | Blocks: 7,8,9,10 | Blocked By: 4,5

  **References** (executor has NO interview context — be exhaustive):
  - Pattern: `diverge/dataflows/interface.py:62-109` — current vendor registry and method map.
  - Pattern: `diverge/dataflows/interface.py:143-153` — fallback chain assembly behavior.

  **Acceptance Criteria** (agent-executable only):
  - [ ] Method registry tests assert no unsupported vendor-method pair is exposed.
  - [ ] Router handles invalid configured vendor names gracefully (skip with traceable error).

  **QA Scenarios** (MANDATORY — task incomplete without these):
  ```
  Scenario: Configured vendor not supported for method is filtered out
    Tool: Bash
    Steps: Run `pytest tests/dataflows/test_vendor_registry.py::test_unsupported_vendor_filtered -q`
    Expected: Router skips unsupported vendor and continues chain
    Evidence: .sisyphus/evidence/task-6-vendor-registry.log

  Scenario: Supported CN vendor selected for CN ticker
    Tool: Bash
    Steps: Run `pytest tests/dataflows/test_vendor_registry.py::test_cn_vendor_selected -q`
    Expected: Dispatch target is CN vendor for CN symbol path
    Evidence: .sisyphus/evidence/task-6-vendor-registry-edge.log
  ```

  **Commit**: YES | Message: `feat(router): register cn vendors in method map` | Files: `diverge/dataflows/interface.py`, `tests/dataflows/test_vendor_registry.py`

- [ ] 7. Decouple indicator computation from hardwired yfinance download path

  **What to do**: Refactor indicator data-fetch path so stockstats inputs come from routed OHLCV source rather than direct `yf.download()` dependence in CN flow. Introduce a reusable OHLCV fetch utility that respects market/vendor selection.
  **Must NOT do**: Do not regress existing US indicator behavior or remove caching support.

  **Recommended Agent Profile**:
  - Category: `deep` — Reason: Hidden coupling in indicator internals and cache behavior.
  - Skills: [`software-architecture`, `backend-patterns`] — isolate dependency and preserve behavior.
  - Omitted: [`api-design`] — no external API changes.

  **Parallelization**: Can Parallel: NO | Wave 2 | Blocks: 9,10 | Blocked By: 4,6

  **References** (executor has NO interview context — be exhaustive):
  - Pattern: `diverge/dataflows/y_finance.py:197-247` — current direct yfinance indicator data path.
  - Pattern: `diverge/dataflows/stockstats_utils.py` — existing stockstats helper behavior.
  - Pattern: `diverge/agents/utils/technical_indicators_tools.py:23` — routed indicator call contract.

  **Acceptance Criteria** (agent-executable only):
  - [ ] Indicator tests show CN ticker path no longer requires direct yfinance download.
  - [ ] Cached-path tests still pass for existing US flow.

  **QA Scenarios** (MANDATORY — task incomplete without these):
  ```
  Scenario: CN indicator path uses routed OHLCV source
    Tool: Bash
    Steps: Run `pytest tests/dataflows/test_indicator_source_routing.py::test_cn_indicator_uses_routed_ohlcv -q`
    Expected: No direct yfinance call in CN-mode test fixture
    Evidence: .sisyphus/evidence/task-7-indicator-routing.log

  Scenario: US cached indicator behavior unchanged
    Tool: Bash
    Steps: Run `pytest tests/dataflows/test_indicator_source_routing.py::test_us_indicator_cache_unchanged -q`
    Expected: Existing cache behavior preserved
    Evidence: .sisyphus/evidence/task-7-indicator-routing-edge.log
  ```

  **Commit**: YES | Message: `fix(indicators): route ohlcv source for cross-vendor consistency` | Files: `diverge/dataflows/y_finance.py`, `diverge/dataflows/stockstats_utils.py`, `tests/dataflows/test_indicator_source_routing.py`

- [ ] 8. Add optional CN news/insider support with capability-gated fallback

  **What to do**: Implement `get_news`, `get_global_news` (if available), and `get_insider_transactions` support in CN adapters where practical. For unsupported capabilities, emit `VendorNotSupportedError` so router can fallback to next configured vendor (e.g., yfinance/global news).
  **Must NOT do**: Do not fake unsupported vendor capabilities with placeholder text.

  **Recommended Agent Profile**:
  - Category: `unspecified-high` — Reason: External API capability variability and fallback sensitivity.
  - Skills: [`software-architecture`] — capability gating and policy-safe fallback.
  - Omitted: [`backend-patterns`] — optional for this narrow capability task.

  **Parallelization**: Can Parallel: YES | Wave 2 | Blocks: 9,10 | Blocked By: 4,6

  **References** (executor has NO interview context — be exhaustive):
  - Pattern: `diverge/agents/utils/news_data_tools.py:21-53` — news/insider method contracts.
  - Pattern: `diverge/dataflows/yfinance_news.py:49-190` — baseline news return formatting.
  - Pattern: `diverge/dataflows/interface.py:97-109` — current news/global/insider vendor mappings.

  **Acceptance Criteria** (agent-executable only):
  - [ ] Unsupported capability path raises `VendorNotSupportedError` and fallback test passes.
  - [ ] At least one CN news happy-path test returns formatted `str` payload.

  **QA Scenarios** (MANDATORY — task incomplete without these):
  ```
  Scenario: Unsupported CN capability falls back correctly
    Tool: Bash
    Steps: Run `pytest tests/dataflows/test_cn_news_capabilities.py::test_not_supported_fallback -q`
    Expected: Router continues to next vendor without raw traceback
    Evidence: .sisyphus/evidence/task-8-cn-news.log

  Scenario: Global news method bypasses ticker parsing
    Tool: Bash
    Steps: Run `pytest tests/dataflows/test_cn_news_capabilities.py::test_global_news_no_ticker_parse -q`
    Expected: Method executes without symbol parse branch
    Evidence: .sisyphus/evidence/task-8-cn-news-edge.log
  ```

  **Commit**: YES | Message: `feat(dataflows): add capability-gated cn news and insider routing` | Files: `diverge/dataflows/akshare.py`, `diverge/dataflows/tushare.py`, `diverge/dataflows/interface.py`, `tests/dataflows/test_cn_news_capabilities.py`

- [ ] 9. Build full contract + routing + fallback + config regression suite

  **What to do**: Add test modules covering method signature compatibility, schema extraction (`METHOD_ARG_SCHEMA`), market detection matrix, precedence chain, semantic fallback behavior, and deep-merge config stability. Include regression tests for existing US routing behavior.
  **Must NOT do**: Do not leave acceptance to ad-hoc manual checks; require deterministic tests and command outputs.

  **Recommended Agent Profile**:
  - Category: `unspecified-high` — Reason: Broad regression coverage across multiple modules.
  - Skills: [`test-driven-development`, `software-architecture`] — robust, behavior-focused tests.
  - Omitted: [`frontend-patterns`] — no UI scope.

  **Parallelization**: Can Parallel: NO | Wave 2 | Blocks: 10 | Blocked By: 4,6,7,8

  **References** (executor has NO interview context — be exhaustive):
  - Pattern: `diverge/dataflows/interface.py` — central behavior under test.
  - Pattern: `diverge/dataflows/config.py` — deep-merge correctness.
  - Pattern: `diverge/default_config.py` — default precedence fixtures.
  - API/Type: `diverge/agents/utils/*.py` — public method signatures that must remain unchanged.

  **Acceptance Criteria** (agent-executable only):
  - [ ] `pytest tests/dataflows -q` passes.
  - [ ] `pytest tests/integration -q` passes for routing contract tests.
  - [ ] Added tests explicitly cover: `600519`, `600519.SH`, `AAPL`, unknown symbol, and `get_global_news` no-ticker path.

  **QA Scenarios** (MANDATORY — task incomplete without these):
  ```
  Scenario: Full router regression suite passes
    Tool: Bash
    Steps: Run `pytest tests/dataflows tests/integration -q`
    Expected: All router/config/fallback tests pass with zero failures
    Evidence: .sisyphus/evidence/task-9-regression-suite.log

  Scenario: Signature compatibility remains stable
    Tool: Bash
    Steps: Run `python - <<'PY'\nimport inspect\nfrom diverge.agents.utils.core_stock_tools import get_stock_data\nfrom diverge.agents.utils.technical_indicators_tools import get_indicators\nfrom diverge.agents.utils.fundamental_data_tools import get_fundamentals\nfrom diverge.agents.utils.news_data_tools import get_news\nprint(inspect.signature(get_stock_data))\nprint(inspect.signature(get_indicators))\nprint(inspect.signature(get_fundamentals))\nprint(inspect.signature(get_news))\nPY`
    Expected: Signatures remain unchanged versus baseline contracts
    Evidence: .sisyphus/evidence/task-9-signature-compat.log
  ```

  **Commit**: YES | Message: `test(router): add cn/us routing and fallback regression matrix` | Files: `tests/dataflows/*`, `tests/integration/*`

- [ ] 10. Final integration validation, docs alignment, and execution handoff readiness

  **What to do**: Update docs/config guidance for CN usage (`TUSHARE_TOKEN`, sample ticker formats, market override examples). Run end-to-end CLI smoke path and summarize operational runbook for implementers.
  **Must NOT do**: Do not claim completion without command evidence and generated artifacts.

  **Recommended Agent Profile**:
  - Category: `writing` — Reason: Documentation clarity + operational handoff quality.
  - Skills: [`verification-before-completion`] — evidence-first completion protocol.
  - Omitted: [`frontend-patterns`] — non-UI deliverable.

  **Parallelization**: Can Parallel: NO | Wave 2 | Blocks: none | Blocked By: 4,6,7,8,9

  **References** (executor has NO interview context — be exhaustive):
  - Pattern: `README.md` (installation/env sections) — where token/env instructions belong.
  - Pattern: `diverge/default_config.py` — authoritative default config examples.
  - Pattern: `cli/main.py` — CN ticker/date flow entry point for smoke validation.

  **Acceptance Criteria** (agent-executable only):
  - [ ] Documentation includes explicit CN setup and fallback examples.
  - [ ] CLI smoke command/path runs without router exceptions under CN config.
  - [ ] Evidence logs captured for docs checks + smoke execution.

  **QA Scenarios** (MANDATORY — task incomplete without these):
  ```
  Scenario: CN config smoke path completes startup and routing
    Tool: Bash
    Steps: Run `python -m cli.main` with scripted inputs: ticker `600519`, valid date, CN-capable config selection
    Expected: Analysis flow starts and no immediate routing/config exception is raised
    Evidence: .sisyphus/evidence/task-10-cli-smoke.log

  Scenario: Missing token guidance is actionable
    Tool: Bash
    Steps: Run `python - <<'PY'\nfrom pathlib import Path\ntext = Path('README.md').read_text(encoding='utf-8')\nassert 'TUSHARE_TOKEN' in text\nassert 'fallback' in text.lower()\nprint('docs-token-guidance-ok')\nPY`
    Expected: Script prints `docs-token-guidance-ok` and exits 0
    Evidence: .sisyphus/evidence/task-10-docs-validation.log
  ```

  **Commit**: YES | Message: `docs(cn-data): add v3 setup, fallback, and runbook guidance` | Files: `README.md`, `docs/plans/2026-03-10-cn-datasources-design.md` (or successor doc)

## Final Verification Wave (4 parallel agents, ALL must APPROVE)
- [ ] F1. Plan Compliance Audit — oracle
- [ ] F2. Code Quality Review — unspecified-high
- [ ] F3. Real Manual QA — unspecified-high (+ playwright if UI)
- [ ] F4. Scope Fidelity Check — deep

## Commit Strategy
- Commit per task boundary where code + tests are green.
- Conventional commits format: `feat(dataflows): ...`, `fix(router): ...`, `test(dataflows): ...`, `docs(config): ...`.
- Never batch unrelated task outputs into one commit.

## Success Criteria
- CN vendor routing works without breaking existing US behavior.
- Fallback semantics are deterministic, test-backed, and no longer AlphaVantage-only.
- Config precedence and market resolution behavior are explicit and validated.
- CLI + graph path can complete CN analysis flow under configured providers.
