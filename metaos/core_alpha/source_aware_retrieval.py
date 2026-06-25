"""Source-aware retrieval orchestration for Core Alpha.

This module is deliberately small: it turns an already-fixed
KnowledgeScope/ResearchPlan/ResearchRun into deterministic RetrievalRun,
EvidenceUnit, and ResearchEvidenceUse records. It does not call models, rebuild
indexes, or produce judgments.
"""

from __future__ import annotations

import hashlib
import re
import uuid
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from pydantic import Field

from metaos.core_alpha.commands import ApplicationCommandHandler, CommandExecution, CommandOutcome
from metaos.core_alpha.contracts.common import (
    CommandContext,
    NonEmptyString,
    OpenCodeValue,
    ResourceId,
    StrictContractModel,
)
from metaos.core_alpha.contracts.execution import (
    EvidenceLocation,
    EvidenceUnitResponse,
    EvidenceUseType,
    EvidenceValidityStatus,
    ResearchAttemptMode,
    ResearchAttemptStatus,
    ResearchEvidenceUseResponse,
    ResearchRunStatus,
    RetrievalOutcome,
    RetrievalRunResponse,
    RetrievalRunStatus,
)
from metaos.core_alpha.contracts.scope import (
    AccessPolicy,
    AnalysisRole,
    KnowledgeScopeSourceBindingResponse,
)
from metaos.core_alpha.persistence import (
    ConcurrencyConflictError,
    CoreAlphaDatabase,
    RecordNotFoundError,
    UnitOfWork,
)
from metaos.knowledge.catalog import (
    KnowledgeCatalogAdapter,
    KnowledgeCatalogChunk,
    KnowledgeCatalogError,
)


Clock = Callable[[], datetime]

RETRIEVAL_POLICY_VERSION = "core-alpha-v1-candidate"
PARAMETER_SET_VERSION = "core-alpha-v1-defaults"
RRF_K = 60
FULL_SCAN_CHUNK_THRESHOLD = 32
FULL_SCAN_TOKEN_THRESHOLD = 24_000
MAX_CANDIDATE_GROUPS = 80
MAX_CONTEXT_CHUNKS = 20
PER_SOURCE_CANDIDATE_LIMIT = 12
PER_SOURCE_MINIMUM_POOL = 4


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _new_id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex}"


def _code(value: str) -> OpenCodeValue:
    return OpenCodeValue(code=value, registry_version="core-alpha-v1")


class ExecuteResearchPlanRetrievalRequest(StrictContractModel):
    research_attempt_id: ResourceId
    evidence_query: NonEmptyString
    max_candidate_groups: int = Field(default=MAX_CANDIDATE_GROUPS, ge=1)
    max_context_chunks: int = Field(default=MAX_CONTEXT_CHUNKS, ge=1)


class ReuseExistingEvidenceRequest(StrictContractModel):
    research_attempt_id: ResourceId
    evidence_unit_ids: list[ResourceId] = Field(min_length=1)


class SourceRetrievalReport(StrictContractModel):
    knowledge_scope_source_binding_id: ResourceId
    knowledge_item_id: ResourceId
    knowledge_item_version_id: ResourceId | None
    access_policy: AccessPolicy
    analysis_role: AnalysisRole | None
    full_scan_eligible: bool
    active_chunk_count: int
    terminal_status: NonEmptyString
    retrieval_run_id: ResourceId | None
    candidate_group_count: int
    evidence_use_ids: list[ResourceId]


class ContextPackResult(StrictContractModel):
    context_pack_id: ResourceId
    max_context_chunks: int
    evidence_use_ids: list[ResourceId]


class SourceAwareRetrievalData(StrictContractModel):
    retrieval_policy_version: NonEmptyString
    parameter_set_version: NonEmptyString
    retrieval_runs: list[RetrievalRunResponse]
    evidence_units: list[EvidenceUnitResponse]
    research_evidence_uses: list[ResearchEvidenceUseResponse]
    source_reports: list[SourceRetrievalReport]
    context_pack: ContextPackResult


@dataclass(frozen=True)
class _Candidate:
    binding: KnowledgeScopeSourceBindingResponse
    chunk: KnowledgeCatalogChunk
    retrieval_run: RetrievalRunResponse
    score: float
    term_hits: int

    @property
    def evidence_group_id(self) -> str:
        return _evidence_group_id(self.chunk)


class SourceAwareRetrievalOrchestrator:
    """Executes the Minimum Slice source-aware retrieval contract."""

    def __init__(
        self,
        command_handler: ApplicationCommandHandler,
        catalog: KnowledgeCatalogAdapter,
        *,
        clock: Clock | None = None,
    ):
        self.command_handler = command_handler
        self.catalog = catalog
        self.clock = clock or _now

    def execute_research_plan(
        self,
        research_run_id: str,
        request: ExecuteResearchPlanRetrievalRequest,
        *,
        context: CommandContext,
    ) -> CommandExecution:
        body = request.model_dump(mode="json")
        return self.command_handler.execute(
            scope=f"{context.actor_id}:POST:/internal/alpha/research-runs/{research_run_id}/source-aware-retrieval",
            idempotency_key=context.idempotency_key,
            request_body=body,
            context=context,
            callback=lambda uow: self._execute(
                uow=uow,
                research_run_id=research_run_id,
                request=request,
            ),
        )

    def reuse_existing_evidence(
        self,
        research_run_id: str,
        request: ReuseExistingEvidenceRequest,
        *,
        context: CommandContext,
    ) -> CommandExecution:
        body = request.model_dump(mode="json")
        return self.command_handler.execute(
            scope=f"{context.actor_id}:POST:/internal/alpha/research-runs/{research_run_id}/reuse-existing-evidence",
            idempotency_key=context.idempotency_key,
            request_body=body,
            context=context,
            callback=lambda uow: self._reuse(
                uow=uow,
                research_run_id=research_run_id,
                request=request,
            ),
        )

    def _execute(
        self,
        *,
        uow: UnitOfWork,
        research_run_id: str,
        request: ExecuteResearchPlanRetrievalRequest,
    ) -> CommandOutcome:
        now = self._now()
        run = uow.run_evidence.get_research_run(research_run_id)
        self._ensure_run_active(run)
        attempt = uow.run_evidence.get_attempt(request.research_attempt_id)
        if attempt.research_run_id != research_run_id:
            raise ValueError("retrieval attempt must belong to the research run")
        if attempt.attempt_mode != ResearchAttemptMode.retrieval:
            raise ValueError("source-aware retrieval requires a retrieval attempt")
        if attempt.status != ResearchAttemptStatus.running:
            raise ValueError("source-aware retrieval requires a running attempt")
        scope = uow.case_scope.get_knowledge_scope_version(run.knowledge_scope_version_id)

        reports: dict[str, SourceRetrievalReport] = {}
        retrieval_runs: list[RetrievalRunResponse] = []
        candidates: list[_Candidate] = []
        query_terms = _query_terms(request.evidence_query)
        for binding in _sorted_bindings(scope.source_bindings):
            if binding.access_policy == AccessPolicy.excluded:
                reports[binding.knowledge_scope_source_binding_id] = self._report(
                    binding=binding,
                    terminal_status="excluded",
                    full_scan_eligible=False,
                    active_chunk_count=0,
                    retrieval_run_id=None,
                    candidate_group_count=0,
                    evidence_use_ids=[],
                )
                continue

            retrieval_run_id = _new_id("rr")
            retrieval: RetrievalRunResponse
            try:
                version = self.catalog.get_version(binding.knowledge_item_version_id or "")
                chunks = self.catalog.list_chunks(version.knowledge_item_version_id, limit=10000)
                index_generation_id = self._index_generation_id(version.knowledge_item_version_id)
            except (KnowledgeCatalogError, ValueError):
                retrieval = self._retrieval_run(
                    retrieval_run_id=retrieval_run_id,
                    attempt_id=attempt.research_attempt_id,
                    binding_id=binding.knowledge_scope_source_binding_id,
                    outcome=RetrievalOutcome.source_unavailable,
                    query=request.evidence_query,
                    now=now,
                    index_generation_id=None,
                    failure_reason=None,
                )
                uow.run_evidence.add_retrieval_run(retrieval)
                retrieval_runs.append(retrieval)
                reports[binding.knowledge_scope_source_binding_id] = self._report(
                    binding=binding,
                    terminal_status="unavailable",
                    full_scan_eligible=False,
                    active_chunk_count=0,
                    retrieval_run_id=retrieval.retrieval_run_id,
                    candidate_group_count=0,
                    evidence_use_ids=[],
                )
                continue

            source_candidates = self._rank_source_chunks(
                binding=binding,
                chunks=chunks,
                retrieval_run_id=retrieval_run_id,
                query_terms=query_terms,
            )
            retrieval = self._retrieval_run(
                retrieval_run_id=retrieval_run_id,
                attempt_id=attempt.research_attempt_id,
                binding_id=binding.knowledge_scope_source_binding_id,
                outcome=(
                    RetrievalOutcome.completed_with_candidates
                    if source_candidates
                    else RetrievalOutcome.no_evidence
                ),
                query=request.evidence_query,
                now=now,
                index_generation_id=index_generation_id,
                failure_reason=None,
            )
            uow.run_evidence.add_retrieval_run(retrieval)
            retrieval_runs.append(retrieval)
            source_candidates = [
                _Candidate(
                    binding=candidate.binding,
                    chunk=candidate.chunk,
                    retrieval_run=retrieval,
                    score=candidate.score,
                    term_hits=candidate.term_hits,
                )
                for candidate in source_candidates
            ]
            candidates.extend(source_candidates[:PER_SOURCE_CANDIDATE_LIMIT])
            reports[binding.knowledge_scope_source_binding_id] = self._report(
                binding=binding,
                terminal_status="evidence_found" if source_candidates else "no_evidence",
                full_scan_eligible=_full_scan_eligible(chunks),
                active_chunk_count=len(chunks),
                retrieval_run_id=retrieval.retrieval_run_id,
                candidate_group_count=len(source_candidates),
                evidence_use_ids=[],
            )

        selected = self._select_context_candidates(
            candidates,
            max_candidate_groups=request.max_candidate_groups,
            max_context_chunks=request.max_context_chunks,
        )
        evidence_units: list[EvidenceUnitResponse] = []
        evidence_uses: list[ResearchEvidenceUseResponse] = []
        for candidate in selected:
            evidence_unit = self._evidence_unit(candidate, created_at=now)
            persisted_evidence = uow.run_evidence.create_evidence_unit(evidence_unit)
            evidence_use = self._evidence_use(
                run_id=run.research_run_id,
                attempt_id=attempt.research_attempt_id,
                knowledge_scope_version_id=run.knowledge_scope_version_id,
                evidence=persisted_evidence,
                use_type=EvidenceUseType.retrieved,
                retrieval_run_id=candidate.retrieval_run.retrieval_run_id,
                now=now,
            )
            uow.run_evidence.add_research_evidence_use(evidence_use)
            evidence_units.append(persisted_evidence)
            evidence_uses.append(evidence_use)
            report = reports[candidate.binding.knowledge_scope_source_binding_id]
            reports[candidate.binding.knowledge_scope_source_binding_id] = report.model_copy(
                update={"evidence_use_ids": [*report.evidence_use_ids, evidence_use.research_evidence_use_id]}
            )

        context_pack = ContextPackResult(
            context_pack_id=_new_id("ctxpack"),
            max_context_chunks=request.max_context_chunks,
            evidence_use_ids=[use.research_evidence_use_id for use in evidence_uses],
        )
        data = SourceAwareRetrievalData(
            retrieval_policy_version=RETRIEVAL_POLICY_VERSION,
            parameter_set_version=PARAMETER_SET_VERSION,
            retrieval_runs=retrieval_runs,
            evidence_units=evidence_units,
            research_evidence_uses=evidence_uses,
            source_reports=[
                reports[binding.knowledge_scope_source_binding_id]
                for binding in _sorted_bindings(scope.source_bindings)
            ],
            context_pack=context_pack,
        )
        return CommandOutcome(
            data=data.model_dump(mode="json"),
            primary_aggregate_type="research_run",
            primary_aggregate_id=run.research_run_id,
            primary_aggregate_revision=run.revision,
            event_type_code="source_aware_retrieval_executed",
            event_payload={
                "research_run_id": run.research_run_id,
                "research_attempt_id": attempt.research_attempt_id,
                "retrieval_policy_version": RETRIEVAL_POLICY_VERSION,
                "parameter_set_version": PARAMETER_SET_VERSION,
                "context_pack_id": context_pack.context_pack_id,
                "source_reports": [report.model_dump(mode="json") for report in data.source_reports],
            },
        )

    def _reuse(
        self,
        *,
        uow: UnitOfWork,
        research_run_id: str,
        request: ReuseExistingEvidenceRequest,
    ) -> CommandOutcome:
        now = self._now()
        run = uow.run_evidence.get_research_run(research_run_id)
        self._ensure_run_active(run)
        attempt = uow.run_evidence.get_attempt(request.research_attempt_id)
        if attempt.research_run_id != research_run_id:
            raise ValueError("reuse attempt must belong to the research run")
        if attempt.attempt_mode != ResearchAttemptMode.reuse_existing_evidence:
            raise ValueError("reuse_existing_evidence requires a matching attempt mode")
        if attempt.status != ResearchAttemptStatus.running:
            raise ValueError("reuse requires a running attempt")
        scope = uow.case_scope.get_knowledge_scope_version(run.knowledge_scope_version_id)
        allowed_version_ids = {
            binding.knowledge_item_version_id
            for binding in scope.source_bindings
            if binding.access_policy != AccessPolicy.excluded
            and binding.knowledge_item_version_id is not None
        }
        excluded_item_ids = {
            binding.knowledge_item_id
            for binding in scope.source_bindings
            if binding.access_policy == AccessPolicy.excluded
        }
        evidence_units: list[EvidenceUnitResponse] = []
        evidence_uses: list[ResearchEvidenceUseResponse] = []
        for evidence_unit_id in request.evidence_unit_ids:
            evidence = uow.run_evidence.get_evidence_unit(evidence_unit_id)
            if evidence.validity_status != EvidenceValidityStatus.valid:
                raise ValueError("only valid EvidenceUnit records can be reused")
            if evidence.knowledge_item_id in excluded_item_ids:
                raise ValueError("excluded source evidence cannot be reused")
            if evidence.knowledge_item_version_id not in allowed_version_ids:
                raise ValueError("EvidenceUnit source version is outside the current scope")
            try:
                version = self.catalog.get_version(evidence.knowledge_item_version_id)
                self.catalog.get_chunk(evidence.chunk_id or "")
            except KnowledgeCatalogError as exc:
                raise ValueError("EvidenceUnit provenance is no longer verifiable") from exc
            if version.availability_status != "available":
                raise ValueError("EvidenceUnit source version is not available")
            evidence_use = self._evidence_use(
                run_id=run.research_run_id,
                attempt_id=attempt.research_attempt_id,
                knowledge_scope_version_id=run.knowledge_scope_version_id,
                evidence=evidence,
                use_type=EvidenceUseType.reused,
                retrieval_run_id=None,
                now=now,
            )
            uow.run_evidence.add_research_evidence_use(evidence_use)
            evidence_units.append(evidence)
            evidence_uses.append(evidence_use)

        context_pack = ContextPackResult(
            context_pack_id=_new_id("ctxpack"),
            max_context_chunks=len(evidence_uses),
            evidence_use_ids=[use.research_evidence_use_id for use in evidence_uses],
        )
        data = SourceAwareRetrievalData(
            retrieval_policy_version=RETRIEVAL_POLICY_VERSION,
            parameter_set_version=PARAMETER_SET_VERSION,
            retrieval_runs=[],
            evidence_units=evidence_units,
            research_evidence_uses=evidence_uses,
            source_reports=[],
            context_pack=context_pack,
        )
        return CommandOutcome(
            data=data.model_dump(mode="json"),
            primary_aggregate_type="research_run",
            primary_aggregate_id=run.research_run_id,
            primary_aggregate_revision=run.revision,
            event_type_code="existing_evidence_reused",
            event_payload={
                "research_run_id": run.research_run_id,
                "research_attempt_id": attempt.research_attempt_id,
                "evidence_unit_ids": request.evidence_unit_ids,
                "context_pack_id": context_pack.context_pack_id,
            },
        )

    def _rank_source_chunks(
        self,
        *,
        binding: KnowledgeScopeSourceBindingResponse,
        chunks: list[KnowledgeCatalogChunk],
        retrieval_run_id: str,
        query_terms: set[str],
    ) -> list[_Candidate]:
        candidates: list[_Candidate] = []
        seen_groups: set[str] = set()
        for chunk in chunks:
            term_hits = _term_hits(query_terms, chunk.text_preview)
            if term_hits <= 0:
                continue
            group_id = _evidence_group_id(chunk)
            if group_id in seen_groups:
                continue
            seen_groups.add(group_id)
            score = float(term_hits) + (1 / (RRF_K + max(chunk.position + 1, 1)))
            candidates.append(
                _Candidate(
                    binding=binding,
                    chunk=chunk,
                    retrieval_run=self._placeholder_retrieval_run(retrieval_run_id),
                    score=score,
                    term_hits=term_hits,
                )
            )
        return sorted(
            candidates,
            key=lambda candidate: (
                -candidate.score,
                candidate.chunk.knowledge_item_version_id,
                candidate.chunk.position,
                candidate.chunk.chunk_id,
            ),
        )

    @staticmethod
    def _select_context_candidates(
        candidates: list[_Candidate],
        *,
        max_candidate_groups: int,
        max_context_chunks: int,
    ) -> list[_Candidate]:
        by_binding: dict[str, list[_Candidate]] = {}
        for candidate in sorted(
            candidates,
            key=lambda item: (
                item.binding.knowledge_scope_source_binding_id,
                -item.score,
                item.chunk.position,
                item.chunk.chunk_id,
            ),
        ):
            by_binding.setdefault(candidate.binding.knowledge_scope_source_binding_id, []).append(candidate)

        selected: list[_Candidate] = []
        selected_group_ids: set[str] = set()

        def add(candidate: _Candidate) -> None:
            if len(selected) >= min(max_candidate_groups, max_context_chunks):
                return
            if candidate.evidence_group_id in selected_group_ids:
                return
            selected.append(candidate)
            selected_group_ids.add(candidate.evidence_group_id)

        for binding_id in sorted(by_binding):
            binding_candidates = by_binding[binding_id]
            first = binding_candidates[0]
            minimum = 1 if first.binding.access_policy == AccessPolicy.required else 0
            if first.binding.analysis_role in {AnalysisRole.primary, AnalysisRole.comparison}:
                minimum = max(minimum, 2)
            for candidate in binding_candidates[:minimum]:
                add(candidate)

        remaining = sorted(
            candidates,
            key=lambda candidate: (
                _access_priority(candidate.binding.access_policy),
                _role_priority(candidate.binding.analysis_role),
                -candidate.score,
                candidate.chunk.knowledge_item_version_id,
                candidate.chunk.position,
                candidate.evidence_group_id,
            ),
        )
        for candidate in remaining:
            add(candidate)
        return selected

    def _evidence_unit(self, candidate: _Candidate, *, created_at: datetime) -> EvidenceUnitResponse:
        chunk = candidate.chunk
        return EvidenceUnitResponse(
            evidence_unit_id=_new_id("eu"),
            knowledge_item_id=candidate.binding.knowledge_item_id,
            knowledge_item_version_id=chunk.knowledge_item_version_id,
            location=EvidenceLocation(
                section_path=chunk.section_path or [f"chunk:{chunk.chunk_id}"],
                page=chunk.page,
                timestamp_seconds=chunk.timestamp_seconds,
                start_offset=chunk.start_offset,
                end_offset=chunk.end_offset,
            ),
            excerpt=_excerpt(chunk.text_preview),
            content_hash=chunk.content_hash,
            origin_type=_code("retrieval"),
            validity_status=EvidenceValidityStatus.valid,
            revision=1,
            created_at=created_at,
            updated_at=created_at,
            chunk_id=chunk.chunk_id,
            origin_retrieval_run_id=candidate.retrieval_run.retrieval_run_id,
        )

    @staticmethod
    def _evidence_use(
        *,
        run_id: str,
        attempt_id: str,
        knowledge_scope_version_id: str,
        evidence: EvidenceUnitResponse,
        use_type: EvidenceUseType,
        retrieval_run_id: str | None,
        now: datetime,
    ) -> ResearchEvidenceUseResponse:
        return ResearchEvidenceUseResponse(
            research_evidence_use_id=_new_id("reu"),
            research_run_id=run_id,
            research_attempt_id=attempt_id,
            evidence_unit_id=evidence.evidence_unit_id,
            evidence_revision=evidence.revision,
            knowledge_scope_version_id=knowledge_scope_version_id,
            use_type=use_type,
            validity_checked_at=now,
            validity_result=evidence.validity_status,
            created_at=now,
            retrieval_run_id=retrieval_run_id,
        )

    @staticmethod
    def _retrieval_run(
        *,
        retrieval_run_id: str,
        attempt_id: str,
        binding_id: str,
        outcome: RetrievalOutcome,
        query: str,
        now: datetime,
        index_generation_id: str | None,
        failure_reason: str | None,
    ) -> RetrievalRunResponse:
        return RetrievalRunResponse(
            retrieval_run_id=retrieval_run_id,
            research_attempt_id=attempt_id,
            knowledge_scope_source_binding_id=binding_id,
            retrieval_channel=_code("fulltext"),
            query_ref=f"query_{_stable_hash(query)[:24]}",
            status=RetrievalRunStatus.completed,
            retrieval_outcome=outcome,
            created_at=now,
            index_generation_id=index_generation_id,
            started_at=now,
            ended_at=now,
            failure_reason=failure_reason,
        )

    @staticmethod
    def _placeholder_retrieval_run(retrieval_run_id: str) -> RetrievalRunResponse:
        now = datetime(2026, 1, 1, tzinfo=timezone.utc)
        return RetrievalRunResponse(
            retrieval_run_id=retrieval_run_id,
            research_attempt_id="attempt_placeholder",
            knowledge_scope_source_binding_id="binding_placeholder",
            retrieval_channel=_code("fulltext"),
            query_ref="query_placeholder",
            status=RetrievalRunStatus.completed,
            retrieval_outcome=RetrievalOutcome.completed_with_candidates,
            created_at=now,
            index_generation_id=None,
            started_at=now,
            ended_at=now,
            failure_reason=None,
        )

    def _index_generation_id(self, knowledge_item_version_id: str) -> str | None:
        generations = self.catalog.list_index_generations(knowledge_item_version_id)
        ready = [generation for generation in generations if generation.status == "ready"]
        if not ready:
            return None
        return sorted(ready, key=lambda generation: generation.index_generation_id)[0].index_generation_id

    @staticmethod
    def _report(
        *,
        binding: KnowledgeScopeSourceBindingResponse,
        terminal_status: str,
        full_scan_eligible: bool,
        active_chunk_count: int,
        retrieval_run_id: str | None,
        candidate_group_count: int,
        evidence_use_ids: list[str],
    ) -> SourceRetrievalReport:
        return SourceRetrievalReport(
            knowledge_scope_source_binding_id=binding.knowledge_scope_source_binding_id,
            knowledge_item_id=binding.knowledge_item_id,
            knowledge_item_version_id=binding.knowledge_item_version_id,
            access_policy=binding.access_policy,
            analysis_role=binding.analysis_role,
            full_scan_eligible=full_scan_eligible,
            active_chunk_count=active_chunk_count,
            terminal_status=terminal_status,
            retrieval_run_id=retrieval_run_id,
            candidate_group_count=candidate_group_count,
            evidence_use_ids=evidence_use_ids,
        )

    @staticmethod
    def _ensure_run_active(run: Any) -> None:
        if run.status in {
            ResearchRunStatus.completed,
            ResearchRunStatus.failed,
            ResearchRunStatus.cancelled,
            ResearchRunStatus.superseded,
        }:
            raise ConcurrencyConflictError("research run is already terminal")

    def _now(self) -> datetime:
        value = self.clock()
        if value.utcoffset() is None or value.utcoffset().total_seconds() != 0:
            raise ValueError("source-aware retrieval clock must return UTC datetimes")
        return value.astimezone(timezone.utc)


def _sorted_bindings(
    bindings: list[KnowledgeScopeSourceBindingResponse],
) -> list[KnowledgeScopeSourceBindingResponse]:
    return sorted(
        bindings,
        key=lambda binding: (
            _access_priority(binding.access_policy),
            _role_priority(binding.analysis_role),
            binding.knowledge_item_id,
            binding.knowledge_scope_source_binding_id,
        ),
    )


def _access_priority(policy: AccessPolicy) -> int:
    order = {
        AccessPolicy.required: 0,
        AccessPolicy.allowed: 1,
        AccessPolicy.excluded: 2,
    }
    return order[policy]


def _role_priority(role: AnalysisRole | None) -> int:
    order = {
        AnalysisRole.primary: 0,
        AnalysisRole.comparison: 1,
        AnalysisRole.background: 2,
        None: 3,
    }
    return order[role]


def _query_terms(query: str) -> set[str]:
    terms = {
        token.lower()
        for token in re.findall(r"[\w\u4e00-\u9fff]+", query)
        if len(token.strip()) >= 2
    }
    return terms or {query.strip().lower()}


def _term_hits(query_terms: set[str], text: str) -> int:
    lowered = text.lower()
    return sum(1 for term in query_terms if term and term in lowered)


def _full_scan_eligible(chunks: list[KnowledgeCatalogChunk]) -> bool:
    return (
        len(chunks) <= FULL_SCAN_CHUNK_THRESHOLD
        and sum(chunk.token_count for chunk in chunks) <= FULL_SCAN_TOKEN_THRESHOLD
    )


def _evidence_group_id(chunk: KnowledgeCatalogChunk) -> str:
    return ":".join(
        [
            chunk.knowledge_item_version_id,
            str(chunk.position),
            chunk.content_hash,
        ]
    )


def _stable_hash(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _excerpt(value: str, limit: int = 600) -> str:
    normalized = " ".join(value.split())
    if not normalized:
        return "Evidence excerpt unavailable."
    if len(normalized) <= limit:
        return normalized
    return normalized[:limit].rstrip()


__all__ = [
    "ContextPackResult",
    "ExecuteResearchPlanRetrievalRequest",
    "ReuseExistingEvidenceRequest",
    "SourceAwareRetrievalData",
    "SourceAwareRetrievalOrchestrator",
    "SourceRetrievalReport",
]
