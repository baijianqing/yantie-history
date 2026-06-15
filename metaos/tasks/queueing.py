"""Redis/RQ queue helpers for asynchronous MetaOS jobs."""

from __future__ import annotations

from enum import Enum
from typing import Any

from redis import Redis
from redis.exceptions import RedisError
from rq import Queue

from metaos.core.config import get_settings
from metaos.core.errors import ConfigurationError
from metaos.core.schemas import Job, JobStatus, JobType
from metaos.workspace.jobs import JobRepository


class QueueName(str, Enum):
    ingest = "ingest"
    ocr = "ocr"
    index = "index"
    rag = "rag"


TASK_INGEST_DOCUMENT = "metaos.tasks.ingest.run_ingest_document"
TASK_REBUILD_CHUNKS = "metaos.tasks.ingest.run_rebuild_chunks"
TASK_PDF_ROUTE = "metaos.tasks.pdf.run_pdf_route"
TASK_OCR_DOCUMENT = "metaos.tasks.ocr.run_ocr_document"
TASK_OCR_PDF_PAGES = "metaos.tasks.ocr.run_ocr_pdf_pages"
TASK_INDEX_KNOWLEDGE = "metaos.tasks.indexing.run_index_knowledge"
TASK_REBUILD_INDEX = "metaos.tasks.indexing.run_rebuild_index"
TASK_RAG_ANSWER = "metaos.tasks.rag.run_answer_question"

DEFAULT_TIMEOUT_SECONDS = 60 * 60
MIN_TIMEOUT_SECONDS = 60


def redis_connection() -> Redis:
    return Redis.from_url(get_settings().redis_url)


def rq_queue(queue_name: QueueName | str) -> Queue:
    name = queue_name.value if isinstance(queue_name, QueueName) else queue_name
    return Queue(name, connection=redis_connection())


def configured_timeout(value: int | None) -> int:
    return max(MIN_TIMEOUT_SECONDS, int(value or DEFAULT_TIMEOUT_SECONDS))


def enqueue_job(
    *,
    job_type: JobType,
    queue_name: QueueName,
    task_path: str,
    payload: dict[str, Any] | None = None,
    timeout: int = DEFAULT_TIMEOUT_SECONDS,
) -> Job:
    repo = JobRepository()
    job = repo.create(job_type, payload or {})
    try:
        queue = rq_queue(queue_name)
        queue.enqueue_call(
            func=task_path,
            args=(job.id,),
            timeout=timeout,
            result_ttl=24 * 60 * 60,
            failure_ttl=7 * 24 * 60 * 60,
            job_id=job.id,
            description=f"{job_type.value}:{job.id}",
        )
    except RedisError as exc:
        repo.update(
            job.id,
            status=JobStatus.failed,
            progress=1,
            message="任务提交失败",
            error=f"无法连接 Redis：{exc}",
        )
        raise ConfigurationError(
            f"无法连接 Redis：{get_settings().redis_url}。请先启动 Redis。"
        ) from exc
    return repo.update(job.id, message=f"已提交队列：{queue_name.value}")


def enqueue_ingest_document(source_id: str, asset_id: str) -> Job:
    return enqueue_job(
        job_type=JobType.ingest_document,
        queue_name=QueueName.ingest,
        task_path=TASK_INGEST_DOCUMENT,
        payload={"source_id": source_id, "asset_id": asset_id},
    )


def enqueue_rebuild_chunks(knowledge_item_id: str) -> Job:
    return enqueue_job(
        job_type=JobType.rebuild_chunks,
        queue_name=QueueName.ingest,
        task_path=TASK_REBUILD_CHUNKS,
        payload={"knowledge_item_id": knowledge_item_id},
    )


def enqueue_pdf_route(source_id: str, asset_id: str) -> Job:
    return enqueue_job(
        job_type=JobType.pdf_route,
        queue_name=QueueName.ingest,
        task_path=TASK_PDF_ROUTE,
        payload={"source_id": source_id, "asset_id": asset_id},
        timeout=2 * 60 * 60,
    )


def enqueue_ocr_document(source_id: str, asset_id: str) -> Job:
    return enqueue_job(
        job_type=JobType.ocr_document,
        queue_name=QueueName.ocr,
        task_path=TASK_OCR_DOCUMENT,
        payload={"source_id": source_id, "asset_id": asset_id},
        timeout=2 * 60 * 60,
    )


def enqueue_ocr_pdf_pages(source_id: str, asset_id: str, plan_path: str) -> Job:
    return enqueue_job(
        job_type=JobType.ocr_document,
        queue_name=QueueName.ocr,
        task_path=TASK_OCR_PDF_PAGES,
        payload={"source_id": source_id, "asset_id": asset_id, "plan_path": plan_path},
        timeout=2 * 60 * 60,
    )


def enqueue_index_knowledge(knowledge_item_id: str, *, force_rebuild: bool = False) -> Job:
    settings = get_settings()
    return enqueue_job(
        job_type=JobType.index_knowledge,
        queue_name=QueueName.index,
        task_path=TASK_INDEX_KNOWLEDGE,
        payload={"knowledge_item_id": knowledge_item_id, "force_rebuild": force_rebuild},
        timeout=configured_timeout(settings.index_job_timeout_seconds),
    )


def enqueue_rebuild_index(*, force_rebuild: bool = False) -> Job:
    settings = get_settings()
    return enqueue_job(
        job_type=JobType.rebuild_index,
        queue_name=QueueName.index,
        task_path=TASK_REBUILD_INDEX,
        payload={"force_rebuild": force_rebuild},
        timeout=configured_timeout(settings.rebuild_index_job_timeout_seconds),
    )


def enqueue_rag_answer(question: str, top_k: int = 5) -> Job:
    return enqueue_job(
        job_type=JobType.answer_question,
        queue_name=QueueName.rag,
        task_path=TASK_RAG_ANSWER,
        payload={"question": question, "top_k": top_k},
    )


def enqueue_retry_job(job_id: str) -> Job:
    repo = JobRepository()
    job = repo.get(job_id)
    queue_name, task_path, timeout = retry_dispatch_for_job(job)
    retried = repo.retry_failed(job_id)
    try:
        queue = rq_queue(queue_name)
        queue.enqueue_call(
            func=task_path,
            args=(retried.id,),
            timeout=timeout,
            result_ttl=24 * 60 * 60,
            failure_ttl=7 * 24 * 60 * 60,
            job_id=retried.id,
            description=f"retry:{retried.type.value}:{retried.id}",
        )
    except RedisError as exc:
        repo.update(
            retried.id,
            status=JobStatus.failed,
            progress=1,
            message="Retry enqueue failed",
            error=f"Cannot connect to Redis: {exc}",
        )
        raise ConfigurationError(
            f"Cannot connect to Redis: {get_settings().redis_url}. Start Redis before retrying jobs."
        ) from exc
    return repo.update(retried.id, message=f"Requeued: {queue_name.value}")


def retry_dispatch_for_job(job: Job) -> tuple[QueueName, str, int]:
    settings = get_settings()
    if job.type == JobType.ingest_document:
        return QueueName.ingest, TASK_INGEST_DOCUMENT, DEFAULT_TIMEOUT_SECONDS
    if job.type == JobType.rebuild_chunks:
        return QueueName.ingest, TASK_REBUILD_CHUNKS, DEFAULT_TIMEOUT_SECONDS
    if job.type == JobType.pdf_route:
        return QueueName.ingest, TASK_PDF_ROUTE, 2 * 60 * 60
    if job.type == JobType.ocr_document:
        task_path = TASK_OCR_PDF_PAGES if job.payload.get("plan_path") else TASK_OCR_DOCUMENT
        return QueueName.ocr, task_path, 2 * 60 * 60
    if job.type == JobType.index_knowledge:
        return (
            QueueName.index,
            TASK_INDEX_KNOWLEDGE,
            configured_timeout(settings.index_job_timeout_seconds),
        )
    if job.type == JobType.rebuild_index:
        return (
            QueueName.index,
            TASK_REBUILD_INDEX,
            configured_timeout(settings.rebuild_index_job_timeout_seconds),
        )
    if job.type == JobType.answer_question:
        return QueueName.rag, TASK_RAG_ANSWER, DEFAULT_TIMEOUT_SECONDS
    raise ValueError(f"job type cannot be retried: {job.type.value}")
