# Task Troubleshooting

This runbook keeps task operations on logs and backend state only. It does not
require frontend or API contract changes.

## Production Baseline

Production task operations should run with durable task state:

```bash
TASK_BACKEND=redis
DATABASE_URL=postgresql://...
REDIS_URL=redis://redis:6379/0
LOG_LEVEL=INFO
```

`compose.prod.yml` already runs separate `backend` and `worker` services. Task
execution happens in `worker`; API submission and read endpoints happen in
`backend`.

## Tail Task Logs

Show recent task lifecycle and progress events:

```bash
scripts/ops-task-logs.sh
```

Filter to one task:

```bash
scripts/ops-task-logs.sh <task_id>
```

Follow live logs:

```bash
FOLLOW=true scripts/ops-task-logs.sh <task_id>
```

The task logs use a stable `task_event` marker and key/value fields:

```text
task_event event="task_started" kind="analysis" task_id="..." status="running" worker_id="host:123"
task_event event="task_progress" kind="screener" task_id="..." stage="Features" current="12" total="200"
task_event event="task_completed" kind="data_sync" task_id="..." elapsed_seconds="83.42"
```

Important fields:

- `event`: lifecycle marker such as `task_queued`, `task_queue_claimed`,
  `task_started`, `task_progress`, `task_waiting_for_quota`, `task_completed`,
  `task_failed`, `task_canceled`, or `worker_task_acknowledged`.
- `kind`: `analysis`, `screener`, or `data_sync`.
- `task_id`: task identifier to use across logs, Redis, and `job_records`.
- `worker_id`: `WORKER_ID` when configured, otherwise `hostname:pid`.
- `elapsed_seconds`: runtime since `started_at` when available.
- `queue_wait_seconds`: time from creation to start when available.
- `stage`, `current_agent`, `current`, `total`, `symbol`: progress details when
  the task runner emits them.

## Inspect Durable Task Records

Use Postgres when the task is not visible in current logs:

```sql
select kind, id, status, owner_user_id, tenant_id,
       created_at, queued_at, started_at, heartbeat_at, updated_at, finished_at,
       worker_id, error
from job_records
where status in ('pending', 'queued', 'waiting_for_quota', 'running')
order by coalesce(started_at, queued_at, created_at) desc;
```

For a single task:

```sql
select *
from job_records
where id = '<task_id>';
```

## Inspect Redis Queues

Queue keys use the configured `TASK_STORE_PREFIX`, defaulting to `diverge`.

```bash
docker compose -f compose.prod.yml exec redis redis-cli llen diverge:analysis:queue
docker compose -f compose.prod.yml exec redis redis-cli lrange diverge:analysis:processing 0 -1
docker compose -f compose.prod.yml exec redis redis-cli zrange diverge:analysis:delayed 0 -1 withscores
```

Repeat with `screener` or `data_sync`.

## Read The Result

- Queued but no `task_queue_claimed`: worker is not healthy, Redis is blocked,
  or running limits are saturated.
- `task_queue_claimed` but no later `task_started`: worker crashed immediately
  after claim.
- `task_started` with old `heartbeat_at`: the running task is stale or blocked
  inside a vendor/model call.
- `task_waiting_for_quota`: task was delayed by vendor quota and should return
  to the queue after `blocked_until`.
- `task_failed`: inspect `error_type`, short `error`, then tail backend/worker
  logs around the same timestamp for the stack trace.
