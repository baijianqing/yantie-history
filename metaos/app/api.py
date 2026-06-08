"""FastAPI entrypoint for MetaOS Lite."""

from __future__ import annotations

from fastapi import FastAPI, File, HTTPException, UploadFile

from metaos import __version__
from metaos.core.errors import (
    ConfigurationError,
    EmbeddingProviderError,
    JobNotFoundError,
    KnowledgeItemNotFoundError,
    WorkspaceError,
)
from metaos.core.schemas import JobType
from metaos.ingest.pipeline import DocumentIngestPipeline
from metaos.knowledge.service import KnowledgeService
from metaos.retrieval.service import RetrievalService
from metaos.workspace.catalog import ChunkRepository, KnowledgeRepository
from metaos.workspace.jobs import JobRepository
from metaos.workspace.paths import ensure_workspace


app = FastAPI(title="MetaOS Lite", version=__version__)


def job_repo() -> JobRepository:
    return JobRepository()


def knowledge_repo() -> KnowledgeRepository:
    return KnowledgeRepository()


def chunk_repo() -> ChunkRepository:
    return ChunkRepository()


def knowledge_service() -> KnowledgeService:
    return KnowledgeService()


def retrieval_service() -> RetrievalService:
    return RetrievalService()


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "version": __version__}


@app.get("/workspace")
def workspace() -> dict[str, str]:
    return ensure_workspace().as_jsonable()


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
    job = job_repo().create(JobType.ingest_document, {"demo": True})
    return job.model_dump(mode="json")


@app.post("/ingest/documents")
async def ingest_document(file: UploadFile = File(...)) -> dict:
    content = await file.read()
    result = DocumentIngestPipeline().ingest_upload(
        filename=file.filename or "uploaded.txt",
        content=content,
    )
    return {
        "job": result.job.model_dump(mode="json"),
        "source": result.source.model_dump(mode="json"),
        "asset": result.asset.model_dump(mode="json"),
        "knowledge_item": result.knowledge_item.model_dump(mode="json"),
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


@app.post("/knowledge/{item_id}/chunks/rebuild")
def rebuild_knowledge_chunks(item_id: str) -> dict:
    try:
        item, chunk_count = knowledge_service().rebuild_chunks(item_id)
    except KnowledgeItemNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except WorkspaceError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {
        "knowledge_item": item.model_dump(mode="json"),
        "chunk_count": chunk_count,
    }


@app.post("/knowledge/{item_id}/index")
def index_knowledge_item(item_id: str) -> dict:
    try:
        return retrieval_service().index_knowledge_item(item_id).as_dict()
    except KnowledgeItemNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except (ConfigurationError, EmbeddingProviderError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/index/rebuild")
def rebuild_index() -> dict:
    try:
        return retrieval_service().rebuild_all().as_dict()
    except (ConfigurationError, EmbeddingProviderError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.get("/index/status")
def index_status() -> dict:
    try:
        return retrieval_service().embedding_status()
    except ConfigurationError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.get("/search")
def search(q: str, top_k: int = 5) -> list[dict]:
    if not q.strip():
        raise HTTPException(status_code=400, detail="Search query cannot be empty.")
    try:
        return [result.as_dict() for result in retrieval_service().search(q, top_k=top_k)]
    except (ConfigurationError, EmbeddingProviderError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
