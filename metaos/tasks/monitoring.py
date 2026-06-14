"""Runtime monitoring helpers for Redis/RQ workers and queues."""

from __future__ import annotations

from typing import Any

from redis.exceptions import RedisError
from rq import Worker

from metaos.core.config import get_settings
from metaos.tasks.queueing import QueueName, redis_connection, rq_queue


def runtime_status() -> dict[str, Any]:
    """Return a best-effort snapshot of Redis, queues, and active RQ workers."""

    settings = get_settings()
    status: dict[str, Any] = {
        "redis": {
            "url": settings.redis_url,
            "ok": False,
            "error": None,
        },
        "queues": [],
        "workers": [],
        "worker_coverage": {},
    }

    try:
        connection = redis_connection()
        connection.ping()
        status["redis"]["ok"] = True
    except RedisError as exc:
        status["redis"]["error"] = str(exc)
        return status

    queues = [queue.value for queue in QueueName]
    try:
        for queue_name in queues:
            status["queues"].append(queue_status(queue_name))

        workers = worker_statuses()
        status["workers"] = workers
        status["worker_coverage"] = {
            queue_name: any(queue_name in worker.get("queues", []) for worker in workers)
            for queue_name in queues
        }
    except RedisError as exc:
        status["redis"]["ok"] = False
        status["redis"]["error"] = str(exc)
    return status


def queue_status(queue_name: str) -> dict[str, Any]:
    queue = rq_queue(queue_name)
    return {
        "name": queue_name,
        "queued": queue.count,
        "started": safe_registry_count(queue.started_job_registry),
        "deferred": safe_registry_count(queue.deferred_job_registry),
        "scheduled": safe_registry_count(queue.scheduled_job_registry),
        "finished": safe_registry_count(queue.finished_job_registry),
        "failed": safe_registry_count(queue.failed_job_registry),
    }


def worker_statuses() -> list[dict[str, Any]]:
    connection = redis_connection()
    workers = Worker.all(connection=connection)
    return [serialize_worker(worker) for worker in workers]


def serialize_worker(worker: Worker) -> dict[str, Any]:
    return {
        "name": worker.name,
        "state": str(getattr(worker, "state", "unknown")),
        "queues": [queue.name for queue in getattr(worker, "queues", [])],
        "current_job_id": safe_current_job_id(worker),
        "last_heartbeat": str(getattr(worker, "last_heartbeat", "") or ""),
        "birth_date": str(getattr(worker, "birth_date", "") or ""),
    }


def safe_current_job_id(worker: Worker) -> str | None:
    try:
        return worker.get_current_job_id()
    except Exception:
        return None


def safe_registry_count(registry) -> int:
    try:
        count = registry.count
        if callable(count):
            count = count()
        return int(count)
    except Exception:
        return 0
