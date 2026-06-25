from __future__ import annotations

import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

from metaos.core_alpha.commands import ApplicationCommandHandler
from metaos.core_alpha.contracts.common import CommandContext, OpenCodeValue
from metaos.core_alpha.contracts.judgment import (
    AcknowledgeAuditFindingRequest,
    SupportStrength,
)
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


TEST_NOW = datetime(2026, 6, 25, 13, 0, tzinfo=timezone.utc)


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


class JudgmentAuditTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.database = CoreAlphaDatabase(Path(self.temp_dir.name) / "core-alpha.db")
        self.database.initialize()
        self.clock = FixedClock()
        app = ApplicationCommandHandler(self.database)
        self.judgment_commands = JudgmentDomainCommandHandler(app, clock=self.clock)
        self.audit_commands = JudgmentAuditCommandHandler(app, clock=self.clock)
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

    def fact_candidate(
        self,
        *,
        evidence_status: str = "supported",
        confidence_level: str = "high",
    ) -> ClaimCandidate:
        return ClaimCandidate(
            claim_text="The selected passage supports the narrow factual claim.",
            epistemic_type="fact",
            expression_role="core_judgment",
            evidence_status=evidence_status,
            importance="core",
            confidence_level=confidence_level,
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

    def create_draft(
        self,
        *,
        evidence_status: str = "supported",
        key_suffix: str = "draft",
    ) -> dict:
        response = self.judgment_commands.create_judgment_draft(
            "run_1",
            CreateJudgmentDraftRequest(
                expected_run_revision=1,
                summary="A draft judgment assembled from retrieved evidence.",
                uncertainties=["Only one source version was checked."],
                evidence_gaps=[],
                claims=[
                    self.fact_candidate(
                        evidence_status=evidence_status,
                        confidence_level=(
                            "medium"
                            if evidence_status in {"partially_supported", "mixed"}
                            else "high"
                        ),
                    )
                ],
            ),
            context=context(
                f"cmd_judgment_{key_suffix}",
                idempotency_key=f"idem_judgment_{key_suffix}",
            ),
        )
        return dict(response.response_body["data"]["judgment_card"])

    def run_audit(
        self,
        judgment_version_id: str,
        *,
        expected_revision: int = 1,
        semantic_findings: list[AuditFindingCandidate] | None = None,
        key_suffix: str = "audit",
    ) -> dict:
        response = self.audit_commands.run_audit(
            judgment_version_id,
            RunJudgmentAuditRequest(
                expected_judgment_revision=expected_revision,
                semantic_findings=semantic_findings or [],
            ),
            context=context(
                f"cmd_audit_{key_suffix}",
                idempotency_key=f"idem_audit_{key_suffix}",
            ),
        )
        self.assertEqual(response.status_code, 200)
        return dict(response.response_body["data"])

    def test_valid_judgment_becomes_acceptable_with_decision_fitness(self) -> None:
        judgment = self.create_draft(key_suffix="acceptable")

        data = self.run_audit(
            judgment["judgment_card_version_id"],
            key_suffix="acceptable",
        )

        updated = data["judgment_card"]
        self.assertEqual(data["judgment_audit"]["gate_result"], "acceptable")
        self.assertEqual(updated["audit_status"], "acceptable")
        self.assertEqual(updated["revision"], 2)
        self.assertIsNotNone(updated["decision_fitness_id"])
        self.assertEqual(data["decision_fitness"]["policy_version"], "fitness-v1")
        self.assertIn("understanding", data["decision_fitness"]["allowed_uses"])
        self.assertIn("reversible_action", data["decision_fitness"]["forbidden_uses"])
        self.assertEqual(data["audit_findings"], [])

    def test_warning_finding_produces_provisional_and_can_be_acknowledged(self) -> None:
        judgment = self.create_draft(key_suffix="warning")
        warning = AuditFindingCandidate(
            affected_claim_version_ids=judgment["claim_version_ids"],
            finding_type=code("citation_quality"),
            severity="warning",
            description="Citation is acceptable only under constrained use.",
            supporting_reason="Semantic audit candidate found an uncertainty.",
            recommended_revision="Keep the limitation visible.",
        )

        data = self.run_audit(
            judgment["judgment_card_version_id"],
            semantic_findings=[warning],
            key_suffix="warning",
        )
        updated = data["judgment_card"]
        finding = data["audit_findings"][0]
        self.assertEqual(updated["audit_status"], "provisionally_acceptable")
        self.assertEqual(data["judgment_audit"]["gate_result"], "provisionally_acceptable")
        self.assertEqual(finding["severity"], "warning")
        self.assertIsNotNone(data["decision_fitness"])

        ack = self.audit_commands.acknowledge_warning(
            finding["audit_finding_id"],
            AcknowledgeAuditFindingRequest(
                expected_revision=updated["revision"],
                judgment_card_version_id=updated["judgment_card_version_id"],
                acknowledgement_note="Accepted with caution.",
            ),
            context=context("cmd_ack_warning", idempotency_key="idem_ack_warning"),
        )
        payload = ack.response_body["data"]
        self.assertEqual(payload["warning_acknowledgement"]["audit_finding_id"], finding["audit_finding_id"])
        self.assertEqual(payload["judgment_card"]["audit_status"], "provisionally_acceptable")

    def test_blocking_finding_blocks_without_decision_fitness_and_cannot_be_acknowledged(self) -> None:
        judgment = self.create_draft(key_suffix="blocking")
        blocking = AuditFindingCandidate(
            affected_claim_version_ids=judgment["claim_version_ids"],
            finding_type=code("unsupported_causal_jump"),
            severity="blocking",
            description="The claim overstates causality.",
            supporting_reason="Evidence supports sequence, not causation.",
        )

        data = self.run_audit(
            judgment["judgment_card_version_id"],
            semantic_findings=[blocking],
            key_suffix="blocking",
        )

        updated = data["judgment_card"]
        finding = data["audit_findings"][0]
        self.assertEqual(updated["audit_status"], "blocked")
        self.assertIsNone(updated["decision_fitness_id"])
        self.assertIsNone(data["decision_fitness"])
        with self.assertRaises(ValueError):
            self.audit_commands.acknowledge_warning(
                finding["audit_finding_id"],
                AcknowledgeAuditFindingRequest(
                    expected_revision=updated["revision"],
                    judgment_card_version_id=updated["judgment_card_version_id"],
                    acknowledgement_note=None,
                ),
                context=context("cmd_ack_blocking", idempotency_key="idem_ack_blocking"),
            )

    def test_deterministic_gate_blocks_unsupported_core_claim(self) -> None:
        judgment = self.create_draft(
            evidence_status="insufficient",
            key_suffix="unsupported",
        )

        data = self.run_audit(
            judgment["judgment_card_version_id"],
            key_suffix="unsupported",
        )

        self.assertEqual(data["judgment_card"]["audit_status"], "blocked")
        self.assertEqual(data["judgment_audit"]["gate_result"], "blocked")
        self.assertIn(
            "unsupported_core_claim",
            {finding["finding_type"]["code"] for finding in data["audit_findings"]},
        )
        self.assertIsNone(data["decision_fitness"])

    def test_audit_is_idempotent_and_rejects_stale_revision(self) -> None:
        judgment = self.create_draft(key_suffix="idempotent")
        request = RunJudgmentAuditRequest(expected_judgment_revision=1)

        first = self.audit_commands.run_audit(
            judgment["judgment_card_version_id"],
            request,
            context=context("cmd_audit_once_1", idempotency_key="idem_audit_once"),
        )
        replay = self.audit_commands.run_audit(
            judgment["judgment_card_version_id"],
            request,
            context=context("cmd_audit_once_2", idempotency_key="idem_audit_once"),
        )
        self.assertFalse(first.response_body["command"]["idempotent_replay"])
        self.assertTrue(replay.response_body["command"]["idempotent_replay"])
        self.assertEqual(first.response_body["data"], replay.response_body["data"])

        with self.assertRaises(ConcurrencyConflictError):
            self.audit_commands.run_audit(
                judgment["judgment_card_version_id"],
                RunJudgmentAuditRequest(expected_judgment_revision=1),
                context=context("cmd_audit_stale", idempotency_key="idem_audit_stale"),
            )


if __name__ == "__main__":
    unittest.main()
