# Job Records Task State Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Move durable background task state into database-backed job records while keeping Redis as the live queue and local JSON as a development fallback.

**Architecture:** Add a `job_records` table and service that stores the task fact record for analysis, screener, and data_sync jobs. Runtime task code dual-writes existing local/Redis state plus DB records first; admin task queue then prefers DB records and enriches them with Redis queue positions. Local JSON remains a fallback for development and migration.

**Tech Stack:** FastAPI backend, SQLAlchemy ORM on `web.backend.auth.Base`, Alembic migrations, Redis-backed `task_store`, Next.js admin UI.

---

### Task 1: Add Job Record DB Model And Migration

**Files:**
- Create: `web/backend/alembic/versions/20260430_000013_create_job_records.py`
- Create: `web/backend/job_records.py`
- Test: `tests/web/test_job_records.py`

**Steps:**
1. Write a failing test that creates/upserts a job record through a service function and reads it back.
2. Run `UV_CACHE_DIR=/tmp/uv-cache uv run --with pytest python -m pytest -q tests/web/test_job_records.py`.
3. Add `job_records` SQLAlchemy model with fields: `id`, `kind`, `tenant_id`, `owner_user_id`, `status`, `request_payload`, `result_summary`, `error`, timestamps, `heartbeat_at`, `worker_id`, and `updated_at`.
4. Add Alembic migration and table check runtime initializer.
5. Re-run the focused test.

### Task 2: Dual Write Runtime Task State

**Files:**
- Modify: `web/backend/runtime/data_sync_tasks.py`
- Modify: `web/backend/runtime/analysis_tasks.py`
- Modify: `web/backend/runtime/screener_tasks.py`
- Test: `tests/web/test_data_sync_backend.py`
- Test: `tests/web/test_backend_main.py`

**Steps:**
1. Write failing tests that data_sync creation, running, completion, failure, and recovery call the job record service.
2. Add minimal dual-write calls in `_save_task`/status transition paths.
3. Repeat for analysis and screener save/status helpers.
4. Keep local JSON and Redis behavior unchanged.
5. Run focused runtime tests.

### Task 3: Prefer DB Records In Admin Task Queue

**Files:**
- Modify: `web/backend/routers/admin.py`
- Test: `tests/web/test_backend_main.py`

**Steps:**
1. Write a failing test where DB-backed job records are returned even when local JSON is absent.
2. Add a query path that lists active DB job records when job records DB is available.
3. Enrich active records with Redis queue positions for queued jobs.
4. Fall back to runtime task payloads when DB is unavailable.
5. Run admin task queue tests.

### Task 4: Production Requirements And Migration Script

**Files:**
- Create: `web/backend/devops/import_local_job_records.py`
- Modify: `web/backend/main.py`
- Modify: `.env.example`
- Test: `tests/web/test_job_records.py`

**Steps:**
1. Write tests for importing local JSON task files into job records, marking stale `running` as failed.
2. Add migration script for analysis/screener/data_sync local state.
3. Add startup check warning/error: production requires `DATABASE_URL` and `TASK_BACKEND=redis`.
4. Document local JSON as development fallback only.

### Task 5: Add Admin Data Sync Launch Entry On Task Queue Page

**Files:**
- Modify: `web/frontend/app/admin/task-queue/page.tsx`
- Modify: `web/frontend/lib/api.ts`
- Test: `web/frontend/app/admin-task-queue.test.mjs`

**Steps:**
1. Write a failing frontend source test that task queue page exposes a data sync launch action.
2. Add compact admin controls for OHLCV sync: market, as-of date, source, and run button.
3. Call existing admin data-sync API and refresh the queue after creation.
4. Keep the page operational and compact; avoid adding a separate landing flow.
5. Run frontend source tests.
