from __future__ import annotations

import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

from fastapi import FastAPI
from fastapi.testclient import TestClient

from metaos.core_alpha.api_judgment import create_judgment_api_router
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
from metaos.core_alpha.persistence import CoreAlphaDatabase, UnitOfWork
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


class CoreAlphaJudgmentApiTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.database = CoreAlphaDatabase(Path(self.temp_dir.name) / "core-alpha.db")
        self.database.initialize()
        self.clock = FixedClock()
        self.app = FastAPI()
        self.app.include_router(create_judgment_api_router(database=self.database))
        self.client = TestClient(self.app)

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def post(self, url: str, payload: dict, *, idem: str) -> TestClient:
        return self.client.post(
            url,
            json=payload,
            headers={
                "Idempotency-Key": idem,
                "X-Actor-Id": "user_1",
                "X-Trace-Id": f"trace_{idem}",
            },
        )

    def seed_case_scope_plan(self) -> None:
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

    def seed_run_and_evidence(self) -> None:
        self.seed_case_scope_plan()
        with UnitOfWork(self.database) as uow:
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

    def fact_candidate(self, *, evidence_status: str = "supported") -> ClaimCandidate:
        return ClaimCandidate(
            claim_text="The selected passage supports the narrow factual claim.",
            epistemic_type="fact",
            expression_role="core_judgment",
            evidence_status=evidence_status,
            importance="core",
            confidence_level="high" if evidence_status == "supported" else "medium",
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

    def create_judgment(self, *, evidence_status: str = "supported") -> dict:
        command = JudgmentDomainCommandHandler(
            ApplicationCommandHandler(self.database),
            clock=self.clock,
        )
        response = command.create_judgment_draft(
            "run_1",
            CreateJudgmentDraftRequest(
                expected_run_revision=1,
                summary="A draft judgment assembled from retrieved evidence.",
                uncertainties=["Only one source version was checked."],
                evidence_gaps=[],
                claims=[self.fact_candidate(evidence_status=evidence_status)],
            ),
            context=context(
                f"cmd_judgment_{evidence_status}",
                idempotency_key=f"idem_judgment_{evidence_status}",
            ),
        )
        return dict(response.response_body["data"]["judgment_card"])

    def run_audit(
        self,
        judgment: dict,
        *,
        warning: bool = False,
        blocking: bool = False,
    ) -> dict:
        command = JudgmentAuditCommandHandler(
            ApplicationCommandHandler(self.database),
            clock=self.clock,
        )
        semantic_findings: list[AuditFindingCandidate] = []
        if warning:
            semantic_findings.append(
                AuditFindingCandidate(
                    affected_claim_version_ids=judgment["claim_version_ids"],
                    finding_type=code("citation_quality"),
                    severity="warning",
                    description="Citation is acceptable only under constrained use.",
                    supporting_reason="Semantic audit found a visible limitation.",
                    recommended_revision="Keep the limitation visible.",
                )
            )
        if blocking:
            semantic_findings.append(
                AuditFindingCandidate(
                    affected_claim_version_ids=judgment["claim_version_ids"],
                    finding_type=code("unsupported_causal_jump"),
                    severity="blocking",
                    description="The claim overstates causality.",
                    supporting_reason="Evidence supports sequence, not causation.",
                )
            )
        response = command.run_audit(
            judgment["judgment_card_version_id"],
            RunJudgmentAuditRequest(
                expected_judgment_revision=judgment["revision"],
                semantic_findings=semantic_findings,
            ),
            context=context(
                f"cmd_audit_{warning}_{blocking}",
                idempotency_key=f"idem_audit_{warning}_{blocking}",
            ),
        )
        return dict(response.response_body["data"])

    def test_start_run_cancel_outcome_attempts_and_trace_routes(self) -> None:
        self.seed_case_scope_plan()

        response = self.post(
            "/alpha/research-cases/case_1/research-runs",
            {
                "expected_research_case_revision": 4,
                "research_question_id": "rq_1",
                "knowledge_scope_version_id": "ksv_1",
                "research_plan_version_id": "rpv_1",
                "execution_mode": "synchronous",
            },
            idem="idem_start_run",
        )
        self.assertEqual(response.status_code, 201)
        payload = response.json()
        self.assertEqual(set(payload["data"]), {"research_run", "research_run_outcome", "judgment_card"})
        run_id = payload["data"]["research_run"]["research_run_id"]

        attempts = self.client.get(f"/alpha/research-runs/{run_id}/attempts")
        self.assertEqual(attempts.status_code, 200)
        attempt_id = attempts.json()["data"][0]["research_attempt_id"]
        self.assertEqual(
            self.client.get(f"/alpha/research-attempts/{attempt_id}/retrieval-runs").json()["data"],
            [],
        )
        self.assertIsNone(self.client.get(f"/alpha/research-runs/{run_id}/outcome").json()["data"])

        cancelled = self.post(
            f"/alpha/research-runs/{run_id}/commands/cancel",
            {"expected_revision": 1, "reason": "User stopped the run."},
            idem="idem_cancel_run",
        )
        self.assertEqual(cancelled.status_code, 200)
        outcome = self.client.get(f"/alpha/research-runs/{run_id}/outcome").json()["data"]
        self.assertEqual(outcome["outcome_type"], "cancelled_by_user")
        trace = self.client.get(f"/alpha/research-runs/{run_id}/trace").json()["data"]
        self.assertEqual(trace["research_run"]["research_run_id"], run_id)

    def test_evidence_judgment_claim_audit_and_decision_fitness_routes(self) -> None:
        self.seed_run_and_evidence()
        judgment = self.create_judgment()
        audit = self.run_audit(judgment)
        updated_judgment = audit["judgment_card"]
        claim_id = updated_judgment["claim_version_ids"][0]

        evidence = self.client.get("/alpha/evidence-units/eu_1")
        self.assertEqual(evidence.status_code, 200)
        self.assertEqual(evidence.json()["data"]["evidence_unit_id"], "eu_1")
        evidence_use = self.client.get("/alpha/research-evidence-uses/reu_1")
        self.assertEqual(evidence_use.json()["data"]["research_evidence_use_id"], "reu_1")
        self.assertEqual(
            self.client.get("/alpha/research-runs/run_1/evidence-uses").json()["data"][0]["research_evidence_use_id"],
            "reu_1",
        )

        current_judgment = self.client.get("/alpha/research-cases/case_1/judgment-cards/current")
        self.assertEqual(
            current_judgment.json()["data"]["judgment_card_version_id"],
            updated_judgment["judgment_card_version_id"],
        )
        claims = self.client.get(
            f"/alpha/judgment-card-versions/{updated_judgment['judgment_card_version_id']}/claims"
        ).json()["data"]["claims"]
        claim = claims[0]["claim"]
        self.assertEqual(claim["claim_version_id"], claim_id)
        self.assertEqual(claims[0]["evidence_links"][0]["research_evidence_use_id"], "reu_1")
        self.assertEqual(claims[0]["rationale"]["rationale_profile"]["profile_type"], "fact")

        current_claim = self.client.get(f"/alpha/claims/{claim['claim_id']}/current")
        self.assertEqual(current_claim.json()["data"]["claim_version_id"], claim_id)
        claim_version = self.client.get(f"/alpha/claim-versions/{claim_id}")
        self.assertEqual(claim_version.json()["data"]["evidence_status"], "supported")

        audits = self.client.get(
            f"/alpha/judgment-card-versions/{updated_judgment['judgment_card_version_id']}/audits"
        )
        self.assertEqual(audits.json()["data"][0]["judgment_audit_id"], audit["judgment_audit"]["judgment_audit_id"])
        audit_detail = self.client.get(
            f"/alpha/judgment-audits/{audit['judgment_audit']['judgment_audit_id']}"
        )
        self.assertEqual(audit_detail.json()["data"]["audit_findings"], [])

        fitness_id = updated_judgment["decision_fitness_id"]
        current_fitness = self.client.get(
            f"/alpha/judgment-card-versions/{updated_judgment['judgment_card_version_id']}/decision-fitness/current"
        )
        self.assertEqual(current_fitness.json()["data"]["decision_fitness_id"], fitness_id)
        fitness = self.client.get(f"/alpha/decision-fitness/{fitness_id}")
        self.assertIn("understanding", fitness.json()["data"]["allowed_uses"])

        attitude = self.post(
            f"/alpha/claim-versions/{claim_id}/commands/set-user-attitude",
            {"expected_revision": 1, "user_attitude": "accepted"},
            idem="idem_claim_attitude",
        )
        self.assertEqual(attitude.status_code, 200)
        self.assertEqual(attitude.json()["data"]["claim"]["user_attitude"], "accepted")
        self.assertEqual(attitude.json()["data"]["claim"]["evidence_status"], "supported")

    def test_warning_acknowledge_and_blocking_acknowledge_errors(self) -> None:
        self.seed_run_and_evidence()
        warning_judgment = self.create_judgment(evidence_status="partially_supported")
        warning_audit = self.run_audit(warning_judgment, warning=True)
        warning_finding = warning_audit["audit_findings"][0]
        warning_ack = self.post(
            f"/alpha/audit-findings/{warning_finding['audit_finding_id']}/commands/acknowledge",
            {
                "expected_revision": warning_audit["judgment_card"]["revision"],
                "judgment_card_version_id": warning_audit["judgment_card"]["judgment_card_version_id"],
                "acknowledgement_note": "Accepted with caution.",
            },
            idem="idem_warning_ack",
        )
        self.assertEqual(warning_ack.status_code, 200)
        self.assertEqual(
            warning_ack.json()["data"]["warning_acknowledgement"]["audit_finding_id"],
            warning_finding["audit_finding_id"],
        )

        blocking_judgment = self.create_judgment(evidence_status="supported")
        blocking_audit = self.run_audit(blocking_judgment, blocking=True)
        blocking_finding = blocking_audit["audit_findings"][0]
        blocking_ack = self.post(
            f"/alpha/audit-findings/{blocking_finding['audit_finding_id']}/commands/acknowledge",
            {
                "expected_revision": blocking_audit["judgment_card"]["revision"],
                "judgment_card_version_id": blocking_audit["judgment_card"]["judgment_card_version_id"],
                "acknowledgement_note": "Try to override.",
            },
            idem="idem_blocking_ack",
        )
        self.assertEqual(blocking_ack.status_code, 409)
        self.assertEqual(blocking_ack.json()["error"]["code"], "lifecycle_conflict")


if __name__ == "__main__":
    unittest.main()
