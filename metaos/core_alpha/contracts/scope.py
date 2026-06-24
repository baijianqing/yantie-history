"""Core Alpha contracts for cases, source scope, and research plans."""

from __future__ import annotations

from enum import Enum
from typing import Annotated, Literal

from pydantic import Field, StrictBool, model_validator

from metaos.core_alpha.contracts.common import (
    NonEmptyString,
    OpenCodeValue,
    ResourceId,
    ResourceReference,
    Revision,
    StrictContractModel,
    UtcDateTime,
)


class QuestionRole(str, Enum):
    root = "root"
    follow_up = "follow_up"
    clarification = "clarification"
    derived = "derived"


class ResearchCaseLifecycleStatus(str, Enum):
    open = "open"
    archived = "archived"


class AttentionStatus(str, Enum):
    saved = "saved"
    active = "active"
    paused = "paused"
    observing = "observing"
    deferred = "deferred"
    closed = "closed"


class ResolutionStage(str, Enum):
    preliminary = "preliminary"
    full = "full"


class ResolutionStatus(str, Enum):
    resolved = "resolved"
    ambiguous = "ambiguous"
    not_found = "not_found"
    unavailable = "unavailable"


class AccessPolicy(str, Enum):
    required = "required"
    allowed = "allowed"
    excluded = "excluded"


class AnalysisRole(str, Enum):
    primary = "primary"
    comparison = "comparison"
    background = "background"


class ScopeMode(str, Enum):
    evidence_only = "evidence_only"


class VersionLifecycleStatus(str, Enum):
    current = "current"
    superseded = "superseded"


class ResearchMode(str, Enum):
    fact_lookup = "fact_lookup"
    source_interpretation = "source_interpretation"
    compare_sources = "compare_sources"
    enumerate_pattern = "enumerate_pattern"
    claim_evaluation = "claim_evaluation"


class ExpectedRevisionRequest(StrictContractModel):
    expected_revision: Revision


class CreateResearchCaseRequest(StrictContractModel):
    title: NonEmptyString
    question_text: NonEmptyString
    question_role: Literal[QuestionRole.root]


class AddResearchQuestionRequest(ExpectedRevisionRequest):
    question_text: NonEmptyString
    question_role: QuestionRole
    parent_question_id: ResourceId | None = None

    @model_validator(mode="after")
    def reject_second_root(self) -> "AddResearchQuestionRequest":
        if self.question_role == QuestionRole.root:
            raise ValueError("an existing research case cannot add another root question")
        return self


class DeriveResearchCaseRequest(ExpectedRevisionRequest):
    source_question_id: ResourceId | None = None
    judgment_card_version_id: ResourceId | None = None
    title: NonEmptyString
    question_text: NonEmptyString

    @model_validator(mode="after")
    def require_one_derivation_source(self) -> "DeriveResearchCaseRequest":
        source_count = sum(
            value is not None
            for value in (self.source_question_id, self.judgment_card_version_id)
        )
        if source_count != 1:
            raise ValueError("derive requires exactly one question or judgment source")
        return self


class SourceAnchorInput(StrictContractModel):
    raw_anchor: NonEmptyString
    requested_access_policy: AccessPolicy
    requested_version_hint: NonEmptyString | None = None


class CreateSourceResolutionsRequest(ExpectedRevisionRequest):
    research_question_id: ResourceId
    resolution_stage: Literal[ResolutionStage.full]
    anchors: list[SourceAnchorInput] = Field(min_length=1)

    @model_validator(mode="after")
    def reject_duplicate_anchors(self) -> "CreateSourceResolutionsRequest":
        keys = [
            (
                anchor.raw_anchor,
                anchor.requested_access_policy,
                anchor.requested_version_hint,
            )
            for anchor in self.anchors
        ]
        if len(keys) != len(set(keys)):
            raise ValueError("source anchors must be unique within one command")
        return self


class ResearchQuestionResponse(StrictContractModel):
    research_question_id: ResourceId
    research_case_id: ResourceId
    question_text: NonEmptyString
    question_role: QuestionRole
    created_by: ResourceId
    created_at: UtcDateTime
    parent_question_id: ResourceId | None

    @model_validator(mode="after")
    def validate_root_parent(self) -> "ResearchQuestionResponse":
        if self.question_role == QuestionRole.root and self.parent_question_id is not None:
            raise ValueError("root questions cannot have a parent question")
        return self


class ResearchCaseResponse(StrictContractModel):
    research_case_id: ResourceId
    title: NonEmptyString
    root_question_id: ResourceId
    current_question_id: ResourceId
    lifecycle_status: ResearchCaseLifecycleStatus
    attention_status: AttentionStatus
    revision: Revision
    created_at: UtcDateTime
    updated_at: UtcDateTime
    current_knowledge_scope_version_id: ResourceId | None
    current_judgment_card_version_id: ResourceId | None
    current_research_disposition_id: ResourceId | None
    parent_research_case_id: ResourceId | None
    archived_at: UtcDateTime | None

    @model_validator(mode="after")
    def validate_case_times(self) -> "ResearchCaseResponse":
        if self.updated_at < self.created_at:
            raise ValueError("updated_at cannot be earlier than created_at")
        if self.archived_at is not None and self.archived_at < self.created_at:
            raise ValueError("archived_at cannot be earlier than created_at")
        return self


class SourceResolutionResponse(StrictContractModel):
    source_resolution_id: ResourceId
    research_question_id: ResourceId
    resolution_stage: ResolutionStage
    raw_anchor: NonEmptyString
    requested_access_policy: AccessPolicy
    resolution_status: ResolutionStatus
    candidate_knowledge_item_ids: list[ResourceId]
    created_at: UtcDateTime
    requested_version_hint: NonEmptyString | None
    resolved_knowledge_item_id: ResourceId | None
    resolved_knowledge_item_version_id: ResourceId | None
    ambiguity_reason: NonEmptyString | None
    failure_reason: NonEmptyString | None

    @model_validator(mode="after")
    def validate_resolution_result(self) -> "SourceResolutionResponse":
        candidates = self.candidate_knowledge_item_ids
        if len(candidates) != len(set(candidates)):
            raise ValueError("candidate knowledge item ids must be unique")

        if self.resolution_status == ResolutionStatus.ambiguous:
            if not candidates or self.ambiguity_reason is None:
                raise ValueError("ambiguous resolutions require candidates and ambiguity_reason")
            if self.resolved_knowledge_item_id is not None:
                raise ValueError("ambiguous resolutions cannot select a knowledge item")
        elif self.ambiguity_reason is not None:
            raise ValueError("ambiguity_reason is only valid for ambiguous resolutions")

        if self.resolution_status in {
            ResolutionStatus.not_found,
            ResolutionStatus.unavailable,
        }:
            if self.failure_reason is None:
                raise ValueError("failed resolutions require failure_reason")
            if self.resolved_knowledge_item_id is not None:
                raise ValueError("failed resolutions cannot select a knowledge item")
        elif self.failure_reason is not None:
            raise ValueError("failure_reason is only valid for failed resolutions")

        if (
            self.resolution_status == ResolutionStatus.resolved
            and self.resolution_stage == ResolutionStage.full
        ):
            if self.resolved_knowledge_item_id is None:
                raise ValueError("full resolved records require a knowledge item")
            if (
                self.requested_access_policy != AccessPolicy.excluded
                and self.resolved_knowledge_item_version_id is None
            ):
                raise ValueError("non-excluded full resolutions require a content version")
        elif self.resolution_status != ResolutionStatus.resolved:
            if self.resolved_knowledge_item_version_id is not None:
                raise ValueError("unresolved records cannot select a content version")
        return self


class KnowledgeScopeBindingInput(StrictContractModel):
    source_resolution_id: ResourceId
    knowledge_item_id: ResourceId
    knowledge_item_version_id: ResourceId | None = None
    access_policy: AccessPolicy
    analysis_role: AnalysisRole | None = None

    @model_validator(mode="after")
    def validate_access_policy(self) -> "KnowledgeScopeBindingInput":
        if self.access_policy == AccessPolicy.excluded:
            if self.analysis_role is not None:
                raise ValueError("excluded bindings cannot have an analysis role")
        elif self.knowledge_item_version_id is None:
            raise ValueError("required and allowed bindings require a content version")
        return self


class KnowledgeScopeSourceBindingResponse(KnowledgeScopeBindingInput):
    knowledge_item_version_id: ResourceId | None
    analysis_role: AnalysisRole | None
    knowledge_scope_source_binding_id: ResourceId
    knowledge_scope_version_id: ResourceId
    created_at: UtcDateTime


class KnowledgeScopePayload(StrictContractModel):
    expected_revision: Revision
    default_access_policy: AccessPolicy
    scope_mode: Literal[ScopeMode.evidence_only]
    bindings: list[KnowledgeScopeBindingInput]

    @model_validator(mode="after")
    def validate_scope_policies(self) -> "KnowledgeScopePayload":
        if self.default_access_policy == AccessPolicy.required:
            raise ValueError("default access policy cannot be required")
        item_ids = [binding.knowledge_item_id for binding in self.bindings]
        if len(item_ids) != len(set(item_ids)):
            raise ValueError("one scope version cannot bind the same knowledge item twice")
        resolution_ids = [binding.source_resolution_id for binding in self.bindings]
        if len(resolution_ids) != len(set(resolution_ids)):
            raise ValueError("one source resolution cannot be reused by multiple bindings")
        return self


class CreateKnowledgeScopeRequest(KnowledgeScopePayload):
    pass


class AdjustKnowledgeScopeRequest(KnowledgeScopePayload):
    pass


class KnowledgeScopeVersionResponse(StrictContractModel):
    knowledge_scope_id: ResourceId
    knowledge_scope_version_id: ResourceId
    research_case_id: ResourceId
    version: Revision
    lifecycle_status: VersionLifecycleStatus
    scope_mode: ScopeMode
    default_access_policy: AccessPolicy
    source_bindings: list[KnowledgeScopeSourceBindingResponse]
    created_by: ResourceId
    created_at: UtcDateTime
    previous_version_id: ResourceId | None

    @model_validator(mode="after")
    def validate_version_and_bindings(self) -> "KnowledgeScopeVersionResponse":
        if self.default_access_policy == AccessPolicy.required:
            raise ValueError("default access policy cannot be required")
        if self.version == 1 and self.previous_version_id is not None:
            raise ValueError("initial scope version cannot have a previous version")
        if self.version > 1 and self.previous_version_id is None:
            raise ValueError("later scope versions require a previous version")
        binding_ids: set[str] = set()
        item_ids: set[str] = set()
        for binding in self.source_bindings:
            if binding.knowledge_scope_version_id != self.knowledge_scope_version_id:
                raise ValueError("scope bindings must belong to the enclosing scope version")
            if binding.knowledge_scope_source_binding_id in binding_ids:
                raise ValueError("scope binding ids must be unique")
            if binding.knowledge_item_id in item_ids:
                raise ValueError("scope knowledge item bindings must be unique")
            binding_ids.add(binding.knowledge_scope_source_binding_id)
            item_ids.add(binding.knowledge_item_id)
        return self


class EvidenceRequirementInput(StrictContractModel):
    requirement_type: OpenCodeValue
    description: NonEmptyString
    required_knowledge_scope_source_binding_ids: list[ResourceId]
    counterevidence_required: StrictBool
    alternative_interpretation_required: StrictBool
    completion_condition: NonEmptyString
    minimum_count: Annotated[int, Field(strict=True, ge=1)] | None = None

    @model_validator(mode="after")
    def validate_binding_ids(self) -> "EvidenceRequirementInput":
        binding_ids = self.required_knowledge_scope_source_binding_ids
        if len(binding_ids) != len(set(binding_ids)):
            raise ValueError("required binding ids must be unique")
        return self


class EvidenceRequirementResponse(EvidenceRequirementInput):
    minimum_count: Annotated[int, Field(strict=True, ge=1)] | None
    evidence_requirement_id: ResourceId


class ResearchPlanPayload(StrictContractModel):
    expected_revision: Revision
    knowledge_scope_version_id: ResourceId
    research_mode: ResearchMode
    primary_objective: NonEmptyString
    evidence_requirements: list[EvidenceRequirementInput] = Field(min_length=1)
    minimum_completion_condition: NonEmptyString


class CreateResearchPlanRequest(ResearchPlanPayload):
    pass


class AdjustResearchPlanRequest(ResearchPlanPayload):
    pass


class ResearchPlanVersionResponse(StrictContractModel):
    research_plan_id: ResourceId
    research_plan_version_id: ResourceId
    research_case_id: ResourceId
    knowledge_scope_version_id: ResourceId
    version: Revision
    lifecycle_status: VersionLifecycleStatus
    research_mode: ResearchMode
    primary_objective: NonEmptyString
    evidence_requirements: list[EvidenceRequirementResponse] = Field(min_length=1)
    minimum_completion_condition: NonEmptyString
    created_at: UtcDateTime
    previous_version_id: ResourceId | None
    stop_conditions: None
    research_budget: None

    @model_validator(mode="after")
    def validate_version_chain(self) -> "ResearchPlanVersionResponse":
        if self.version == 1 and self.previous_version_id is not None:
            raise ValueError("initial plan version cannot have a previous version")
        if self.version > 1 and self.previous_version_id is None:
            raise ValueError("later plan versions require a previous version")
        requirement_ids = [
            requirement.evidence_requirement_id for requirement in self.evidence_requirements
        ]
        if len(requirement_ids) != len(set(requirement_ids)):
            raise ValueError("evidence requirement ids must be unique")
        return self


class CreateResearchCaseData(StrictContractModel):
    research_case: ResearchCaseResponse
    research_question: ResearchQuestionResponse


class DeriveResearchCaseData(StrictContractModel):
    source_research_case_ref: ResourceReference
    research_case: ResearchCaseResponse
    research_question: ResearchQuestionResponse


class CreateSourceResolutionsData(StrictContractModel):
    source_resolutions: list[SourceResolutionResponse]


class KnowledgeScopeCommandData(StrictContractModel):
    knowledge_scope: KnowledgeScopeVersionResponse
    superseded_version_ref: ResourceReference | None = None


class ResearchPlanCommandData(StrictContractModel):
    research_plan: ResearchPlanVersionResponse
    superseded_version_ref: ResourceReference | None = None


__all__ = [
    "AccessPolicy",
    "AddResearchQuestionRequest",
    "AdjustKnowledgeScopeRequest",
    "AdjustResearchPlanRequest",
    "AnalysisRole",
    "AttentionStatus",
    "CreateKnowledgeScopeRequest",
    "CreateResearchCaseData",
    "CreateResearchCaseRequest",
    "CreateResearchPlanRequest",
    "CreateSourceResolutionsData",
    "CreateSourceResolutionsRequest",
    "DeriveResearchCaseData",
    "DeriveResearchCaseRequest",
    "EvidenceRequirementInput",
    "EvidenceRequirementResponse",
    "ExpectedRevisionRequest",
    "KnowledgeScopeBindingInput",
    "KnowledgeScopeCommandData",
    "KnowledgeScopeSourceBindingResponse",
    "KnowledgeScopeVersionResponse",
    "QuestionRole",
    "ResearchCaseLifecycleStatus",
    "ResearchCaseResponse",
    "ResearchMode",
    "ResearchPlanCommandData",
    "ResearchPlanVersionResponse",
    "ResearchQuestionResponse",
    "ResolutionStage",
    "ResolutionStatus",
    "ScopeMode",
    "SourceAnchorInput",
    "SourceResolutionResponse",
    "VersionLifecycleStatus",
]
