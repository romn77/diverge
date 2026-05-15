# SH Development Support Services

This workflow keeps local development lightweight:

- local machine: Next.js frontend, FastAPI backend, worker, and `DATA_DIR`
- SH server: development-only Postgres and Redis
- optional sync: local `DATA_DIR` to/from the SH development data directory

The SH host is assumed to contain development databases only. If production data
is added later, create separate credentials and update these scripts before use.

## One-Time Local Setup

```bash
cp configs/env/sh-dev.example.env configs/env/sh-dev.env
```

Edit `configs/env/sh-dev.env`:

- set `SH_DEV_SSH_TARGET`
- set the `DATABASE_URL` password and database name
- set bootstrap admin values if the development database is empty
- keep `REDIS_URL` on a non-production Redis DB such as `/1`
- keep `TASK_STORE_PREFIX` unique per developer or machine

`configs/env/*.env` is ignored by git; only `*.example.env` files should be
committed.

## Startup Flow

Use this sequence when developing locally against the SH development support
services.

First, open the tunnel and leave it running:

```bash
scripts/dev-support-tunnel.sh
```

In a second terminal, initialize the SH development database the first time you
use it:

```bash
scripts/dev-check-support-services.sh --upgrade --bootstrap-admin
```

For normal daily checks after the database has already been initialized:

```bash
scripts/dev-check-support-services.sh
```

Optionally pull the SH development data snapshot before launching:

```bash
scripts/dev-sync-data.sh pull
```

Start the local Workbench:

```bash
scripts/dev-start-sh.sh
```

Open the frontend:

```text
http://localhost:3000
```

In this mode, frontend, backend, worker, and `DATA_DIR` are local. Postgres and
Redis are reached through the tunnel on the SH development server.

With `TASK_BACKEND=redis`, `web/start.sh` starts a local worker automatically.
Tasks created by your local backend are consumed by your local worker and write
files to your local `DATA_DIR`.

## Data Sync

Pull the SH development data snapshot:

```bash
scripts/dev-sync-data.sh pull
```

Push local generated data to the SH development data directory:

```bash
scripts/dev-sync-data.sh push
```

Preview changes without copying:

```bash
DEV_SYNC_DRY_RUN=true scripts/dev-sync-data.sh pull
DEV_SYNC_DRY_RUN=true scripts/dev-sync-data.sh push
```

Deletion mirroring is disabled by default. Enable it only when you explicitly
want the destination to match the source:

```bash
DEV_SYNC_DELETE=true scripts/dev-sync-data.sh pull
```

The sync script excludes temporary report directories such as `reports/.tmp/`.

## Important Boundaries

- Do not expose Postgres or Redis publicly; access them through SSH/Tailscale.
- Keep the worker local for this mode.
- Do not share a Redis DB and `TASK_STORE_PREFIX` with another active worker
  unless you want both workers to compete for the same queue.
- Keep generated files local while testing. Sync them only when the SH
  development data directory needs a copy.
