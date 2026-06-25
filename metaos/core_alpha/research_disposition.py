"""DispositionProposal and ResearchDisposition command handlers."""

from __future__ import annotations

import uuid
from collections.abc import Callable
from datetime import datetime, timezone
from typing import Any

from pydantic import Field, model_validator

from metaos.core_alpha.commands import ApplicationCommandHandler, CommandExecution, CommandOutcome
from metaos.core_alpha.contracts.common import (
    CommandContext,
    NonEmptyString,
    ResourceId,
    ResourceReference,
    Revision,
    StrictContractModel,
    UtcDateTime,
)
from metaos.core_alpha.contracts.decision import (
    AcceptDispositionProposalData,
    AcceptDispositionProposalRequest,
    AdjustDispositionProposalData,
    AdjustDispositionProposalRequest,
    DispositionLifecycleStatus,
    DispositionProposalVersionResponse,
    DispositionType,
    DispositionUserDecisionStatus,
    RejectDispositionProposalData,
    RejectDispositionProposalRequest,
    ResearchDispositionResponse,
)
from metaos.core_alpha.contracts.judgment import (
    AuditFindingSeverity,
    DecisionFitnessResponse,
    DecisionUse,
    JudgmentAuditStatus,
)
from metaos.core_alpha.persistence import (
    ConcurrencyConflictError,
    CoreAlphaDatabase,
    RecordNotFoundError,
    UnitOfWork,
)


Clock = Callable[[], datetime]


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _new_id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex}"


class CreateDispositionProposalRequest(StrictContractModel):
    expected_judgment_revision: Revision
    proposed_disposition_type: DispositionType
    reason: NonEmptyString
    warning_acknowledgement_ids: list[ResourceId] = Field(default_factory=list)
    defer_until: UtcDateTime | None = None
    observation_condition: NonEmptyString | None = None

    @model_validator(mode="after")
    def validate_warning_ids(self) -> "CreateDispositionProposalRequest":
        if len(self.warning_acknowledgement_ids) != len(set(self.warning_acknowledgement_ids)):
            raise ValueError("warning acknowledgement ids must be unique")
        return self


class CreateDispositionProposalData(StrictContractModel):
    disposition_proposal: DispositionProposalVersionResponse


class ResearchDispositionCommandHandler:
    """Application facade for user-confirmed research disposition."""

    def __init__(
        self,
        command_handler: ApplicationCommandHandler,
        *,
        clock: Clock | None = None,
    ):
        self.command_handler = command_handler
        self.clock = clock or _now

    def create_disposition_proposal(
        self,
        judgment_card_version_id: str,
        request: CreateDispositionProposalRequest,
        *,
        context: CommandContext,
    ) -> CommandExecution:
        body = request.model_dump(mode="json")
        return self.command_handler.execute(
            scope=f"{context.actor_id}:POST:/internal/alpha/judgment-card-versions/{judgment_card_version_id}/disposition-proposals",
            idempotency_key=context.idempotency_key,
            request_body=body,
            context=context,
            callback=lambda uow: self._create_disposition_proposal(
                uow=uow,
                judgment_card_version_id=judgment_card_version_id,
                request=request,
            ),
        )

    def adjust_disposition_proposal(
        self,
        disposition_proposal_version_id: str,
        request: AdjustDispositionProposalRequest,
        *,
        context: CommandContext,
    ) -> CommandExecution:
        body = request.model_dump(mode="json")
        return self.command_handler.execute(
            scope=f"{context.actor_id}:POST:/internal/alpha/disposition-proposal-versions/{disposition_proposal_version_id}/adjust",
            idempotency_key=context.idempotency_key,
            request_body=body,
            context=context,
            callback=lambda uow: self._adjust_disposition_proposal(
                uow=uow,
                disposition_proposal_version_id=disposition_proposal_version_id,
                request=request,
            ),
        )

    def reject_disposition_proposal(
        self,
        disposition_proposal_version_id: str,
        request: RejectDispositionProposalRequest,
        *,
        context: CommandContext,
    ) -> CommandExecution:
        body = request.model_dump(mode="json")
        return self.command_handler.execute(
            scope=f"{context.actor_id}:POST:/internal/alpha/disposition-proposal-versions/{disposition_proposal_version_id}/reject",
            idempotency_key=context.idempotency_key,
            request_body=body,
            context=context,
            callback=lambda uow: self._reject_disposition_proposal(
                uow=uow,
                disposition_proposal_version_id=disposition_proposal_version_id,
                request=request,
            ),
        )

    def accept_disposition_proposal(
        self,
        disposition_proposal_version_id: str,
        request: AcceptDispositionProposalRequest,
        *,
        context: CommandContext,
    ) -> CommandExecution:
        body = request.model_dump(mode="json")
        return self.command_handler.execute(
            scope=f"{context.actor_id}:POST:/internal/alpha/disposition-proposal-versions/{disposition_proposal_version_id}/accept",
            idempotency_key=context.idempotency_key,
            request_body=body,
            context=context,
            callback=lambda uow: self._accept_disposition_proposal(
                uow=uow,
                disposition_proposal_version_id=disposition_proposal_version_id,
                request=request,
                context=context,
            ),
        )

    def _create_disposition_proposal(
        self,
        *,
        uow: UnitOfWork,
        judgment_card_version_id: str,
        request: CreateDispositionProposalRequest,
    ) -> CommandOutcome:
        now = self._now()
        judgment = uow.judgment_decision.get_judgment_card_version(judgment_card_version_id)
        if judgment.revision != request.expected_judgment_revision:
            raise ConcurrencyConflictError(
                f"judgment revision conflict for {judgment_card_version_id}: "
                f"expected {request.expected_judgment_revision}"
            )
        fitness = self._validate_judgment_can_propose(
            uow=uow,
            judgment_card_version_id=judgment_card_version_id,
            decision_fitness_id=judgment.decision_fitness_id,
            disposition_type=request.proposed_disposition_type,
            warning_acknowledgement_ids=request.warning_acknowledgement_ids,
        )
        proposal = DispositionProposalVersionResponse(
            disposition_proposal_id=_new_id("dp"),
            disposition_proposal_version_id=_new_id("dpv"),
            research_case_id=judgment.research_case_id,
            judgment_card_version_id=judgment.judgment_card_version_id,
            decision_fitness_id=fitness.decision_fitness_id,
            proposed_disposition_type=request.proposed_disposition_type,
            reason=request.reason,
            user_decision_status=DispositionUserDecisionStatus.pending,
            lifecycle_status=DispositionLifecycleStatus.current,
            version=1,
            revision=1,
            created_at=now,
            warning_acknowledgement_ids=request.warning_acknowledgement_ids,
            previous_version_id=None,
            expires_at=None,
            defer_until=request.defer_until,
            observation_condition=request.observation_condition,
        )
        uow.judgment_decision.create_disposition_proposal(proposal)
        data = CreateDispositionProposalData(disposition_proposal=proposal)
        return CommandOutcome(
            data=data.model_dump(mode="json"),
            primary_aggregate_type="disposition_proposal",
            primary_aggregate_id=proposal.disposition_proposal_id,
            primary_aggregate_revision=proposal.revision,
            response_status=201,
            event_type_code="disposition_proposal_created",
            event_payload={
                "disposition_proposal_version_id": proposal.disposition_proposal_version_id,
                "judgment_card_version_id": judgment_card_version_id,
                "proposed_disposition_type": proposal.proposed_disposition_type.value,
            },
        )

    def _adjust_disposition_proposal(
        self,
        *,
        uow: UnitOfWork,
        disposition_proposal_version_id: str,
        request: AdjustDispositionProposalRequest,
    ) -> CommandOutcome:
        now = self._now()
        current = uow.judgment_decision.get_disposition_proposal_version(
            disposition_proposal_version_id,
        )
        if current.revision != request.expected_revision:
            raise ConcurrencyConflictError(
                f"proposal revision conflict for {disposition_proposal_version_id}: "
                f"expected {request.expected_revision}"
            )
        if current.lifecycle_status != DispositionLifecycleStatus.current:
            raise ConcurrencyConflictError("only current proposal versions can be adjusted")
        self._validate_judgment_can_propose(
            uow=uow,
            judgment_card_version_id=current.judgment_card_version_id,
            decision_fitness_id=current.decision_fitness_id,
            disposition_type=request.proposed_disposition_type,
            warning_acknowledgement_ids=current.warning_acknowledgement_ids,
        )
        adjusted = DispositionProposalVersionResponse(
            disposition_proposal_id=current.disposition_proposal_id,
            disposition_proposal_version_id=_new_id("dpv"),
            research_case_id=current.research_case_id,
            judgment_card_version_id=current.judgment_card_version_id,
            decision_fitness_id=current.decision_fitness_id,
            proposed_disposition_type=request.proposed_disposition_type,
            reason=request.reason,
            user_decision_status=DispositionUserDecisionStatus.adjusted,
            lifecycle_status=DispositionLifecycleStatus.current,
            version=current.version + 1,
            revision=1,
            created_at=now,
            warning_acknowledgement_ids=current.warning_acknowledgement_ids,
            previous_version_id=current.disposition_proposal_version_id,
            expires_at=None,
            defer_until=request.defer_until,
            observation_condition=request.observation_condition,
        )
        uow.judgment_decision.adjust_disposition_proposal(adjusted)
        data = AdjustDispositionProposalData(
            disposition_proposal=adjusted,
            superseded_version_ref=ResourceReference(
                resource_type="disposition_proposal_version",
                resource_id=current.disposition_proposal_version_id,
            ),
        )
        return CommandOutcome(
            data=data.model_dump(mode="json"),
            primary_aggregate_type="disposition_proposal",
            primary_aggregate_id=adjusted.disposition_proposal_id,
            primary_aggregate_revision=adjusted.revision,
            event_type_code="disposition_proposal_adjusted",
            event_payload={
                "disposition_proposal_version_id": adjusted.disposition_proposal_version_id,
                "previous_version_id": current.disposition_proposal_version_id,
                "proposed_disposition_type": adjusted.proposed_disposition_type.value,
            },
        )

    def _reject_disposition_proposal(
        self,
        *,
        uow: UnitOfWork,
        disposition_proposal_version_id: str,
        request: RejectDispositionProposalRequest,
    ) -> CommandOutcome:
        proposal = uow.judgment_decision.get_disposition_proposal_version(
            disposition_proposal_version_id,
        )
        if proposal.revision != request.expected_revision:
            raise ConcurrencyConflictError(
                f"proposal revision conflict for {disposition_proposal_version_id}: "
                f"expected {request.expected_revision}"
            )
        updated = self._update_proposal_decision(
            uow=uow,
            proposal=proposal,
            expected_revision=request.expected_revision,
            user_decision_status=DispositionUserDecisionStatus.rejected,
            lifecycle_status=DispositionLifecycleStatus.withdrawn,
        )
        data = RejectDispositionProposalData(disposition_proposal=updated)
        return CommandOutcome(
            data=data.model_dump(mode="json"),
            primary_aggregate_type="disposition_proposal",
            primary_aggregate_id=updated.disposition_proposal_id,
            primary_aggregate_revision=updated.revision,
            event_type_code="disposition_proposal_rejected",
            event_payload={
                "disposition_proposal_version_id": updated.disposition_proposal_version_id,
            },
        )

    def _accept_disposition_proposal(
        self,
        *,
        uow: UnitOfWork,
        disposition_proposal_version_id: str,
        request: AcceptDispositionProposalRequest,
        context: CommandContext,
    ) -> CommandOutcome:
        now = self._now()
        current = uow.judgment_decision.get_disposition_proposal_version(
            disposition_proposal_version_id,
        )
        if current.revision != request.expected_revision:
            raise ConcurrencyConflictError(
                f"proposal revision conflict for {disposition_proposal_version_id}: "
                f"expected {request.expected_revision}"
            )
        if current.judgment_card_version_id != request.judgment_card_version_id:
            raise ValueError("accepted proposal judgment must match request")
        if current.decision_fitness_id != request.decision_fitness_id:
            raise ValueError("accepted proposal fitness must match request")
        if set(current.warning_acknowledgement_ids) != set(request.warning_acknowledgement_ids):
            raise ValueError("accepted warning acknowledgements must match the proposal")
        self._validate_judgment_can_propose(
            uow=uow,
            judgment_card_version_id=current.judgment_card_version_id,
            decision_fitness_id=current.decision_fitness_id,
            disposition_type=current.proposed_disposition_type,
            warning_acknowledgement_ids=request.warning_acknowledgement_ids,
        )
        accepted = current.model_copy(
            update={
                "user_decision_status": DispositionUserDecisionStatus.accepted,
                "revision": current.revision + 1,
            }
        )
        case = uow.case_scope.get_case(current.research_case_id)
        disposition = ResearchDispositionResponse(
            research_disposition_id=_new_id("disp"),
            research_case_id=current.research_case_id,
            source_disposition_proposal_version_id=current.disposition_proposal_version_id,
            judgment_card_version_id=current.judgment_card_version_id,
            decision_fitness_id=current.decision_fitness_id,
            disposition_type=current.proposed_disposition_type,
            confirmed_by=context.actor_id,
            confirmed_at=now,
            supersedes_disposition_id=case.current_research_disposition_id,
            defer_until=current.defer_until,
            observation_condition=current.observation_condition,
        )
        persisted = uow.judgment_decision.accept_disposition_proposal(
            accepted_proposal=accepted,
            disposition=disposition,
            expected_proposal_revision=request.expected_revision,
            expected_case_revision=case.revision,
            case_updated_at=now,
        )
        updated_case = uow.case_scope.get_case(current.research_case_id)
        updated_proposal = uow.judgment_decision.get_disposition_proposal_version(
            current.disposition_proposal_version_id,
        )
        data = AcceptDispositionProposalData(
            disposition_proposal=updated_proposal,
            research_disposition=persisted,
            research_case=updated_case,
        )
        return CommandOutcome(
            data=data.model_dump(mode="json"),
            primary_aggregate_type="research_case",
            primary_aggregate_id=updated_case.research_case_id,
            primary_aggregate_revision=updated_case.revision,
            event_type_code="research_disposition_accepted",
            event_payload={
                "disposition_proposal_version_id": current.disposition_proposal_version_id,
                "research_disposition_id": persisted.research_disposition_id,
                "disposition_type": persisted.disposition_type.value,
            },
        )

    def _validate_judgment_can_propose(
        self,
        *,
        uow: UnitOfWork,
        judgment_card_version_id: str,
        decision_fitness_id: str | None,
        disposition_type: DispositionType,
        warning_acknowledgement_ids: list[str],
    ) -> DecisionFitnessResponse:
        judgment = uow.judgment_decision.get_judgment_card_version(judgment_card_version_id)
        if judgment.audit_status not in {
            JudgmentAuditStatus.acceptable,
            JudgmentAuditStatus.provisionally_acceptable,
        }:
            raise ValueError("only acceptable or provisionally acceptable judgments can produce disposition proposals")
        if decision_fitness_id is None:
            raise ValueError("disposition proposals require DecisionFitness")
        if decision_fitness_id != judgment.decision_fitness_id:
            raise ValueError("DecisionFitness must match the JudgmentCard version")
        fitness = uow.judgment_decision.get_decision_fitness(decision_fitness_id)
        if fitness.judgment_card_version_id != judgment_card_version_id:
            raise ValueError("DecisionFitness belongs to another JudgmentCard")
        required_use = _use_for_disposition(disposition_type)
        if required_use in fitness.forbidden_uses or required_use not in fitness.allowed_uses:
            raise ValueError("DecisionFitness does not allow the requested disposition type")
        self._validate_warning_acknowledgements(
            uow=uow,
            judgment_card_version_id=judgment_card_version_id,
            warning_acknowledgement_ids=warning_acknowledgement_ids,
        )
        return fitness

    @staticmethod
    def _validate_warning_acknowledgements(
        *,
        uow: UnitOfWork,
        judgment_card_version_id: str,
        warning_acknowledgement_ids: list[str],
    ) -> None:
        judgment = uow.judgment_decision.get_judgment_card_version(judgment_card_version_id)
        required_warning_ids: set[str] = set()
        if judgment.current_judgment_audit_id is not None:
            for finding in uow.judgment_decision.list_audit_findings(
                judgment.current_judgment_audit_id,
            ):
                if finding.severity == AuditFindingSeverity.warning:
                    required_warning_ids.add(finding.audit_finding_id)
        acknowledged_warning_ids: set[str] = set()
        for acknowledgement_id in warning_acknowledgement_ids:
            acknowledgement = uow.judgment_decision.get_warning_acknowledgement(
                acknowledgement_id,
            )
            if acknowledgement.judgment_card_version_id != judgment_card_version_id:
                raise ValueError("warning acknowledgement belongs to another judgment")
            acknowledged_warning_ids.add(acknowledgement.audit_finding_id)
        if not required_warning_ids.issubset(acknowledged_warning_ids):
            raise ValueError("all current non-blocking warnings must be acknowledged")

    @staticmethod
    def _update_proposal_decision(
        *,
        uow: UnitOfWork,
        proposal: DispositionProposalVersionResponse,
        expected_revision: int,
        user_decision_status: DispositionUserDecisionStatus,
        lifecycle_status: DispositionLifecycleStatus,
    ) -> DispositionProposalVersionResponse:
        cursor = uow.connection.execute(
            """
            UPDATE core_alpha_disposition_proposal_versions
            SET user_decision_status = ?,
                lifecycle_status = ?,
                revision = ?
            WHERE disposition_proposal_version_id = ? AND revision = ?
            """,
            (
                user_decision_status.value,
                lifecycle_status.value,
                expected_revision + 1,
                proposal.disposition_proposal_version_id,
                expected_revision,
            ),
        )
        if cursor.rowcount != 1:
            raise ConcurrencyConflictError("proposal revision changed during decision")
        return uow.judgment_decision.get_disposition_proposal_version(
            proposal.disposition_proposal_version_id,
        )

    def _now(self) -> datetime:
        value = self.clock()
        if value.utcoffset() is None or value.utcoffset().total_seconds() != 0:
            raise ValueError("research disposition clock must return UTC datetimes")
        return value.astimezone(timezone.utc)


class ResearchDispositionQueryHandler:
    def __init__(self, database: CoreAlphaDatabase):
        self.database = database

    def get_disposition_proposal_version(
        self,
        disposition_proposal_version_id: str,
    ) -> DispositionProposalVersionResponse:
        with UnitOfWork(self.database, write=False) as uow:
            return uow.judgment_decision.get_disposition_proposal_version(
                disposition_proposal_version_id,
            )

    def get_research_disposition(
        self,
        research_disposition_id: str,
    ) -> ResearchDispositionResponse:
        with UnitOfWork(self.database, write=False) as uow:
            return uow.judgment_decision.get_research_disposition(research_disposition_id)


def _use_for_disposition(disposition_type: DispositionType) -> DecisionUse:
    mapping = {
        DispositionType.proceed_to_action: DecisionUse.reversible_action,
        DispositionType.continue_research: DecisionUse.research_planning,
        DispositionType.defer_decision: DecisionUse.understanding,
        DispositionType.observe: DecisionUse.observation,
        DispositionType.discard: DecisionUse.understanding,
        DispositionType.explicit_no_action: DecisionUse.understanding,
        DispositionType.knowledge_only_closure: DecisionUse.understanding,
    }
    return mapping[disposition_type]


__all__ = [
    "CreateDispositionProposalData",
    "CreateDispositionProposalRequest",
    "ResearchDispositionCommandHandler",
    "ResearchDispositionQueryHandler",
]
