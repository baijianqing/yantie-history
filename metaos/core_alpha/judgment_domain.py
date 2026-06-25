"""Judgment draft assembly for Core Alpha.

The handler converts structured candidate output plus ResearchEvidenceUse
records into JudgmentCard draft versions. It intentionally stops before audit
and DecisionFitness.
"""

from __future__ import annotations

import uuid
from collections.abc import Callable, Mapping
from datetime import datetime, timezone
from typing import Any

from pydantic import Field, model_validator

from metaos.core_alpha.commands import ApplicationCommandHandler, CommandExecution, CommandOutcome
from metaos.core_alpha.contracts.common import (
    CommandContext,
    NonEmptyString,
    OpenCodeValue,
    ResourceId,
    Revision,
    StrictContractModel,
)
from metaos.core_alpha.contracts.execution import (
    EvidenceValidityStatus,
    ResearchEvidenceUseResponse,
    ResearchRunStatus,
)
from metaos.core_alpha.contracts.judgment import (
    ClaimEvidenceLinkResponse,
    ClaimEvidenceStatus,
    ClaimImportance,
    ClaimLifecycleStatus,
    ClaimUserAttitude,
    ClaimUserAttitudeCommandData,
    ClaimVersionResponse,
    ConfidenceLevel,
    EpistemicType,
    EvidenceRole,
    ExpressionRole,
    JudgmentAuditStatus,
    JudgmentCardVersionResponse,
    JudgmentLifecycleStatus,
    JudgmentRationaleResponse,
    JudgmentValidityStatus,
    RationaleProfile,
    SetClaimUserAttitudeRequest,
    SupportStrength,
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


class CandidateEvidenceLink(StrictContractModel):
    research_evidence_use_id: ResourceId
    evidence_role: EvidenceRole
    support_strength: SupportStrength
    scope_note: NonEmptyString | None = None


class ClaimCandidate(StrictContractModel):
    claim_text: NonEmptyString
    epistemic_type: EpistemicType
    expression_role: ExpressionRole
    evidence_status: ClaimEvidenceStatus
    importance: ClaimImportance
    confidence_level: ConfidenceLevel
    rationale_profile: RationaleProfile
    reasoning_summary: NonEmptyString
    evidence_links: list[CandidateEvidenceLink] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_candidate_shape(self) -> "ClaimCandidate":
        profile_type = self.rationale_profile.profile_type
        if self.expression_role == ExpressionRole.recommendation:
            if profile_type != "recommendation":
                raise ValueError("recommendation claims require recommendation rationale")
        elif self.epistemic_type == EpistemicType.fact:
            if profile_type != "fact":
                raise ValueError("fact claims require fact rationale")
        elif self.epistemic_type == EpistemicType.interpretation:
            if profile_type != "interpretation":
                raise ValueError("interpretation claims require interpretation rationale")
        elif self.epistemic_type in {EpistemicType.inference, EpistemicType.analogy}:
            if profile_type != "inference":
                raise ValueError("inference and analogy claims require inference rationale")
        elif self.epistemic_type == EpistemicType.hypothesis:
            if profile_type != "hypothesis":
                raise ValueError("hypothesis claims require hypothesis rationale")

        if self.expression_role in {
            ExpressionRole.core_judgment,
            ExpressionRole.recommendation,
        } and not self.evidence_links:
            raise ValueError("core judgment and recommendation claims require evidence links")
        use_ids = [link.research_evidence_use_id for link in self.evidence_links]
        if len(use_ids) != len(set(use_ids)):
            raise ValueError("candidate evidence use ids must be unique")
        return self


class CreateJudgmentDraftRequest(StrictContractModel):
    expected_run_revision: Revision
    summary: NonEmptyString
    uncertainties: list[NonEmptyString]
    evidence_gaps: list[NonEmptyString]
    claims: list[ClaimCandidate] = Field(min_length=1)


class JudgmentDraftCommandData(StrictContractModel):
    judgment_card: JudgmentCardVersionResponse
    claims: list[ClaimVersionResponse]
    evidence_links: list[ClaimEvidenceLinkResponse]
    rationales: list[JudgmentRationaleResponse]


class JudgmentDomainCommandHandler:
    """Application facade for JudgmentCard draft creation and claim attitude."""

    def __init__(
        self,
        command_handler: ApplicationCommandHandler,
        *,
        clock: Clock | None = None,
    ):
        self.command_handler = command_handler
        self.clock = clock or _now

    def create_judgment_draft(
        self,
        research_run_id: str,
        request: CreateJudgmentDraftRequest,
        *,
        context: CommandContext,
    ) -> CommandExecution:
        body = request.model_dump(mode="json")
        return self.command_handler.execute(
            scope=f"{context.actor_id}:POST:/internal/alpha/research-runs/{research_run_id}/judgment-drafts",
            idempotency_key=context.idempotency_key,
            request_body=body,
            context=context,
            callback=lambda uow: self._create_judgment_draft(
                uow=uow,
                research_run_id=research_run_id,
                request=request,
            ),
        )

    def set_claim_user_attitude(
        self,
        claim_version_id: str,
        request: SetClaimUserAttitudeRequest,
        *,
        context: CommandContext,
    ) -> CommandExecution:
        body = request.model_dump(mode="json")
        return self.command_handler.execute(
            scope=f"{context.actor_id}:POST:/alpha/claim-versions/{claim_version_id}/commands/set-user-attitude",
            idempotency_key=context.idempotency_key,
            request_body=body,
            context=context,
            callback=lambda uow: self._set_claim_user_attitude(
                uow=uow,
                claim_version_id=claim_version_id,
                request=request,
            ),
        )

    def _create_judgment_draft(
        self,
        *,
        uow: UnitOfWork,
        research_run_id: str,
        request: CreateJudgmentDraftRequest,
    ) -> CommandOutcome:
        now = self._now()
        run = uow.run_evidence.get_research_run(research_run_id)
        self._ensure_run_active(run)
        if run.revision != request.expected_run_revision:
            raise ConcurrencyConflictError(
                f"revision conflict for {research_run_id}: expected {request.expected_run_revision}"
            )
        previous = self._current_judgment_for_run(uow, research_run_id)
        judgment_card_id = previous.judgment_card_id if previous else _new_id("jc")
        judgment_card_version_id = _new_id("jcv")
        next_version = 1 if previous is None else previous.version + 1
        claim_versions: list[ClaimVersionResponse] = []
        evidence_links: list[ClaimEvidenceLinkResponse] = []
        rationales: list[JudgmentRationaleResponse] = []

        for candidate in request.claims:
            claim_version_id = _new_id("claimv")
            rationale_id = _new_id("rat")
            claim_link_ids: list[str] = []
            seen_evidence_units: set[str] = set()
            for link_candidate in candidate.evidence_links:
                evidence_use = uow.run_evidence.get_research_evidence_use(
                    link_candidate.research_evidence_use_id,
                )
                if evidence_use.research_run_id != research_run_id:
                    raise ValueError("candidate evidence use belongs to another ResearchRun")
                if evidence_use.validity_result == EvidenceValidityStatus.invalid:
                    raise ValueError("invalid evidence use cannot support a claim")
                evidence = uow.run_evidence.get_evidence_unit(evidence_use.evidence_unit_id)
                if evidence.evidence_unit_id in seen_evidence_units:
                    continue
                seen_evidence_units.add(evidence.evidence_unit_id)
                link = ClaimEvidenceLinkResponse(
                    claim_evidence_link_id=_new_id("cel"),
                    claim_version_id=claim_version_id,
                    research_evidence_use_id=evidence_use.research_evidence_use_id,
                    evidence_unit_id=evidence.evidence_unit_id,
                    evidence_role=link_candidate.evidence_role,
                    support_strength=link_candidate.support_strength,
                    created_at=now,
                    scope_note=link_candidate.scope_note,
                )
                evidence_links.append(link)
                claim_link_ids.append(link.claim_evidence_link_id)

            if candidate.expression_role in {
                ExpressionRole.core_judgment,
                ExpressionRole.recommendation,
            } and not claim_link_ids:
                raise ValueError("core judgment and recommendation claims require distinct evidence")

            rationale = JudgmentRationaleResponse(
                judgment_rationale_id=rationale_id,
                claim_version_id=claim_version_id,
                rationale_profile=candidate.rationale_profile,
                evidence_link_ids=claim_link_ids,
                reasoning_summary=candidate.reasoning_summary,
                created_at=now,
            )
            rationales.append(rationale)
            claim_versions.append(
                ClaimVersionResponse(
                    claim_id=_new_id("claim"),
                    claim_version_id=claim_version_id,
                    judgment_card_version_id=judgment_card_version_id,
                    claim_text=candidate.claim_text,
                    epistemic_type=candidate.epistemic_type,
                    expression_role=candidate.expression_role,
                    evidence_status=candidate.evidence_status,
                    importance=candidate.importance,
                    confidence_level=candidate.confidence_level,
                    lifecycle_status=ClaimLifecycleStatus.current,
                    user_attitude=ClaimUserAttitude.unreviewed,
                    version=1,
                    created_at=now,
                    judgment_rationale_id=rationale_id,
                    previous_version_id=None,
                )
            )

        judgment = JudgmentCardVersionResponse(
            judgment_card_id=judgment_card_id,
            judgment_card_version_id=judgment_card_version_id,
            research_case_id=run.research_case_id,
            research_run_id=run.research_run_id,
            version=next_version,
            revision=1,
            claim_version_ids=[claim.claim_version_id for claim in claim_versions],
            summary=request.summary,
            uncertainties=request.uncertainties,
            evidence_gaps=request.evidence_gaps,
            audit_status=JudgmentAuditStatus.pending,
            validity_status=JudgmentValidityStatus.valid,
            lifecycle_status=JudgmentLifecycleStatus.current,
            created_at=now,
            previous_version_id=previous.judgment_card_version_id if previous else None,
            current_judgment_audit_id=None,
            decision_fitness_id=None,
        )
        uow.judgment_decision.create_judgment_version(
            judgment_card=judgment,
            claims=claim_versions,
            evidence_links=evidence_links,
            rationales=rationales,
            decision_fitness=None,
        )
        data = JudgmentDraftCommandData(
            judgment_card=judgment,
            claims=claim_versions,
            evidence_links=evidence_links,
            rationales=rationales,
        )
        return CommandOutcome(
            data=data.model_dump(mode="json"),
            primary_aggregate_type="judgment_card",
            primary_aggregate_id=judgment.judgment_card_id,
            primary_aggregate_revision=judgment.revision,
            event_type_code="judgment_draft_created",
            event_payload={
                "judgment_card_version_id": judgment.judgment_card_version_id,
                "research_run_id": run.research_run_id,
                "claim_version_ids": judgment.claim_version_ids,
            },
        )

    def _set_claim_user_attitude(
        self,
        *,
        uow: UnitOfWork,
        claim_version_id: str,
        request: SetClaimUserAttitudeRequest,
    ) -> CommandOutcome:
        claim = uow.judgment_decision.get_claim(claim_version_id)
        if claim.version != request.expected_revision:
            raise ConcurrencyConflictError(
                f"claim version conflict for {claim_version_id}: expected {request.expected_revision}"
            )
        updated = uow.judgment_decision.set_claim_user_attitude(
            claim_version_id,
            user_attitude=request.user_attitude,
        )
        data = ClaimUserAttitudeCommandData(claim=updated)
        return CommandOutcome(
            data=data.model_dump(mode="json"),
            primary_aggregate_type="claim",
            primary_aggregate_id=updated.claim_id,
            primary_aggregate_revision=updated.version,
            event_type_code="claim_user_attitude_set",
            event_payload={
                "claim_version_id": updated.claim_version_id,
                "user_attitude": updated.user_attitude.value,
                "evidence_status": updated.evidence_status.value,
            },
        )

    @staticmethod
    def _current_judgment_for_run(
        uow: UnitOfWork,
        research_run_id: str,
    ) -> JudgmentCardVersionResponse | None:
        row = uow.connection.execute(
            """
            SELECT current_version_id FROM core_alpha_judgment_cards
            WHERE research_run_id = ?
            ORDER BY rowid DESC
            LIMIT 1
            """,
            (research_run_id,),
        ).fetchone()
        if row is None:
            return None
        return uow.judgment_decision.get_judgment_card_version(row["current_version_id"])

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
            raise ValueError("judgment domain clock must return UTC datetimes")
        return value.astimezone(timezone.utc)


class JudgmentDomainQueryHandler:
    """Read-side helpers for Judgment draft tests and internal callers."""

    def __init__(self, database: CoreAlphaDatabase):
        self.database = database

    def get_judgment_card_version(
        self,
        judgment_card_version_id: str,
    ) -> JudgmentCardVersionResponse:
        with UnitOfWork(self.database, write=False) as uow:
            return uow.judgment_decision.get_judgment_card_version(judgment_card_version_id)

    def get_current_judgment_card_for_case(
        self,
        research_case_id: str,
    ) -> JudgmentCardVersionResponse | None:
        with UnitOfWork(self.database, write=False) as uow:
            uow.case_scope.get_case(research_case_id)
            row = uow.connection.execute(
                """
                SELECT current_version_id
                FROM core_alpha_judgment_cards
                WHERE research_case_id = ?
                ORDER BY rowid DESC
                LIMIT 1
                """,
                (research_case_id,),
            ).fetchone()
            if row is None:
                return None
            return uow.judgment_decision.get_judgment_card_version(row["current_version_id"])

    def list_claims(self, judgment_card_version_id: str) -> list[ClaimVersionResponse]:
        with UnitOfWork(self.database, write=False) as uow:
            return uow.judgment_decision.list_claims(judgment_card_version_id)

    def get_claim_version(self, claim_version_id: str) -> ClaimVersionResponse:
        with UnitOfWork(self.database, write=False) as uow:
            return uow.judgment_decision.get_claim(claim_version_id)

    def get_current_claim(self, claim_id: str) -> ClaimVersionResponse:
        with UnitOfWork(self.database, write=False) as uow:
            row = uow.connection.execute(
                """
                SELECT claim_version_id
                FROM core_alpha_claim_versions
                WHERE claim_id = ? AND lifecycle_status = 'current'
                ORDER BY version DESC, claim_version_id DESC
                LIMIT 1
                """,
                (claim_id,),
            ).fetchone()
            if row is None:
                raise RecordNotFoundError(f"claim not found: {claim_id}")
            return uow.judgment_decision.get_claim(row["claim_version_id"])

    def list_claim_evidence_links(
        self,
        claim_version_id: str,
    ) -> list[ClaimEvidenceLinkResponse]:
        with UnitOfWork(self.database, write=False) as uow:
            return uow.judgment_decision.list_claim_evidence_links(claim_version_id)

    def get_judgment_rationale(
        self,
        judgment_rationale_id: str,
    ) -> JudgmentRationaleResponse:
        with UnitOfWork(self.database, write=False) as uow:
            return uow.judgment_decision.get_judgment_rationale(judgment_rationale_id)


__all__ = [
    "CandidateEvidenceLink",
    "ClaimCandidate",
    "CreateJudgmentDraftRequest",
    "JudgmentDomainCommandHandler",
    "JudgmentDomainQueryHandler",
    "JudgmentDraftCommandData",
]
