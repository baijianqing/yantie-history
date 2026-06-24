from __future__ import annotations

import unittest
from datetime import datetime, timezone

from pydantic import ValidationError

from metaos.core_alpha.contracts.common import OpenCodeValue
from metaos.core_alpha.contracts.scope import (
    AccessPolicy,
    AddResearchQuestionRequest,
    AdjustKnowledgeScopeRequest,
    AnalysisRole,
    AttentionStatus,
    CreateKnowledgeScopeRequest,
    CreateResearchCaseRequest,
    CreateResearchPlanRequest,
    CreateSourceResolutionsRequest,
    DeriveResearchCaseRequest,
    EvidenceRequirementInput,
    EvidenceRequirementResponse,
    KnowledgeScopeBindingInput,
    KnowledgeScopeSourceBindingResponse,
    KnowledgeScopeVersionResponse,
    QuestionRole,
    ResearchCaseLifecycleStatus,
    ResearchCaseResponse,
    ResearchMode,
    ResearchPlanVersionResponse,
    ResearchQuestionResponse,
    ResolutionStage,
    ResolutionStatus,
    ScopeMode,
    SourceAnchorInput,
    SourceResolutionResponse,
    VersionLifecycleStatus,
)


NOW = datetime(2026, 6, 25, 2, 0, tzinfo=timezone.utc)


def source_binding(
    *,
    policy: AccessPolicy = AccessPolicy.required,
    item_id: str = "ki_1",
    resolution_id: str = "sr_1",
    version_id: str | None = "kiv_1",
    role: AnalysisRole | None = AnalysisRole.primary,
) -> KnowledgeScopeBindingInput:
    return KnowledgeScopeBindingInput(
        source_resolution_id=resolution_id,
        knowledge_item_id=item_id,
        knowledge_item_version_id=version_id,
        access_policy=policy,
        analysis_role=role,
    )


def requirement_input() -> EvidenceRequirementInput:
    return EvidenceRequirementInput(
        requirement_type=OpenCodeValue(code="direct_support", registry_version="v1"),
        description="Find direct support",
        required_knowledge_scope_source_binding_ids=["kssb_1"],
        counterevidence_required=True,
        alternative_interpretation_required=False,
        completion_condition="One located support and a counterevidence report",
        minimum_count=1,
    )


class CoreAlphaScopeContractTests(unittest.TestCase):
    def test_case_creation_and_question_commands_reject_invalid_shapes(self) -> None:
        request = CreateResearchCaseRequest(
            title=" Hidden intent ",
            question_text=" What is hidden? ",
            question_role="root",
        )
        self.assertEqual(request.title, "Hidden intent")

        with self.assertRaises(ValidationError):
            CreateResearchCaseRequest(
                title="Case",
                question_text="Question",
                question_role="follow_up",
            )
        with self.assertRaises(ValidationError):
            AddResearchQuestionRequest(
                expected_revision=1,
                question_text="Another root",
                question_role="root",
            )
        with self.assertRaises(ValidationError):
            CreateResearchCaseRequest(
                title="Case",
                question_text="Question",
                question_role="root",
                research_case_id="client_owned_id",
            )

    def test_derive_requires_exactly_one_source(self) -> None:
        valid = DeriveResearchCaseRequest(
            expected_revision=3,
            source_question_id="rq_1",
            title="Derived case",
            question_text="Follow the branch",
        )
        self.assertEqual(valid.source_question_id, "rq_1")

        with self.assertRaises(ValidationError):
            DeriveResearchCaseRequest(
                expected_revision=3,
                title="No source",
                question_text="Question",
            )
        with self.assertRaises(ValidationError):
            DeriveResearchCaseRequest(
                expected_revision=3,
                source_question_id="rq_1",
                judgment_card_version_id="jcv_1",
                title="Two sources",
                question_text="Question",
            )

    def test_source_resolution_request_and_conditional_response_fields(self) -> None:
        request = CreateSourceResolutionsRequest(
            expected_revision=2,
            research_question_id="rq_1",
            resolution_stage="full",
            anchors=[
                SourceAnchorInput(
                    raw_anchor="鬼谷子",
                    requested_access_policy="required",
                )
            ],
        )
        self.assertEqual(request.resolution_stage, ResolutionStage.full)

        with self.assertRaises(ValidationError):
            CreateSourceResolutionsRequest(
                expected_revision=2,
                research_question_id="rq_1",
                resolution_stage="preliminary",
                anchors=request.anchors,
            )
        with self.assertRaises(ValidationError):
            CreateSourceResolutionsRequest(
                expected_revision=2,
                research_question_id="rq_1",
                resolution_stage="full",
                anchors=request.anchors * 2,
            )

        resolved = SourceResolutionResponse(
            source_resolution_id="sr_1",
            research_question_id="rq_1",
            resolution_stage="full",
            raw_anchor="鬼谷子",
            requested_access_policy="required",
            resolution_status="resolved",
            candidate_knowledge_item_ids=[],
            created_at=NOW,
            requested_version_hint=None,
            resolved_knowledge_item_id="ki_1",
            resolved_knowledge_item_version_id="kiv_1",
            ambiguity_reason=None,
            failure_reason=None,
        )
        self.assertEqual(resolved.resolution_status, ResolutionStatus.resolved)

        invalid = resolved.model_dump()
        invalid["resolved_knowledge_item_version_id"] = None
        with self.assertRaises(ValidationError):
            SourceResolutionResponse.model_validate(invalid)

        ambiguous = resolved.model_dump()
        ambiguous.update(
            resolution_status="ambiguous",
            candidate_knowledge_item_ids=["ki_1", "ki_2"],
            resolved_knowledge_item_id=None,
            resolved_knowledge_item_version_id=None,
            ambiguity_reason="Two editions match",
        )
        self.assertEqual(
            SourceResolutionResponse.model_validate(ambiguous).resolution_status,
            ResolutionStatus.ambiguous,
        )

        unavailable = ambiguous.copy()
        unavailable.update(
            resolution_status="unavailable",
            candidate_knowledge_item_ids=[],
            ambiguity_reason=None,
            failure_reason="Requested version is unavailable",
        )
        self.assertEqual(
            SourceResolutionResponse.model_validate(unavailable).resolution_status,
            ResolutionStatus.unavailable,
        )

    def test_scope_bindings_enforce_access_policy_and_unique_sources(self) -> None:
        required = source_binding()
        excluded = source_binding(
            policy=AccessPolicy.excluded,
            item_id="ki_2",
            resolution_id="sr_2",
            version_id=None,
            role=None,
        )
        request = CreateKnowledgeScopeRequest(
            expected_revision=4,
            default_access_policy="excluded",
            scope_mode="evidence_only",
            bindings=[required, excluded],
        )
        self.assertEqual(request.scope_mode, ScopeMode.evidence_only)

        with self.assertRaises(ValidationError):
            source_binding(version_id=None)
        with self.assertRaises(ValidationError):
            source_binding(
                policy=AccessPolicy.excluded,
                version_id=None,
                role=AnalysisRole.background,
            )
        with self.assertRaises(ValidationError):
            CreateKnowledgeScopeRequest(
                expected_revision=4,
                default_access_policy="required",
                scope_mode="evidence_only",
                bindings=[],
            )
        with self.assertRaises(ValidationError):
            AdjustKnowledgeScopeRequest(
                expected_revision=4,
                default_access_policy="allowed",
                scope_mode="evidence_only",
                bindings=[required, required],
            )

    def test_scope_response_requires_dual_ids_and_matching_binding_versions(self) -> None:
        binding = KnowledgeScopeSourceBindingResponse(
            **source_binding().model_dump(),
            knowledge_scope_source_binding_id="kssb_1",
            knowledge_scope_version_id="ksv_1",
            created_at=NOW,
        )
        scope = KnowledgeScopeVersionResponse(
            knowledge_scope_id="ks_1",
            knowledge_scope_version_id="ksv_1",
            research_case_id="case_1",
            version=1,
            lifecycle_status="current",
            scope_mode="evidence_only",
            default_access_policy="excluded",
            source_bindings=[binding],
            created_by="user_1",
            created_at=NOW,
            previous_version_id=None,
        )
        self.assertEqual(scope.knowledge_scope_id, "ks_1")
        self.assertEqual(scope.knowledge_scope_version_id, "ksv_1")

        invalid = scope.model_dump()
        invalid["version"] = 2
        with self.assertRaises(ValidationError):
            KnowledgeScopeVersionResponse.model_validate(invalid)
        invalid = scope.model_dump()
        invalid["source_bindings"][0]["knowledge_scope_version_id"] = "ksv_other"
        with self.assertRaises(ValidationError):
            KnowledgeScopeVersionResponse.model_validate(invalid)
        missing_nullable_field = binding.model_dump()
        del missing_nullable_field["analysis_role"]
        with self.assertRaises(ValidationError):
            KnowledgeScopeSourceBindingResponse.model_validate(missing_nullable_field)

    def test_plan_requests_and_responses_enforce_requirements_and_version_chain(self) -> None:
        request = CreateResearchPlanRequest(
            expected_revision=5,
            knowledge_scope_version_id="ksv_1",
            research_mode="claim_evaluation",
            primary_objective="Evaluate the claim",
            evidence_requirements=[requirement_input()],
            minimum_completion_condition="All mandatory requirements reach a terminal state",
        )
        self.assertEqual(request.research_mode, ResearchMode.claim_evaluation)
        with self.assertRaises(ValidationError):
            CreateResearchPlanRequest(
                expected_revision=5,
                knowledge_scope_version_id="ksv_1",
                research_mode="claim_evaluation",
                primary_objective="Evaluate",
                evidence_requirements=[],
                minimum_completion_condition="Complete",
            )
        invalid_requirement = requirement_input().model_dump()
        invalid_requirement["counterevidence_required"] = "true"
        with self.assertRaises(ValidationError):
            EvidenceRequirementInput.model_validate(invalid_requirement)

        response_requirement = EvidenceRequirementResponse(
            **requirement_input().model_dump(),
            evidence_requirement_id="er_1",
        )
        missing_minimum_count = response_requirement.model_dump()
        del missing_minimum_count["minimum_count"]
        with self.assertRaises(ValidationError):
            EvidenceRequirementResponse.model_validate(missing_minimum_count)
        plan = ResearchPlanVersionResponse(
            research_plan_id="rp_1",
            research_plan_version_id="rpv_1",
            research_case_id="case_1",
            knowledge_scope_version_id="ksv_1",
            version=1,
            lifecycle_status=VersionLifecycleStatus.current,
            research_mode=ResearchMode.claim_evaluation,
            primary_objective="Evaluate",
            evidence_requirements=[response_requirement],
            minimum_completion_condition="Complete",
            created_at=NOW,
            previous_version_id=None,
            stop_conditions=None,
            research_budget=None,
        )
        dumped = plan.model_dump()
        self.assertIn("stop_conditions", dumped)
        self.assertIsNone(dumped["research_budget"])

        invalid = plan.model_dump()
        invalid["version"] = 2
        with self.assertRaises(ValidationError):
            ResearchPlanVersionResponse.model_validate(invalid)
        missing_nullable_field = plan.model_dump()
        del missing_nullable_field["research_budget"]
        with self.assertRaises(ValidationError):
            ResearchPlanVersionResponse.model_validate(missing_nullable_field)
        with self.assertRaises(ValidationError):
            CreateResearchPlanRequest(
                **request.model_dump(),
                stop_conditions=["client must not define Complete fields"],
            )

    def test_case_and_question_responses_keep_state_dimensions_separate(self) -> None:
        question = ResearchQuestionResponse(
            research_question_id="rq_1",
            research_case_id="case_1",
            question_text="What matters?",
            question_role=QuestionRole.root,
            created_by="user_1",
            created_at=NOW,
            parent_question_id=None,
        )
        case = ResearchCaseResponse(
            research_case_id="case_1",
            title="Question",
            root_question_id=question.research_question_id,
            current_question_id=question.research_question_id,
            lifecycle_status=ResearchCaseLifecycleStatus.open,
            attention_status=AttentionStatus.active,
            revision=1,
            created_at=NOW,
            updated_at=NOW,
            current_knowledge_scope_version_id=None,
            current_judgment_card_version_id=None,
            current_research_disposition_id=None,
            parent_research_case_id=None,
            archived_at=None,
        )
        self.assertEqual(case.lifecycle_status, ResearchCaseLifecycleStatus.open)
        self.assertEqual(case.attention_status, AttentionStatus.active)

        invalid_question = question.model_dump()
        invalid_question["parent_question_id"] = "rq_parent"
        with self.assertRaises(ValidationError):
            ResearchQuestionResponse.model_validate(invalid_question)

    def test_scope_and_plan_schemas_are_closed(self) -> None:
        scope_schema = KnowledgeScopeVersionResponse.model_json_schema()
        plan_schema = ResearchPlanVersionResponse.model_json_schema()
        self.assertFalse(scope_schema["additionalProperties"])
        self.assertFalse(plan_schema["additionalProperties"])


if __name__ == "__main__":
    unittest.main()
