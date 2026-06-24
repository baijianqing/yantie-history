from __future__ import annotations

import unittest
from datetime import datetime, timedelta, timezone

from pydantic import ValidationError

from metaos.core_alpha.contracts.common import OpenCodeValue
from metaos.core_alpha.contracts.execution import (
    CreateResearchRunRequest,
    EvidenceLocation,
    EvidenceUnitResponse,
    ExecutionCheckpointResponse,
    ResearchAttemptResponse,
    ResearchEvidenceUseResponse,
    ResearchRunOutcomeResponse,
    ResearchRunResponse,
    RetrievalRunResponse,
    RunExecutionSpecResponse,
)
from metaos.core_alpha.contracts.judgment import (
    AcknowledgeAuditFindingRequest,
    AuditFindingResponse,
    ClaimEvidenceLinkResponse,
    ClaimVersionResponse,
    DecisionFitnessResponse,
    DecisionRiskCeiling,
    FactRationaleProfile,
    InferenceRationaleProfile,
    JudgmentAuditResponse,
    JudgmentCardVersionResponse,
    JudgmentRationaleResponse,
    SetClaimUserAttitudeRequest,
    StartResearchRunData,
    SupportStrength,
    WarningAcknowledgementCommandData,
    WarningAcknowledgementResponse,
)


NOW = datetime(2026, 6, 25, 3, 0, tzinfo=timezone.utc)
LATER = NOW + timedelta(minutes=1)


def open_code(code: str) -> OpenCodeValue:
    return OpenCodeValue(code=code, registry_version="core-alpha-v1")


def run_response(status: str = "created", **updates: object) -> ResearchRunResponse:
    payload: dict[str, object] = {
        "research_run_id": "run_1",
        "research_case_id": "case_1",
        "research_question_id": "rq_1",
        "knowledge_scope_version_id": "ksv_1",
        "research_plan_version_id": "rpv_1",
        "run_execution_spec_id": "spec_1",
        "status": status,
        "revision": 1,
        "created_at": NOW,
        "started_at": None,
        "ended_at": None,
        "superseded_by_run_id": None,
    }
    payload.update(updates)
    return ResearchRunResponse.model_validate(payload)


def judgment_response(
    audit_status: str = "acceptable",
    **updates: object,
) -> JudgmentCardVersionResponse:
    payload: dict[str, object] = {
        "judgment_card_id": "jc_1",
        "judgment_card_version_id": "jcv_1",
        "research_case_id": "case_1",
        "research_run_id": "run_1",
        "version": 1,
        "revision": 2,
        "claim_version_ids": ["clv_1"],
        "summary": "The evidence supports a bounded conclusion.",
        "uncertainties": ["One source remains disputed."],
        "evidence_gaps": [],
        "audit_status": audit_status,
        "validity_status": "valid",
        "lifecycle_status": "current",
        "created_at": NOW,
        "previous_version_id": None,
        "current_judgment_audit_id": "audit_1",
        "decision_fitness_id": "fit_1",
    }
    payload.update(updates)
    return JudgmentCardVersionResponse.model_validate(payload)


def claim_response(**updates: object) -> ClaimVersionResponse:
    payload: dict[str, object] = {
        "claim_id": "claim_1",
        "claim_version_id": "clv_1",
        "judgment_card_version_id": "jcv_1",
        "claim_text": "The source supports a bounded interpretation.",
        "epistemic_type": "interpretation",
        "expression_role": "core_judgment",
        "evidence_status": "partially_supported",
        "importance": "core",
        "confidence_level": "medium",
        "lifecycle_status": "current",
        "user_attitude": "unreviewed",
        "version": 1,
        "created_at": NOW,
        "judgment_rationale_id": "rat_1",
        "previous_version_id": None,
    }
    payload.update(updates)
    return ClaimVersionResponse.model_validate(payload)


class CoreAlphaJudgmentContractTests(unittest.TestCase):
    def test_run_requests_and_lifecycle_times_are_explicit(self) -> None:
        request = CreateResearchRunRequest(
            expected_research_case_revision=4,
            research_question_id="rq_1",
            knowledge_scope_version_id="ksv_1",
            research_plan_version_id="rpv_1",
        )
        self.assertEqual(request.execution_mode.value, "synchronous")
        with self.assertRaises(ValidationError):
            CreateResearchRunRequest(
                **request.model_dump(),
                research_run_id="client_owned_id",
            )

        running = run_response(status="running", started_at=LATER)
        self.assertEqual(running.status.value, "running")
        with self.assertRaises(ValidationError):
            run_response(status="running")
        with self.assertRaises(ValidationError):
            run_response(status="completed", started_at=LATER)
        with self.assertRaises(ValidationError):
            run_response(
                status="superseded",
                ended_at=LATER,
                superseded_by_run_id=None,
            )

    def test_attempt_and_retrieval_terminal_contracts_match_status(self) -> None:
        attempt = ResearchAttemptResponse(
            research_attempt_id="attempt_1",
            research_run_id="run_1",
            attempt_number=1,
            attempt_mode="retrieval",
            status="completed",
            created_at=NOW,
            previous_attempt_id=None,
            started_at=NOW,
            ended_at=LATER,
            failure_category=None,
            failure_reason=None,
        )
        self.assertEqual(attempt.status.value, "completed")

        created = RetrievalRunResponse(
            retrieval_run_id="retrieval_1",
            research_attempt_id="attempt_1",
            knowledge_scope_source_binding_id="kssb_1",
            retrieval_channel=open_code("fulltext"),
            query_ref="query_1",
            status="created",
            retrieval_outcome=None,
            created_at=NOW,
            index_generation_id="index_1",
            started_at=None,
            ended_at=None,
            failure_reason=None,
        )
        self.assertIsNone(created.retrieval_outcome)

        invalid = created.model_dump()
        invalid.update(
            status="completed",
            retrieval_outcome="failed",
            started_at=NOW,
            ended_at=LATER,
        )
        with self.assertRaises(ValidationError):
            RetrievalRunResponse.model_validate(invalid)

    def test_execution_snapshot_and_checkpoint_keep_attempt_boundary(self) -> None:
        spec = RunExecutionSpecResponse(
            run_execution_spec_id="spec_1",
            research_run_id="run_1",
            knowledge_scope_version_id="ksv_1",
            source_resolution_ids=["sr_1"],
            research_plan_version_id="rpv_1",
            source_version_ids=["kiv_1"],
            index_generation_ids=["index_1"],
            retrieval_strategy_version="retrieval-v1",
            context_strategy_version="context-v1",
            embedding_contract={"name": "bge-m3", "version": "v1"},
            reranker_contract={"enabled": False},
            capability_contracts=[{"name": "fulltext", "version": "v1"}],
            allowed_implementations=["sqlite_fts5"],
            fallback_policy={"policy_version": "fallback-v1"},
            prompt_version="prompt-v1",
            output_schema_version="judgment-v1",
            audit_policy_version="audit-v1",
            decision_fitness_policy_version="fitness-v1",
            egress_policy_version="egress-v1",
            system_safety_limits={"max_context_chunks": 20},
            created_at=NOW,
            budget_snapshot_id=None,
        )
        self.assertEqual(spec.source_version_ids, ["kiv_1"])

        run_checkpoint = ExecutionCheckpointResponse(
            execution_checkpoint_id="checkpoint_1",
            research_run_id="run_1",
            checkpoint_type="run_started",
            input_revision=1,
            completed_at=NOW,
            result_ref_id="run_1",
            idempotency_key="idem_1",
            research_attempt_id=None,
        )
        self.assertIsNone(run_checkpoint.research_attempt_id)

        invalid = run_checkpoint.model_dump()
        invalid["checkpoint_type"] = "evidence_assembled"
        with self.assertRaises(ValidationError):
            ExecutionCheckpointResponse.model_validate(invalid)

    def test_run_outcome_requires_only_valid_judgment_references(self) -> None:
        outcome = ResearchRunOutcomeResponse(
            research_run_outcome_id="outcome_1",
            research_run_id="run_1",
            outcome_type="completed_with_judgment",
            reason_code=open_code("requirements_satisfied"),
            reason_summary="The mandatory evidence requirements were satisfied.",
            created_at=LATER,
            judgment_card_version_id="jcv_1",
        )
        data = StartResearchRunData(
            research_run=run_response(
                status="completed",
                started_at=NOW,
                ended_at=LATER,
            ),
            research_run_outcome=outcome,
            judgment_card=judgment_response(),
        )
        self.assertEqual(data.judgment_card.judgment_card_version_id, "jcv_1")

        invalid = outcome.model_dump()
        invalid.update(outcome_type="execution_failed", judgment_card_version_id="jcv_1")
        with self.assertRaises(ValidationError):
            ResearchRunOutcomeResponse.model_validate(invalid)

    def test_evidence_location_and_use_preserve_provenance(self) -> None:
        location = EvidenceLocation(
            section_path=["Chapter 1"],
            page=3,
            timestamp_seconds=None,
            start_offset=10,
            end_offset=40,
        )
        evidence = EvidenceUnitResponse(
            evidence_unit_id="evidence_1",
            knowledge_item_id="ki_1",
            knowledge_item_version_id="kiv_1",
            location=location,
            excerpt="A located source excerpt.",
            content_hash="sha256:00af",
            origin_type=open_code("retrieval"),
            validity_status="valid",
            revision=1,
            created_at=NOW,
            updated_at=NOW,
            chunk_id="chunk_1",
            origin_retrieval_run_id="retrieval_1",
        )
        self.assertEqual(evidence.location.page, 3)

        retrieved = ResearchEvidenceUseResponse(
            research_evidence_use_id="use_1",
            research_run_id="run_1",
            research_attempt_id="attempt_1",
            evidence_unit_id=evidence.evidence_unit_id,
            evidence_revision=1,
            knowledge_scope_version_id="ksv_1",
            use_type="retrieved",
            validity_checked_at=NOW,
            validity_result="valid",
            created_at=NOW,
            retrieval_run_id="retrieval_1",
        )
        self.assertEqual(retrieved.retrieval_run_id, "retrieval_1")
        invalid = retrieved.model_dump()
        invalid["retrieval_run_id"] = None
        with self.assertRaises(ValidationError):
            ResearchEvidenceUseResponse.model_validate(invalid)
        with self.assertRaises(ValidationError):
            EvidenceLocation(
                section_path=[],
                page=None,
                timestamp_seconds=None,
                start_offset=None,
                end_offset=None,
            )

    def test_rationale_profile_is_a_closed_discriminated_union(self) -> None:
        rationale = JudgmentRationaleResponse(
            judgment_rationale_id="rat_1",
            claim_version_id="clv_1",
            rationale_profile=FactRationaleProfile(
                profile_type="fact",
                source_summary="The selected edition.",
                location_summary="Chapter 1, page 3.",
                fact_mapping="The excerpt states the fact directly.",
                version_limitations=["Only this edition was inspected."],
            ),
            evidence_link_ids=["link_1"],
            reasoning_summary="Direct source mapping.",
            created_at=NOW,
        )
        self.assertEqual(rationale.rationale_profile.profile_type, "fact")

        invalid = rationale.model_dump()
        invalid["rationale_profile"]["premises"] = ["Unrelated inference field"]
        with self.assertRaises(ValidationError):
            JudgmentRationaleResponse.model_validate(invalid)

        inference = InferenceRationaleProfile(
            profile_type="inference",
            premises=["Located evidence A"],
            reasoning_method=open_code("analogy"),
            key_assumptions=["The compared contexts are sufficiently similar."],
            applicability_boundaries=["Only applies to reversible decisions."],
            counterevidence_summary=["The contexts differ in scale."],
            invalidation_conditions=["A direct contradictory source is found."],
        )
        self.assertEqual(inference.reasoning_method.code, "analogy")

    def test_claim_keeps_evidence_status_and_user_attitude_orthogonal(self) -> None:
        accepted = claim_response(user_attitude="accepted", evidence_status="mixed")
        self.assertEqual(accepted.user_attitude.value, "accepted")
        self.assertEqual(accepted.evidence_status.value, "mixed")

        with self.assertRaises(ValidationError):
            claim_response(expression_role="user_reflection", evidence_status="supported")
        with self.assertRaises(ValidationError):
            claim_response(expression_role="open_question", evidence_status="supported")
        with self.assertRaises(ValidationError):
            claim_response(expression_role="recommendation", judgment_rationale_id=None)

        request = SetClaimUserAttitudeRequest(expected_revision=3, user_attitude="accepted")
        self.assertEqual(request.user_attitude.value, "accepted")

    def test_evidence_links_keep_research_use_identity(self) -> None:
        link = ClaimEvidenceLinkResponse(
            claim_evidence_link_id="link_1",
            claim_version_id="clv_1",
            research_evidence_use_id="use_1",
            evidence_unit_id="evidence_1",
            evidence_role="supports",
            support_strength=SupportStrength(level="strong", reason="Direct quotation"),
            created_at=NOW,
            scope_note=None,
        )
        self.assertEqual(link.research_evidence_use_id, "use_1")

    def test_judgment_status_dimensions_and_decision_fitness_remain_separate(self) -> None:
        blocked = judgment_response(audit_status="blocked", decision_fitness_id=None)
        self.assertEqual(blocked.lifecycle_status.value, "current")
        self.assertEqual(blocked.audit_status.value, "blocked")

        with self.assertRaises(ValidationError):
            judgment_response(audit_status="acceptable", decision_fitness_id=None)
        with self.assertRaises(ValidationError):
            judgment_response(audit_status="pending", decision_fitness_id="fit_1")

        fitness = DecisionFitnessResponse(
            decision_fitness_id="fit_1",
            judgment_card_version_id="jcv_1",
            policy_version="decision-v1",
            allowed_uses=["understanding", "research_planning"],
            forbidden_uses=["reversible_action"],
            required_conditions=["Display the unresolved warning."],
            risk_ceiling=DecisionRiskCeiling(
                maximum_cost_level="low",
                minimum_reversibility="reversible",
                maximum_external_impact="limited",
                expert_review_required=False,
            ),
            escalation_triggers=["The source version changes."],
            created_at=NOW,
        )
        self.assertIn("understanding", fitness.allowed_uses)

        invalid = fitness.model_dump()
        invalid["forbidden_uses"] = ["understanding"]
        with self.assertRaises(ValidationError):
            DecisionFitnessResponse.model_validate(invalid)

    def test_audit_gate_and_warning_acknowledgement_are_conditioned(self) -> None:
        audit = JudgmentAuditResponse(
            judgment_audit_id="audit_1",
            judgment_card_version_id="jcv_1",
            audit_policy_version="audit-v1",
            audit_run_status="completed",
            finding_ids=["finding_1"],
            created_at=NOW,
            gate_result="provisionally_acceptable",
            started_at=NOW,
            completed_at=LATER,
        )
        self.assertEqual(audit.gate_result.value, "provisionally_acceptable")
        invalid = audit.model_dump()
        invalid.update(audit_run_status="failed", gate_result="blocked")
        with self.assertRaises(ValidationError):
            JudgmentAuditResponse.model_validate(invalid)

        finding = AuditFindingResponse(
            audit_finding_id="finding_1",
            judgment_audit_id="audit_1",
            affected_claim_version_ids=["clv_1"],
            finding_type=open_code("missing_counterevidence"),
            severity="warning",
            description="Counterevidence remains incomplete.",
            supporting_reason="Only one side was located.",
            policy_version="audit-v1",
            created_at=LATER,
            recommended_revision=None,
            risk_trigger_condition="The claim is used for action.",
        )
        self.assertEqual(finding.severity.value, "warning")

        request = AcknowledgeAuditFindingRequest(
            expected_revision=2,
            judgment_card_version_id="jcv_1",
            acknowledgement_note="Proceed only for understanding.",
        )
        acknowledgement = WarningAcknowledgementResponse(
            warning_acknowledgement_id="ack_1",
            audit_finding_id=finding.audit_finding_id,
            judgment_card_version_id=request.judgment_card_version_id,
            acknowledged_by="user_1",
            acknowledged_at=LATER,
            acknowledgement_note=request.acknowledgement_note,
        )
        data = WarningAcknowledgementCommandData(
            warning_acknowledgement=acknowledgement,
            judgment_card=judgment_response(audit_status="provisionally_acceptable"),
        )
        self.assertEqual(data.warning_acknowledgement.audit_finding_id, "finding_1")

    def test_contracts_emit_closed_json_schema_with_rationale_discriminator(self) -> None:
        execution_schema = ResearchRunResponse.model_json_schema()
        rationale_schema = JudgmentRationaleResponse.model_json_schema()
        self.assertFalse(execution_schema["additionalProperties"])
        self.assertFalse(rationale_schema["additionalProperties"])
        profile_schema = rationale_schema["properties"]["rationale_profile"]
        self.assertEqual(profile_schema["discriminator"]["propertyName"], "profile_type")


if __name__ == "__main__":
    unittest.main()
