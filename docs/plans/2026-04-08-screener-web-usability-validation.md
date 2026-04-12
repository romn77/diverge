# Screener Web Usability And Validation Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Make Web-launched screener tasks robust by accepting the full progress callback signature and rejecting invalid screener requests before they enter the async queue.

**Architecture:** Keep the fix narrow. The backend will normalize validation by constructing `ScreenRunConfig` before queueing and by broadening the Web callback signature to accept optional `status/detail`. The frontend will add lightweight pre-submit guards so users see immediate errors before the POST.

**Tech Stack:** Python, FastAPI, Pydantic, TypeScript/React, pytest, node:test

---

### Task 1: Lock the backend callback bug with a failing test

**Files:**
- Modify: `tests/web/test_backend_main.py`
- Modify: `web/backend/main.py`

**Step 1: Write the failing test**

Add a test that patches `run_screen` to call the provided callback with:
- `stage`
- `current`
- `total`
- `symbol`
- `status=...`
- `detail=...`

and then returns a valid `ScreenRunResult`.

**Step 2: Run test to verify it fails**

Run: `uv run --with pytest pytest tests/web/test_backend_main.py -q`

Expected: FAIL because `_run_screener_task()` currently defines a callback that rejects keyword args.

**Step 3: Write minimal implementation**

Broaden the Web callback in `web/backend/main.py` to accept optional `status` and `detail` and convert them into the progress message without breaking existing status tracking.

**Step 4: Run test to verify it passes**

Run: `uv run --with pytest pytest tests/web/test_backend_main.py -q`

Expected: PASS

### Task 2: Lock queue-time validation with failing tests

**Files:**
- Modify: `tests/web/test_backend_main.py`
- Modify: `web/backend/main.py`

**Step 1: Write the failing tests**

Add tests showing `create_screener_task()` rejects before queueing when:
- `markets` is empty
- `top_k <= 0`
- `as_of_date` is malformed

**Step 2: Run test to verify it fails**

Run: `uv run --with pytest pytest tests/web/test_backend_main.py -q`

Expected: FAIL because invalid payloads currently reach queue creation.

**Step 3: Write minimal implementation**

Inside `create_screener_task()`:
- keep the existing US manifest handling
- construct `ScreenRunConfig(**config_payload)` before creating the task
- translate `ValueError` into `HTTPException(status_code=400, ...)`

**Step 4: Run test to verify it passes**

Run: `uv run --with pytest pytest tests/web/test_backend_main.py -q`

Expected: PASS

### Task 3: Add lightweight frontend submit guards

**Files:**
- Modify: `web/frontend/components/NewScreenerForm.tsx`
- Modify: `web/frontend/components/NewScreenerForm.test.mjs`

**Step 1: Write the failing test**

Add a source-level test that expects explicit client-side error handling for:
- empty `markets`
- non-positive `top_k`
- invalid `as_of_date` format

**Step 2: Run test to verify it fails**

Run: `cd web/frontend && node --test components/NewScreenerForm.test.mjs`

Expected: FAIL because the form currently posts immediately.

**Step 3: Write minimal implementation**

Add a small validation helper or inline guard in `submitTask()` that sets `error` and returns before `createScreenerTask(formState)`.

**Step 4: Run test to verify it passes**

Run: `cd web/frontend && node --test components/NewScreenerForm.test.mjs`

Expected: PASS

### Task 4: Focused verification

**Step 1: Run backend and frontend focused checks**

Run:
- `uv run --with pytest pytest tests/web/test_backend_main.py -q`
- `cd web/frontend && node --test components/NewScreenerForm.test.mjs`

**Step 2: Report**

Post in the task thread with:
- changed files
- exact verification commands
- any intentionally deferred items
