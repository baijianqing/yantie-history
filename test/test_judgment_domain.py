from __future__ import annotations

import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

from metaos.core_alpha.commands import ApplicationCommandHandler
from metaos.core_alpha.contracts.common import CommandContext, OpenCodeValue
from metaos.core_alpha.contracts.judgment import (
    ClaimUserAttitude,
    SetClaimUserAttitudeRequest,
    SupportStrength,
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


TEST_NOW = datetime(2026, 6, 25, 12, 0, tzinfo=timezone.utc)


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


class JudgmentDomainTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.database = CoreAlphaDatabase(Path(self.temp_dir.name) / "core-alpha.db")
        self.database.initialize()
        self.clock = FixedClock()
        self.commands = JudgmentDomainCommandHandler(
            ApplicationCommandHandler(self.database),
            clock=self.clock,
        )
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

    def direct_link(self, use_id: str = "reu_1") -> CandidateEvidenceLink:
        return CandidateEvidenceLink(
            research_evidence_use_id=use_id,
            evidence_role="supports",
            support_strength=SupportStrength(level="strong", reason="Direct source match."),
            scope_note="Within required source.",
        )

    def fact_candidate(
        self,
        *,
        evidence_status: str = "supported",
        confidence_level: str = "high",
        links: list[CandidateEvidenceLink] | None = None,
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
            evidence_links=links or [self.direct_link()],
        )

    def draft_request(
        self,
        *,
        claims: list[ClaimCandidate] | None = None,
    ) -> CreateJudgmentDraftRequest:
        return CreateJudgmentDraftRequest(
            expected_run_revision=1,
            summary="A draft judgment assembled from retrieved evidence.",
            uncertainties=["Only the selected source version was checked."],
            evidence_gaps=["Counterevidence still needs audit."],
            claims=claims or [self.fact_candidate()],
        )

    def create_draft(self, *, idempotency_key: str = "idem_judgment") -> dict:
        response = self.commands.create_judgment_draft(
            "run_1",
            self.draft_request(),
            context=context(f"cmd_judgment_{idempotency_key}", idempotency_key=idempotency_key),
        )
        self.assertEqual(response.status_code, 200)
        return dict(response.response_body["data"])

    def test_create_judgment_draft_links_evidence_rationale_and_claim(self) -> None:
        data = self.create_draft()

        judgment = data["judgment_card"]
        self.assertEqual(judgment["audit_status"], "pending")
        self.assertEqual(judgment["validity_status"], "valid")
        self.assertIsNone(judgment["decision_fitness_id"])
        self.assertEqual(len(data["claims"]), 1)
        claim = data["claims"][0]
        self.assertEqual(claim["evidence_status"], "supported")
        self.assertEqual(claim["user_attitude"], "unreviewed")
        self.assertEqual(claim["judgment_rationale_id"], data["rationales"][0]["judgment_rationale_id"])
        self.assertEqual(data["evidence_links"][0]["research_evidence_use_id"], "reu_1")
        self.assertEqual(
            data["rationales"][0]["rationale_profile"]["profile_type"],
            "fact",
        )

        with UnitOfWork(self.database, write=False) as uow:
            stored = uow.judgment_decision.get_judgment_card_version(
                judgment["judgment_card_version_id"],
            )
            links = uow.judgment_decision.list_claim_evidence_links(claim["claim_version_id"])
            rationale = uow.judgment_decision.get_judgment_rationale(
                claim["judgment_rationale_id"],
            )
            self.assertEqual(stored.audit_status.value, "pending")
            self.assertEqual(len(links), 1)
            self.assertEqual(rationale.rationale_profile.profile_type, "fact")

    def test_create_judgment_draft_is_idempotent_and_versions_follow_up_drafts(self) -> None:
        first = self.commands.create_judgment_draft(
            "run_1",
            self.draft_request(),
            context=context("cmd_judgment_once_1", idempotency_key="idem_judgment_once"),
        )
        replay = self.commands.create_judgment_draft(
            "run_1",
            self.draft_request(),
            context=context("cmd_judgment_once_2", idempotency_key="idem_judgment_once"),
        )
        self.assertFalse(first.response_body["command"]["idempotent_replay"])
        self.assertTrue(replay.response_body["command"]["idempotent_replay"])
        self.assertEqual(first.response_body["data"], replay.response_body["data"])

        second = self.commands.create_judgment_draft(
            "run_1",
            self.draft_request(),
            context=context("cmd_judgment_second", idempotency_key="idem_judgment_second"),
        )
        first_judgment = first.response_body["data"]["judgment_card"]
        second_judgment = second.response_body["data"]["judgment_card"]
        self.assertEqual(second_judgment["version"], 2)
        self.assertEqual(
            second_judgment["previous_version_id"],
            first_judgment["judgment_card_version_id"],
        )
        with UnitOfWork(self.database, write=False) as uow:
            old = uow.judgment_decision.get_judgment_card_version(
                first_judgment["judgment_card_version_id"],
            )
            current = uow.judgment_decision.get_current_judgment_card(
                second_judgment["judgment_card_id"],
            )
            self.assertEqual(old.lifecycle_status.value, "superseded")
            self.assertEqual(current.judgment_card_version_id, second_judgment["judgment_card_version_id"])

    def test_rationale_shape_must_match_claim_type(self) -> None:
        with self.assertRaises(ValueError):
            ClaimCandidate(
                claim_text="Mismatched candidate.",
                epistemic_type="fact",
                expression_role="core_judgment",
                evidence_status="supported",
                importance="core",
                confidence_level="medium",
                rationale_profile={
                    "profile_type": "inference",
                    "premises": ["The source mentions an event."],
                    "reasoning_method": code("analogy"),
                    "key_assumptions": ["The analogy is appropriate."],
                    "applicability_boundaries": ["Only this context."],
                    "counterevidence_summary": [],
                    "invalidation_conditions": ["Contrary source appears."],
                },
                reasoning_summary="Wrong profile.",
                evidence_links=[self.direct_link()],
            )

    def test_duplicate_evidence_unit_does_not_inflate_evidence_links(self) -> None:
        with UnitOfWork(self.database) as uow:
            uow.run_evidence.add_research_evidence_use(
                evidence_use(
                    research_evidence_use_id="reu_duplicate",
                    created_at=NOW + timedelta(minutes=4),
                    validity_checked_at=NOW + timedelta(minutes=4),
                )
            )
        response = self.commands.create_judgment_draft(
            "run_1",
            self.draft_request(
                claims=[
                    self.fact_candidate(
                        links=[
                            self.direct_link("reu_1"),
                            self.direct_link("reu_duplicate"),
                        ]
                    )
                ]
            ),
            context=context("cmd_judgment_dedup", idempotency_key="idem_judgment_dedup"),
        )

        data = response.response_body["data"]
        self.assertEqual(len(data["evidence_links"]), 1)
        self.assertEqual(len(data["rationales"][0]["evidence_link_ids"]), 1)

    def test_user_attitude_does_not_change_evidence_status(self) -> None:
        data = self.commands.create_judgment_draft(
            "run_1",
            self.draft_request(
                claims=[
                    self.fact_candidate(
                        evidence_status="partially_supported",
                        confidence_level="medium",
                    )
                ]
            ),
            context=context("cmd_judgment_partial", idempotency_key="idem_judgment_partial"),
        ).response_body["data"]
        claim = data["claims"][0]

        accepted = self.commands.set_claim_user_attitude(
            claim["claim_version_id"],
            SetClaimUserAttitudeRequest(
                expected_revision=1,
                user_attitude=ClaimUserAttitude.accepted,
            ),
            context=context("cmd_claim_accept", idempotency_key="idem_claim_accept"),
        )

        updated_claim = accepted.response_body["data"]["claim"]
        self.assertEqual(updated_claim["user_attitude"], "accepted")
        self.assertEqual(updated_claim["evidence_status"], "partially_supported")

    def test_stale_run_revision_or_cross_run_evidence_is_rejected(self) -> None:
        with self.assertRaises(ConcurrencyConflictError):
            self.commands.create_judgment_draft(
                "run_1",
                self.draft_request().model_copy(update={"expected_run_revision": 9}),
                context=context("cmd_judgment_stale", idempotency_key="idem_judgment_stale"),
            )
        with UnitOfWork(self.database) as uow:
            uow.run_evidence.create_research_run(
                research_run=run_response(
                    research_run_id="run_2",
                    run_execution_spec_id="spec_2",
                ),
                execution_spec=execution_spec(
                    run_execution_spec_id="spec_2",
                    research_run_id="run_2",
                ),
            )
            uow.run_evidence.add_attempt(
                attempt_response(
                    research_attempt_id="attempt_2",
                    research_run_id="run_2",
                )
            )
            uow.run_evidence.add_research_evidence_use(
                evidence_use(
                    research_evidence_use_id="reu_other_run",
                    research_run_id="run_2",
                    research_attempt_id="attempt_2",
                    use_type="reused",
                    retrieval_run_id=None,
                    created_at=NOW + timedelta(minutes=4),
                    validity_checked_at=NOW + timedelta(minutes=4),
                )
            )
        with self.assertRaises(ValueError):
            self.commands.create_judgment_draft(
                "run_1",
                self.draft_request(
                    claims=[self.fact_candidate(links=[self.direct_link("reu_other_run")])]
                ),
                context=context("cmd_judgment_cross_run", idempotency_key="idem_judgment_cross_run"),
            )


if __name__ == "__main__":
    unittest.main()
