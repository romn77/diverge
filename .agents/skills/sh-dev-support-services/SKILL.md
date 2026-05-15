---
name: sh-dev-support-services
description: Operate the Diverge local-development workflow that runs frontend, backend, worker, and DATA_DIR locally while using SH development-only Postgres and Redis through an SSH tunnel. Use when asked how to start, check, troubleshoot, document, or modify the SH dev support-service workflow; when local/company development cannot access database or Redis features; or when working on scripts/configuration for dev-support tunnels, Redis task prefixes, local workers, or DATA_DIR sync.
---

# SH Dev Support Services

## Purpose

Use this skill for the SH development support-service workflow:

- local machine runs Next.js frontend, FastAPI backend, worker, and `DATA_DIR`
- SH server provides development-only Postgres and Redis
- access to SH services goes through SSH/Tailscale, not public database ports
- optional `DATA_DIR` sync uses `rsync`

## Core Rules

- Keep the worker local in this mode. The local backend enqueues tasks, the local
  worker consumes them, and local `DATA_DIR` receives generated files.
- Do not point this workflow at production databases. The SH server is assumed to
  contain development databases only.
- Do not expose Postgres or Redis publicly. Use `scripts/dev-support-tunnel.sh`
  or an equivalent secure tunnel.
- Use a non-production Redis DB and a unique `TASK_STORE_PREFIX` per developer
  or machine so workers do not compete for the same queue.
- Keep real env files untracked. Edit `configs/env/sh-dev.env`; commit only
  `configs/env/sh-dev.example.env`.

## Startup Workflow

When the user asks how to start the SH dev flow, give this sequence:

```bash
cp configs/env/sh-dev.example.env configs/env/sh-dev.env
# edit configs/env/sh-dev.env

scripts/dev-support-tunnel.sh
scripts/dev-check-support-services.sh --upgrade --bootstrap-admin
scripts/dev-start-sh.sh
```

For normal daily use after the database is initialized:

```bash
scripts/dev-support-tunnel.sh
scripts/dev-check-support-services.sh
scripts/dev-start-sh.sh
```

Optional file sync:

```bash
scripts/dev-sync-data.sh pull
scripts/dev-sync-data.sh push
```

## Editing Guidance

When modifying this workflow:

1. Prefer script/config/docs changes over business-code changes.
2. Keep `web/start.sh` compatible with the default `.env` flow.
3. Preserve `ENV_FILE=...` support for alternate profiles.
4. Preserve local worker startup when `TASK_BACKEND=redis`.
5. Preserve `TASK_STORE_PREFIX` export and visibility.
6. Run `bash -n` on changed shell scripts and `git diff --check`.

## References

Load only when details are needed:

- `docs/operations/sh-dev-support-services.md`: current runbook and command
  sequence.
- `configs/env/sh-dev.example.env`: env variables and defaults for this flow.
- `scripts/dev-support-tunnel.sh`: SSH tunnel entrypoint.
- `scripts/dev-check-support-services.sh`: Postgres/Redis connectivity check and
  optional migration/bootstrap wrapper.
- `scripts/dev-start-sh.sh`: local workbench starter for SH dev.
- `scripts/dev-sync-data.sh`: optional `DATA_DIR` pull/push helper.
