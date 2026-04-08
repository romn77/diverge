# Screener Date/Data Semantics Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Implement the accepted screener date semantics so `as_of_date` and `data_end_date` are explicit in outputs and stale rows are dropped as `stale_data`.

**Architecture:** Reuse the existing feature-building behavior that already selects the last row with `Date <= as_of_date` and emits `data_end_date`. Add a hard-filter layer for stale rows, then verify the resulting `filtered_out.csv` preserves the accepted fields and reason codes.

**Tech Stack:** Python, pandas, pytest

---

### Task 1: Add failing filter tests for stale data

**Files:**
- Modify: `tests/screener/test_filters.py`
- Modify: `tradingagents/screener/filters.py`

**Step 1: Write the failing test**

Add tests that:
- drop a row as `stale_data` when `data_end_date` trails `as_of_date` by more than 3 business days
- prioritize `stale_data` ahead of `missing_features`

**Step 2: Run test to verify it fails**

Run: `uv run --with pytest pytest tests/screener/test_filters.py -q`

Expected: FAIL because stale-data handling does not exist yet.

**Step 3: Write minimal implementation**

Add a helper in `tradingagents/screener/filters.py` to:
- parse `as_of_date` / `data_end_date`
- compute business-day lag
- return `True` when lag is greater than 3

Then apply it before bar-count / feature checks.

**Step 4: Run test to verify it passes**

Run: `uv run --with pytest pytest tests/screener/test_filters.py -q`

Expected: PASS

### Task 2: Verify stale-data artifacts are written out

**Files:**
- Modify: `tests/screener/test_pipeline.py`
- Reuse: `tradingagents/screener/pipeline.py`
- Reuse: `tradingagents/screener/storage.py`

**Step 1: Write the failing test**

Add a pipeline test that produces a stale feature row and asserts:
- `filtered_out.csv` contains `drop_reason=stale_data`
- `filtered_out.csv` preserves `as_of_date` and `data_end_date`

**Step 2: Run test to verify it fails**

Run: `uv run --with pytest pytest tests/screener/test_pipeline.py -q`

Expected: FAIL until stale rows flow through the real filter path.

**Step 3: Write minimal implementation**

Keep implementation minimal. If the filter change already causes the pipeline assertion to pass, do not add extra production code.

**Step 4: Run test to verify it passes**

Run: `uv run --with pytest pytest tests/screener/test_pipeline.py -q`

Expected: PASS

### Task 3: Final focused verification

**Files:**
- Modify: `notes/work-log.md` only if project-memory updates are needed outside this repo

**Step 1: Run focused suite**

Run: `uv run --with pytest pytest tests/screener/test_filters.py tests/screener/test_pipeline.py tests/screener/test_indicators.py -q`

Expected: PASS

**Step 2: Report task result**

Post in the task thread with:
- what changed
- exact verification command
- any remaining gaps (for example, no exchange-holiday-aware calendar yet)
