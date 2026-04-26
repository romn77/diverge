from __future__ import annotations

import json
import os
import time
import contextlib
from typing import Any


ACTIVE_STATUSES = {"pending", "running"}


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
        self.tasks: dict[str, dict[str, dict]] = {"analysis": {}, "screener": {}}
        self.events: dict[str, dict[str, list[dict]]] = {"analysis": {}, "screener": {}}
        self.queue_names: dict[str, list[str]] = {"analysis": [], "screener": []}
        self.ids: dict[str, list[str]] = {"analysis": [], "screener": []}

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
            self.ids.setdefault(kind, []).remove(task_id)

    def list_tasks(self, kind: str) -> list[dict]:
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

    def append_event(self, kind: str, task_id: str, payload: dict) -> None:
        self.events.setdefault(kind, {}).setdefault(task_id, []).append(dict(payload))

    def list_events(self, kind: str, task_id: str, start: int = 0) -> list[dict]:
        return list(self.events.setdefault(kind, {}).setdefault(task_id, [])[start:])

    def enqueue(self, kind: str, task_id: str) -> None:
        queue = self.queue_names.setdefault(kind, [])
        if task_id not in queue:
            queue.append(task_id)

    def claim(self, kind: str, *, timeout: int = 5) -> str | None:
        queue = self.queue_names.setdefault(kind, [])
        if not queue:
            return None
        return queue.pop(0)


class RedisTaskStore:
    def __init__(self, client, *, prefix: str = "tradingagents"):
        self.client = client
        self.prefix = prefix.strip(":")

    def _key(self, kind: str, suffix: str) -> str:
        return f"{self.prefix}:{kind}:{suffix}"

    def save_task(self, kind: str, task_id: str, payload: dict, *, enqueue: bool = False) -> None:
        self.client.set(self._key(kind, f"task:{task_id}"), _dumps(payload))
        self.client.rpush(self._key(kind, "ids"), task_id)
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
        self.client.lrem(self._key(kind, "ids"), 0, task_id)
        self.client.lrem(self._key(kind, "queue"), 0, task_id)

    def list_tasks(self, kind: str) -> list[dict]:
        ids = self.client.lrange(self._key(kind, "ids"), 0, -1) or []
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
        return tasks

    def count_active(self, kind: str) -> int:
        return sum(1 for task in self.list_tasks(kind) if task.get("status") in ACTIVE_STATUSES)

    def append_event(self, kind: str, task_id: str, payload: dict) -> None:
        self.client.rpush(self._key(kind, f"task:{task_id}:events"), _dumps(payload))

    def list_events(self, kind: str, task_id: str, start: int = 0) -> list[dict]:
        values = self.client.lrange(self._key(kind, f"task:{task_id}:events"), start, -1) or []
        return [_loads(value) for value in values]

    def enqueue(self, kind: str, task_id: str) -> None:
        self.client.rpush(self._key(kind, "queue"), task_id)

    def claim(self, kind: str, *, timeout: int = 5) -> str | None:
        result = self.client.blpop(self._key(kind, "queue"), timeout=timeout)
        if result is None:
            return None
        _queue, raw_task_id = result
        task_id = raw_task_id.decode("utf-8") if isinstance(raw_task_id, bytes) else str(raw_task_id)
        task = self.get_task(kind, task_id)
        if task is not None:
            task["status"] = "running"
            task["worker_claimed_at"] = int(time.time())
            self.save_task(kind, task_id, task, enqueue=False)
        return task_id


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
        prefix=os.environ.get("TASK_STORE_PREFIX", "tradingagents"),
    )
    return _TASK_STORE
