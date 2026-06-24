"""Core Alpha contracts for trusted internal application commands."""

from __future__ import annotations

from enum import Enum
from typing import Annotated

from pydantic import Field, JsonValue, model_validator

from metaos.core_alpha.contracts.common import (
    NonEmptyString,
    OpenCodeValue,
    ResourceId,
    ResourceReference,
    Revision,
    StrictContractModel,
    UtcDateTime,
)
from metaos.core_alpha.contracts.decision import (
    DispositionProposalVersionResponse,
    DispositionType,
)


LifecycleGeneration = Annotated[int, Field(strict=True, ge=1)]


class CandidateSubmissionStatus(str, Enum):
    accepted_for_domain_processing = "accepted_for_domain_processing"
    rejected_stale = "rejected_stale"
    rejected_version_mismatch = "rejected_version_mismatch"
    rejected_lifecycle = "rejected_lifecycle"
    rejected_tombstoned = "rejected_tombstoned"
    rejected_schema = "rejected_schema"


class CandidateInputVersions(StrictContractModel):
    research_run_revision: Revision
    knowledge_scope_version_id: ResourceId
    research_plan_version_id: ResourceId


class SubmitCandidateResultCommandRequest(StrictContractModel):
    operation_type: OpenCodeValue
    research_run_id: ResourceId
    research_attempt_id: ResourceId
    run_execution_spec_id: ResourceId
    input_versions: CandidateInputVersions
    lifecycle_generation: LifecycleGeneration
    capability_implementation_version: NonEmptyString
    output_schema_version: NonEmptyString
    candidate_result: dict[str, JsonValue]


class SubmitCandidateResultData(StrictContractModel):
    submission_status: CandidateSubmissionStatus
    capability_candidate_result_id: ResourceId | None
    follow_up_commands: list[ResourceReference]

    @model_validator(mode="after")
    def validate_candidate_result_identity(self) -> "SubmitCandidateResultData":
        accepted = (
            self.submission_status
            == CandidateSubmissionStatus.accepted_for_domain_processing
        )
        if accepted and self.capability_candidate_result_id is None:
            raise ValueError("accepted submissions require capability_candidate_result_id")
        if not accepted and self.capability_candidate_result_id is not None:
            raise ValueError("rejected submissions cannot create a candidate result")
        command_keys = [
            (command.resource_type, command.resource_id)
            for command in self.follow_up_commands
        ]
        if len(command_keys) != len(set(command_keys)):
            raise ValueError("follow-up command references must be unique")
        return self


class CreateDispositionProposalCommandRequest(StrictContractModel):
    research_case_id: ResourceId
    expected_research_case_revision: Revision | None = None
    judgment_card_version_id: ResourceId
    judgment_card_revision: Revision
    judgment_audit_id: ResourceId
    decision_fitness_id: ResourceId
    proposed_disposition_type: DispositionType
    reason: NonEmptyString
    warning_acknowledgement_ids: list[ResourceId] = Field(default_factory=list)
    expires_at: UtcDateTime | None = None
    defer_until: UtcDateTime | None = None
    observation_condition: NonEmptyString | None = None

    @model_validator(mode="after")
    def validate_disposition_command(self) -> "CreateDispositionProposalCommandRequest":
        if len(self.warning_acknowledgement_ids) != len(
            set(self.warning_acknowledgement_ids)
        ):
            raise ValueError("warning acknowledgement ids must be unique")
        if self.proposed_disposition_type == DispositionType.defer_decision:
            if self.defer_until is None or self.observation_condition is not None:
                raise ValueError("defer_decision requires only defer_until")
        elif self.proposed_disposition_type == DispositionType.observe:
            if self.observation_condition is None or self.defer_until is not None:
                raise ValueError("observe requires only observation_condition")
        elif self.defer_until is not None or self.observation_condition is not None:
            raise ValueError("this disposition type cannot include conditional fields")
        return self


class CreateDispositionProposalCommandData(StrictContractModel):
    disposition_proposal: DispositionProposalVersionResponse


__all__ = [
    "CandidateInputVersions",
    "CandidateSubmissionStatus",
    "CreateDispositionProposalCommandData",
    "CreateDispositionProposalCommandRequest",
    "LifecycleGeneration",
    "SubmitCandidateResultCommandRequest",
    "SubmitCandidateResultData",
]
