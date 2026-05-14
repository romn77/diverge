# Vercel SG Frontend Demo

This runbook deploys only the Web Workbench frontend to Vercel for a Singapore
demo. Backend API, worker, Redis, Postgres, and object storage stay in the
current backend environment.

## Vercel Project

Set the Vercel project root to:

```text
web/frontend
```

Configure:

```bash
NEXT_PUBLIC_API_BASE_URL=https://<backend-api-domain>
```

The Vercel demo can use the generated `*.vercel.app` domain. A later custom
domain can use `sg.<domain>` for frontend and `api.<domain>` for backend.

## Backend Demo Environment

Use the API-only compose stack on the SG server:

```bash
docker compose -f compose.sg-vercel.yml build
docker compose -f compose.sg-vercel.yml up -d --remove-orphans
docker compose -f compose.sg-vercel.yml ps
```

This stack runs Nginx, FastAPI, the Redis task worker, prewarm workers, Postgres,
Redis, backups, and optional Dozzle. It does not build or run the Next.js
frontend. Nginx is the only public web entrypoint and forwards `/api/` to the
backend over the Docker network. The backend, worker, and prewarm services all
mount `./data:/app/data` so newly generated reports stay on the host.

Allow the Vercel origin and use cross-site secure cookies when the frontend is
served from `*.vercel.app`:

```bash
FRONTEND_ORIGIN=https://<demo>.vercel.app
SESSION_COOKIE_SECURE=true
SESSION_COOKIE_SAMESITE=none
```

Keep `AUTH_ENABLED`, `AUTH_MODE`, `DATABASE_URL`, and `STORAGE_BACKEND`
configured on the backend as usual. The compose file sets `TASK_BACKEND=redis`
and uses the in-stack Redis URL for API and worker services.

The public API must be HTTPS because the Vercel frontend is HTTPS and browsers
will reject mixed-content API calls. Place TLS certificates at `deploy/certs/`
for the Nginx container.

## Acceptance Checks

1. Login succeeds from `https://<demo>.vercel.app`.
2. Authenticated API calls include the session cookie.
3. Report list and report detail load.
4. New analysis form submits to the backend.
5. Activity and task progress routes can read backend task state.

If the frontend and API later move to same-site subdomains, consider returning
`SESSION_COOKIE_SAMESITE` to `lax`.
