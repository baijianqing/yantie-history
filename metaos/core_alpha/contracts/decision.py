"""Core Alpha contracts for disposition proposals and user decisions."""

from __future__ import annotations

from enum import Enum

from pydantic import model_validator

from metaos.core_alpha.contracts.common import (
    NonEmptyString,
    ResourceId,
    ResourceReference,
    Revision,
    StrictContractModel,
    UtcDateTime,
)
from metaos.core_alpha.contracts.scope import ResearchCaseResponse


class DispositionType(str, Enum):
    proceed_to_action = "proceed_to_action"
    continue_research = "continue_research"
    defer_decision = "defer_decision"
    observe = "observe"
    discard = "discard"
    explicit_no_action = "explicit_no_action"
    knowledge_only_closure = "knowledge_only_closure"


class DispositionUserDecisionStatus(str, Enum):
    pending = "pending"
    accepted = "accepted"
    adjusted = "adjusted"
    rejected = "rejected"


class DispositionLifecycleStatus(str, Enum):
    current = "current"
    superseded = "superseded"
    expired = "expired"
    withdrawn = "withdrawn"


def _validate_disposition_conditions(
    disposition_type: DispositionType,
    defer_until: UtcDateTime | None,
    observation_condition: str | None,
) -> None:
    if disposition_type == DispositionType.defer_decision:
        if defer_until is None:
            raise ValueError("defer_decision requires defer_until")
        if observation_condition is not None:
            raise ValueError("defer_decision cannot include observation_condition")
    elif disposition_type == DispositionType.observe:
        if observation_condition is None:
            raise ValueError("observe requires observation_condition")
        if defer_until is not None:
            raise ValueError("observe cannot include defer_until")
    elif defer_until is not None or observation_condition is not None:
        raise ValueError("this disposition type cannot include defer or observation conditions")


class DispositionProposalVersionResponse(StrictContractModel):
    disposition_proposal_id: ResourceId
    disposition_proposal_version_id: ResourceId
    research_case_id: ResourceId
    judgment_card_version_id: ResourceId
    decision_fitness_id: ResourceId
    proposed_disposition_type: DispositionType
    reason: NonEmptyString
    user_decision_status: DispositionUserDecisionStatus
    lifecycle_status: DispositionLifecycleStatus
    version: Revision
    revision: Revision
    created_at: UtcDateTime
    warning_acknowledgement_ids: list[ResourceId]
    previous_version_id: ResourceId | None
    expires_at: UtcDateTime | None
    defer_until: UtcDateTime | None
    observation_condition: NonEmptyString | None

    @model_validator(mode="after")
    def validate_proposal(self) -> "DispositionProposalVersionResponse":
        if self.version == 1 and self.previous_version_id is not None:
            raise ValueError("initial proposal version cannot have a previous version")
        if self.version > 1 and self.previous_version_id is None:
            raise ValueError("later proposal versions require previous_version_id")
        if len(self.warning_acknowledgement_ids) != len(
            set(self.warning_acknowledgement_ids)
        ):
            raise ValueError("warning acknowledgement ids must be unique")
        if self.lifecycle_status == DispositionLifecycleStatus.expired:
            if self.expires_at is None:
                raise ValueError("expired proposals require expires_at")
        if self.expires_at is not None and self.expires_at < self.created_at:
            raise ValueError("expires_at cannot be earlier than created_at")
        _validate_disposition_conditions(
            self.proposed_disposition_type,
            self.defer_until,
            self.observation_condition,
        )
        return self


class ResearchDispositionResponse(StrictContractModel):
    research_disposition_id: ResourceId
    research_case_id: ResourceId
    source_disposition_proposal_version_id: ResourceId
    judgment_card_version_id: ResourceId
    decision_fitness_id: ResourceId
    disposition_type: DispositionType
    confirmed_by: ResourceId
    confirmed_at: UtcDateTime
    supersedes_disposition_id: ResourceId | None
    defer_until: UtcDateTime | None
    observation_condition: NonEmptyString | None

    @model_validator(mode="after")
    def validate_conditions(self) -> "ResearchDispositionResponse":
        _validate_disposition_conditions(
            self.disposition_type,
            self.defer_until,
            self.observation_condition,
        )
        return self


class AcceptDispositionProposalRequest(StrictContractModel):
    expected_revision: Revision
    judgment_card_version_id: ResourceId
    decision_fitness_id: ResourceId
    warning_acknowledgement_ids: list[ResourceId]

    @model_validator(mode="after")
    def validate_warning_ids(self) -> "AcceptDispositionProposalRequest":
        if len(self.warning_acknowledgement_ids) != len(
            set(self.warning_acknowledgement_ids)
        ):
            raise ValueError("warning acknowledgement ids must be unique")
        return self


class AdjustDispositionProposalRequest(StrictContractModel):
    expected_revision: Revision
    proposed_disposition_type: DispositionType
    reason: NonEmptyString
    defer_until: UtcDateTime | None = None
    observation_condition: NonEmptyString | None = None

    @model_validator(mode="after")
    def validate_conditions(self) -> "AdjustDispositionProposalRequest":
        _validate_disposition_conditions(
            self.proposed_disposition_type,
            self.defer_until,
            self.observation_condition,
        )
        return self


class RejectDispositionProposalRequest(StrictContractModel):
    expected_revision: Revision


class AcceptDispositionProposalData(StrictContractModel):
    disposition_proposal: DispositionProposalVersionResponse
    research_disposition: ResearchDispositionResponse
    research_case: ResearchCaseResponse

    @model_validator(mode="after")
    def validate_accepted_resources(self) -> "AcceptDispositionProposalData":
        proposal = self.disposition_proposal
        disposition = self.research_disposition
        if proposal.disposition_proposal_version_id != (
            disposition.source_disposition_proposal_version_id
        ):
            raise ValueError("research disposition must reference the accepted proposal version")
        if proposal.research_case_id != disposition.research_case_id:
            raise ValueError("proposal and disposition must belong to the same research case")
        if disposition.research_case_id != self.research_case.research_case_id:
            raise ValueError("returned research case must match the disposition")
        if proposal.judgment_card_version_id != disposition.judgment_card_version_id:
            raise ValueError("proposal and disposition judgment versions must match")
        if proposal.decision_fitness_id != disposition.decision_fitness_id:
            raise ValueError("proposal and disposition decision fitness must match")
        if proposal.proposed_disposition_type != disposition.disposition_type:
            raise ValueError("accepted disposition type must match the proposal")
        return self


class AdjustDispositionProposalData(StrictContractModel):
    disposition_proposal: DispositionProposalVersionResponse
    superseded_version_ref: ResourceReference

    @model_validator(mode="after")
    def validate_superseded_reference(self) -> "AdjustDispositionProposalData":
        if self.superseded_version_ref.resource_type != "disposition_proposal_version":
            raise ValueError("superseded reference must identify a proposal version")
        if (
            self.disposition_proposal.previous_version_id
            != self.superseded_version_ref.resource_id
        ):
            raise ValueError("new proposal version must reference the superseded version")
        return self


class RejectDispositionProposalData(StrictContractModel):
    disposition_proposal: DispositionProposalVersionResponse


__all__ = [
    "AcceptDispositionProposalData",
    "AcceptDispositionProposalRequest",
    "AdjustDispositionProposalData",
    "AdjustDispositionProposalRequest",
    "DispositionLifecycleStatus",
    "DispositionProposalVersionResponse",
    "DispositionType",
    "DispositionUserDecisionStatus",
    "RejectDispositionProposalData",
    "RejectDispositionProposalRequest",
    "ResearchDispositionResponse",
]
