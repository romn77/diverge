# Screener OHLCV Sync Resilience Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Make admin OHLCV sync resilient to partial vendor failures, remove symbols without same-day bars from that day's screener universe, and expose the outcome through artifacts and audit events.

**Architecture:** Admin data-sync remains the only path that may fetch OHLCV data. The sync step retries failed or stale symbols up to three times, writes a normalized data-quality artifact, and records summary audit events. Screener tasks consume the post-sync cache in cache-only mode, but prune symbols that are explicitly known to lack the requested as-of bar instead of failing the whole run.

**Tech Stack:** Python, FastAPI, pandas, SQLAlchemy audit events, existing `diverge.screener` cache/artifact layout, pytest/unittest web backend tests.

---

### Task 1: Define Data Quality Result Schema

**Files:**
- Modify: `diverge/screener/sync.py`
- Modify: `diverge/screener/history_cache.py`
- Test: `tests/screener/test_sync.py` or create `tests/screener/test_sync_ohlcv_quality.py`

**Step 1: Write failing tests**

Add tests that construct small history frames and verify the data-quality classifier returns:

- `ready` when cache contains `as_of_date`
- `missing_as_of_bar` when cache has a valid lookback window but max date is before `as_of_date`
- `history_cache_miss` when no cache file/frame exists

Expected artifact row shape:

```python
{
    "symbol": "000010.SZ",
    "market": "cn",
    "status": "missing_as_of_bar",
    "cache_span": "2025-02-19..2026-04-28",
    "as_of_date": "2026-04-29",
}
```

**Step 2: Implement minimal classifier**

Create a small helper, preferably in `diverge/screener/history_cache.py`, that normalizes a cached frame and classifies coverage for a symbol/as-of date without doing vendor fetches.

**Step 3: Run tests**

Run:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -q tests/screener/test_sync_ohlcv_quality.py
```

Expected: new tests pass.

---

### Task 2: Retry Failed Or Stale Symbols Up To Three Times

**Files:**
- Modify: `diverge/screener/market_data.py`
- Modify: `diverge/screener/sync.py`
- Test: `tests/screener/test_sync_ohlcv_quality.py`

**Step 1: Write failing tests**

Mock `fetch_price_history` so selected symbols fail or return empty for the first two attempts and succeed on the third. Verify:

- each retryable symbol is attempted at most three extra retry rounds
- success after retry writes cache and is counted as ready
- persistent failure remains in the failed/stale artifact

**Step 2: Implement retry orchestration**

Keep the existing per-symbol retry/backoff for vendor retryable errors, but add an outer sync-level retry pass for symbols that are not ready after the first full pass. The retry list should include:

- explicit fetch failures
- cache miss
- cache stale for `as_of_date`
- fetched-empty reuse-cache where max cache date is still before `as_of_date`

Do not create a permanent blacklist. Each new sync job starts from the current manifest/universe.

**Step 3: Run focused tests**

Run:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -q tests/screener/test_sync_ohlcv_quality.py
```

Expected: retry tests pass.

---

### Task 3: Persist Sync Quality Artifact

**Files:**
- Modify: `diverge/screener/sync.py`
- Possibly modify: `web/backend/app_config.py`
- Test: `tests/web/test_data_sync_backend.py`

**Step 1: Write failing tests**

Extend data-sync tests to assert completed OHLCV result includes:

- `quality_artifact_path`
- `symbols_missing_as_of_bar`
- `symbols_pruned_from_screener`
- `failed_symbols`
- `missing_as_of_bar_symbols` or equivalent summarized list

**Step 2: Implement artifact writing**

Write a CSV or JSON artifact under a stable location, for example:

```text
data/cache/screener/sync/ohlcv_quality_2026-04-29_cn_tushare.json
```

Keep full per-symbol rows in the artifact. Keep the task result compact with counts, reason distribution, and artifact path.

**Step 3: Run tests**

Run:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -q tests/web/test_data_sync_backend.py
```

Expected: data-sync result exposes the quality artifact summary.

---

### Task 4: Prune Symbols Without Same-Day Bars From Screener Runs

**Files:**
- Modify: `web/backend/services/screeners.py`
- Modify: `diverge/screener/stages.py` only if pruning belongs closer to universe preparation
- Test: `tests/web/test_screener_breakout_contracts.py`

**Step 1: Write failing tests**

Add a case where prefiltered CN universe has three symbols:

- two have cache through `2026-04-29`
- one has cache only through `2026-04-28`

Expected behavior:

- screener cache coverage check does not raise 409
- stale symbol is returned in a prune summary
- if all symbols are stale/missing, task still fails with data-not-ready

**Step 2: Implement pruning**

Change the preflight from "any stale symbol fails the whole run" to:

- classify each symbol
- keep ready symbols
- prune known missing/stale symbols
- fail only when no usable symbols remain, or when usable count falls below a conservative minimum if a threshold is introduced

The pruning must be per-run only. Do not edit manifest, universe cache, or history cache to remove symbols.

**Step 3: Ensure artifacts capture pruning**

Add pruned-symbol summary to screener run metadata or a dedicated artifact such as:

```text
pruned_symbols.csv
```

Include reason distribution in `run_meta.json`.

**Step 4: Run focused tests**

Run:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -q tests/web/test_screener_breakout_contracts.py
```

Expected: stale symbols are pruned, not blocking, while all-stale cases still fail.

---

### Task 5: Add Audit Log Events

**Files:**
- Modify: `web/backend/routers/data_sync.py`
- Modify: `web/backend/runtime/data_sync_tasks.py`
- Modify: `web/backend/runtime/screener_tasks.py`
- Test: `tests/web/test_auth_backend.py` or create focused audit tests in `tests/web/test_data_sync_backend.py`

**Step 1: Write failing tests**

Verify audit events are recorded for authenticated admin flows:

- `data_sync.ohlcv.created`
- `data_sync.ohlcv.completed`
- `data_sync.ohlcv.failed`
- `screener.universe.pruned` when pruning count is greater than zero

Audit metadata should include compact fields only:

```python
{
    "as_of_date": "2026-04-29",
    "markets": ["cn"],
    "symbols_total": 4980,
    "symbols_success": 4972,
    "symbols_missing_as_of_bar": 40,
    "quality_artifact_path": "cache/screener/sync/...",
}
```

**Step 2: Implement audit recording**

Use `audit.record_audit_event_safely()` with sanitized metadata. Store full lists in artifacts, not directly in audit rows.

**Step 3: Run audit tests**

Run:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -q tests/web/test_data_sync_backend.py tests/web/test_auth_backend.py
```

Expected: audit log can observe created/completed/failed/pruned summaries.

---

### Task 6: Fix Data Sync Terminal State Persistence

**Files:**
- Modify: `web/backend/runtime/data_sync_tasks.py`
- Test: `tests/web/test_data_sync_backend.py`

**Step 1: Write failing test**

Create a local-backend data-sync task, mark it completed, reload it from disk, and assert status is `completed` with `result` preserved.

**Step 2: Implement fix**

Change `_save_task()` so terminal states are persisted before any active-task cleanup behavior. If active-only retention is desired, introduce a separate archive or explicit cleanup path instead of silently leaving stale `running` JSON on disk.

**Step 3: Run tests**

Run:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -q tests/web/test_data_sync_backend.py
```

Expected: completed data-sync jobs no longer reappear as stale `running`.

---

### Task 7: End-To-End Verification

**Files:**
- No direct code file ownership

**Step 1: Run targeted backend suite**

Run:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -q tests/web/test_data_sync_backend.py tests/web/test_screener_breakout_contracts.py
```

Expected: all targeted tests pass.

**Step 2: Run relevant screener tests**

Run:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -q tests/screener
```

Expected: all screener tests pass.

**Step 3: Manual local check with 2026-04-29 data**

Using the existing `.env`, run a cache coverage check for CN `2026-04-29` and verify:

- no full-run 409 when only stale symbols exist
- pruned count equals the expected stale/missing set
- run artifacts include pruned-symbol details
- admin audit endpoint shows compact summary events

---

### Task 8: Documentation

**Files:**
- Modify: `web/README.md`

**Step 1: Update admin data-sync docs**

Document:

- sync retries failed/stale symbols up to three times
- symbols still missing the same-day bar are excluded from that day's screener only
- excluded symbols are eligible for the next daily sync
- audit log records summaries and artifact paths

**Step 2: Run doc-adjacent tests if present**

Run any existing README/start-script tests touched by wording or environment assumptions:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -q tests/test_web_start_script.py
```

Expected: pass.
