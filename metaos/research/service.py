"""Research execution service helpers for candidate recall."""

from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime
from enum import Enum
from typing import Protocol

from pydantic import BaseModel, Field, field_validator

from metaos.compiler import EvidenceRequirement, ResearchCompilation
from metaos.core.schemas import new_id, utc_now
from metaos.research.executor import ResearchExecutionDraft, build_evidence_matrix
from metaos.search import EvidenceCandidate


RESEARCH_EXECUTION_VERSION = "research_execution_v1"


class EvidenceSearch(Protocol):
    def __call__(self, query: str, *, top_k: int = 5) -> Sequence[EvidenceCandidate]:
        """Return evidence candidates for one query."""


class ResearchProgressStage(str, Enum):
    planned = "planned"
    retrieving = "retrieving"
    matrix_built = "matrix_built"
    completed = "completed"


class ResearchProgressEvent(BaseModel):
    id: str = Field(default_factory=lambda: new_id("rpe"))
    task_id: str
    stage: ResearchProgressStage
    progress: float = Field(ge=0, le=1)
    message: str
    requirement_id: str | None = None
    query: str | None = None
    created_at: datetime = Field(default_factory=utc_now)

    @field_validator("task_id", "message")
    @classmethod
    def validate_required_text(cls, value: str) -> str:
        text = value.strip()
        if not text:
            raise ValueError("field cannot be blank")
        return text

    @field_validator("requirement_id", "query")
    @classmethod
    def clean_optional_text(cls, value: str | None) -> str | None:
        if value is None:
            return None
        return value.strip() or None


class ResearchRetrievalRun(BaseModel):
    id: str = Field(default_factory=lambda: new_id("rrun"))
    task_id: str
    requirement_id: str
    requirement_type: str
    query: str
    top_k: int = Field(ge=1)
    returned_count: int = Field(ge=0)
    accepted_count: int = Field(ge=0)
    candidate_ids: list[str] = Field(default_factory=list)
    execution_version: str = RESEARCH_EXECUTION_VERSION
    created_at: datetime = Field(default_factory=utc_now)

    @field_validator("task_id", "requirement_id", "requirement_type", "query", "execution_version")
    @classmethod
    def validate_required_text(cls, value: str) -> str:
        text = value.strip()
        if not text:
            raise ValueError("field cannot be blank")
        return text


class ResearchExecutionReport(BaseModel):
    id: str = Field(default_factory=lambda: new_id("rexec"))
    task_id: str
    execution_version: str = RESEARCH_EXECUTION_VERSION
    candidates: list[EvidenceCandidate] = Field(default_factory=list)
    retrieval_runs: list[ResearchRetrievalRun] = Field(default_factory=list)
    progress_events: list[ResearchProgressEvent] = Field(default_factory=list)
    execution: ResearchExecutionDraft
    created_at: datetime = Field(default_factory=utc_now)

    @field_validator("task_id", "execution_version")
    @classmethod
    def validate_required_text(cls, value: str) -> str:
        text = value.strip()
        if not text:
            raise ValueError("field cannot be blank")
        return text


COUNTER_STANCE_TERMS = (
    "counter",
    "counterevidence",
    "contradict",
    "dispute",
    "weaken",
    "gap",
    "missing",
    "not enough",
    "fails",
    "however",
)


def execute_research_plan(
    compilation: ResearchCompilation,
    search: EvidenceSearch,
    *,
    top_k_per_query: int = 5,
) -> ResearchExecutionDraft:
    return execute_research_plan_with_trace(
        compilation,
        search,
        top_k_per_query=top_k_per_query,
    ).execution


def execute_research_plan_with_trace(
    compilation: ResearchCompilation,
    search: EvidenceSearch,
    *,
    top_k_per_query: int = 5,
) -> ResearchExecutionReport:
    task_id = compilation.research_task.id
    progress_events = [
        progress_event(
            task_id=task_id,
            stage=ResearchProgressStage.planned,
            progress=0.0,
            message="Research execution planned.",
        )
    ]
    candidates, retrieval_runs, retrieval_events = retrieve_research_candidates_with_trace(
        compilation,
        search,
        top_k_per_query=top_k_per_query,
    )
    progress_events.extend(retrieval_events)
    execution = build_evidence_matrix(compilation, candidates)
    progress_events.append(
        progress_event(
            task_id=task_id,
            stage=ResearchProgressStage.matrix_built,
            progress=0.9,
            message="Evidence matrix built.",
        )
    )
    progress_events.append(
        progress_event(
            task_id=task_id,
            stage=ResearchProgressStage.completed,
            progress=1.0,
            message="Research execution completed.",
        )
    )
    return ResearchExecutionReport(
        task_id=task_id,
        candidates=candidates,
        retrieval_runs=retrieval_runs,
        progress_events=progress_events,
        execution=execution,
    )


def retrieve_research_candidates(
    compilation: ResearchCompilation,
    search: EvidenceSearch,
    *,
    top_k_per_query: int = 5,
) -> list[EvidenceCandidate]:
    candidates, _, _ = retrieve_research_candidates_with_trace(
        compilation,
        search,
        top_k_per_query=top_k_per_query,
    )
    return candidates


def retrieve_research_candidates_with_trace(
    compilation: ResearchCompilation,
    search: EvidenceSearch,
    *,
    top_k_per_query: int = 5,
) -> tuple[list[EvidenceCandidate], list[ResearchRetrievalRun], list[ResearchProgressEvent]]:
    candidates: list[EvidenceCandidate] = []
    retrieval_runs: list[ResearchRetrievalRun] = []
    progress_events: list[ResearchProgressEvent] = []
    seen: set[tuple[str, str, str]] = set()
    query_pairs = [
        (requirement, query)
        for requirement in compilation.evidence_requirements
        for query in queries_for_requirement(compilation, requirement)
    ]
    total_queries = len(query_pairs)
    for index, (requirement, query) in enumerate(query_pairs, start=1):
        raw_candidates = list(search(query, top_k=max(1, top_k_per_query)))
        accepted_ids: list[str] = []
        for candidate in raw_candidates:
            tagged = tag_candidate(candidate, requirement=requirement, query=query)
            key = (
                requirement.id,
                tagged.chunk_id,
                str(tagged.metadata.get("stance", "support")),
            )
            if key in seen:
                continue
            seen.add(key)
            candidates.append(tagged)
            accepted_ids.append(tagged.chunk_id)
        retrieval_runs.append(
            ResearchRetrievalRun(
                task_id=compilation.research_task.id,
                requirement_id=requirement.id,
                requirement_type=requirement.requirement_type.value,
                query=query,
                top_k=max(1, top_k_per_query),
                returned_count=len(raw_candidates),
                accepted_count=len(accepted_ids),
                candidate_ids=accepted_ids,
            )
        )
        progress_events.append(
            progress_event(
                task_id=compilation.research_task.id,
                stage=ResearchProgressStage.retrieving,
                progress=retrieval_progress(index, total_queries),
                message=f"Retrieved {len(accepted_ids)} new candidates.",
                requirement_id=requirement.id,
                query=query,
            )
        )
    return candidates, retrieval_runs, progress_events


def queries_for_requirement(
    compilation: ResearchCompilation,
    requirement: EvidenceRequirement,
) -> list[str]:
    queries = [requirement.description]
    queries.extend(
        query
        for query in compilation.research_plan.query_plan
        if query_targets_requirement(query, requirement)
    )
    for step in compilation.research_plan.steps:
        target_text = " ".join([step.description, *step.expected_evidence])
        if query_targets_requirement(target_text, requirement):
            queries.extend(step.query_hints)
    return dedupe_queries(queries)


def tag_candidate(
    candidate: EvidenceCandidate,
    *,
    requirement: EvidenceRequirement,
    query: str,
) -> EvidenceCandidate:
    metadata = dict(candidate.metadata or {})
    metadata.setdefault("requirement_id", requirement.id)
    metadata.setdefault("requirement_type", requirement.requirement_type.value)
    metadata.setdefault("query", query)
    metadata.setdefault("stance", infer_stance(candidate))
    return candidate.model_copy(update={"metadata": metadata})


def infer_stance(candidate: EvidenceCandidate) -> str:
    raw_stance = str((candidate.metadata or {}).get("stance") or "").strip().lower()
    if raw_stance:
        return "counter" if raw_stance in {"counter", "counterevidence", "contradicts"} else "support"
    text = candidate.text.lower()
    if any(term in text for term in COUNTER_STANCE_TERMS):
        return "counter"
    return "support"


def dedupe_queries(queries: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for query in queries:
        text = query.strip()
        if not text or text in seen:
            continue
        seen.add(text)
        result.append(text)
    return result


def query_targets_requirement(query: str, requirement: EvidenceRequirement) -> bool:
    text = query.lower()
    return requirement.id.lower() in text or requirement.requirement_type.value in text


def progress_event(
    *,
    task_id: str,
    stage: ResearchProgressStage,
    progress: float,
    message: str,
    requirement_id: str | None = None,
    query: str | None = None,
) -> ResearchProgressEvent:
    return ResearchProgressEvent(
        task_id=task_id,
        stage=stage,
        progress=progress,
        message=message,
        requirement_id=requirement_id,
        query=query,
    )


def retrieval_progress(index: int, total: int) -> float:
    if total <= 0:
        return 0.8
    return round(0.1 + 0.7 * min(index, total) / total, 4)
