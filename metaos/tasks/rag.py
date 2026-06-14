"""RAG answer tasks for the rag worker."""

from __future__ import annotations

from metaos.core.schemas import JobStatus
from metaos.rag.service import RagService
from metaos.workspace.jobs import JobRepository
from metaos.workspace.paths import ensure_workspace


def run_answer_question(job_id: str) -> dict:
    paths = ensure_workspace()
    jobs = JobRepository(paths.database)
    job = jobs.get(job_id)
    question = str(job.payload.get("question") or "")
    top_k = int(job.payload.get("top_k") or 5)

    try:
        jobs.update(job_id, status=JobStatus.running, progress=0.15, message="检索知识库")
        result = RagService(paths).answer(question, top_k=top_k).as_dict()
        jobs.update(
            job_id,
            status=JobStatus.succeeded,
            progress=1,
            message="回答完成",
            result=result,
        )
        return result
    except Exception as exc:
        jobs.update(
            job_id,
            status=JobStatus.failed,
            progress=1,
            message="回答失败",
            error=str(exc),
        )
        raise
