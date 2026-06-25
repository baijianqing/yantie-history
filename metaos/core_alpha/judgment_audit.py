"""Audit pipeline and DecisionFitness gate for Core Alpha judgments."""

from __future__ import annotations

import uuid
from collections.abc import Callable
from datetime import datetime, timezone
from typing import Any

from pydantic import Field

from metaos.core_alpha.commands import ApplicationCommandHandler, CommandExecution, CommandOutcome
from metaos.core_alpha.contracts.common import (
    CommandContext,
    NonEmptyString,
    OpenCodeValue,
    ResourceId,
    Revision,
    StrictContractModel,
)
from metaos.core_alpha.contracts.execution import EvidenceValidityStatus
from metaos.core_alpha.contracts.judgment import (
    AcknowledgeAuditFindingRequest,
    AuditFindingResponse,
    AuditFindingSeverity,
    ClaimEvidenceStatus,
    ClaimImportance,
    ClaimVersionResponse,
    CostLevel,
    DecisionFitnessResponse,
    DecisionRiskCeiling,
    DecisionUse,
    ExternalImpact,
    JudgmentAuditResponse,
    JudgmentAuditRunStatus,
    JudgmentAuditStatus,
    JudgmentCardVersionResponse,
    JudgmentGateResult,
    JudgmentLifecycleStatus,
    Reversibility,
    WarningAcknowledgementCommandData,
    WarningAcknowledgementResponse,
)
from metaos.core_alpha.persistence import (
    ConcurrencyConflictError,
    CoreAlphaDatabase,
    UnitOfWork,
)
from metaos.core_alpha.persistence.repositories import _utc_iso


Clock = Callable[[], datetime]


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _new_id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex}"


def _code(value: str) -> OpenCodeValue:
    return OpenCodeValue(code=value, registry_version="core-alpha-v1")


class AuditFindingCandidate(StrictContractModel):
    affected_claim_version_ids: list[ResourceId] = Field(default_factory=list)
    finding_type: OpenCodeValue
    severity: AuditFindingSeverity
    description: NonEmptyString
    supporting_reason: NonEmptyString
    recommended_revision: NonEmptyString | None = None
    risk_trigger_condition: NonEmptyString | None = None


class RunJudgmentAuditRequest(StrictContractModel):
    expected_judgment_revision: Revision
    audit_policy_version: NonEmptyString = "audit-v1"
    decision_fitness_policy_version: NonEmptyString = "fitness-v1"
    semantic_findings: list[AuditFindingCandidate] = Field(default_factory=list)


class JudgmentAuditCommandData(StrictContractModel):
    judgment_card: JudgmentCardVersionResponse
    judgment_audit: JudgmentAuditResponse
    audit_findings: list[AuditFindingResponse]
    decision_fitness: DecisionFitnessResponse | None


class JudgmentAuditCommandHandler:
    """Application facade for deterministic audit and warning acknowledgement."""

    def __init__(
        self,
        command_handler: ApplicationCommandHandler,
        *,
        clock: Clock | None = None,
    ):
        self.command_handler = command_handler
        self.clock = clock or _now

    def run_audit(
        self,
        judgment_card_version_id: str,
        request: RunJudgmentAuditRequest,
        *,
        context: CommandContext,
    ) -> CommandExecution:
        body = request.model_dump(mode="json")
        return self.command_handler.execute(
            scope=f"{context.actor_id}:POST:/internal/alpha/judgment-card-versions/{judgment_card_version_id}/audit",
            idempotency_key=context.idempotency_key,
            request_body=body,
            context=context,
            callback=lambda uow: self._run_audit(
                uow=uow,
                judgment_card_version_id=judgment_card_version_id,
                request=request,
            ),
        )

    def acknowledge_warning(
        self,
        audit_finding_id: str,
        request: AcknowledgeAuditFindingRequest,
        *,
        context: CommandContext,
    ) -> CommandExecution:
        body = request.model_dump(mode="json")
        return self.command_handler.execute(
            scope=f"{context.actor_id}:POST:/internal/alpha/audit-findings/{audit_finding_id}/acknowledge",
            idempotency_key=context.idempotency_key,
            request_body=body,
            context=context,
            callback=lambda uow: self._acknowledge_warning(
                uow=uow,
                audit_finding_id=audit_finding_id,
                request=request,
                context=context,
            ),
        )

    def _run_audit(
        self,
        *,
        uow: UnitOfWork,
        judgment_card_version_id: str,
        request: RunJudgmentAuditRequest,
    ) -> CommandOutcome:
        now = self._now()
        judgment = uow.judgment_decision.get_judgment_card_version(judgment_card_version_id)
        if judgment.lifecycle_status != JudgmentLifecycleStatus.current:
            raise ValueError("only current JudgmentCard versions can be audited")
        if judgment.revision != request.expected_judgment_revision:
            raise ConcurrencyConflictError(
                f"judgment revision conflict for {judgment_card_version_id}: "
                f"expected {request.expected_judgment_revision}"
            )
        claims = uow.judgment_decision.list_claims(judgment_card_version_id)
        deterministic_candidates = self._deterministic_precheck(
            uow=uow,
            judgment=judgment,
            claims=claims,
        )
        all_candidates = [*deterministic_candidates, *request.semantic_findings]
        audit_id = _new_id("audit")
        findings = [
            self._finding(
                candidate=candidate,
                audit_id=audit_id,
                policy_version=request.audit_policy_version,
                created_at=now,
                valid_claim_ids={claim.claim_version_id for claim in claims},
            )
            for candidate in all_candidates
        ]
        gate = self._gate_result(findings)
        decision_fitness = None
        if gate in {
            JudgmentGateResult.acceptable,
            JudgmentGateResult.provisionally_acceptable,
        }:
            decision_fitness = self._decision_fitness(
                judgment_card_version_id=judgment_card_version_id,
                policy_version=request.decision_fitness_policy_version,
                gate=gate,
                created_at=now,
            )
        audit = JudgmentAuditResponse(
            judgment_audit_id=audit_id,
            judgment_card_version_id=judgment_card_version_id,
            audit_policy_version=request.audit_policy_version,
            audit_run_status=JudgmentAuditRunStatus.completed,
            finding_ids=[finding.audit_finding_id for finding in findings],
            created_at=now,
            gate_result=gate,
            started_at=now,
            completed_at=now,
        )
        uow.judgment_decision.append_judgment_audit(audit=audit, findings=findings)
        if decision_fitness is not None:
            uow.judgment_decision.add_decision_fitness(decision_fitness)
        updated = self._apply_gate(
            uow=uow,
            judgment=judgment,
            audit=audit,
            decision_fitness=decision_fitness,
            gate=gate,
            expected_revision=request.expected_judgment_revision,
        )
        data = JudgmentAuditCommandData(
            judgment_card=updated,
            judgment_audit=audit,
            audit_findings=findings,
            decision_fitness=decision_fitness,
        )
        return CommandOutcome(
            data=data.model_dump(mode="json"),
            primary_aggregate_type="judgment_card",
            primary_aggregate_id=updated.judgment_card_id,
            primary_aggregate_revision=updated.revision,
            event_type_code="judgment_audit_completed",
            event_payload={
                "judgment_card_version_id": updated.judgment_card_version_id,
                "judgment_audit_id": audit.judgment_audit_id,
                "gate_result": gate.value,
                "finding_ids": audit.finding_ids,
                "decision_fitness_id": updated.decision_fitness_id,
            },
        )

    def _acknowledge_warning(
        self,
        *,
        uow: UnitOfWork,
        audit_finding_id: str,
        request: AcknowledgeAuditFindingRequest,
        context: CommandContext,
    ) -> CommandOutcome:
        judgment = uow.judgment_decision.get_judgment_card_version(
            request.judgment_card_version_id,
        )
        if judgment.revision != request.expected_revision:
            raise ConcurrencyConflictError(
                f"judgment revision conflict for {judgment.judgment_card_version_id}: "
                f"expected {request.expected_revision}"
            )
        acknowledgement = WarningAcknowledgementResponse(
            warning_acknowledgement_id=_new_id("ack"),
            audit_finding_id=audit_finding_id,
            judgment_card_version_id=request.judgment_card_version_id,
            acknowledged_by=context.actor_id,
            acknowledged_at=self._now(),
            acknowledgement_note=request.acknowledgement_note,
        )
        uow.judgment_decision.acknowledge_warning(acknowledgement)
        data = WarningAcknowledgementCommandData(
            warning_acknowledgement=acknowledgement,
            judgment_card=judgment,
        )
        return CommandOutcome(
            data=data.model_dump(mode="json"),
            primary_aggregate_type="judgment_card",
            primary_aggregate_id=judgment.judgment_card_id,
            primary_aggregate_revision=judgment.revision,
            event_type_code="warning_acknowledged",
            event_payload={
                "warning_acknowledgement_id": acknowledgement.warning_acknowledgement_id,
                "audit_finding_id": audit_finding_id,
                "judgment_card_version_id": request.judgment_card_version_id,
            },
        )

    @staticmethod
    def _deterministic_precheck(
        *,
        uow: UnitOfWork,
        judgment: JudgmentCardVersionResponse,
        claims: list[ClaimVersionResponse],
    ) -> list[AuditFindingCandidate]:
        findings: list[AuditFindingCandidate] = []
        for claim in claims:
            links = uow.judgment_decision.list_claim_evidence_links(claim.claim_version_id)
            if claim.importance == ClaimImportance.core:
                if not links:
                    findings.append(
                        AuditFindingCandidate(
                            affected_claim_version_ids=[claim.claim_version_id],
                            finding_type=_code("missing_core_evidence"),
                            severity=AuditFindingSeverity.blocking,
                            description="Core Claim lacks a ClaimEvidenceLink.",
                            supporting_reason="Core claims must be grounded in ResearchEvidenceUse.",
                        )
                    )
                if claim.judgment_rationale_id is None:
                    findings.append(
                        AuditFindingCandidate(
                            affected_claim_version_ids=[claim.claim_version_id],
                            finding_type=_code("missing_rationale"),
                            severity=AuditFindingSeverity.blocking,
                            description="Core Claim lacks JudgmentRationale.",
                            supporting_reason="Core claims require typed rationale before adoption.",
                        )
                    )
                if claim.evidence_status in {
                    ClaimEvidenceStatus.unassessed,
                    ClaimEvidenceStatus.insufficient,
                    ClaimEvidenceStatus.contradicted,
                }:
                    findings.append(
                        AuditFindingCandidate(
                            affected_claim_version_ids=[claim.claim_version_id],
                            finding_type=_code("unsupported_core_claim"),
                            severity=AuditFindingSeverity.blocking,
                            description="Core Claim evidence status is not adoptable.",
                            supporting_reason=(
                                "Unassessed, insufficient, or contradicted core claims cannot pass the decision gate."
                            ),
                        )
                    )
                elif claim.evidence_status in {
                    ClaimEvidenceStatus.partially_supported,
                    ClaimEvidenceStatus.mixed,
                }:
                    findings.append(
                        AuditFindingCandidate(
                            affected_claim_version_ids=[claim.claim_version_id],
                            finding_type=_code("limited_core_support"),
                            severity=AuditFindingSeverity.warning,
                            description="Core Claim has limited or mixed evidence support.",
                            supporting_reason="The claim may be usable only under constrained conditions.",
                            recommended_revision="Preserve the limited evidence status in downstream use.",
                        )
                    )
            for link in links:
                evidence_use = uow.run_evidence.get_research_evidence_use(
                    link.research_evidence_use_id,
                )
                if evidence_use.validity_result == EvidenceValidityStatus.invalid:
                    findings.append(
                        AuditFindingCandidate(
                            affected_claim_version_ids=[claim.claim_version_id],
                            finding_type=_code("invalid_evidence_use"),
                            severity=AuditFindingSeverity.blocking,
                            description="Claim links to invalid evidence use.",
                            supporting_reason="Invalid evidence cannot support an adoptable judgment.",
                        )
                    )
        return findings

    @staticmethod
    def _finding(
        *,
        candidate: AuditFindingCandidate,
        audit_id: str,
        policy_version: str,
        created_at: datetime,
        valid_claim_ids: set[str],
    ) -> AuditFindingResponse:
        if not set(candidate.affected_claim_version_ids).issubset(valid_claim_ids):
            raise ValueError("audit finding references a claim outside the JudgmentCard")
        return AuditFindingResponse(
            audit_finding_id=_new_id("finding"),
            judgment_audit_id=audit_id,
            affected_claim_version_ids=candidate.affected_claim_version_ids,
            finding_type=candidate.finding_type,
            severity=candidate.severity,
            description=candidate.description,
            supporting_reason=candidate.supporting_reason,
            policy_version=policy_version,
            created_at=created_at,
            recommended_revision=candidate.recommended_revision,
            risk_trigger_condition=candidate.risk_trigger_condition,
        )

    @staticmethod
    def _gate_result(findings: list[AuditFindingResponse]) -> JudgmentGateResult:
        if any(finding.severity == AuditFindingSeverity.blocking for finding in findings):
            return JudgmentGateResult.blocked
        if any(finding.severity == AuditFindingSeverity.warning for finding in findings):
            return JudgmentGateResult.provisionally_acceptable
        return JudgmentGateResult.acceptable

    @staticmethod
    def _decision_fitness(
        *,
        judgment_card_version_id: str,
        policy_version: str,
        gate: JudgmentGateResult,
        created_at: datetime,
    ) -> DecisionFitnessResponse:
        allowed = [DecisionUse.understanding, DecisionUse.research_planning]
        if gate == JudgmentGateResult.acceptable:
            allowed.append(DecisionUse.observation)
        return DecisionFitnessResponse(
            decision_fitness_id=_new_id("df"),
            judgment_card_version_id=judgment_card_version_id,
            policy_version=policy_version,
            allowed_uses=allowed,
            forbidden_uses=[DecisionUse.low_risk_experiment, DecisionUse.reversible_action],
            required_conditions=(
                ["Resolve or acknowledge non-blocking warnings before downstream decisions."]
                if gate == JudgmentGateResult.provisionally_acceptable
                else ["Stay within the cited source and rationale boundaries."]
            ),
            risk_ceiling=DecisionRiskCeiling(
                maximum_cost_level=CostLevel.low,
                minimum_reversibility=Reversibility.reversible,
                maximum_external_impact=ExternalImpact.none,
                expert_review_required=False,
            ),
            escalation_triggers=[
                "New counterevidence appears.",
                "Requested use exceeds the current allowed uses.",
            ],
            created_at=created_at,
        )

    @staticmethod
    def _apply_gate(
        *,
        uow: UnitOfWork,
        judgment: JudgmentCardVersionResponse,
        audit: JudgmentAuditResponse,
        decision_fitness: DecisionFitnessResponse | None,
        gate: JudgmentGateResult,
        expected_revision: int,
    ) -> JudgmentCardVersionResponse:
        status = {
            JudgmentGateResult.acceptable: JudgmentAuditStatus.acceptable,
            JudgmentGateResult.provisionally_acceptable: (
                JudgmentAuditStatus.provisionally_acceptable
            ),
            JudgmentGateResult.blocked: JudgmentAuditStatus.blocked,
        }[gate]
        cursor = uow.connection.execute(
            """
            UPDATE core_alpha_judgment_card_versions
            SET audit_status = ?,
                current_judgment_audit_id = ?,
                decision_fitness_id = ?,
                revision = ?
            WHERE judgment_card_version_id = ? AND revision = ?
            """,
            (
                status.value,
                audit.judgment_audit_id,
                decision_fitness.decision_fitness_id if decision_fitness else None,
                expected_revision + 1,
                judgment.judgment_card_version_id,
                expected_revision,
            ),
        )
        if cursor.rowcount != 1:
            raise ConcurrencyConflictError("judgment revision changed during audit")
        return uow.judgment_decision.get_judgment_card_version(
            judgment.judgment_card_version_id,
        )

    def _now(self) -> datetime:
        value = self.clock()
        if value.utcoffset() is None or value.utcoffset().total_seconds() != 0:
            raise ValueError("judgment audit clock must return UTC datetimes")
        return value.astimezone(timezone.utc)


class JudgmentAuditQueryHandler:
    def __init__(self, database: CoreAlphaDatabase):
        self.database = database

    def get_judgment_audit(self, judgment_audit_id: str) -> JudgmentAuditResponse:
        with UnitOfWork(self.database, write=False) as uow:
            return uow.judgment_decision.get_judgment_audit(judgment_audit_id)

    def list_audit_findings(self, judgment_audit_id: str) -> list[AuditFindingResponse]:
        with UnitOfWork(self.database, write=False) as uow:
            return uow.judgment_decision.list_audit_findings(judgment_audit_id)

    def get_decision_fitness(self, decision_fitness_id: str) -> DecisionFitnessResponse:
        with UnitOfWork(self.database, write=False) as uow:
            return uow.judgment_decision.get_decision_fitness(decision_fitness_id)


__all__ = [
    "AuditFindingCandidate",
    "JudgmentAuditCommandData",
    "JudgmentAuditCommandHandler",
    "JudgmentAuditQueryHandler",
    "RunJudgmentAuditRequest",
]
