from __future__ import annotations

import tempfile
import unittest
from datetime import timedelta
from pathlib import Path

from metaos.core_alpha.contracts.decision import (
    DispositionProposalVersionResponse,
    ResearchDispositionResponse,
)
from metaos.core_alpha.contracts.judgment import (
    AuditFindingResponse,
    ClaimEvidenceLinkResponse,
    ClaimUserAttitude,
    ClaimVersionResponse,
    DecisionFitnessResponse,
    JudgmentAuditResponse,
    JudgmentCardVersionResponse,
    JudgmentRationaleResponse,
    SupportStrength,
    WarningAcknowledgementResponse,
)
from metaos.core_alpha.persistence import (
    ConcurrencyConflictError,
    CoreAlphaDatabase,
    RecordNotFoundError,
    UnitOfWork,
)
from test_core_alpha_run_evidence_repository import (
    NOW,
    attempt_response,
    case_response,
    code,
    evidence_unit,
    evidence_use,
    execution_spec,
    plan_response,
    question_response,
    retrieval_response,
    run_response,
    scope_response,
    source_resolution,
)


def evidence_link(
    link_id: str = "cel_1",
    *,
    claim_version_id: str = "claim_v1",
    research_evidence_use_id: str = "reu_1",
) -> ClaimEvidenceLinkResponse:
    return ClaimEvidenceLinkResponse(
        claim_evidence_link_id=link_id,
        claim_version_id=claim_version_id,
        research_evidence_use_id=research_evidence_use_id,
        evidence_unit_id="eu_1",
        evidence_role="supports",
        support_strength=SupportStrength(level="strong", reason="Direct source match."),
        created_at=NOW + timedelta(minutes=4),
        scope_note="Within required source.",
    )


def rationale(
    rationale_id: str = "rat_1",
    *,
    claim_version_id: str = "claim_v1",
    link_id: str = "cel_1",
) -> JudgmentRationaleResponse:
    return JudgmentRationaleResponse(
        judgment_rationale_id=rationale_id,
        claim_version_id=claim_version_id,
        rationale_profile={
            "profile_type": "fact",
            "source_summary": "The selected source contains the statement.",
            "location_summary": "chapter_1 page 1 offsets 10-40.",
            "fact_mapping": "The sentence directly maps to the claim.",
            "version_limitations": ["Only the selected version is covered."],
        },
        evidence_link_ids=[link_id],
        reasoning_summary="Direct fact mapping.",
        created_at=NOW + timedelta(minutes=4),
    )


def claim_version(
    claim_version_id: str = "claim_v1",
    *,
    judgment_card_version_id: str = "jcv_1",
    version: int = 1,
    previous_version_id: str | None = None,
    rationale_id: str = "rat_1",
) -> ClaimVersionResponse:
    return ClaimVersionResponse(
        claim_id="claim_1",
        claim_version_id=claim_version_id,
        judgment_card_version_id=judgment_card_version_id,
        claim_text="The selected passage supports the narrow factual claim.",
        epistemic_type="fact",
        expression_role="core_judgment",
        evidence_status="supported",
        importance="core",
        confidence_level="high",
        lifecycle_status="current",
        user_attitude="unreviewed",
        version=version,
        created_at=NOW + timedelta(minutes=4 + version),
        judgment_rationale_id=rationale_id,
        previous_version_id=previous_version_id,
    )


def decision_fitness(
    fitness_id: str = "df_1",
    *,
    judgment_card_version_id: str = "jcv_2",
) -> DecisionFitnessResponse:
    return DecisionFitnessResponse(
        decision_fitness_id=fitness_id,
        judgment_card_version_id=judgment_card_version_id,
        policy_version="fitness-v1",
        allowed_uses=["understanding", "research_planning"],
        forbidden_uses=["reversible_action"],
        required_conditions=["Do not treat this as action advice."],
        risk_ceiling={
            "maximum_cost_level": "low",
            "minimum_reversibility": "reversible",
            "maximum_external_impact": "none",
            "expert_review_required": False,
        },
        escalation_triggers=["New counterevidence appears."],
        created_at=NOW + timedelta(minutes=5),
    )


def judgment_card(
    version_id: str = "jcv_1",
    *,
    version: int = 1,
    previous_version_id: str | None = None,
    claim_ids: list[str] | None = None,
    audit_status: str = "pending",
    lifecycle_status: str = "current",
    decision_fitness_id: str | None = None,
) -> JudgmentCardVersionResponse:
    return JudgmentCardVersionResponse(
        judgment_card_id="jc_1",
        judgment_card_version_id=version_id,
        research_case_id="case_1",
        research_run_id="run_1",
        version=version,
        revision=1,
        claim_version_ids=claim_ids or ["claim_v1"],
        summary="A narrow judgment summary.",
        uncertainties=["Only one source version was checked."],
        evidence_gaps=[],
        audit_status=audit_status,
        validity_status="valid",
        lifecycle_status=lifecycle_status,
        created_at=NOW + timedelta(minutes=4 + version),
        previous_version_id=previous_version_id,
        current_judgment_audit_id=None,
        decision_fitness_id=decision_fitness_id,
    )


def audit_response(*, finding_ids: list[str]) -> JudgmentAuditResponse:
    return JudgmentAuditResponse(
        judgment_audit_id="audit_1",
        judgment_card_version_id="jcv_2",
        audit_policy_version="audit-v1",
        audit_run_status="completed",
        finding_ids=finding_ids,
        created_at=NOW + timedelta(minutes=6),
        gate_result="provisionally_acceptable",
        started_at=NOW + timedelta(minutes=6),
        completed_at=NOW + timedelta(minutes=7),
    )


def finding(
    finding_id: str,
    *,
    severity: str,
    claim_id: str = "claim_v2",
) -> AuditFindingResponse:
    return AuditFindingResponse(
        audit_finding_id=finding_id,
        judgment_audit_id="audit_1",
        affected_claim_version_ids=[claim_id],
        finding_type=code("citation_quality"),
        severity=severity,
        description=f"{severity} finding",
        supporting_reason="Audit policy reason.",
        policy_version="audit-v1",
        created_at=NOW + timedelta(minutes=7),
        recommended_revision="Lower confidence." if severity == "warning" else None,
        risk_trigger_condition=None,
    )


def proposal(
    version_id: str = "dpv_1",
    *,
    version: int = 1,
    previous_version_id: str | None = None,
    proposal_type: str = "knowledge_only_closure",
    reason: str = "Understanding is sufficient.",
    status: str = "pending",
    lifecycle_status: str = "current",
    revision: int = 1,
) -> DispositionProposalVersionResponse:
    return DispositionProposalVersionResponse(
        disposition_proposal_id="dp_1",
        disposition_proposal_version_id=version_id,
        research_case_id="case_1",
        judgment_card_version_id="jcv_2",
        decision_fitness_id="df_1",
        proposed_disposition_type=proposal_type,
        reason=reason,
        user_decision_status=status,
        lifecycle_status=lifecycle_status,
        version=version,
        revision=revision,
        created_at=NOW + timedelta(minutes=8 + version),
        warning_acknowledgement_ids=[],
        previous_version_id=previous_version_id,
        expires_at=None,
        defer_until=None,
        observation_condition=None,
    )


def disposition() -> ResearchDispositionResponse:
    return ResearchDispositionResponse(
        research_disposition_id="disp_1",
        research_case_id="case_1",
        source_disposition_proposal_version_id="dpv_2",
        judgment_card_version_id="jcv_2",
        decision_fitness_id="df_1",
        disposition_type="knowledge_only_closure",
        confirmed_by="user_1",
        confirmed_at=NOW + timedelta(minutes=10),
        supersedes_disposition_id=None,
        defer_until=None,
        observation_condition=None,
    )


class CoreAlphaJudgmentDecisionRepositoryTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.database = CoreAlphaDatabase(Path(self.temp_dir.name) / "core-alpha.db")
        self.database.initialize()
        self.seed_run_and_evidence()

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def seed_run_and_evidence(self) -> None:
        with UnitOfWork(self.database) as uow:
            uow.case_scope.create_case(
                research_case=case_response(),
                root_question=question_response(),
            )
            uow.case_scope.add_source_resolutions(
                [source_resolution()],
                expected_case_revision=1,
                updated_at=NOW + timedelta(seconds=1),
            )
            uow.case_scope.create_knowledge_scope(
                scope_response(),
                expected_case_revision=2,
                updated_at=NOW + timedelta(seconds=2),
            )
            uow.case_scope.create_research_plan(
                plan_response(),
                expected_case_revision=3,
                updated_at=NOW + timedelta(seconds=3),
            )
            uow.run_evidence.create_research_run(
                research_run=run_response(),
                execution_spec=execution_spec(),
            )
            uow.run_evidence.add_attempt(attempt_response())
            uow.run_evidence.add_retrieval_run(retrieval_response())
            uow.run_evidence.create_evidence_unit(evidence_unit())
            uow.run_evidence.add_research_evidence_use(evidence_use())

    def seed_judgment_chain(self) -> None:
        with UnitOfWork(self.database) as uow:
            uow.judgment_decision.create_judgment_version(
                judgment_card=judgment_card(),
                claims=[claim_version()],
                evidence_links=[evidence_link()],
                rationales=[rationale()],
            )
            uow.judgment_decision.create_judgment_version(
                judgment_card=judgment_card(
                    "jcv_2",
                    version=2,
                    previous_version_id="jcv_1",
                    claim_ids=["claim_v2"],
                    audit_status="provisionally_acceptable",
                    decision_fitness_id="df_1",
                ),
                claims=[
                    claim_version(
                        "claim_v2",
                        judgment_card_version_id="jcv_2",
                        version=2,
                        previous_version_id="claim_v1",
                        rationale_id="rat_2",
                    )
                ],
                evidence_links=[
                    evidence_link(
                        "cel_2",
                        claim_version_id="claim_v2",
                    )
                ],
                rationales=[
                    rationale(
                        "rat_2",
                        claim_version_id="claim_v2",
                        link_id="cel_2",
                    )
                ],
                decision_fitness=decision_fitness(),
            )

    def test_judgment_version_chain_and_decision_fitness(self) -> None:
        self.seed_judgment_chain()
        with UnitOfWork(self.database, write=False) as uow:
            old = uow.judgment_decision.get_judgment_card_version("jcv_1")
            current = uow.judgment_decision.get_current_judgment_card("jc_1")
            fitness = uow.judgment_decision.get_decision_fitness("df_1")
            claims = uow.judgment_decision.list_claims("jcv_2")
            self.assertEqual(old.lifecycle_status, "superseded")
            self.assertEqual(current.judgment_card_version_id, "jcv_2")
            self.assertEqual(fitness.allowed_uses[0], "understanding")
            self.assertEqual([claim.claim_version_id for claim in claims], ["claim_v2"])

    def test_judgment_rejects_missing_evidence_use_and_rolls_back(self) -> None:
        with self.assertRaises(RecordNotFoundError):
            with UnitOfWork(self.database) as uow:
                uow.judgment_decision.create_judgment_version(
                    judgment_card=judgment_card(),
                    claims=[claim_version()],
                    evidence_links=[
                        evidence_link(research_evidence_use_id="missing_use")
                    ],
                    rationales=[rationale()],
                )
        with UnitOfWork(self.database, write=False) as uow:
            with self.assertRaises(RecordNotFoundError):
                uow.judgment_decision.get_judgment_card_version("jcv_1")

    def test_audit_warning_acknowledgement_rejects_blocking_findings(self) -> None:
        self.seed_judgment_chain()
        with UnitOfWork(self.database) as uow:
            uow.judgment_decision.append_judgment_audit(
                audit=audit_response(finding_ids=["finding_warn", "finding_block"]),
                findings=[
                    finding("finding_warn", severity="warning"),
                    finding("finding_block", severity="blocking"),
                ],
            )
            uow.judgment_decision.acknowledge_warning(
                WarningAcknowledgementResponse(
                    warning_acknowledgement_id="ack_1",
                    audit_finding_id="finding_warn",
                    judgment_card_version_id="jcv_2",
                    acknowledged_by="user_1",
                    acknowledged_at=NOW + timedelta(minutes=8),
                    acknowledgement_note="Accepted with caution.",
                )
            )
            with self.assertRaises(ValueError):
                uow.judgment_decision.acknowledge_warning(
                    WarningAcknowledgementResponse(
                        warning_acknowledgement_id="ack_block",
                        audit_finding_id="finding_block",
                        judgment_card_version_id="jcv_2",
                        acknowledged_by="user_1",
                        acknowledged_at=NOW + timedelta(minutes=8),
                        acknowledgement_note=None,
                    )
                )

        with UnitOfWork(self.database, write=False) as uow:
            findings = uow.judgment_decision.list_audit_findings("audit_1")
            ack = uow.judgment_decision.get_warning_acknowledgement("ack_1")
            self.assertEqual([item.audit_finding_id for item in findings], ["finding_block", "finding_warn"])
            self.assertEqual(ack.audit_finding_id, "finding_warn")

    def test_user_attitude_does_not_change_claim_evidence_status(self) -> None:
        self.seed_judgment_chain()
        with UnitOfWork(self.database) as uow:
            updated = uow.judgment_decision.set_claim_user_attitude(
                "claim_v2",
                user_attitude=ClaimUserAttitude.accepted,
            )
            self.assertEqual(updated.user_attitude, "accepted")
            self.assertEqual(updated.evidence_status, "supported")

    def test_disposition_version_chain_and_acceptance_updates_case(self) -> None:
        self.seed_judgment_chain()
        with UnitOfWork(self.database) as uow:
            uow.judgment_decision.create_disposition_proposal(proposal())
            uow.judgment_decision.adjust_disposition_proposal(
                proposal(
                    "dpv_2",
                    version=2,
                    previous_version_id="dpv_1",
                    reason="Close as knowledge-only understanding.",
                )
            )
            current = uow.judgment_decision.get_current_disposition_proposal("dp_1")
            self.assertEqual(current.disposition_proposal_version_id, "dpv_2")
            self.assertEqual(
                uow.judgment_decision.get_disposition_proposal_version("dpv_1").lifecycle_status,
                "superseded",
            )

        with self.assertRaises(ConcurrencyConflictError):
            with UnitOfWork(self.database) as uow:
                uow.judgment_decision.accept_disposition_proposal(
                    accepted_proposal=proposal(
                        "dpv_2",
                        version=2,
                        previous_version_id="dpv_1",
                        status="accepted",
                        revision=2,
                    ),
                    disposition=disposition(),
                    expected_proposal_revision=9,
                    expected_case_revision=4,
                    case_updated_at=NOW + timedelta(minutes=10),
                )

        with UnitOfWork(self.database) as uow:
            accepted = uow.judgment_decision.accept_disposition_proposal(
                accepted_proposal=proposal(
                    "dpv_2",
                    version=2,
                    previous_version_id="dpv_1",
                    status="accepted",
                    revision=2,
                ),
                disposition=disposition(),
                expected_proposal_revision=1,
                expected_case_revision=4,
                case_updated_at=NOW + timedelta(minutes=10),
            )
            self.assertEqual(accepted.disposition_type, "knowledge_only_closure")

        with UnitOfWork(self.database, write=False) as uow:
            case = uow.case_scope.get_case("case_1")
            proposal_after = uow.judgment_decision.get_current_disposition_proposal("dp_1")
            disposition_after = uow.judgment_decision.get_research_disposition("disp_1")
            self.assertEqual(case.current_research_disposition_id, "disp_1")
            self.assertEqual(case.revision, 5)
            self.assertEqual(proposal_after.user_decision_status, "accepted")
            self.assertEqual(disposition_after.source_disposition_proposal_version_id, "dpv_2")


if __name__ == "__main__":
    unittest.main()
