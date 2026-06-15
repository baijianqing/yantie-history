"""FastAPI entrypoint for MetaOS Lite."""

from __future__ import annotations

from datetime import date

from fastapi import FastAPI, File, HTTPException, UploadFile
from pydantic import BaseModel, Field

from metaos import __version__
from metaos.chancellor import ChancellorBriefing, generate_chancellor_briefing, generate_weekly_report
from metaos.core.errors import (
    ConfigurationError,
    EmbeddingProviderError,
    JobNotFoundError,
    KnowledgeItemNotFoundError,
    UnsupportedDocumentError,
    WorkspaceError,
)
from metaos.compiler import CompileResearchRequest, IssueCompiler, LLMCompilerProvider
from metaos.ingest.service import IngestService
from metaos.knowledge.deletion import KnowledgeDeletionService
from metaos.ledger import DailyReview, DailySummary
from metaos.ministries import MinistryReport
from metaos.research import ResearchAnswer
from metaos.retrieval.service import RetrievalService
from metaos.search import hybrid_search
from metaos.sovereignty import (
    AttentionBudget,
    CognitiveConstitution,
    CurrentRole,
    Intent,
    IntentStatus,
    NotToDoItem,
    SovereigntyRecordNotFoundError,
    SovereigntyRepository,
)
from metaos.tasks.monitoring import runtime_status
from metaos.tasks.pipeline import enqueue_document_pipeline
from metaos.tasks.queueing import (
    enqueue_index_knowledge,
    enqueue_rag_answer,
    enqueue_rebuild_chunks,
    enqueue_rebuild_index,
    enqueue_retry_job,
)
from metaos.workspace.catalog import ChunkRepository, KnowledgeRepository
from metaos.workspace.jobs import JobRepository
from metaos.workspace.paths import ensure_workspace
from metaos.workshop import VideoExport


app = FastAPI(title="MetaOS Lite", version=__version__)


class RagAnswerRequest(BaseModel):
    question: str
    top_k: int = 5


class AlphaSearchRequest(BaseModel):
    query: str
    top_k: int = 5
    full_text_top_k: int | None = None
    vector_top_k: int | None = None
    filters: dict[str, str] | None = None
    include_vector: bool = True


class AlphaWeeklyReportRequest(BaseModel):
    week_start: date
    week_end: date
    intent: Intent
    daily_summaries: list[DailySummary] = Field(default_factory=list)
    briefings: list[ChancellorBriefing] = Field(default_factory=list)
    research_answers: list[ResearchAnswer] = Field(default_factory=list)
    video_exports: list[VideoExport] = Field(default_factory=list)


class AlphaChancellorBriefingRequest(BaseModel):
    date: date
    intent: Intent
    attention_budget: AttentionBudget
    role: CurrentRole | None = None
    daily_review: DailyReview | None = None
    research_answers: list[ResearchAnswer] = Field(default_factory=list)
    ministry_reports: list[MinistryReport] = Field(default_factory=list)


class ActiveStateRequest(BaseModel):
    active: bool


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


def sovereignty_repo() -> SovereigntyRepository:
    return SovereigntyRepository()


def issue_compiler() -> IssueCompiler:
    return IssueCompiler(LLMCompilerProvider())


def as_json(value) -> dict:
    return value.model_dump(mode="json")


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "version": __version__}


@app.get("/workspace")
def workspace() -> dict[str, str]:
    return ensure_workspace().as_jsonable()


@app.get("/runtime/status")
def get_runtime_status() -> dict:
    return runtime_status()


@app.post("/alpha/constitution")
def upsert_cognitive_constitution(request: CognitiveConstitution) -> dict:
    return as_json(sovereignty_repo().constitutions.add(request))


@app.get("/alpha/constitution")
def list_cognitive_constitutions(limit: int = 50) -> list[dict]:
    return [as_json(item) for item in sovereignty_repo().constitutions.list(limit=limit)]


@app.post("/alpha/intents")
def create_intent(request: Intent) -> dict:
    repo = sovereignty_repo().intents
    repo.add(request)
    if request.status == IntentStatus.active:
        return as_json(repo.update_active(request.id))
    return as_json(repo.get(request.id))


@app.get("/alpha/intents")
def list_intents(limit: int = 50) -> list[dict]:
    return [as_json(item) for item in sovereignty_repo().intents.list(limit=limit)]


@app.get("/alpha/intents/active")
def list_active_intents(limit: int = 50) -> list[dict]:
    return [
        as_json(item)
        for item in sovereignty_repo().intents.list(
            limit=limit,
            status=IntentStatus.active,
        )
    ]


@app.post("/alpha/intents/{intent_id}/activate")
def activate_intent(intent_id: str) -> dict:
    try:
        return as_json(sovereignty_repo().intents.update_active(intent_id))
    except SovereigntyRecordNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.post("/alpha/current-role")
def set_current_role(request: CurrentRole) -> dict:
    repo = sovereignty_repo().roles
    repo.add(request)
    return as_json(repo.update_active(request.id))


@app.get("/alpha/current-role")
def list_current_roles(limit: int = 50) -> list[dict]:
    return [
        as_json(item)
        for item in sovereignty_repo().roles.list(
            limit=limit,
            active_only=True,
        )
    ]


@app.post("/alpha/attention-budgets")
def create_attention_budget(request: AttentionBudget) -> dict:
    return as_json(sovereignty_repo().attention_budgets.add(request))


@app.get("/alpha/attention-budgets")
def list_attention_budgets(limit: int = 50) -> list[dict]:
    return [as_json(item) for item in sovereignty_repo().attention_budgets.list(limit=limit)]


@app.post("/alpha/not-to-do")
def create_not_to_do_item(request: NotToDoItem) -> dict:
    return as_json(sovereignty_repo().not_to_do.add(request))


@app.get("/alpha/not-to-do")
def list_not_to_do_items(limit: int = 50, active: bool | None = None) -> list[dict]:
    return [
        as_json(item)
        for item in sovereignty_repo().not_to_do.list(
            limit=limit,
            active=active,
        )
    ]


@app.patch("/alpha/not-to-do/{item_id}/active")
def update_not_to_do_active_state(item_id: str, request: ActiveStateRequest) -> dict:
    try:
        return as_json(sovereignty_repo().not_to_do.update_active(item_id, active=request.active))
    except SovereigntyRecordNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.get("/jobs")
def list_jobs(limit: int = 50) -> list[dict]:
    return [job.model_dump(mode="json") for job in job_repo().list(limit=limit)]


@app.get("/jobs/{job_id}")
def get_job(job_id: str) -> dict:
    try:
        return job_repo().get(job_id).model_dump(mode="json")
    except JobNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.post("/jobs/{job_id}/retry")
def retry_job(job_id: str) -> dict:
    try:
        return enqueue_retry_job(job_id).model_dump(mode="json")
    except JobNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except (ConfigurationError, ValueError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


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


@app.post("/alpha/search")
def alpha_search(request: AlphaSearchRequest) -> list[dict]:
    if not request.query.strip():
        raise HTTPException(status_code=400, detail="Search query cannot be empty.")
    vector_retrieval = retrieval_service() if request.include_vector else None
    try:
        results = hybrid_search(
            request.query,
            chunks=chunk_repo().list_all(limit=10000),
            vector_retrieval=vector_retrieval,
            filters=request.filters,
            top_k=request.top_k,
            full_text_top_k=request.full_text_top_k,
            vector_top_k=request.vector_top_k,
        )
    except (ConfigurationError, EmbeddingProviderError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return [result.model_dump(mode="json") for result in results]


@app.post("/alpha/research/compile")
def compile_alpha_research(request: CompileResearchRequest) -> dict:
    try:
        return issue_compiler().compile(request).model_dump(mode="json")
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/alpha/chancellor/daily-briefings")
def create_alpha_chancellor_briefing(request: AlphaChancellorBriefingRequest) -> dict:
    try:
        briefing = generate_chancellor_briefing(
            request.date,
            intent=request.intent,
            role=request.role,
            attention_budget=request.attention_budget,
            daily_review=request.daily_review,
            research_answers=request.research_answers,
            ministry_reports=request.ministry_reports,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return briefing.model_dump(mode="json")


@app.post("/alpha/chancellor/weekly-reports")
def create_alpha_weekly_report(request: AlphaWeeklyReportRequest) -> dict:
    try:
        report = generate_weekly_report(
            request.week_start,
            request.week_end,
            intent=request.intent,
            daily_summaries=request.daily_summaries,
            briefings=request.briefings,
            research_answers=request.research_answers,
            video_exports=request.video_exports,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return report.model_dump(mode="json")


@app.post("/rag/answer/jobs")
def enqueue_rag_answer_job(request: RagAnswerRequest) -> dict:
    if not request.question.strip():
        raise HTTPException(status_code=400, detail="Question cannot be empty.")
    try:
        return enqueue_rag_answer(request.question, top_k=request.top_k).model_dump(mode="json")
    except ConfigurationError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
