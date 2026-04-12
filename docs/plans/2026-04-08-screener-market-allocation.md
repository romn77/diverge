# Screener Dual-Market Allocation Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add a dual-market candidate allocation layer that preserves raw ranking scores while selecting candidates via "per-market floor + global backfill".

**Architecture:** Keep ranking unchanged. After `score_candidates()` returns globally ranked rows, apply a small selection function in the pipeline: if both `cn` and `us` are requested, first reserve `floor(top_k / 2)` per market, then fill any remaining slots from the remaining global ranking. Preserve original `global_rank` / `market_rank` columns.

**Tech Stack:** Python, pandas, pytest

---

### Task 1: Lock dual-market allocation with failing pipeline tests

**Files:**
- Modify: `tests/screener/test_pipeline.py`
- Modify: `tradingagents/screener/pipeline.py`

**Step 1: Write the failing tests**

Add tests that assert:
- when `markets=["cn", "us"]` and `top_k=4`, candidate selection takes `2` per market when available
- when one market has fewer than its floor, the remaining slots are filled by the highest-ranked remaining rows globally
- when only one market is requested, behavior stays `head(top_k)`

**Step 2: Run test to verify it fails**

Run: `uv run --with pytest pytest tests/screener/test_pipeline.py -q`

Expected: FAIL because pipeline currently uses plain `head(config.top_k)`.

**Step 3: Write minimal implementation**

Implement a small selection helper in `tradingagents/screener/pipeline.py` that:
- no-ops for single-market runs
- allocates by per-market floor for `cn` + `us`
- backfills remaining slots from unselected rows in original ranked order
- returns rows sorted by original `global_rank`

**Step 4: Run test to verify it passes**

Run: `uv run --with pytest pytest tests/screener/test_pipeline.py -q`

Expected: PASS

### Task 2: Focused regression verification

**Step 1: Run focused suite**

Run: `uv run --with pytest pytest tests/screener/test_pipeline.py tests/screener/test_ranker.py -q`

Expected: PASS

**Step 2: Report**

Post in the task thread with:
- the selection rule implemented
- exact verification command
- any remaining follow-up ideas if needed
