# CLI Data Layout Wrap-Up Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Finish the storage migration by moving the legacy analyze CLI runtime outputs from `results/` into `data/eval_results/` and aligning trade-feedback full-state-log references with the real runtime path.

**Architecture:** Keep `data/reports/` as the canonical saved-report location and introduce `data/eval_results/` as the runtime/output root for legacy analyze traces and full state logs. Reuse a shared path helper so CLI, graph, tests, and UI all point at the same project-relative paths.

**Tech Stack:** Python, Typer CLI, pytest, node:test

---

### Task 1: Lock the new analyze runtime path semantics with failing tests

**Files:**
- Modify: `tests/test_data_layout.py`
- Modify: `web/frontend/components/TradeRecordForm.test.mjs`
- Modify: `tests/test_trade_feedback.py`

**Step 1: Write the failing tests**
- Assert the shared data-layout helper/default config uses `./data/eval_results` for legacy analyze runtime outputs.
- Assert the trade-record form builds `data/eval_results/<ticker>/TradingAgentsStrategy_logs/full_states_log_<date>.json`.
- Assert trade-feedback tests reference `data/eval_results/...` instead of `eval_results/...`.

**Step 2: Run tests to verify they fail**
Run: `python -m pytest -q tests/test_data_layout.py tests/test_trade_feedback.py && node --test components/TradeRecordForm.test.mjs`
Expected: FAIL until the path constants and fixtures are updated.

**Step 3: Write the minimal implementation**
- Add a shared `data/eval_results` default to the layout helper.
- Point analyze defaults/tests/UI references at the new relative path.

**Step 4: Run tests to verify they pass**
Run the same commands and expect PASS.

### Task 2: Move the legacy analyze CLI runtime implementation to the new path root

**Files:**
- Modify: `tradingagents/data_layout.py`
- Modify: `tradingagents/default_config.py`
- Modify: `cli/main.py`
- Modify: `tradingagents/graph/trading_graph.py`
- Modify: `tests/test_single_host_deployment_files.py` only if deployment/config expectations need updating

**Step 1: Write the failing test**
Add/update a test that proves the analyze CLI default runtime root no longer points at `./results`.

**Step 2: Run test to verify it fails**
Run a focused pytest command for the updated tests.

**Step 3: Write minimal implementation**
- Introduce `DEFAULT_EVAL_RESULTS_DIR = "./data/eval_results"`.
- Change `DEFAULT_CONFIG["results_dir"]` to use the new default.
- Leave the config key name as `results_dir` for now to minimize churn, but ensure the value points at `data/eval_results`.
- Keep saved reports defaulting to `data/reports`.

**Step 4: Run tests to verify it passes**
Run the focused suite and expect PASS.

### Task 3: Migrate existing on-disk analyze outputs and verify the new steady state

**Files:**
- No source files required beyond docs/config if the migration is done via shell

**Step 1: Move local runtime data**
- Move `results/<ticker>/...` to `data/eval_results/<ticker>/...`.
- Keep unrelated archives only if they are not clearly part of the active runtime layout.

**Step 2: Run focused verification**
Run: `python -m pytest -q tests/test_data_layout.py tests/test_trade_feedback.py tests/cli/test_screen_command.py tests/test_single_host_deployment_files.py` and `node --test components/TradeRecordForm.test.mjs`
Expected: PASS

**Step 3: Report**
Summarize:
- new `data/eval_results` role
- which legacy runtime directories were migrated
- any leftover `results/` artifacts intentionally untouched
