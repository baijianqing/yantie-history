"""Core Alpha contracts for research execution and evidence use."""

from __future__ import annotations

from enum import Enum
from typing import Annotated

from pydantic import Field, JsonValue, model_validator

from metaos.core_alpha.contracts.common import (
    HashValue,
    IdempotencyKey,
    NonEmptyString,
    OpenCodeValue,
    ResourceId,
    Revision,
    StrictContractModel,
    UtcDateTime,
)


PositiveInt = Annotated[int, Field(strict=True, ge=1)]
NonNegativeInt = Annotated[int, Field(strict=True, ge=0)]
NonNegativeFloat = Annotated[float, Field(strict=True, ge=0)]


class ExecutionMode(str, Enum):
    synchronous = "synchronous"
    asynchronous = "asynchronous"


class ResearchRunStatus(str, Enum):
    created = "created"
    running = "running"
    awaiting_user = "awaiting_user"
    completed = "completed"
    failed = "failed"
    cancelled = "cancelled"
    superseded = "superseded"


class ResearchAttemptMode(str, Enum):
    retrieval = "retrieval"
    reuse_existing_evidence = "reuse_existing_evidence"


class ResearchAttemptStatus(str, Enum):
    created = "created"
    running = "running"
    completed = "completed"
    failed = "failed"
    cancelled = "cancelled"
    stale = "stale"


class RetrievalRunStatus(str, Enum):
    created = "created"
    running = "running"
    completed = "completed"
    failed = "failed"
    cancelled = "cancelled"


class RetrievalOutcome(str, Enum):
    completed_with_candidates = "completed_with_candidates"
    no_evidence = "no_evidence"
    source_unavailable = "source_unavailable"
    failed = "failed"
    cancelled = "cancelled"


class ResearchRunOutcomeType(str, Enum):
    completed_with_judgment = "completed_with_judgment"
    insufficient_evidence = "insufficient_evidence"
    audit_blocked = "audit_blocked"
    execution_failed = "execution_failed"
    cancelled_by_user = "cancelled_by_user"
    deferred_before_judgment = "deferred_before_judgment"
    superseded_by_new_run = "superseded_by_new_run"


class EvidenceUseType(str, Enum):
    retrieved = "retrieved"
    reused = "reused"


class EvidenceValidityStatus(str, Enum):
    valid = "valid"
    needs_review = "needs_review"
    invalid = "invalid"


class ExecutionCheckpointType(str, Enum):
    run_started = "run_started"
    retrieval_completed = "retrieval_completed"
    evidence_assembled = "evidence_assembled"
    judgment_candidate_generated = "judgment_candidate_generated"
    deterministic_precheck_completed = "deterministic_precheck_completed"
    semantic_audit_completed = "semantic_audit_completed"
    decision_gate_completed = "decision_gate_completed"
    outcome_committed = "outcome_committed"


class CreateResearchRunRequest(StrictContractModel):
    expected_research_case_revision: Revision
    research_question_id: ResourceId
    knowledge_scope_version_id: ResourceId
    research_plan_version_id: ResourceId
    execution_mode: ExecutionMode = ExecutionMode.synchronous


class CancelResearchRunRequest(StrictContractModel):
    expected_revision: Revision
    reason: NonEmptyString


class RunExecutionSpecResponse(StrictContractModel):
    run_execution_spec_id: ResourceId
    research_run_id: ResourceId
    knowledge_scope_version_id: ResourceId
    source_resolution_ids: list[ResourceId]
    research_plan_version_id: ResourceId
    source_version_ids: list[ResourceId]
    index_generation_ids: list[ResourceId]
    retrieval_strategy_version: NonEmptyString
    context_strategy_version: NonEmptyString
    embedding_contract: dict[str, JsonValue]
    reranker_contract: dict[str, JsonValue]
    capability_contracts: list[dict[str, JsonValue]]
    allowed_implementations: list[NonEmptyString]
    fallback_policy: dict[str, JsonValue]
    prompt_version: NonEmptyString
    output_schema_version: NonEmptyString
    audit_policy_version: NonEmptyString
    decision_fitness_policy_version: NonEmptyString
    egress_policy_version: NonEmptyString
    system_safety_limits: dict[str, JsonValue]
    created_at: UtcDateTime
    budget_snapshot_id: ResourceId | None

    @model_validator(mode="after")
    def validate_stable_sets(self) -> "RunExecutionSpecResponse":
        for field_name in (
            "source_resolution_ids",
            "source_version_ids",
            "index_generation_ids",
            "allowed_implementations",
        ):
            values = getattr(self, field_name)
            if len(values) != len(set(values)):
                raise ValueError(f"{field_name} must contain unique values")
        return self


class ExecutionCheckpointResponse(StrictContractModel):
    execution_checkpoint_id: ResourceId
    research_run_id: ResourceId
    checkpoint_type: ExecutionCheckpointType
    input_revision: Revision
    completed_at: UtcDateTime
    result_ref_id: ResourceId
    idempotency_key: IdempotencyKey
    research_attempt_id: ResourceId | None

    @model_validator(mode="after")
    def validate_attempt_reference(self) -> "ExecutionCheckpointResponse":
        attempt_checkpoints = {
            ExecutionCheckpointType.retrieval_completed,
            ExecutionCheckpointType.evidence_assembled,
            ExecutionCheckpointType.judgment_candidate_generated,
            ExecutionCheckpointType.deterministic_precheck_completed,
            ExecutionCheckpointType.semantic_audit_completed,
            ExecutionCheckpointType.decision_gate_completed,
        }
        if self.checkpoint_type in attempt_checkpoints and self.research_attempt_id is None:
            raise ValueError("attempt-level checkpoints require research_attempt_id")
        return self


class ResearchRunResponse(StrictContractModel):
    research_run_id: ResourceId
    research_case_id: ResourceId
    research_question_id: ResourceId
    knowledge_scope_version_id: ResourceId
    research_plan_version_id: ResourceId
    run_execution_spec_id: ResourceId
    status: ResearchRunStatus
    revision: Revision
    created_at: UtcDateTime
    started_at: UtcDateTime | None
    ended_at: UtcDateTime | None
    superseded_by_run_id: ResourceId | None

    @model_validator(mode="after")
    def validate_lifecycle_times(self) -> "ResearchRunResponse":
        terminal = {
            ResearchRunStatus.completed,
            ResearchRunStatus.failed,
            ResearchRunStatus.cancelled,
            ResearchRunStatus.superseded,
        }
        started = {
            ResearchRunStatus.running,
            ResearchRunStatus.awaiting_user,
            ResearchRunStatus.completed,
            ResearchRunStatus.failed,
        }
        if self.status in started and self.started_at is None:
            raise ValueError("started run states require started_at")
        if self.status in terminal and self.ended_at is None:
            raise ValueError("terminal run states require ended_at")
        if self.status not in terminal and self.ended_at is not None:
            raise ValueError("non-terminal run states cannot include ended_at")
        if self.status == ResearchRunStatus.superseded:
            if self.superseded_by_run_id is None:
                raise ValueError("superseded runs require superseded_by_run_id")
        elif self.superseded_by_run_id is not None:
            raise ValueError("superseded_by_run_id is only valid for superseded runs")
        if self.started_at is not None and self.started_at < self.created_at:
            raise ValueError("started_at cannot be earlier than created_at")
        if self.ended_at is not None:
            lower_bound = self.started_at or self.created_at
            if self.ended_at < lower_bound:
                raise ValueError("ended_at cannot precede the run lifecycle")
        return self


class ResearchAttemptResponse(StrictContractModel):
    research_attempt_id: ResourceId
    research_run_id: ResourceId
    attempt_number: PositiveInt
    attempt_mode: ResearchAttemptMode
    status: ResearchAttemptStatus
    created_at: UtcDateTime
    previous_attempt_id: ResourceId | None
    started_at: UtcDateTime | None
    ended_at: UtcDateTime | None
    failure_category: OpenCodeValue | None
    failure_reason: NonEmptyString | None

    @model_validator(mode="after")
    def validate_attempt(self) -> "ResearchAttemptResponse":
        terminal = {
            ResearchAttemptStatus.completed,
            ResearchAttemptStatus.failed,
            ResearchAttemptStatus.cancelled,
            ResearchAttemptStatus.stale,
        }
        if self.attempt_number == 1 and self.previous_attempt_id is not None:
            raise ValueError("the first attempt cannot reference a previous attempt")
        if self.attempt_number > 1 and self.previous_attempt_id is None:
            raise ValueError("later attempts require previous_attempt_id")
        if self.status in {
            ResearchAttemptStatus.running,
            ResearchAttemptStatus.completed,
            ResearchAttemptStatus.failed,
        } and self.started_at is None:
            raise ValueError("started attempt states require started_at")
        if self.status in terminal and self.ended_at is None:
            raise ValueError("terminal attempt states require ended_at")
        if self.status not in terminal and self.ended_at is not None:
            raise ValueError("non-terminal attempt states cannot include ended_at")
        if self.status == ResearchAttemptStatus.failed:
            if self.failure_category is None or self.failure_reason is None:
                raise ValueError("failed attempts require failure details")
        if self.started_at is not None and self.started_at < self.created_at:
            raise ValueError("started_at cannot be earlier than created_at")
        if self.ended_at is not None:
            lower_bound = self.started_at or self.created_at
            if self.ended_at < lower_bound:
                raise ValueError("ended_at cannot precede the attempt lifecycle")
        return self


class RetrievalRunResponse(StrictContractModel):
    retrieval_run_id: ResourceId
    research_attempt_id: ResourceId
    knowledge_scope_source_binding_id: ResourceId
    retrieval_channel: OpenCodeValue
    query_ref: ResourceId
    status: RetrievalRunStatus
    retrieval_outcome: RetrievalOutcome | None
    created_at: UtcDateTime
    index_generation_id: ResourceId | None
    started_at: UtcDateTime | None
    ended_at: UtcDateTime | None
    failure_reason: NonEmptyString | None

    @model_validator(mode="after")
    def validate_status_and_outcome(self) -> "RetrievalRunResponse":
        terminal_outcomes = {
            RetrievalRunStatus.completed: {
                RetrievalOutcome.completed_with_candidates,
                RetrievalOutcome.no_evidence,
                RetrievalOutcome.source_unavailable,
            },
            RetrievalRunStatus.failed: {RetrievalOutcome.failed},
            RetrievalRunStatus.cancelled: {RetrievalOutcome.cancelled},
        }
        if self.status in {RetrievalRunStatus.created, RetrievalRunStatus.running}:
            if self.retrieval_outcome is not None:
                raise ValueError("non-terminal retrieval runs cannot have an outcome")
        elif self.retrieval_outcome not in terminal_outcomes[self.status]:
            raise ValueError("retrieval outcome does not match terminal status")
        if self.status in {
            RetrievalRunStatus.running,
            RetrievalRunStatus.completed,
            RetrievalRunStatus.failed,
        } and self.started_at is None:
            raise ValueError("started retrieval states require started_at")
        if self.status in terminal_outcomes and self.ended_at is None:
            raise ValueError("terminal retrieval states require ended_at")
        if self.status not in terminal_outcomes and self.ended_at is not None:
            raise ValueError("non-terminal retrieval states cannot include ended_at")
        if self.status == RetrievalRunStatus.failed and self.failure_reason is None:
            raise ValueError("failed retrieval runs require failure_reason")
        if self.started_at is not None and self.started_at < self.created_at:
            raise ValueError("started_at cannot be earlier than created_at")
        if self.ended_at is not None:
            lower_bound = self.started_at or self.created_at
            if self.ended_at < lower_bound:
                raise ValueError("ended_at cannot precede the retrieval lifecycle")
        return self


class ResearchRunOutcomeResponse(StrictContractModel):
    research_run_outcome_id: ResourceId
    research_run_id: ResourceId
    outcome_type: ResearchRunOutcomeType
    reason_code: OpenCodeValue
    reason_summary: NonEmptyString
    created_at: UtcDateTime
    judgment_card_version_id: ResourceId | None

    @model_validator(mode="after")
    def validate_judgment_reference(self) -> "ResearchRunOutcomeResponse":
        requires_judgment = {
            ResearchRunOutcomeType.completed_with_judgment,
            ResearchRunOutcomeType.audit_blocked,
        }
        if self.outcome_type in requires_judgment:
            if self.judgment_card_version_id is None:
                raise ValueError("judgment outcomes require judgment_card_version_id")
        elif self.judgment_card_version_id is not None:
            raise ValueError("this outcome type cannot reference a judgment card")
        return self


class ResearchEvidenceUseResponse(StrictContractModel):
    research_evidence_use_id: ResourceId
    research_run_id: ResourceId
    research_attempt_id: ResourceId
    evidence_unit_id: ResourceId
    evidence_revision: Revision
    knowledge_scope_version_id: ResourceId
    use_type: EvidenceUseType
    validity_checked_at: UtcDateTime
    validity_result: EvidenceValidityStatus
    created_at: UtcDateTime
    retrieval_run_id: ResourceId | None

    @model_validator(mode="after")
    def validate_use_source(self) -> "ResearchEvidenceUseResponse":
        if self.use_type == EvidenceUseType.retrieved and self.retrieval_run_id is None:
            raise ValueError("retrieved evidence use requires retrieval_run_id")
        if self.validity_checked_at > self.created_at:
            raise ValueError("validity check cannot occur after the use record is created")
        return self


class EvidenceLocation(StrictContractModel):
    section_path: list[NonEmptyString]
    page: PositiveInt | None
    timestamp_seconds: NonNegativeFloat | None
    start_offset: NonNegativeInt | None
    end_offset: NonNegativeInt | None

    @model_validator(mode="after")
    def validate_location(self) -> "EvidenceLocation":
        has_location = bool(self.section_path) or any(
            value is not None
            for value in (
                self.page,
                self.timestamp_seconds,
                self.start_offset,
                self.end_offset,
            )
        )
        if not has_location:
            raise ValueError("evidence location requires at least one locator")
        if (
            self.start_offset is not None
            and self.end_offset is not None
            and self.end_offset < self.start_offset
        ):
            raise ValueError("end_offset cannot be earlier than start_offset")
        return self


class EvidenceUnitResponse(StrictContractModel):
    evidence_unit_id: ResourceId
    knowledge_item_id: ResourceId
    knowledge_item_version_id: ResourceId
    location: EvidenceLocation
    excerpt: NonEmptyString
    content_hash: HashValue
    origin_type: OpenCodeValue
    validity_status: EvidenceValidityStatus
    revision: Revision
    created_at: UtcDateTime
    updated_at: UtcDateTime
    chunk_id: ResourceId | None
    origin_retrieval_run_id: ResourceId | None

    @model_validator(mode="after")
    def validate_times(self) -> "EvidenceUnitResponse":
        if self.updated_at < self.created_at:
            raise ValueError("updated_at cannot be earlier than created_at")
        return self


__all__ = [
    "CancelResearchRunRequest",
    "CreateResearchRunRequest",
    "EvidenceLocation",
    "EvidenceUnitResponse",
    "EvidenceUseType",
    "EvidenceValidityStatus",
    "ExecutionCheckpointResponse",
    "ExecutionCheckpointType",
    "ExecutionMode",
    "ResearchAttemptMode",
    "ResearchAttemptResponse",
    "ResearchAttemptStatus",
    "ResearchEvidenceUseResponse",
    "ResearchRunOutcomeResponse",
    "ResearchRunOutcomeType",
    "ResearchRunResponse",
    "ResearchRunStatus",
    "RetrievalOutcome",
    "RetrievalRunResponse",
    "RetrievalRunStatus",
    "RunExecutionSpecResponse",
]
