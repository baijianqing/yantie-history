from __future__ import annotations

import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from fastapi import FastAPI
from fastapi.testclient import TestClient

from metaos.core_alpha.api_decision import create_decision_api_router
from metaos.core_alpha.commands import ApplicationCommandHandler
from metaos.core_alpha.contracts.common import CommandContext, OpenCodeValue
from metaos.core_alpha.contracts.judgment import SupportStrength
from metaos.core_alpha.judgment_audit import JudgmentAuditCommandHandler, RunJudgmentAuditRequest
from metaos.core_alpha.judgment_domain import (
    CandidateEvidenceLink,
    ClaimCandidate,
    CreateJudgmentDraftRequest,
    JudgmentDomainCommandHandler,
)
from metaos.core_alpha.persistence import CoreAlphaDatabase, UnitOfWork
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


def context(command_id: str, *, idempotency_key: str, actor: str = "user") -> CommandContext:
    return CommandContext(
        command_id=command_id,
        actor_type=OpenCodeValue(code=actor, registry_version="core-alpha-v1"),
        actor_id="user_1" if actor == "user" else "worker_1",
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


class CoreAlphaDecisionApiTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.database = CoreAlphaDatabase(Path(self.temp_dir.name) / "core-alpha.db")
        self.database.initialize()
        self.clock = FixedClock()
        self.app = FastAPI()
        self.app.include_router(create_decision_api_router(database=self.database))
        self.client = TestClient(self.app)

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def post(self, url: str, payload: dict[str, Any], *, idem: str) -> Any:
        return self.client.post(
            url,
            json=payload,
            headers={
                "Idempotency-Key": idem,
                "X-Actor-Id": "user_1",
                "X-Trace-Id": f"trace_{idem}",
            },
        )

    def internal_post(
        self,
        payload: dict[str, Any],
        *,
        idem: str,
        service_actor_id: str | None = "worker_1",
    ) -> Any:
        headers = {
            "Idempotency-Key": idem,
            "X-Trace-Id": f"trace_{idem}",
        }
        if service_actor_id is not None:
            headers["X-Service-Actor-Id"] = service_actor_id
        return self.client.post(
            "/internal/alpha/candidate-results",
            json=payload,
            headers=headers,
        )

    def seed_run_and_evidence(self, *, lifecycle: bool = False) -> None:
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
            if lifecycle:
                uow.lifecycle.ensure("research_run", "run_1", now=NOW)

    def direct_link(self) -> CandidateEvidenceLink:
        return CandidateEvidenceLink(
            research_evidence_use_id="reu_1",
            evidence_role="supports",
            support_strength=SupportStrength(level="strong", reason="Direct source match."),
            scope_note="Within required source.",
        )

    def create_acceptable_judgment(self, *, key_suffix: str) -> dict[str, Any]:
        judgment_response = JudgmentDomainCommandHandler(
            ApplicationCommandHandler(self.database),
            clock=self.clock,
        ).create_judgment_draft(
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
                        evidence_status="supported",
                        importance="core",
                        confidence_level="high",
                        rationale_profile={
                            "profile_type": "fact",
                            "source_summary": "The selected source contains the statement.",
                            "location_summary": "chapter_1 page 1 offsets 10-40.",
                            "fact_mapping": "The sentence directly maps to the claim.",
                            "version_limitations": [
                                "Only the selected version is covered.",
                            ],
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
        judgment = judgment_response.response_body["data"]["judgment_card"]
        audit_response = JudgmentAuditCommandHandler(
            ApplicationCommandHandler(self.database),
            clock=self.clock,
        ).run_audit(
            judgment["judgment_card_version_id"],
            RunJudgmentAuditRequest(
                expected_judgment_revision=judgment["revision"],
                semantic_findings=[],
            ),
            context=context(
                f"cmd_audit_{key_suffix}",
                idempotency_key=f"idem_audit_{key_suffix}",
            ),
        )
        return dict(audit_response.response_body["data"])

    def create_proposal(self, *, key_suffix: str, disposition_type: str) -> dict[str, Any]:
        audited = self.create_acceptable_judgment(key_suffix=key_suffix)
        judgment = audited["judgment_card"]
        response = ResearchDispositionCommandHandler(
            ApplicationCommandHandler(self.database),
            clock=self.clock,
        ).create_disposition_proposal(
            judgment["judgment_card_version_id"],
            CreateDispositionProposalRequest(
                expected_judgment_revision=judgment["revision"],
                proposed_disposition_type=disposition_type,
                reason="Close the research loop with a user decision.",
            ),
            context=context(
                f"cmd_create_proposal_{key_suffix}",
                idempotency_key=f"idem_create_proposal_{key_suffix}",
            ),
        )
        return {
            "proposal": response.response_body["data"]["disposition_proposal"],
            "judgment": judgment,
            "fitness": audited["decision_fitness"],
        }

    def candidate_payload(self) -> dict[str, Any]:
        return {
            "operation_type": code("draft_judgment").model_dump(mode="json"),
            "research_run_id": "run_1",
            "research_attempt_id": "attempt_1",
            "run_execution_spec_id": "spec_1",
            "input_versions": {
                "research_run_revision": 1,
                "knowledge_scope_version_id": "ksv_1",
                "research_plan_version_id": "rpv_1",
            },
            "lifecycle_generation": 1,
            "capability_implementation_version": "impl-v1",
            "output_schema_version": "candidate-schema-v1",
            "candidate_result": {"claim": "candidate"},
        }

    def test_query_accept_and_replay_disposition_proposal(self) -> None:
        self.seed_run_and_evidence()
        seeded = self.create_proposal(
            key_suffix="accept",
            disposition_type="knowledge_only_closure",
        )
        proposal = seeded["proposal"]

        proposals = self.client.get("/alpha/research-cases/case_1/disposition-proposals")
        self.assertEqual(proposals.status_code, 200)
        self.assertEqual(
            proposals.json()["data"][0]["disposition_proposal_version_id"],
            proposal["disposition_proposal_version_id"],
        )

        current = self.client.get(
            f"/alpha/disposition-proposals/{proposal['disposition_proposal_id']}/current"
        )
        self.assertEqual(current.status_code, 200)
        self.assertEqual(current.json()["data"], proposal)

        version = self.client.get(
            f"/alpha/disposition-proposal-versions/{proposal['disposition_proposal_version_id']}"
        )
        self.assertEqual(version.status_code, 200)
        self.assertEqual(version.json()["data"]["user_decision_status"], "pending")

        accept_payload = {
            "expected_revision": proposal["revision"],
            "judgment_card_version_id": seeded["judgment"]["judgment_card_version_id"],
            "decision_fitness_id": seeded["fitness"]["decision_fitness_id"],
            "warning_acknowledgement_ids": [],
        }
        first = self.post(
            f"/alpha/disposition-proposal-versions/{proposal['disposition_proposal_version_id']}/commands/accept",
            accept_payload,
            idem="idem_accept_api",
        )
        replay = self.post(
            f"/alpha/disposition-proposal-versions/{proposal['disposition_proposal_version_id']}/commands/accept",
            accept_payload,
            idem="idem_accept_api",
        )
        self.assertEqual(first.status_code, 200)
        self.assertEqual(replay.status_code, 200)
        self.assertFalse(first.json()["command"]["idempotent_replay"])
        self.assertTrue(replay.json()["command"]["idempotent_replay"])
        self.assertEqual(first.json()["data"], replay.json()["data"])

        disposition = first.json()["data"]["research_disposition"]
        fetched = self.client.get(
            f"/alpha/research-dispositions/{disposition['research_disposition_id']}"
        )
        self.assertEqual(fetched.status_code, 200)
        self.assertEqual(fetched.json()["data"], disposition)

        stale = self.post(
            f"/alpha/disposition-proposal-versions/{proposal['disposition_proposal_version_id']}/commands/accept",
            accept_payload,
            idem="idem_accept_api_stale",
        )
        self.assertEqual(stale.status_code, 409)
        self.assertEqual(stale.json()["error"]["code"], "concurrency_conflict")

    def test_adjust_and_reject_routes_do_not_create_disposition(self) -> None:
        self.seed_run_and_evidence()
        seeded = self.create_proposal(
            key_suffix="adjust",
            disposition_type="knowledge_only_closure",
        )
        proposal = seeded["proposal"]

        adjusted = self.post(
            f"/alpha/disposition-proposal-versions/{proposal['disposition_proposal_version_id']}/commands/adjust",
            {
                "expected_revision": proposal["revision"],
                "proposed_disposition_type": "observe",
                "reason": "Observe for new evidence.",
                "observation_condition": "New cited source appears.",
            },
            idem="idem_adjust_api",
        )
        self.assertEqual(adjusted.status_code, 200)
        new_proposal = adjusted.json()["data"]["disposition_proposal"]
        self.assertEqual(new_proposal["version"], 2)
        self.assertEqual(new_proposal["user_decision_status"], "adjusted")

        current = self.client.get(
            f"/alpha/disposition-proposals/{proposal['disposition_proposal_id']}/current"
        ).json()["data"]
        self.assertEqual(
            current["disposition_proposal_version_id"],
            new_proposal["disposition_proposal_version_id"],
        )

        rejected = self.post(
            f"/alpha/disposition-proposal-versions/{new_proposal['disposition_proposal_version_id']}/commands/reject",
            {"expected_revision": new_proposal["revision"]},
            idem="idem_reject_api",
        )
        self.assertEqual(rejected.status_code, 200)
        self.assertEqual(
            rejected.json()["data"]["disposition_proposal"]["user_decision_status"],
            "rejected",
        )
        with UnitOfWork(self.database, write=False) as uow:
            self.assertIsNone(uow.case_scope.get_case("case_1").current_research_disposition_id)

    def test_internal_candidate_result_requires_service_identity_and_is_idempotent(self) -> None:
        self.seed_run_and_evidence(lifecycle=True)
        payload = self.candidate_payload()

        rejected = self.internal_post(payload, idem="idem_candidate_missing_auth", service_actor_id=None)
        self.assertEqual(rejected.status_code, 401)
        self.assertEqual(rejected.json()["error"]["code"], "authentication_required")

        first = self.internal_post(payload, idem="idem_candidate_submit")
        replay = self.internal_post(payload, idem="idem_candidate_submit")
        self.assertEqual(first.status_code, 200)
        self.assertEqual(replay.status_code, 200)
        self.assertEqual(
            first.json()["data"]["submission_status"],
            "accepted_for_domain_processing",
        )
        self.assertFalse(first.json()["command"]["idempotent_replay"])
        self.assertTrue(replay.json()["command"]["idempotent_replay"])
        self.assertEqual(first.json()["data"], replay.json()["data"])

        changed = dict(payload)
        changed["candidate_result"] = {"claim": "changed candidate"}
        conflict = self.internal_post(changed, idem="idem_candidate_submit")
        self.assertEqual(conflict.status_code, 409)
        self.assertEqual(conflict.json()["error"]["code"], "idempotency_conflict")


if __name__ == "__main__":
    unittest.main()
