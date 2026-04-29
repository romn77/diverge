# Module RBAC, Tenant Isolation, and Audit Log Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add module-scoped permissions, tenant-level data isolation, and durable audit logging for the authenticated Diverge workbench.

**Architecture:** Keep the existing `admin/operator/viewer` roles as presets, but route authorization through explicit module permissions. Introduce a `tenants` table and `tenant_id` columns so ownership queries are scoped by organization before user. Record security-relevant actions in append-only audit events without blocking the primary workflow when audit writes fail.

**Tech Stack:** FastAPI, SQLAlchemy ORM, Alembic, PostgreSQL/SQLite test runtime, existing pytest backend harness.

---

## Phase 1: Module-Scoped RBAC

### Task 1: Add permission vocabulary and role presets

**Files:**
- Modify: `web/backend/auth.py`
- Test: `tests/web/test_auth_backend.py`

**What this does:**
Define capabilities such as `analysis:create`, `analysis:read`, `screener:create`, `screener:read`, `assets:read`, `assets:write`, `journal:read`, `journal:write`, `admin:users`, and `admin:settings`. Existing roles become defaults: admin gets all, operator gets create/read/write on workbench modules, viewer gets read plus limited create if desired.

**Steps:**
1. Write tests for `permissions_for_role("admin")`, `permissions_for_role("operator")`, and `permissions_for_role("viewer")`.
2. Add constants for module names and permission strings in `auth.py`.
3. Add `permissions_for_role(role: str) -> set[str]`.
4. Keep current role behavior unchanged by making presets match today's access rules.
5. Run `pytest tests/web/test_auth_backend.py -q`.

### Task 2: Add request-level permission checks

**Files:**
- Modify: `web/backend/access.py`
- Modify: `web/backend/routers/tasks.py`
- Modify: `web/backend/routers/screeners.py`
- Modify: `web/backend/routers/assets.py`
- Modify: `web/backend/routers/trades.py`
- Modify: `web/backend/routers/admin.py`
- Test: `tests/web/test_auth_backend.py`
- Test: `tests/web/test_asset_backend.py`
- Test: `tests/web/test_trade_owner_scoping_backend.py`

**What this does:**
Replace broad route checks like "operator/admin/viewer can enter this router" with exact capability checks at route boundaries.

**Steps:**
1. Write failing tests: viewer cannot create analysis if missing `analysis:create`; operator can create; viewer can read workspace reports if allowed.
2. Add `access.require_permission(db, request, permission)`.
3. Use `analysis:create` for task creation and `analysis:read` for task/report reads.
4. Use `screener:create` and `screener:read` for screener routes.
5. Use `assets:read/assets:write` and `journal:read/journal:write` for portfolio routes.
6. Use `admin:users` for user management and `admin:settings` for data-source/admin queue endpoints.
7. Run focused web auth/asset/trade tests.

### Task 3: Optional per-user permission overrides

**Files:**
- Create migration: `web/backend/alembic/versions/20260427_000008_create_user_permissions.py`
- Modify: `web/backend/auth.py`
- Modify: `web/backend/routers/admin.py`
- Modify: `web/backend/schemas/admin.py`
- Test: `tests/web/test_auth_backend.py`

**What this does:**
Allow explicit grants/denies later without changing the role enum. This can be hidden from UI initially and used only through admin API/tests.

**Steps:**
1. Add `user_permissions` table: `id`, `user_id`, `permission`, `effect`, `created_at`, `updated_at`.
2. Add ORM model `UserPermission`.
3. Resolve effective permissions as role preset plus grants minus denies.
4. Add admin API fields only if needed; otherwise keep internal helpers.
5. Test deny-overrides-grant behavior.

## Phase 2: Tenant Isolation

### Task 4: Add tenant model and user membership

**Files:**
- Create migration: `web/backend/alembic/versions/20260427_000009_create_tenants.py`
- Modify: `web/backend/auth.py`
- Modify: `web/backend/devops/bootstrap_admin.py`
- Modify: `web/backend/devops/backfill_metadata.py`
- Test: `tests/web/test_auth_backend.py`
- Test: `tests/web/test_metadata_backfill.py`

**What this does:**
Create a default workspace tenant and assign every user to a tenant. Current single-team behavior remains the same because every existing user lands in the same default tenant.

**Steps:**
1. Create `tenants` table: `id`, `name`, `slug`, `status`, timestamps.
2. Add `users.tenant_id` nullable first, backfill to default tenant, then make non-null where supported.
3. Add FK/index `ix_users_tenant_email`.
4. Update bootstrap admin to create/find default tenant.
5. Update auth serialization to include `tenant_id`.
6. Run auth and metadata backfill tests.

### Task 5: Add tenant_id to business tables

**Files:**
- Create migration: `web/backend/alembic/versions/20260427_000010_add_tenant_ids.py`
- Modify: `web/backend/report_metadata.py`
- Modify: `web/backend/screener_runs.py`
- Modify: `web/backend/trade_entries.py`
- Modify: `web/backend/asset_entries.py`
- Modify: `web/backend/analysis_limits.py`
- Test: `tests/web/test_report_metadata_auth.py`
- Test: `tests/web/test_screener_result_read_model.py`
- Test: `tests/web/test_trade_owner_scoping_backend.py`
- Test: `tests/web/test_asset_backend.py`

**What this does:**
Add `tenant_id` to reports, screeners, trades, asset accounts, asset positions, valuation snapshots, and usage limits. Queries must filter by tenant before owner visibility rules are applied.

**Steps:**
1. Add nullable `tenant_id` columns and indexes to each table.
2. Backfill from `owner_user_id -> users.tenant_id`.
3. Add ORM fields.
4. Update upsert/create helpers to require `tenant_id`.
5. Update list/get helpers to accept `tenant_id`.
6. Preserve current `owner_user_id` semantics inside a tenant.
7. Run focused permission matrix tests.

### Task 6: Enforce tenant scope at service and task boundaries

**Files:**
- Modify: `web/backend/access.py`
- Modify: `web/backend/services/reports.py`
- Modify: `web/backend/services/assets.py`
- Modify: `web/backend/services/trades.py`
- Modify: `web/backend/services/screeners.py`
- Modify: `web/backend/runtime/analysis_tasks.py`
- Modify: `web/backend/runtime/screener_tasks.py`
- Modify: `web/backend/runtime/task_store.py`
- Test: `tests/web/test_auth_backend.py`
- Test: `tests/web/test_backend_main.py`

**What this does:**
Tasks and reads carry both `owner_user_id` and `tenant_id`. Admin override becomes tenant-admin override, not global override, unless a future super-admin role is introduced.

**Steps:**
1. Add `tenant_id` to task payload snapshots and Redis task serialization.
2. Update `owner_scope_for_user` to return both tenant and owner visibility context.
3. Make report workspace visibility mean "visible to authenticated users in the same tenant".
4. Make screener result workspace state tenant-specific.
5. Add tests where two users in different tenants cannot see each other's workspace reports/screeners.
6. Add tests where two users in same tenant can see workspace reports but not private reports.

## Phase 3: Multi-Tenant Audit Log

### Task 7: Add audit event table and service

**Files:**
- Create migration: `web/backend/alembic/versions/20260427_000011_create_audit_events.py`
- Create: `web/backend/audit.py`
- Test: `tests/web/test_audit_backend.py`

**What this does:**
Record security and sharing actions in a structured table.

**Schema:**
- `id`
- `tenant_id`
- `actor_user_id`
- `action`
- `resource_type`
- `resource_id`
- `metadata_json`
- `ip_address`
- `user_agent`
- `created_at`

**Steps:**
1. Write tests for `record_audit_event`.
2. Add ORM model `AuditEvent`.
3. Add helper that best-effort records events and logs failures.
4. Add list API later only for admins; do not expose in first task unless needed.

### Task 8: Instrument critical actions

**Files:**
- Modify: `web/backend/routers/auth.py`
- Modify: `web/backend/routers/admin.py`
- Modify: `web/backend/routers/tasks.py`
- Modify: `web/backend/routers/screeners.py`
- Modify: `web/backend/services/reports.py`
- Modify: `web/backend/services/assets.py`
- Modify: `web/backend/services/trades.py`
- Test: `tests/web/test_audit_backend.py`

**What this does:**
Audit login success/failure, logout, user create/update/delete/password reset, analysis/screener creation, report visibility changes, asset writes, journal writes, and permission denials.

**Steps:**
1. Add audit calls after successful mutations.
2. Add audit calls for denied sensitive actions.
3. Keep audit metadata small and avoid secrets, report content, API keys, raw prompts, portfolio details, and full exception text.
4. Test representative actions create expected event rows.

### Task 9: Admin audit read API

**Files:**
- Modify: `web/backend/routers/admin.py`
- Modify: `web/backend/schemas/admin.py`
- Test: `tests/web/test_audit_backend.py`

**What this does:**
Let tenant admins inspect audit events for their tenant with filters.

**Steps:**
1. Add `GET /api/admin/audit-events`.
2. Require `admin:audit` permission.
3. Filter by current user's tenant_id.
4. Support optional filters: `action`, `resource_type`, `actor_user_id`, `created_from`, `created_to`, `limit`.
5. Verify admins from tenant A cannot read tenant B events.

## Phase 4: Frontend and Operations

### Task 10: Surface permissions in auth state

**Files:**
- Modify: `web/backend/auth.py`
- Modify: `web/frontend/app/**`
- Test: `tests/web/test_auth_backend.py`
- Test: `web/frontend/app/globals.test.mjs`

**What this does:**
Return effective permissions and tenant in `/api/auth/me`, then hide or disable UI actions based on permissions.

**Steps:**
1. Add `permissions` and `tenant` fields to auth payload.
2. Update frontend auth types.
3. Hide create buttons when create permission is missing.
4. Keep backend enforcement as source of truth.

### Task 11: Documentation and deployment checklist

**Files:**
- Modify: `README.md`
- Modify: `web/README.md`
- Modify: `docs/deployment/tencent-cloud-production.md`

**What this does:**
Document tenant model, permission presets, migration order, and audit retention.

**Steps:**
1. Document default tenant migration.
2. Document role preset mapping.
3. Document audit event retention and what must never be logged.
4. Add rollback notes for each migration phase.

## Recommended Execution Order

1. Phase 1 RBAC first, preserving current behavior.
2. Phase 2 tenant schema and query filters second.
3. Phase 3 audit logging third.
4. Phase 4 frontend/docs after backend contracts stabilize.

## Verification Commands

Run after each phase:

```bash
UV_CACHE_DIR=/tmp/uv-cache uv run --with pytest python -m pytest -q tests/web/test_auth_backend.py tests/web/test_backend_main.py
```

Run before merging:

```bash
UV_CACHE_DIR=/tmp/uv-cache uv run --with pytest python -m pytest -q
```

Expected before merge: all tests pass.
