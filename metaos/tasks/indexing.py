"""Chroma indexing tasks for the index worker."""

from __future__ import annotations

from metaos.core.schemas import JobStatus
from metaos.retrieval.service import RetrievalService
from metaos.workspace.jobs import JobRepository
from metaos.workspace.paths import ensure_workspace


def index_failure_result(exc: Exception, *, knowledge_item_id: str | None = None) -> dict:
    error = str(exc)
    requires_rebuild = (
        "different embedding provider" in error
        or "embedding_dimensions" in error
        or "Chroma index" in error
    )
    result = {
        "error_type": type(exc).__name__,
        "requires_rebuild_index": requires_rebuild,
        "recommended_action": (
            "请先执行“重建全部索引”，再重新索引或搜索。"
            if requires_rebuild
            else "请查看 error 字段并修复对应服务或配置。"
        ),
    }
    if knowledge_item_id:
        result["knowledge_item_id"] = knowledge_item_id
    return result


def run_index_knowledge(job_id: str) -> dict:
    paths = ensure_workspace()
    jobs = JobRepository(paths.database)
    job = jobs.get(job_id)
    item_id = str(job.payload["knowledge_item_id"])
    force_rebuild = bool(job.payload.get("force_rebuild", False))

    try:
        retrieval = RetrievalService(paths)
        jobs.update(job_id, status=JobStatus.running, progress=0.05, message="索引知识条目")

        def update_progress(done: int, total: int) -> None:
            progress = 1.0 if total <= 0 else min(0.95, 0.05 + 0.9 * done / total)
            jobs.update(job_id, progress=progress, message=f"索引进度：{done}/{total} chunks")

        stats = retrieval.index_knowledge_item(
            item_id,
            progress_callback=update_progress,
            force_rebuild=force_rebuild,
        )
        result = stats.as_dict()
        result["knowledge_item_id"] = item_id
        jobs.update(
            job_id,
            status=JobStatus.succeeded,
            progress=1,
            message="索引完成",
            result=result,
        )
        return result
    except Exception as exc:
        jobs.update(
            job_id,
            status=JobStatus.failed,
            progress=1,
            message="索引失败",
            error=str(exc),
            result=index_failure_result(exc, knowledge_item_id=item_id),
        )
        raise


def run_rebuild_index(job_id: str) -> dict:
    paths = ensure_workspace()
    jobs = JobRepository(paths.database)
    job = jobs.get(job_id)
    force_rebuild = bool(job.payload.get("force_rebuild", False))

    try:
        retrieval = RetrievalService(paths)
        jobs.update(job_id, status=JobStatus.running, progress=0.05, message="重建全部索引")

        def update_progress(done: int, total: int) -> None:
            progress = 1.0 if total <= 0 else min(0.95, 0.05 + 0.9 * done / total)
            jobs.update(job_id, progress=progress, message=f"重建进度：{done}/{total} chunks")

        stats = retrieval.rebuild_all(
            progress_callback=update_progress,
            force_rebuild=force_rebuild,
        )
        result = stats.as_dict()
        jobs.update(
            job_id,
            status=JobStatus.succeeded,
            progress=1,
            message="全部索引已重建",
            result=result,
        )
        return result
    except Exception as exc:
        jobs.update(
            job_id,
            status=JobStatus.failed,
            progress=1,
            message="重建索引失败",
            error=str(exc),
            result=index_failure_result(exc),
        )
        raise
