"""FastAPI entrypoint for MetaOS Lite."""

from __future__ import annotations

from pydantic import BaseModel
from fastapi import FastAPI, File, HTTPException, UploadFile

from metaos import __version__
from metaos.core.errors import (
    ConfigurationError,
    EmbeddingProviderError,
    JobNotFoundError,
    KnowledgeItemNotFoundError,
    UnsupportedDocumentError,
    WorkspaceError,
)
from metaos.ingest.service import IngestService
from metaos.knowledge.deletion import KnowledgeDeletionService
from metaos.retrieval.service import RetrievalService
from metaos.tasks.monitoring import runtime_status
from metaos.tasks.pipeline import enqueue_document_pipeline
from metaos.tasks.queueing import (
    enqueue_index_knowledge,
    enqueue_rag_answer,
    enqueue_rebuild_chunks,
    enqueue_rebuild_index,
)
from metaos.workspace.catalog import ChunkRepository, KnowledgeRepository
from metaos.workspace.jobs import JobRepository
from metaos.workspace.paths import ensure_workspace


app = FastAPI(title="MetaOS Lite", version=__version__)


class RagAnswerRequest(BaseModel):
    question: str
    top_k: int = 5


def job_repo() -> JobRepository:
    return JobRepository()


def knowledge_repo() -> KnowledgeRepository:
    return KnowledgeRepository()


def chunk_repo() -> ChunkRepository:
    return ChunkRepository()


def retrieval_service() -> RetrievalService:
    return RetrievalService()


def knowledge_deletion_service() -> KnowledgeDeletionService:
    return KnowledgeDeletionService()


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "version": __version__}


@app.get("/workspace")
def workspace() -> dict[str, str]:
    return ensure_workspace().as_jsonable()


@app.get("/runtime/status")
def get_runtime_status() -> dict:
    return runtime_status()


@app.get("/jobs")
def list_jobs(limit: int = 50) -> list[dict]:
    return [job.model_dump(mode="json") for job in job_repo().list(limit=limit)]


@app.get("/jobs/{job_id}")
def get_job(job_id: str) -> dict:
    try:
        return job_repo().get(job_id).model_dump(mode="json")
    except JobNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.post("/jobs/demo")
def create_demo_job() -> dict:
    from metaos.core.schemas import JobType

    job = job_repo().create(JobType.ingest_document, {"demo": True})
    return job.model_dump(mode="json")


@app.post("/ingest/documents")
async def ingest_document(file: UploadFile = File(...)) -> dict:
    content = await file.read()
    source, asset = IngestService().add_bytes(
        filename=file.filename or "uploaded.txt",
        content=content,
    )
    try:
        job = enqueue_document_pipeline(source, asset)
    except (ConfigurationError, UnsupportedDocumentError, WorkspaceError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {
        "job": job.model_dump(mode="json"),
        "source": source.model_dump(mode="json"),
        "asset": asset.model_dump(mode="json"),
    }


@app.get("/knowledge")
def list_knowledge(limit: int = 50) -> list[dict]:
    return [item.model_dump(mode="json") for item in knowledge_repo().list(limit=limit)]


@app.get("/knowledge/{item_id}/chunks")
def list_knowledge_chunks(item_id: str, limit: int = 200) -> list[dict]:
    try:
        knowledge_repo().get(item_id)
    except KnowledgeItemNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return [chunk.model_dump(mode="json") for chunk in chunk_repo().list_by_knowledge_item(item_id, limit=limit)]


@app.delete("/knowledge/{item_id}")
def delete_knowledge_item(item_id: str) -> dict:
    try:
        return knowledge_deletion_service().delete(item_id).as_dict()
    except KnowledgeItemNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except (ConfigurationError, EmbeddingProviderError, WorkspaceError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/knowledge/{item_id}/chunks/rebuild")
def rebuild_knowledge_chunks(item_id: str) -> dict:
    try:
        knowledge_repo().get(item_id)
        job = enqueue_rebuild_chunks(item_id)
    except KnowledgeItemNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except (ConfigurationError, WorkspaceError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return job.model_dump(mode="json")


@app.post("/knowledge/{item_id}/index")
def index_knowledge_item(item_id: str, force_rebuild: bool = False) -> dict:
    try:
        return retrieval_service().index_knowledge_item(
            item_id,
            force_rebuild=force_rebuild,
        ).as_dict()
    except KnowledgeItemNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except (ConfigurationError, EmbeddingProviderError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/knowledge/{item_id}/index/jobs")
def enqueue_index_knowledge_item(item_id: str, force_rebuild: bool = False) -> dict:
    try:
        knowledge_repo().get(item_id)
        return enqueue_index_knowledge(
            item_id,
            force_rebuild=force_rebuild,
        ).model_dump(mode="json")
    except KnowledgeItemNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ConfigurationError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/index/rebuild")
def rebuild_index(force_rebuild: bool = False) -> dict:
    try:
        return retrieval_service().rebuild_all(force_rebuild=force_rebuild).as_dict()
    except (ConfigurationError, EmbeddingProviderError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/index/rebuild/jobs")
def enqueue_rebuild_index_job(force_rebuild: bool = False) -> dict:
    try:
        return enqueue_rebuild_index(force_rebuild=force_rebuild).model_dump(mode="json")
    except ConfigurationError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.get("/index/status")
def index_status() -> dict:
    try:
        return retrieval_service().embedding_status()
    except (ConfigurationError, EmbeddingProviderError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.get("/search")
def search(q: str, top_k: int = 5) -> list[dict]:
    if not q.strip():
        raise HTTPException(status_code=400, detail="Search query cannot be empty.")
    try:
        return [result.as_dict() for result in retrieval_service().search(q, top_k=top_k)]
    except (ConfigurationError, EmbeddingProviderError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/rag/answer/jobs")
def enqueue_rag_answer_job(request: RagAnswerRequest) -> dict:
    if not request.question.strip():
        raise HTTPException(status_code=400, detail="Question cannot be empty.")
    try:
        return enqueue_rag_answer(request.question, top_k=request.top_k).model_dump(mode="json")
    except ConfigurationError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
