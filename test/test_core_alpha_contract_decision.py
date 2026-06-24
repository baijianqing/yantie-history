from __future__ import annotations

import unittest
from datetime import datetime, timedelta, timezone

from pydantic import ValidationError

from metaos.core_alpha.contracts.common import OpenCodeValue, ResourceReference
from metaos.core_alpha.contracts.decision import (
    AcceptDispositionProposalData,
    AcceptDispositionProposalRequest,
    AdjustDispositionProposalData,
    AdjustDispositionProposalRequest,
    DispositionProposalVersionResponse,
    RejectDispositionProposalRequest,
    ResearchDispositionResponse,
)
from metaos.core_alpha.contracts.internal import (
    CandidateInputVersions,
    CreateDispositionProposalCommandRequest,
    SubmitCandidateResultCommandRequest,
    SubmitCandidateResultData,
)
from metaos.core_alpha.contracts.scope import ResearchCaseResponse


NOW = datetime(2026, 6, 25, 4, 0, tzinfo=timezone.utc)
LATER = NOW + timedelta(days=1)


def proposal_response(**updates: object) -> DispositionProposalVersionResponse:
    payload: dict[str, object] = {
        "disposition_proposal_id": "proposal_1",
        "disposition_proposal_version_id": "proposal_v1",
        "research_case_id": "case_1",
        "judgment_card_version_id": "jcv_1",
        "decision_fitness_id": "fitness_1",
        "proposed_disposition_type": "continue_research",
        "reason": "One evidence gap remains material.",
        "user_decision_status": "pending",
        "lifecycle_status": "current",
        "version": 1,
        "revision": 1,
        "created_at": NOW,
        "warning_acknowledgement_ids": ["ack_1"],
        "previous_version_id": None,
        "expires_at": None,
        "defer_until": None,
        "observation_condition": None,
    }
    payload.update(updates)
    return DispositionProposalVersionResponse.model_validate(payload)


def research_case_response() -> ResearchCaseResponse:
    return ResearchCaseResponse(
        research_case_id="case_1",
        title="Evidence review",
        root_question_id="rq_1",
        current_question_id="rq_1",
        lifecycle_status="open",
        attention_status="active",
        revision=5,
        created_at=NOW,
        updated_at=NOW,
        current_knowledge_scope_version_id="ksv_1",
        current_judgment_card_version_id="jcv_1",
        current_research_disposition_id="disposition_1",
        parent_research_case_id=None,
        archived_at=None,
    )


class CoreAlphaDecisionContractTests(unittest.TestCase):
    def test_proposal_enforces_version_and_disposition_conditions(self) -> None:
        proposal = proposal_response()
        self.assertEqual(proposal.proposed_disposition_type.value, "continue_research")

        deferred = proposal_response(
            proposed_disposition_type="defer_decision",
            defer_until=LATER,
        )
        self.assertEqual(deferred.defer_until, LATER)

        with self.assertRaises(ValidationError):
            proposal_response(proposed_disposition_type="defer_decision")
        with self.assertRaises(ValidationError):
            proposal_response(
                proposed_disposition_type="observe",
                observation_condition="Wait for the next source release.",
                defer_until=LATER,
            )
        with self.assertRaises(ValidationError):
            proposal_response(lifecycle_status="expired", expires_at=None)
        with self.assertRaises(ValidationError):
            proposal_response(version=2, previous_version_id=None)

    def test_research_disposition_is_a_confirmed_immutable_fact(self) -> None:
        disposition = ResearchDispositionResponse(
            research_disposition_id="disposition_1",
            research_case_id="case_1",
            source_disposition_proposal_version_id="proposal_v1",
            judgment_card_version_id="jcv_1",
            decision_fitness_id="fitness_1",
            disposition_type="observe",
            confirmed_by="user_1",
            confirmed_at=NOW,
            supersedes_disposition_id=None,
            defer_until=None,
            observation_condition="Wait for an independently published correction.",
        )
        self.assertEqual(disposition.disposition_type.value, "observe")

        invalid = disposition.model_dump()
        invalid["observation_condition"] = None
        with self.assertRaises(ValidationError):
            ResearchDispositionResponse.model_validate(invalid)

    def test_public_decision_requests_have_fixed_concurrency_shapes(self) -> None:
        accepted = AcceptDispositionProposalRequest(
            expected_revision=2,
            judgment_card_version_id="jcv_1",
            decision_fitness_id="fitness_1",
            warning_acknowledgement_ids=["ack_1"],
        )
        self.assertEqual(accepted.expected_revision, 2)
        with self.assertRaises(ValidationError):
            AcceptDispositionProposalRequest(
                **accepted.model_dump(),
                confirmed_by="forged_actor",
            )
        with self.assertRaises(ValidationError):
            AcceptDispositionProposalRequest(
                expected_revision=2,
                judgment_card_version_id="jcv_1",
                decision_fitness_id="fitness_1",
                warning_acknowledgement_ids=["ack_1", "ack_1"],
            )

        adjusted = AdjustDispositionProposalRequest(
            expected_revision=2,
            proposed_disposition_type="defer_decision",
            reason="Wait for the primary source edition.",
            defer_until=LATER,
        )
        self.assertEqual(adjusted.proposed_disposition_type.value, "defer_decision")
        self.assertEqual(RejectDispositionProposalRequest(expected_revision=2).expected_revision, 2)

    def test_accept_and_adjust_data_preserve_version_links(self) -> None:
        proposal = proposal_response(
            proposed_disposition_type="observe",
            user_decision_status="accepted",
            observation_condition="Wait for a correction.",
        )
        disposition = ResearchDispositionResponse(
            research_disposition_id="disposition_1",
            research_case_id="case_1",
            source_disposition_proposal_version_id="proposal_v1",
            judgment_card_version_id="jcv_1",
            decision_fitness_id="fitness_1",
            disposition_type="observe",
            confirmed_by="user_1",
            confirmed_at=NOW,
            supersedes_disposition_id=None,
            defer_until=None,
            observation_condition="Wait for a correction.",
        )
        data = AcceptDispositionProposalData(
            disposition_proposal=proposal,
            research_disposition=disposition,
            research_case=research_case_response(),
        )
        self.assertEqual(data.research_disposition.research_case_id, "case_1")

        invalid_disposition = disposition.model_copy(
            update={"decision_fitness_id": "fitness_other"}
        )
        with self.assertRaises(ValidationError):
            AcceptDispositionProposalData(
                disposition_proposal=proposal,
                research_disposition=invalid_disposition,
                research_case=research_case_response(),
            )

        adjusted_proposal = proposal_response(
            disposition_proposal_version_id="proposal_v2",
            version=2,
            previous_version_id="proposal_v1",
        )
        adjusted_data = AdjustDispositionProposalData(
            disposition_proposal=adjusted_proposal,
            superseded_version_ref=ResourceReference(
                resource_type="disposition_proposal_version",
                resource_id="proposal_v1",
            ),
        )
        self.assertEqual(adjusted_data.superseded_version_ref.resource_id, "proposal_v1")

    def test_candidate_submission_payload_uses_trusted_context_outside_body(self) -> None:
        request = SubmitCandidateResultCommandRequest(
            operation_type=OpenCodeValue(
                code="judgment_candidate",
                registry_version="core-alpha-v1",
            ),
            research_run_id="run_1",
            research_attempt_id="attempt_1",
            run_execution_spec_id="spec_1",
            input_versions=CandidateInputVersions(
                research_run_revision=7,
                knowledge_scope_version_id="ksv_1",
                research_plan_version_id="rpv_1",
            ),
            lifecycle_generation=3,
            capability_implementation_version="capability-v1",
            output_schema_version="judgment-v1",
            candidate_result={"candidate_ref": "candidate_payload_1"},
        )
        self.assertEqual(request.operation_type.code, "judgment_candidate")

        invalid = request.model_dump()
        invalid["actor_id"] = "forged_worker"
        with self.assertRaises(ValidationError):
            SubmitCandidateResultCommandRequest.model_validate(invalid)
        invalid = request.model_dump()
        invalid["idempotency_key"] = "forged_body_key"
        with self.assertRaises(ValidationError):
            SubmitCandidateResultCommandRequest.model_validate(invalid)

    def test_candidate_submission_status_controls_result_identity(self) -> None:
        accepted = SubmitCandidateResultData(
            submission_status="accepted_for_domain_processing",
            capability_candidate_result_id="candidate_result_1",
            follow_up_commands=[
                ResourceReference(
                    resource_type="application_command",
                    resource_id="command_2",
                )
            ],
        )
        self.assertEqual(accepted.capability_candidate_result_id, "candidate_result_1")

        rejected = SubmitCandidateResultData(
            submission_status="rejected_stale",
            capability_candidate_result_id=None,
            follow_up_commands=[],
        )
        self.assertIsNone(rejected.capability_candidate_result_id)

        with self.assertRaises(ValidationError):
            SubmitCandidateResultData(
                submission_status="rejected_tombstoned",
                capability_candidate_result_id="must_not_exist",
                follow_up_commands=[],
            )

    def test_internal_disposition_command_enforces_gate_inputs(self) -> None:
        request = CreateDispositionProposalCommandRequest(
            research_case_id="case_1",
            expected_research_case_revision=5,
            judgment_card_version_id="jcv_1",
            judgment_card_revision=2,
            judgment_audit_id="audit_1",
            decision_fitness_id="fitness_1",
            proposed_disposition_type="observe",
            reason="Observe until the correction condition is met.",
            warning_acknowledgement_ids=["ack_1"],
            observation_condition="A primary source correction is published.",
        )
        self.assertEqual(request.expected_research_case_revision, 5)

        invalid = request.model_dump()
        invalid["observation_condition"] = None
        with self.assertRaises(ValidationError):
            CreateDispositionProposalCommandRequest.model_validate(invalid)
        invalid = request.model_dump()
        invalid["warning_acknowledgement_ids"] = ["ack_1", "ack_1"]
        with self.assertRaises(ValidationError):
            CreateDispositionProposalCommandRequest.model_validate(invalid)

    def test_decision_and_internal_schemas_are_closed(self) -> None:
        proposal_schema = DispositionProposalVersionResponse.model_json_schema()
        candidate_schema = SubmitCandidateResultCommandRequest.model_json_schema()
        self.assertFalse(proposal_schema["additionalProperties"])
        self.assertFalse(candidate_schema["additionalProperties"])
        self.assertIn("OpenCodeValue", candidate_schema["$defs"])


if __name__ == "__main__":
    unittest.main()
