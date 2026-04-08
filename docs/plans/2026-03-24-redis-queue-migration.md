# Plan

把当前“进程内内存任务表 + 后台线程”切换成 Redis-only 的队列架构，目标是在不引入 DB 的前提下，保留现有 API 形状、让任务状态和进度在服务重启后可恢复，并把执行从 Web 进程中拆出去。假设仍然是单机部署，Redis 开启持久化，报告文件继续落在本地 `reports/` 目录。

## Scope
- In:
  - 用 Redis 替换 `web/backend/main.py` 里的内存 `tasks`
  - 新增独立 worker 进程/容器消费任务
  - 保持现有 `/api/tasks`、`/api/tasks/{id}`、`/api/tasks/{id}/stream` 对前端可用
  - 更新本地启动脚本和 Docker Compose 部署
- Out:
  - 引入 Postgres/MySQL/SQLite
  - 改造报告存储到对象存储
  - 多区域/多机高可用
  - 认证、权限、多租户

## Action items
[ ] Add a Redis-backed task store module under `web/backend/` that defines the queue and state model: `tasks:queue` for pending jobs, `task:{id}` hashes for task metadata, `task:{id}:events` streams or lists for progress replay, and an index structure for `GET /api/tasks` ordering.
[ ] Refactor `web/backend/main.py` to remove the process-local `tasks` dictionary and `_start_task_thread()` path, so `POST /api/tasks` validates input, writes initial task metadata to Redis, enqueues `task_id`, and all task-read endpoints load state and progress from Redis.
[ ] Add a dedicated worker entrypoint such as `web/backend/worker.py` that blocks on Redis, claims a task, marks it `running`, executes `run_analysis_streaming()`, appends progress events to Redis, persists reports via `save_report_to_disk()`, and finalizes the task as `completed` or `failed`.
[ ] Add Redis-only recovery semantics: write `worker_id`, `heartbeat_at`, and `lease_expires_at` while a task is running; on worker startup, scan stale `running` tasks and either requeue or fail them; make `reports/.tmp/<task_id>` cleanup and reruns idempotent.
[ ] Move the current queue limit from hardcoded logic to an env-driven setting such as `TASK_QUEUE_LIMIT`, and enforce it using Redis counts for `pending` and `running` tasks rather than local memory.
[ ] Add backend and worker tests that cover enqueue, queue-full rejection, status lookup, SSE event replay, successful completion, failure handling, and stale-task recovery; update `tests/web/test_backend_main.py` and add dedicated task-store or worker tests with `fakeredis` or an equivalent fake Redis layer.
[ ] Update dependency wiring so local development installs the Redis-capable backend environment cleanly, including any new test-only dependency such as `fakeredis`; verify `pyproject.toml`, `requirements.txt`, and `web/backend/requirements.txt` are aligned with the chosen install path.
[ ] Update `web/start.sh` so local development either starts Redis or fails fast if Redis is missing, then launches the API process and the worker process separately with shared `REDIS_URL`, `REPORTS_DIR`, and queue configuration env vars.
[ ] Update `docker-compose.yml` to add a `redis` service with persistence, healthcheck, and a data volume; split the current backend runtime into separate `backend` and `worker` services that share the same image plus the `reports` and `.env` mounts, but use different commands.
[ ] Update `web/backend/Dockerfile`, `web/README.md`, and deployment notes so production clearly runs API-only in the backend container, worker-only in the worker container, documents Redis env vars and persistence mode, and includes rollout and rollback verification steps.

## Open questions
- Redis persistence should use `appendonly yes` with `appendfsync everysec`, or a stricter mode?
- Stale `running` tasks should default to automatic requeue, or fail-fast with manual retry?
- Completed task metadata and progress events should be retained in Redis for how long?
