from __future__ import annotations

import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

from metaos.core_alpha.commands import ApplicationCommandHandler
from metaos.core_alpha.contracts.common import CommandContext, OpenCodeValue
from metaos.core_alpha.contracts.decision import (
    AcceptDispositionProposalRequest,
    AdjustDispositionProposalRequest,
    RejectDispositionProposalRequest,
)
from metaos.core_alpha.contracts.judgment import AcknowledgeAuditFindingRequest, SupportStrength
from metaos.core_alpha.judgment_audit import (
    AuditFindingCandidate,
    JudgmentAuditCommandHandler,
    RunJudgmentAuditRequest,
)
from metaos.core_alpha.judgment_domain import (
    CandidateEvidenceLink,
    ClaimCandidate,
    CreateJudgmentDraftRequest,
    JudgmentDomainCommandHandler,
)
from metaos.core_alpha.persistence import ConcurrencyConflictError, CoreAlphaDatabase, UnitOfWork
from metaos.core_alpha.research_disposition import (
    CreateDispositionProposalRequest,
    ResearchDispositionCommandHandler,
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


TEST_NOW = datetime(2026, 6, 25, 14, 0, tzinfo=timezone.utc)


def context(command_id: str, *, idempotency_key: str) -> CommandContext:
    return CommandContext(
        command_id=command_id,
        actor_type=OpenCodeValue(code="user", registry_version="core-alpha-v1"),
        actor_id="user_1",
        idempotency_key=idempotency_key,
        correlation_id="corr_1",
        causation_id="cause_1",
        trace_id="trace_1",
    )


class FixedClock:
    def __init__(self) -> None:
        self.offset = 0

    def __call__(self) -> datetime:
        value = TEST_NOW + timedelta(minutes=self.offset)
        self.offset += 1
        return value


class ResearchDispositionTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.database = CoreAlphaDatabase(Path(self.temp_dir.name) / "core-alpha.db")
        self.database.initialize()
        self.clock = FixedClock()
        app = ApplicationCommandHandler(self.database)
        self.judgment_commands = JudgmentDomainCommandHandler(app, clock=self.clock)
        self.audit_commands = JudgmentAuditCommandHandler(app, clock=self.clock)
        self.disposition_commands = ResearchDispositionCommandHandler(app, clock=self.clock)
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

    def direct_link(self) -> CandidateEvidenceLink:
        return CandidateEvidenceLink(
            research_evidence_use_id="reu_1",
            evidence_role="supports",
            support_strength=SupportStrength(level="strong", reason="Direct source match."),
            scope_note="Within required source.",
        )

    def create_judgment(
        self,
        *,
        evidence_status: str = "supported",
        key_suffix: str = "base",
    ) -> dict:
        draft = self.judgment_commands.create_judgment_draft(
            "run_1",
            CreateJudgmentDraftRequest(
                expected_run_revision=1,
                summary="A draft judgment assembled from retrieved evidence.",
                uncertainties=["Only one source version was checked."],
                evidence_gaps=[],
                claims=[
                    ClaimCandidate(
                        claim_text="The selected passage supports the narrow factual claim.",
                        epistemic_type="fact",
                        expression_role="core_judgment",
                        evidence_status=evidence_status,
                        importance="core",
                        confidence_level=(
                            "medium"
                            if evidence_status in {"partially_supported", "mixed"}
                            else "high"
                        ),
                        rationale_profile={
                            "profile_type": "fact",
                            "source_summary": "The selected source contains the statement.",
                            "location_summary": "chapter_1 page 1 offsets 10-40.",
                            "fact_mapping": "The sentence directly maps to the claim.",
                            "version_limitations": ["Only the selected version is covered."],
                        },
                        reasoning_summary="Direct fact mapping.",
                        evidence_links=[self.direct_link()],
                    )
                ],
            ),
            context=context(
                f"cmd_judgment_{key_suffix}",
                idempotency_key=f"idem_judgment_{key_suffix}",
            ),
        )
        return dict(draft.response_body["data"]["judgment_card"])

    def audit_judgment(
        self,
        judgment: dict,
        *,
        semantic_findings: list[AuditFindingCandidate] | None = None,
        key_suffix: str = "audit",
    ) -> dict:
        response = self.audit_commands.run_audit(
            judgment["judgment_card_version_id"],
            RunJudgmentAuditRequest(
                expected_judgment_revision=judgment["revision"],
                semantic_findings=semantic_findings or [],
            ),
            context=context(
                f"cmd_audit_{key_suffix}",
                idempotency_key=f"idem_audit_{key_suffix}",
            ),
        )
        return dict(response.response_body["data"])

    def create_acceptable_judgment(self, *, key_suffix: str = "acceptable") -> dict:
        judgment = self.create_judgment(key_suffix=key_suffix)
        return self.audit_judgment(judgment, key_suffix=key_suffix)

    def test_create_then_accept_disposition_is_user_confirmed_and_idempotent(self) -> None:
        audited = self.create_acceptable_judgment(key_suffix="accept")
        judgment = audited["judgment_card"]
        fitness = audited["decision_fitness"]

        proposal_response = self.disposition_commands.create_disposition_proposal(
            judgment["judgment_card_version_id"],
            CreateDispositionProposalRequest(
                expected_judgment_revision=judgment["revision"],
                proposed_disposition_type="knowledge_only_closure",
                reason="Understanding is enough for now.",
            ),
            context=context("cmd_create_proposal", idempotency_key="idem_create_proposal"),
        )
        self.assertEqual(proposal_response.status_code, 201)
        proposal = proposal_response.response_body["data"]["disposition_proposal"]
        self.assertEqual(proposal["user_decision_status"], "pending")
        with UnitOfWork(self.database, write=False) as uow:
            self.assertIsNone(uow.case_scope.get_case("case_1").current_research_disposition_id)

        accept_request = AcceptDispositionProposalRequest(
            expected_revision=proposal["revision"],
            judgment_card_version_id=judgment["judgment_card_version_id"],
            decision_fitness_id=fitness["decision_fitness_id"],
            warning_acknowledgement_ids=[],
        )
        first = self.disposition_commands.accept_disposition_proposal(
            proposal["disposition_proposal_version_id"],
            accept_request,
            context=context("cmd_accept_proposal_1", idempotency_key="idem_accept_proposal"),
        )
        replay = self.disposition_commands.accept_disposition_proposal(
            proposal["disposition_proposal_version_id"],
            accept_request,
            context=context("cmd_accept_proposal_2", idempotency_key="idem_accept_proposal"),
        )
        self.assertFalse(first.response_body["command"]["idempotent_replay"])
        self.assertTrue(replay.response_body["command"]["idempotent_replay"])
        self.assertEqual(first.response_body["data"], replay.response_body["data"])

        data = first.response_body["data"]
        self.assertEqual(data["disposition_proposal"]["user_decision_status"], "accepted")
        self.assertEqual(data["research_disposition"]["disposition_type"], "knowledge_only_closure")
        self.assertEqual(
            data["research_case"]["current_research_disposition_id"],
            data["research_disposition"]["research_disposition_id"],
        )

    def test_blocked_judgment_cannot_create_disposition_proposal(self) -> None:
        judgment = self.create_judgment(evidence_status="insufficient", key_suffix="blocked")
        audited = self.audit_judgment(judgment, key_suffix="blocked")
        self.assertEqual(audited["judgment_card"]["audit_status"], "blocked")

        with self.assertRaises(ValueError):
            self.disposition_commands.create_disposition_proposal(
                audited["judgment_card"]["judgment_card_version_id"],
                CreateDispositionProposalRequest(
                    expected_judgment_revision=audited["judgment_card"]["revision"],
                    proposed_disposition_type="knowledge_only_closure",
                    reason="Should fail.",
                ),
                context=context("cmd_create_blocked_proposal", idempotency_key="idem_create_blocked_proposal"),
            )

    def test_provisional_judgment_requires_warning_acknowledgement_before_proposal(self) -> None:
        judgment = self.create_judgment(key_suffix="warning")
        warning = AuditFindingCandidate(
            affected_claim_version_ids=judgment["claim_version_ids"],
            finding_type=code("citation_quality"),
            severity="warning",
            description="Citation quality is constrained.",
            supporting_reason="Semantic audit found a non-blocking limitation.",
            recommended_revision="Keep limitation visible.",
        )
        audited = self.audit_judgment(
            judgment,
            semantic_findings=[warning],
            key_suffix="warning",
        )
        updated = audited["judgment_card"]
        finding = audited["audit_findings"][0]
        self.assertEqual(updated["audit_status"], "provisionally_acceptable")

        with self.assertRaises(ValueError):
            self.disposition_commands.create_disposition_proposal(
                updated["judgment_card_version_id"],
                CreateDispositionProposalRequest(
                    expected_judgment_revision=updated["revision"],
                    proposed_disposition_type="knowledge_only_closure",
                    reason="Warnings must be acknowledged first.",
                ),
                context=context("cmd_create_without_ack", idempotency_key="idem_create_without_ack"),
            )

        ack = self.audit_commands.acknowledge_warning(
            finding["audit_finding_id"],
            AcknowledgeAuditFindingRequest(
                expected_revision=updated["revision"],
                judgment_card_version_id=updated["judgment_card_version_id"],
                acknowledgement_note="Accepted under limitation.",
            ),
            context=context("cmd_ack_for_disposition", idempotency_key="idem_ack_for_disposition"),
        ).response_body["data"]["warning_acknowledgement"]
        proposal = self.disposition_commands.create_disposition_proposal(
            updated["judgment_card_version_id"],
            CreateDispositionProposalRequest(
                expected_judgment_revision=updated["revision"],
                proposed_disposition_type="knowledge_only_closure",
                reason="Close with acknowledged warning.",
                warning_acknowledgement_ids=[ack["warning_acknowledgement_id"]],
            ),
            context=context("cmd_create_with_ack", idempotency_key="idem_create_with_ack"),
        ).response_body["data"]["disposition_proposal"]
        self.assertEqual(
            proposal["warning_acknowledgement_ids"],
            [ack["warning_acknowledgement_id"]],
        )

    def test_adjust_and_reject_proposal_do_not_create_disposition(self) -> None:
        audited = self.create_acceptable_judgment(key_suffix="adjust")
        judgment = audited["judgment_card"]
        proposal = self.disposition_commands.create_disposition_proposal(
            judgment["judgment_card_version_id"],
            CreateDispositionProposalRequest(
                expected_judgment_revision=judgment["revision"],
                proposed_disposition_type="knowledge_only_closure",
                reason="Initial closure.",
            ),
            context=context("cmd_create_adjustable", idempotency_key="idem_create_adjustable"),
        ).response_body["data"]["disposition_proposal"]

        adjusted = self.disposition_commands.adjust_disposition_proposal(
            proposal["disposition_proposal_version_id"],
            AdjustDispositionProposalRequest(
                expected_revision=proposal["revision"],
                proposed_disposition_type="observe",
                reason="Observe for new evidence.",
                observation_condition="New cited source appears.",
            ),
            context=context("cmd_adjust_proposal", idempotency_key="idem_adjust_proposal"),
        ).response_body["data"]

        new_proposal = adjusted["disposition_proposal"]
        self.assertEqual(new_proposal["version"], 2)
        self.assertEqual(new_proposal["user_decision_status"], "adjusted")
        self.assertEqual(
            adjusted["superseded_version_ref"]["resource_id"],
            proposal["disposition_proposal_version_id"],
        )
        rejected = self.disposition_commands.reject_disposition_proposal(
            new_proposal["disposition_proposal_version_id"],
            RejectDispositionProposalRequest(expected_revision=new_proposal["revision"]),
            context=context("cmd_reject_proposal", idempotency_key="idem_reject_proposal"),
        ).response_body["data"]["disposition_proposal"]
        self.assertEqual(rejected["user_decision_status"], "rejected")
        self.assertEqual(rejected["lifecycle_status"], "withdrawn")
        with UnitOfWork(self.database, write=False) as uow:
            case = uow.case_scope.get_case("case_1")
            old = uow.judgment_decision.get_disposition_proposal_version(
                proposal["disposition_proposal_version_id"],
            )
            self.assertIsNone(case.current_research_disposition_id)
            self.assertEqual(old.lifecycle_status.value, "superseded")

    def test_decision_fitness_rejects_use_escalation_and_stale_revision(self) -> None:
        audited = self.create_acceptable_judgment(key_suffix="fitness")
        judgment = audited["judgment_card"]
        with self.assertRaises(ValueError):
            self.disposition_commands.create_disposition_proposal(
                judgment["judgment_card_version_id"],
                CreateDispositionProposalRequest(
                    expected_judgment_revision=judgment["revision"],
                    proposed_disposition_type="proceed_to_action",
                    reason="Default fitness does not allow action.",
                ),
                context=context("cmd_create_action_escalation", idempotency_key="idem_create_action_escalation"),
            )
        with self.assertRaises(ConcurrencyConflictError):
            self.disposition_commands.create_disposition_proposal(
                judgment["judgment_card_version_id"],
                CreateDispositionProposalRequest(
                    expected_judgment_revision=1,
                    proposed_disposition_type="knowledge_only_closure",
                    reason="Stale judgment revision.",
                ),
                context=context("cmd_create_stale_proposal", idempotency_key="idem_create_stale_proposal"),
            )


if __name__ == "__main__":
    unittest.main()
