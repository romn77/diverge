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

Allow the Vercel origin and use cross-site secure cookies:

```bash
FRONTEND_ORIGIN=https://<demo>.vercel.app
SESSION_COOKIE_SECURE=true
SESSION_COOKIE_SAMESITE=none
```

Keep `AUTH_ENABLED`, `AUTH_MODE`, `DATABASE_URL`, `TASK_BACKEND`, `REDIS_URL`,
and `STORAGE_BACKEND` configured on the backend as usual.

## Acceptance Checks

1. Login succeeds from `https://<demo>.vercel.app`.
2. Authenticated API calls include the session cookie.
3. Report list and report detail load.
4. New analysis form submits to the backend.
5. Activity and task progress routes can read backend task state.

If the frontend and API later move to same-site subdomains, consider returning
`SESSION_COOKIE_SAMESITE` to `lax`.
