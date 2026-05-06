from __future__ import annotations

import json
import os
import time
import contextlib
from typing import Any


QUEUED_STATUSES = {"pending", "queued"}
ACTIVE_STATUSES = {"pending", "queued", "waiting_for_quota", "running"}
RUNNING_STATUSES = {"running"}
TERMINAL_STATUSES = {"completed", "failed", "canceled"}
DEFAULT_TERMINAL_TTL_SECONDS = 7 * 24 * 60 * 60
TASK_KINDS = ("analysis", "screener", "data_sync")


def _dumps(payload: dict) -> str:
    return json.dumps(payload, ensure_ascii=False, separators=(",", ":"))


def _loads(value: Any) -> dict:
    if isinstance(value, bytes):
        value = value.decode("utf-8")
    if isinstance(value, str):
        return json.loads(value)
    if isinstance(value, dict):
        return value
    raise TypeError("Stored task payload must be JSON text or a dict")


class InMemoryTaskStore:
    def __init__(self):
        self.tasks: dict[str, dict[str, dict]] = {kind: {} for kind in TASK_KINDS}
        self.events: dict[str, dict[str, list[dict]]] = {kind: {} for kind in TASK_KINDS}
        self.queue_names: dict[str, list[str]] = {kind: [] for kind in TASK_KINDS}
        self.processing_names: dict[str, list[str]] = {kind: [] for kind in TASK_KINDS}
        self.delayed_names: dict[str, dict[str, float]] = {kind: {} for kind in TASK_KINDS}
        self.ids: dict[str, list[str]] = {kind: [] for kind in TASK_KINDS}

    def save_task(self, kind: str, task_id: str, payload: dict, *, enqueue: bool = False) -> None:
        self.tasks.setdefault(kind, {})[task_id] = dict(payload)
        ids = self.ids.setdefault(kind, [])
        if task_id not in ids:
            ids.append(task_id)
        if enqueue:
            self.enqueue(kind, task_id)

    def get_task(self, kind: str, task_id: str) -> dict | None:
        payload = self.tasks.setdefault(kind, {}).get(task_id)
        return dict(payload) if payload is not None else None

    def delete_task(self, kind: str, task_id: str) -> None:
        self.tasks.setdefault(kind, {}).pop(task_id, None)
        self.events.setdefault(kind, {}).pop(task_id, None)
        with contextlib.suppress(ValueError):
            self.queue_names.setdefault(kind, []).remove(task_id)
        with contextlib.suppress(ValueError):
            self.processing_names.setdefault(kind, []).remove(task_id)
        self.delayed_names.setdefault(kind, {}).pop(task_id, None)
        with contextlib.suppress(ValueError):
            self.ids.setdefault(kind, []).remove(task_id)

    def list_tasks(self, kind: str) -> list[dict]:
        self.tasks.setdefault(kind, {})
        return [
            dict(self.tasks[kind][task_id])
            for task_id in self.ids.setdefault(kind, [])
            if task_id in self.tasks.setdefault(kind, {})
        ]

    def count_active(self, kind: str) -> int:
        return sum(
            1
            for task in self.tasks.setdefault(kind, {}).values()
            if task.get("status") in ACTIVE_STATUSES
        )

    def count_running(self, kind: str | None = None) -> int:
        tasks = (
            [task for task_by_kind in self.tasks.values() for task in task_by_kind.values()]
            if kind is None
            else list(self.tasks.setdefault(kind, {}).values())
        )
        return sum(1 for task in tasks if task.get("status") in RUNNING_STATUSES)

    def count_active_by_owner(self, owner_user_id: str | None) -> int:
        owner_key = owner_user_id or None
        return sum(
            1
            for task_by_kind in self.tasks.values()
            for task in task_by_kind.values()
            if task.get("owner_user_id") == owner_key
            and task.get("status") in ACTIVE_STATUSES
        )

    def count_running_by_owner(self, owner_user_id: str | None) -> int:
        owner_key = owner_user_id or None
        return sum(
            1
            for task_by_kind in self.tasks.values()
            for task in task_by_kind.values()
            if task.get("owner_user_id") == owner_key
            and task.get("status") in RUNNING_STATUSES
        )

    def append_event(self, kind: str, task_id: str, payload: dict) -> None:
        self.events.setdefault(kind, {}).setdefault(task_id, []).append(dict(payload))

    def list_events(self, kind: str, task_id: str, start: int = 0) -> list[dict]:
        return list(self.events.setdefault(kind, {}).setdefault(task_id, [])[start:])

    def enqueue(self, kind: str, task_id: str) -> None:
        queue = self.queue_names.setdefault(kind, [])
        self.delayed_names.setdefault(kind, {}).pop(task_id, None)
        if task_id not in queue:
            queue.append(task_id)

    def claim(self, kind: str, *, timeout: int = 5) -> str | None:
        queue = self.queue_names.setdefault(kind, [])
        if not queue:
            return None
        task_id = queue.pop(0)
        processing = self.processing_names.setdefault(kind, [])
        if task_id not in processing:
            processing.append(task_id)
        return task_id

    def ack(self, kind: str, task_id: str) -> None:
        with contextlib.suppress(ValueError):
            self.processing_names.setdefault(kind, []).remove(task_id)

    def recover_processing(self, kind: str) -> None:
        return None

    def delay(self, kind: str, task_id: str, blocked_until_ts: float) -> None:
        with contextlib.suppress(ValueError):
            self.queue_names.setdefault(kind, []).remove(task_id)
        self.ack(kind, task_id)
        self.delayed_names.setdefault(kind, {})[task_id] = blocked_until_ts

    def promote_due_delayed(self, kind: str, now_ts: float) -> list[str]:
        due_ids = [
            task_id
            for task_id, blocked_until_ts in self.delayed_names.setdefault(kind, {}).items()
            if blocked_until_ts <= now_ts
        ]
        for task_id in due_ids:
            self.delayed_names[kind].pop(task_id, None)
            self.enqueue(kind, task_id)
        return due_ids

    def queue_ids(self, kind: str) -> list[str]:
        return list(self.queue_names.setdefault(kind, []))

    def processing_ids(self, kind: str) -> list[str]:
        return list(self.processing_names.setdefault(kind, []))

    def claim_ready(self, kind: str, task_id: str) -> bool:
        queue = self.queue_names.setdefault(kind, [])
        with contextlib.suppress(ValueError):
            queue.remove(task_id)
            processing = self.processing_names.setdefault(kind, [])
            if task_id not in processing:
                processing.append(task_id)
            return True
        return False

    def remove_task_refs(self, kind: str, task_id: str) -> None:
        with contextlib.suppress(ValueError):
            self.queue_names.setdefault(kind, []).remove(task_id)
        with contextlib.suppress(ValueError):
            self.processing_names.setdefault(kind, []).remove(task_id)
        self.delayed_names.setdefault(kind, {}).pop(task_id, None)

    def queue_position(self, kind: str, task_id: str) -> int | None:
        queue = self.queue_names.setdefault(kind, [])
        try:
            return queue.index(task_id) + 1
        except ValueError:
            return None


class RedisTaskStore:
    def __init__(self, client, *, prefix: str = "diverge"):
        self.client = client
        self.prefix = prefix.strip(":")

    def _key(self, kind: str, suffix: str) -> str:
        return f"{self.prefix}:{kind}:{suffix}"

    def save_task(self, kind: str, task_id: str, payload: dict, *, enqueue: bool = False) -> None:
        self.client.set(self._key(kind, f"task:{task_id}"), _dumps(payload))
        self.client.sadd(self._key(kind, "ids"), task_id)
        self._apply_terminal_ttl(kind, task_id, payload)
        if enqueue:
            self.enqueue(kind, task_id)

    def get_task(self, kind: str, task_id: str) -> dict | None:
        value = self.client.get(self._key(kind, f"task:{task_id}"))
        if value is None:
            return None
        return _loads(value)

    def delete_task(self, kind: str, task_id: str) -> None:
        self.client.delete(
            self._key(kind, f"task:{task_id}"),
            self._key(kind, f"task:{task_id}:events"),
        )
        self.client.srem(self._key(kind, "ids"), task_id)
        self.client.lrem(self._key(kind, "queue"), 0, task_id)
        self.client.lrem(self._key(kind, "processing"), 0, task_id)
        self.client.zrem(self._key(kind, "delayed"), task_id)

    def list_tasks(self, kind: str) -> list[dict]:
        ids = self.client.smembers(self._key(kind, "ids")) or []
        seen: set[str] = set()
        tasks: list[dict] = []
        for raw_task_id in ids:
            task_id = raw_task_id.decode("utf-8") if isinstance(raw_task_id, bytes) else str(raw_task_id)
            if task_id in seen:
                continue
            seen.add(task_id)
            payload = self.get_task(kind, task_id)
            if payload is not None:
                tasks.append(payload)
            else:
                self.client.srem(self._key(kind, "ids"), task_id)
        return tasks

    def count_active(self, kind: str) -> int:
        return sum(1 for task in self.list_tasks(kind) if task.get("status") in ACTIVE_STATUSES)

    def count_running(self, kind: str | None = None) -> int:
        if kind is not None:
            tasks = self.list_tasks(kind)
        else:
            tasks = [
                task
                for task_kind in TASK_KINDS
                for task in self.list_tasks(task_kind)
            ]
        return sum(1 for task in tasks if task.get("status") in RUNNING_STATUSES)

    def count_active_by_owner(self, owner_user_id: str | None) -> int:
        owner_key = owner_user_id or None
        return sum(
            1
            for task_kind in TASK_KINDS
            for task in self.list_tasks(task_kind)
            if task.get("owner_user_id") == owner_key
            and task.get("status") in ACTIVE_STATUSES
        )

    def count_running_by_owner(self, owner_user_id: str | None) -> int:
        owner_key = owner_user_id or None
        return sum(
            1
            for task_kind in TASK_KINDS
            for task in self.list_tasks(task_kind)
            if task.get("owner_user_id") == owner_key
            and task.get("status") in RUNNING_STATUSES
        )

    def append_event(self, kind: str, task_id: str, payload: dict) -> None:
        event_key = self._key(kind, f"task:{task_id}:events")
        self.client.rpush(event_key, _dumps(payload))
        if payload.get("status") in TERMINAL_STATUSES:
            ttl = get_terminal_ttl_seconds()
            if ttl is not None:
                self.client.expire(event_key, ttl)

    def list_events(self, kind: str, task_id: str, start: int = 0) -> list[dict]:
        values = self.client.lrange(self._key(kind, f"task:{task_id}:events"), start, -1) or []
        return [_loads(value) for value in values]

    def enqueue(self, kind: str, task_id: str) -> None:
        self.client.lrem(self._key(kind, "queue"), 0, task_id)
        self.client.zrem(self._key(kind, "delayed"), task_id)
        self.client.rpush(self._key(kind, "queue"), task_id)

    def claim(self, kind: str, *, timeout: int = 5) -> str | None:
        result = self.client.blmove(
            self._key(kind, "queue"),
            self._key(kind, "processing"),
            timeout=timeout,
            src="LEFT",
            dest="RIGHT",
        )
        if result is None:
            return None
        task_id = result.decode("utf-8") if isinstance(result, bytes) else str(result)
        task = self.get_task(kind, task_id)
        if task is not None:
            task["status"] = "running"
            task["worker_claimed_at"] = int(time.time())
            self.save_task(kind, task_id, task, enqueue=False)
        else:
            self.ack(kind, task_id)
        return task_id

    def ack(self, kind: str, task_id: str) -> None:
        self.client.lrem(self._key(kind, "processing"), 0, task_id)

    def recover_processing(self, kind: str) -> None:
        raw_ids = self.client.lrange(self._key(kind, "processing"), 0, -1) or []
        for raw_task_id in raw_ids:
            task_id = raw_task_id.decode("utf-8") if isinstance(raw_task_id, bytes) else str(raw_task_id)
            task = self.get_task(kind, task_id)
            if task is None or task.get("status") in TERMINAL_STATUSES:
                self.ack(kind, task_id)
            elif task.get("status") in QUEUED_STATUSES:
                self.ack(kind, task_id)
                self.enqueue(kind, task_id)

    def delay(self, kind: str, task_id: str, blocked_until_ts: float) -> None:
        self.client.lrem(self._key(kind, "queue"), 0, task_id)
        self.client.lrem(self._key(kind, "processing"), 0, task_id)
        self.client.zadd(self._key(kind, "delayed"), {task_id: blocked_until_ts})

    def promote_due_delayed(self, kind: str, now_ts: float) -> list[str]:
        values = self.client.zrangebyscore(self._key(kind, "delayed"), 0, now_ts) or []
        due_ids = [
            value.decode("utf-8") if isinstance(value, bytes) else str(value)
            for value in values
        ]
        for task_id in due_ids:
            self.client.zrem(self._key(kind, "delayed"), task_id)
            self.enqueue(kind, task_id)
        return due_ids

    def queue_ids(self, kind: str) -> list[str]:
        values = self.client.lrange(self._key(kind, "queue"), 0, -1) or []
        return [
            value.decode("utf-8") if isinstance(value, bytes) else str(value)
            for value in values
        ]

    def processing_ids(self, kind: str) -> list[str]:
        values = self.client.lrange(self._key(kind, "processing"), 0, -1) or []
        return [
            value.decode("utf-8") if isinstance(value, bytes) else str(value)
            for value in values
        ]

    def claim_ready(self, kind: str, task_id: str) -> bool:
        removed = self.client.lrem(self._key(kind, "queue"), 1, task_id)
        if not removed:
            return False
        self.client.rpush(self._key(kind, "processing"), task_id)
        return True

    def remove_task_refs(self, kind: str, task_id: str) -> None:
        self.client.lrem(self._key(kind, "queue"), 0, task_id)
        self.client.lrem(self._key(kind, "processing"), 0, task_id)
        self.client.zrem(self._key(kind, "delayed"), task_id)

    def queue_position(self, kind: str, task_id: str) -> int | None:
        for index, queued_task_id in enumerate(self.queue_ids(kind), start=1):
            if queued_task_id == task_id:
                return index
        return None

    def _apply_terminal_ttl(self, kind: str, task_id: str, payload: dict) -> None:
        if payload.get("status") not in TERMINAL_STATUSES:
            return
        ttl = get_terminal_ttl_seconds()
        if ttl is None:
            return
        self.client.expire(self._key(kind, f"task:{task_id}"), ttl)
        self.client.expire(self._key(kind, f"task:{task_id}:events"), ttl)


_TASK_STORE = None


def reset_task_store_cache() -> None:
    global _TASK_STORE
    _TASK_STORE = None


def redis_task_backend_enabled() -> bool:
    return os.environ.get("TASK_BACKEND", "local").strip().lower() == "redis"


def get_queue_limit() -> int:
    raw_value = os.environ.get("TASK_QUEUE_LIMIT", "2").strip()
    try:
        parsed = int(raw_value)
    except ValueError as exc:
        raise RuntimeError("TASK_QUEUE_LIMIT must be an integer") from exc
    if parsed <= 0:
        raise RuntimeError("TASK_QUEUE_LIMIT must be greater than zero")
    return parsed


def _read_positive_int_env(name: str, default: int) -> int:
    raw_value = os.environ.get(name, str(default)).strip()
    try:
        parsed = int(raw_value)
    except ValueError as exc:
        raise RuntimeError(f"{name} must be an integer") from exc
    if parsed <= 0:
        raise RuntimeError(f"{name} must be greater than zero")
    return parsed


def get_global_running_limit() -> int:
    if "TASK_GLOBAL_RUNNING_LIMIT" in os.environ:
        return _read_positive_int_env("TASK_GLOBAL_RUNNING_LIMIT", 2)
    return get_queue_limit()


def get_user_running_limit() -> int:
    return _read_positive_int_env("TASK_USER_RUNNING_LIMIT", 1)


def get_global_pending_limit() -> int:
    return _read_positive_int_env("TASK_GLOBAL_PENDING_LIMIT", 100)


def get_user_pending_limit(role: str | None) -> int:
    role_key = str(role or "").strip().lower()
    env_key = f"TASK_USER_PENDING_LIMIT_{role_key.upper()}" if role_key else ""
    if env_key and env_key in os.environ:
        return _read_positive_int_env(env_key, 1)
    if role_key == "admin":
        return _read_positive_int_env("TASK_USER_PENDING_LIMIT_ADMIN", 10)
    if role_key == "viewer":
        return _read_positive_int_env("TASK_USER_PENDING_LIMIT_VIEWER", 2)
    return _read_positive_int_env("TASK_USER_PENDING_LIMIT_OPERATOR", 5)


def get_terminal_ttl_seconds() -> int | None:
    raw_value = os.environ.get(
        "TASK_STORE_TERMINAL_TTL_SECONDS",
        str(DEFAULT_TERMINAL_TTL_SECONDS),
    ).strip()
    try:
        parsed = int(raw_value)
    except ValueError as exc:
        raise RuntimeError("TASK_STORE_TERMINAL_TTL_SECONDS must be an integer") from exc
    if parsed <= 0:
        return None
    return parsed


def get_task_store():
    global _TASK_STORE
    if _TASK_STORE is not None:
        return _TASK_STORE
    if not redis_task_backend_enabled():
        _TASK_STORE = InMemoryTaskStore()
        return _TASK_STORE
    try:
        import redis
    except ImportError as exc:  # pragma: no cover - dependency is present in production image.
        raise RuntimeError("redis package is required when TASK_BACKEND=redis") from exc
    redis_url = os.environ.get("REDIS_URL", "redis://redis:6379/0")
    _TASK_STORE = RedisTaskStore(
        redis.Redis.from_url(redis_url, decode_responses=False),
        prefix=os.environ.get("TASK_STORE_PREFIX", "diverge"),
    )
    return _TASK_STORE
