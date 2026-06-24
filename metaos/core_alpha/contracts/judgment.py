"""Core Alpha contracts for claims, judgments, audits, and decision fitness."""

from __future__ import annotations

from enum import Enum
from typing import Annotated, Literal

from pydantic import Field, StrictBool, model_validator

from metaos.core_alpha.contracts.common import (
    NonEmptyString,
    OpenCodeValue,
    ResourceId,
    Revision,
    StrictContractModel,
    UtcDateTime,
)
from metaos.core_alpha.contracts.execution import (
    ResearchRunOutcomeResponse,
    ResearchRunResponse,
)


class EvidenceRole(str, Enum):
    supports = "supports"
    contradicts = "contradicts"
    defines = "defines"
    context = "context"
    background = "background"


class SupportStrengthLevel(str, Enum):
    weak = "weak"
    moderate = "moderate"
    strong = "strong"


class EpistemicType(str, Enum):
    fact = "fact"
    interpretation = "interpretation"
    inference = "inference"
    analogy = "analogy"
    hypothesis = "hypothesis"


class ExpressionRole(str, Enum):
    core_judgment = "core_judgment"
    supplement = "supplement"
    counterargument = "counterargument"
    recommendation = "recommendation"
    open_question = "open_question"
    user_reflection = "user_reflection"


class ClaimEvidenceStatus(str, Enum):
    unassessed = "unassessed"
    supported = "supported"
    partially_supported = "partially_supported"
    mixed = "mixed"
    contradicted = "contradicted"
    insufficient = "insufficient"
    not_applicable = "not_applicable"


class ClaimImportance(str, Enum):
    core = "core"
    supporting = "supporting"


class ConfidenceLevel(str, Enum):
    unknown = "unknown"
    low = "low"
    medium = "medium"
    high = "high"


class ClaimLifecycleStatus(str, Enum):
    draft = "draft"
    current = "current"
    superseded = "superseded"
    archived = "archived"


class ClaimUserAttitude(str, Enum):
    unreviewed = "unreviewed"
    accepted = "accepted"
    rejected = "rejected"
    needs_revision = "needs_revision"


class JudgmentAuditStatus(str, Enum):
    pending = "pending"
    auditing = "auditing"
    provisionally_acceptable = "provisionally_acceptable"
    acceptable = "acceptable"
    blocked = "blocked"


class JudgmentValidityStatus(str, Enum):
    valid = "valid"
    needs_review = "needs_review"
    invalid = "invalid"


class JudgmentLifecycleStatus(str, Enum):
    draft = "draft"
    current = "current"
    superseded = "superseded"
    archived = "archived"


class JudgmentAuditRunStatus(str, Enum):
    pending = "pending"
    running = "running"
    completed = "completed"
    failed = "failed"


class JudgmentGateResult(str, Enum):
    acceptable = "acceptable"
    provisionally_acceptable = "provisionally_acceptable"
    blocked = "blocked"


class AuditFindingSeverity(str, Enum):
    warning = "warning"
    blocking = "blocking"


class DecisionUse(str, Enum):
    understanding = "understanding"
    research_planning = "research_planning"
    observation = "observation"
    low_risk_experiment = "low_risk_experiment"
    reversible_action = "reversible_action"


class CostLevel(str, Enum):
    low = "low"
    medium = "medium"
    high = "high"


class Reversibility(str, Enum):
    reversible = "reversible"
    partially_reversible = "partially_reversible"
    irreversible = "irreversible"


class ExternalImpact(str, Enum):
    none = "none"
    limited = "limited"
    significant = "significant"


class SupportStrength(StrictContractModel):
    level: SupportStrengthLevel
    reason: NonEmptyString


class FactRationaleProfile(StrictContractModel):
    profile_type: Literal["fact"]
    source_summary: NonEmptyString
    location_summary: NonEmptyString
    fact_mapping: NonEmptyString
    version_limitations: list[NonEmptyString]


class InterpretationRationaleProfile(StrictContractModel):
    profile_type: Literal["interpretation"]
    source_text_summary: NonEmptyString
    context_summary: NonEmptyString
    interpretation_path: NonEmptyString
    alternative_interpretations: list[NonEmptyString]


class InferenceRationaleProfile(StrictContractModel):
    profile_type: Literal["inference"]
    premises: list[NonEmptyString] = Field(min_length=1)
    reasoning_method: OpenCodeValue
    key_assumptions: list[NonEmptyString]
    applicability_boundaries: list[NonEmptyString]
    counterevidence_summary: list[NonEmptyString]
    invalidation_conditions: list[NonEmptyString]


class HypothesisRationaleProfile(StrictContractModel):
    profile_type: Literal["hypothesis"]
    premises: list[NonEmptyString] = Field(min_length=1)
    reasoning_method: OpenCodeValue
    key_assumptions: list[NonEmptyString]
    applicability_boundaries: list[NonEmptyString]
    counterevidence_summary: list[NonEmptyString]
    invalidation_conditions: list[NonEmptyString]


class RecommendationRationaleProfile(StrictContractModel):
    profile_type: Literal["recommendation"]
    basis: list[NonEmptyString] = Field(min_length=1)
    target: NonEmptyString
    costs: list[NonEmptyString]
    risks: list[NonEmptyString]
    reversibility: Reversibility
    stop_conditions: list[NonEmptyString] = Field(min_length=1)


RationaleProfile = Annotated[
    FactRationaleProfile
    | InterpretationRationaleProfile
    | InferenceRationaleProfile
    | HypothesisRationaleProfile
    | RecommendationRationaleProfile,
    Field(discriminator="profile_type"),
]


class ClaimEvidenceLinkResponse(StrictContractModel):
    claim_evidence_link_id: ResourceId
    claim_version_id: ResourceId
    research_evidence_use_id: ResourceId
    evidence_unit_id: ResourceId
    evidence_role: EvidenceRole
    support_strength: SupportStrength
    created_at: UtcDateTime
    scope_note: NonEmptyString | None


class JudgmentRationaleResponse(StrictContractModel):
    judgment_rationale_id: ResourceId
    claim_version_id: ResourceId
    rationale_profile: RationaleProfile
    evidence_link_ids: list[ResourceId]
    reasoning_summary: NonEmptyString
    created_at: UtcDateTime

    @model_validator(mode="after")
    def validate_link_ids(self) -> "JudgmentRationaleResponse":
        if len(self.evidence_link_ids) != len(set(self.evidence_link_ids)):
            raise ValueError("rationale evidence link ids must be unique")
        return self


class ClaimVersionResponse(StrictContractModel):
    claim_id: ResourceId
    claim_version_id: ResourceId
    judgment_card_version_id: ResourceId
    claim_text: NonEmptyString
    epistemic_type: EpistemicType
    expression_role: ExpressionRole
    evidence_status: ClaimEvidenceStatus
    importance: ClaimImportance
    confidence_level: ConfidenceLevel
    lifecycle_status: ClaimLifecycleStatus
    user_attitude: ClaimUserAttitude
    version: Revision
    created_at: UtcDateTime
    judgment_rationale_id: ResourceId | None
    previous_version_id: ResourceId | None

    @model_validator(mode="after")
    def validate_claim_semantics(self) -> "ClaimVersionResponse":
        if self.version == 1 and self.previous_version_id is not None:
            raise ValueError("initial claim version cannot have a previous version")
        if self.version > 1 and self.previous_version_id is None:
            raise ValueError("later claim versions require previous_version_id")
        if self.expression_role in {
            ExpressionRole.core_judgment,
            ExpressionRole.recommendation,
        } and self.judgment_rationale_id is None:
            raise ValueError("core judgments and recommendations require a rationale")
        if self.expression_role == ExpressionRole.open_question:
            if self.evidence_status == ClaimEvidenceStatus.supported:
                raise ValueError("open questions cannot be marked supported")
        if self.expression_role == ExpressionRole.user_reflection:
            if self.evidence_status != ClaimEvidenceStatus.not_applicable:
                raise ValueError("user reflections require not_applicable evidence status")
        elif self.evidence_status == ClaimEvidenceStatus.not_applicable:
            raise ValueError("not_applicable evidence status is reserved for user reflections")
        return self


class JudgmentCardVersionResponse(StrictContractModel):
    judgment_card_id: ResourceId
    judgment_card_version_id: ResourceId
    research_case_id: ResourceId
    research_run_id: ResourceId
    version: Revision
    revision: Revision
    claim_version_ids: list[ResourceId]
    summary: NonEmptyString
    uncertainties: list[NonEmptyString]
    evidence_gaps: list[NonEmptyString]
    audit_status: JudgmentAuditStatus
    validity_status: JudgmentValidityStatus
    lifecycle_status: JudgmentLifecycleStatus
    created_at: UtcDateTime
    previous_version_id: ResourceId | None
    current_judgment_audit_id: ResourceId | None
    decision_fitness_id: ResourceId | None

    @model_validator(mode="after")
    def validate_judgment_version(self) -> "JudgmentCardVersionResponse":
        if self.version == 1 and self.previous_version_id is not None:
            raise ValueError("initial judgment version cannot have a previous version")
        if self.version > 1 and self.previous_version_id is None:
            raise ValueError("later judgment versions require previous_version_id")
        if len(self.claim_version_ids) != len(set(self.claim_version_ids)):
            raise ValueError("judgment claim version ids must be unique")
        if self.audit_status in {
            JudgmentAuditStatus.provisionally_acceptable,
            JudgmentAuditStatus.acceptable,
        }:
            if self.decision_fitness_id is None:
                raise ValueError("adoptable judgments require decision_fitness_id")
        elif self.decision_fitness_id is not None:
            raise ValueError("non-adoptable judgments cannot expose decision fitness")
        return self


class JudgmentAuditResponse(StrictContractModel):
    judgment_audit_id: ResourceId
    judgment_card_version_id: ResourceId
    audit_policy_version: NonEmptyString
    audit_run_status: JudgmentAuditRunStatus
    finding_ids: list[ResourceId]
    created_at: UtcDateTime
    gate_result: JudgmentGateResult | None
    started_at: UtcDateTime | None
    completed_at: UtcDateTime | None

    @model_validator(mode="after")
    def validate_audit_lifecycle(self) -> "JudgmentAuditResponse":
        if len(self.finding_ids) != len(set(self.finding_ids)):
            raise ValueError("audit finding ids must be unique")
        if self.audit_run_status == JudgmentAuditRunStatus.pending:
            if self.started_at is not None or self.completed_at is not None:
                raise ValueError("pending audits cannot include execution times")
        elif self.started_at is None:
            raise ValueError("started audit states require started_at")
        if self.audit_run_status in {
            JudgmentAuditRunStatus.completed,
            JudgmentAuditRunStatus.failed,
        }:
            if self.completed_at is None:
                raise ValueError("terminal audit states require completed_at")
        elif self.completed_at is not None:
            raise ValueError("non-terminal audits cannot include completed_at")
        if self.audit_run_status == JudgmentAuditRunStatus.completed:
            if self.gate_result is None:
                raise ValueError("completed audits require gate_result")
        elif self.gate_result is not None:
            raise ValueError("only completed audits can include gate_result")
        if self.started_at is not None and self.started_at < self.created_at:
            raise ValueError("started_at cannot be earlier than created_at")
        if self.completed_at is not None and self.completed_at < self.started_at:
            raise ValueError("completed_at cannot be earlier than started_at")
        return self


class AuditFindingResponse(StrictContractModel):
    audit_finding_id: ResourceId
    judgment_audit_id: ResourceId
    affected_claim_version_ids: list[ResourceId]
    finding_type: OpenCodeValue
    severity: AuditFindingSeverity
    description: NonEmptyString
    supporting_reason: NonEmptyString
    policy_version: NonEmptyString
    created_at: UtcDateTime
    recommended_revision: NonEmptyString | None
    risk_trigger_condition: NonEmptyString | None

    @model_validator(mode="after")
    def validate_claim_ids(self) -> "AuditFindingResponse":
        if len(self.affected_claim_version_ids) != len(set(self.affected_claim_version_ids)):
            raise ValueError("affected claim version ids must be unique")
        return self


class AcknowledgeAuditFindingRequest(StrictContractModel):
    expected_revision: Revision
    judgment_card_version_id: ResourceId
    acknowledgement_note: NonEmptyString | None = None


class WarningAcknowledgementResponse(StrictContractModel):
    warning_acknowledgement_id: ResourceId
    audit_finding_id: ResourceId
    judgment_card_version_id: ResourceId
    acknowledged_by: ResourceId
    acknowledged_at: UtcDateTime
    acknowledgement_note: NonEmptyString | None


class SetClaimUserAttitudeRequest(StrictContractModel):
    expected_revision: Revision
    user_attitude: ClaimUserAttitude


class DecisionRiskCeiling(StrictContractModel):
    maximum_cost_level: CostLevel
    minimum_reversibility: Reversibility
    maximum_external_impact: ExternalImpact
    expert_review_required: StrictBool


class DecisionFitnessResponse(StrictContractModel):
    decision_fitness_id: ResourceId
    judgment_card_version_id: ResourceId
    policy_version: NonEmptyString
    allowed_uses: list[DecisionUse]
    forbidden_uses: list[DecisionUse]
    required_conditions: list[NonEmptyString]
    risk_ceiling: DecisionRiskCeiling
    escalation_triggers: list[NonEmptyString]
    created_at: UtcDateTime

    @model_validator(mode="after")
    def validate_uses(self) -> "DecisionFitnessResponse":
        if not self.allowed_uses:
            raise ValueError("decision fitness requires at least one allowed use")
        if len(self.allowed_uses) != len(set(self.allowed_uses)):
            raise ValueError("allowed uses must be unique")
        if len(self.forbidden_uses) != len(set(self.forbidden_uses)):
            raise ValueError("forbidden uses must be unique")
        if set(self.allowed_uses) & set(self.forbidden_uses):
            raise ValueError("allowed and forbidden uses must be disjoint")
        return self


class StartResearchRunData(StrictContractModel):
    research_run: ResearchRunResponse
    research_run_outcome: ResearchRunOutcomeResponse | None
    judgment_card: JudgmentCardVersionResponse | None

    @model_validator(mode="after")
    def validate_result_shape(self) -> "StartResearchRunData":
        outcome = self.research_run_outcome
        if outcome is None:
            if self.judgment_card is not None:
                raise ValueError("a judgment card requires a run outcome")
            return self
        if outcome.research_run_id != self.research_run.research_run_id:
            raise ValueError("run outcome must belong to the returned research run")
        if outcome.judgment_card_version_id is None:
            if self.judgment_card is not None:
                raise ValueError("non-judgment outcomes cannot return a judgment card")
        else:
            if self.judgment_card is None:
                raise ValueError("judgment outcomes must return a judgment card")
            if outcome.judgment_card_version_id != self.judgment_card.judgment_card_version_id:
                raise ValueError("run outcome and judgment card versions must match")
            if self.judgment_card.research_run_id != self.research_run.research_run_id:
                raise ValueError("judgment card must belong to the returned research run")
        return self


class WarningAcknowledgementCommandData(StrictContractModel):
    warning_acknowledgement: WarningAcknowledgementResponse
    judgment_card: JudgmentCardVersionResponse

    @model_validator(mode="after")
    def validate_judgment_version(self) -> "WarningAcknowledgementCommandData":
        if (
            self.warning_acknowledgement.judgment_card_version_id
            != self.judgment_card.judgment_card_version_id
        ):
            raise ValueError("warning acknowledgement must match the judgment version")
        return self


class ClaimUserAttitudeCommandData(StrictContractModel):
    claim: ClaimVersionResponse


__all__ = [
    "AcknowledgeAuditFindingRequest",
    "AuditFindingResponse",
    "AuditFindingSeverity",
    "ClaimEvidenceLinkResponse",
    "ClaimEvidenceStatus",
    "ClaimImportance",
    "ClaimLifecycleStatus",
    "ClaimUserAttitude",
    "ClaimUserAttitudeCommandData",
    "ClaimVersionResponse",
    "ConfidenceLevel",
    "CostLevel",
    "DecisionFitnessResponse",
    "DecisionRiskCeiling",
    "DecisionUse",
    "EpistemicType",
    "EvidenceRole",
    "ExpressionRole",
    "ExternalImpact",
    "FactRationaleProfile",
    "HypothesisRationaleProfile",
    "InferenceRationaleProfile",
    "InterpretationRationaleProfile",
    "JudgmentAuditResponse",
    "JudgmentAuditRunStatus",
    "JudgmentAuditStatus",
    "JudgmentCardVersionResponse",
    "JudgmentGateResult",
    "JudgmentLifecycleStatus",
    "JudgmentRationaleResponse",
    "JudgmentValidityStatus",
    "RationaleProfile",
    "RecommendationRationaleProfile",
    "Reversibility",
    "SetClaimUserAttitudeRequest",
    "StartResearchRunData",
    "SupportStrength",
    "SupportStrengthLevel",
    "WarningAcknowledgementCommandData",
    "WarningAcknowledgementResponse",
]
