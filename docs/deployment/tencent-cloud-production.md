# Tencent Cloud Production MVP Deployment

This deployment profile is for the domestic MVP stack:

- Tencent Cloud CVM or Lighthouse in mainland China
- Tencent Cloud COS as private object storage
- Docker Compose on one host
- Postgres on the same host with automated dumps to COS
- Redis with AOF for task queue and auth rate-limit state
- Nginx as the only public entrypoint

## DNS And ICP

Use DNSPod or Tencent Cloud DNS for the production domain. A mainland server serving a public website requires ICP filing before the domain is pointed at the server.

## Required Files

Create `.env` from `.env.example` and set at least:

```bash
PUBLIC_HOSTNAME=your-domain.example
FRONTEND_ORIGIN=https://your-domain.example
NEXT_PUBLIC_API_BASE_URL=https://your-domain.example
DATABASE_URL=postgresql://postgres:<password>@postgres:5432/diverge
POSTGRES_PASSWORD=<password>
AUTH_BOOTSTRAP_ADMIN_EMAIL=<admin-email>
AUTH_BOOTSTRAP_ADMIN_PASSWORD=<admin-password>
SESSION_COOKIE_SECURE=true
TASK_BACKEND=redis
STORAGE_BACKEND=tencent_cos
COS_SECRET_ID=<secret-id>
COS_SECRET_KEY=<secret-key>
COS_REGION=<same-region-as-server>
COS_BUCKET=<private-bucket-name>
COS_PREFIX=diverge/prod
```

Use `DATA_DIR` as the single standard data path. Reports, screener state/cache,
history, fundamentals, and manifests are derived from that root. Keep screener
manifests in the standard data layout:

```text
DATA_DIR/manifest/cn.csv
DATA_DIR/manifest/us.csv
```

CN screening can fall back to the configured CN source chain when `cn.csv` is absent. US screening requires `DATA_DIR/manifest/us.csv`; use `MANIFEST_DIR` or `SCREEN_US_MANIFEST_PATH` only when a deployment needs a non-standard location.

Put TLS files at:

```text
deploy/certs/fullchain.pem
deploy/certs/privkey.pem
```

## Start

```bash
docker compose -f compose.prod.yml build
docker compose -f compose.prod.yml up -d
docker compose -f compose.prod.yml ps
```

Only ports `80` and `443` should be public. Do not expose Postgres or Redis in the server firewall.

## Migrate Existing Local Data

After COS credentials are configured:

```bash
python -m web.backend.devops.migrate_local_data_to_storage --dry-run
python -m web.backend.devops.migrate_local_data_to_storage
```

The migration uploads:

- `data/reports` to `reports/`
- `data/screener/runs` to `screener/runs/`
- `data/history` to `history/`
- `data/cache/screener` to `cache/screener/`

Run the existing metadata backfill if historical reports or screener runs are not yet indexed in Postgres.

Auth schema rollout order:

1. Run `scripts/check-database.sh --upgrade --bootstrap-admin` so migrations create user permissions, the default tenant, workbench `tenant_id` columns, and `audit_events`.
2. Run metadata backfill for historical reports, trades, and screener runs; the records land in the default tenant unless you later move users/data with a dedicated migration.
3. Confirm `/api/auth/me` returns `permissions` and `tenant` for the bootstrap admin before switching public traffic to `AUTH_MODE=required`.

Audit events are tenant-scoped and readable from `/api/admin/audit-events` by users with `admin:audit`. Retain them only as long as your operational policy requires, and never log secrets, API keys, auth tokens, raw prompts, report content, portfolio details, or full exception text.

## Backup And Restore

The `backup` service runs `pg_dump` every `BACKUP_INTERVAL_SECONDS` and uploads compressed dumps to `backups/postgres/` in the configured storage backend.

Manual backup:

```bash
docker compose -f compose.prod.yml run --rm -e BACKUP_ONCE=true backup
```

Manual restore from a downloaded backup:

```bash
POSTGRES_HOST=postgres scripts/restore-postgres.sh /path/to/postgres-backup.sql.gz
```

Do a restore rehearsal before real users depend on the service.

## Future Overseas Ports

The storage API is intentionally interface-based. A future overseas deployment can add an `s3_compatible` adapter for Cloudflare R2, S3, or overseas COS without rewriting report, screener, or history business logic.

The frontend is also deployable separately because it uses `NEXT_PUBLIC_API_BASE_URL` and does not assume same-origin APIs. For a future Vercel deployment, set `NEXT_PUBLIC_API_BASE_URL` to the overseas backend URL and add the Vercel domain to backend `FRONTEND_ORIGIN`.
