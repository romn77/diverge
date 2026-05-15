# CI And Quality Gates

Use this reference when turning automated testing into repeatable repository
checks.

## PR Fast Lane

Goal: catch high-signal regressions without making every PR painful.

Recommended initial checks:

```bash
python -m pytest -q tests/web tests/runtime tests/decision_card
cd web/frontend && npm test
cd web/frontend && npm run build
cd web/frontend && npm run test:e2e -- --project=chromium
```

Tune the pytest subset after measuring runtime. When a PR changes dataflows,
valuation, auth, screeners, or runtime, add the relevant focused subset.

## Nightly Lane

Goal: find slower integration and production-shape issues.

Recommended checks:

```bash
python -m pytest -q
cd web/frontend && npm run lint
docker compose up -d postgres redis
scripts/check-database.sh --upgrade --bootstrap-admin
cd web/frontend && npm run test:e2e:smoke
```

Use nightly or manual release gates for Docker, Postgres, Redis, and broader
browser matrices.

## Release Smoke

Goal: prove the deployable system can boot.

Cover:

- backend `/api/healthz`
- frontend reachable
- auth bootstrap admin with database migrations
- Redis worker reachable when `TASK_BACKEND=redis`
- one deterministic task or queue lifecycle operation

Keep provider secrets optional. If a release check needs real provider keys,
make it an explicit scheduled/manual job and document failure ownership.

## PR Review Expectations

For each PR, ask:

- Which user workflow or API contract changed?
- Which test would fail on the old bug?
- Are auth, ownership, tenant, audit, or secret boundaries involved?
- Are generated report/screener artifacts involved?
- Are start scripts, Compose, or env vars involved?
- Was the browser path checked if the user-visible route changed?

## Quarantine Policy

If an E2E test is flaky:

- mark it with an issue link and owner
- keep the stable part of the assertion if possible
- do not silently remove coverage
- prefer fixing waits/fixtures/selectors over adding retries

## Reporting

Final responses and PR descriptions should include:

- tests run
- tests skipped and why
- fixture mode used
- any live external dependencies avoided
- remaining risk, especially for auth, task runtime, storage, and deployment
