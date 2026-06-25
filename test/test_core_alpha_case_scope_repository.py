from __future__ import annotations

import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

from pydantic import ValidationError

from metaos.core_alpha.contracts.common import OpenCodeValue
from metaos.core_alpha.contracts.scope import (
    AccessPolicy,
    AnalysisRole,
    EvidenceRequirementResponse,
    KnowledgeScopeSourceBindingResponse,
    KnowledgeScopeVersionResponse,
    QuestionRole,
    ResearchCaseResponse,
    ResearchPlanVersionResponse,
    ResearchQuestionResponse,
    SourceResolutionResponse,
    VersionLifecycleStatus,
)
from metaos.core_alpha.persistence import (
    ConcurrencyConflictError,
    CoreAlphaDatabase,
    RecordNotFoundError,
    UnitOfWork,
)


NOW = datetime(2026, 6, 25, 6, 0, tzinfo=timezone.utc)


def case_response(**updates: object) -> ResearchCaseResponse:
    payload: dict[str, object] = {
        "research_case_id": "case_1",
        "title": "Hidden intention",
        "root_question_id": "rq_1",
        "current_question_id": "rq_1",
        "lifecycle_status": "open",
        "attention_status": "active",
        "revision": 1,
        "created_at": NOW,
        "updated_at": NOW,
        "current_knowledge_scope_version_id": None,
        "current_judgment_card_version_id": None,
        "current_research_disposition_id": None,
        "parent_research_case_id": None,
        "archived_at": None,
    }
    payload.update(updates)
    return ResearchCaseResponse.model_validate(payload)


def question_response(**updates: object) -> ResearchQuestionResponse:
    payload: dict[str, object] = {
        "research_question_id": "rq_1",
        "research_case_id": "case_1",
        "question_text": "How should hidden intention be evaluated?",
        "question_role": "root",
        "created_by": "user_1",
        "created_at": NOW,
        "parent_question_id": None,
    }
    payload.update(updates)
    return ResearchQuestionResponse.model_validate(payload)


def source_resolution(
    resolution_id: str = "sr_1",
    *,
    access_policy: str = "required",
    status: str = "resolved",
    item_id: str | None = "ki_1",
    version_id: str | None = "kiv_1",
) -> SourceResolutionResponse:
    return SourceResolutionResponse(
        source_resolution_id=resolution_id,
        research_question_id="rq_1",
        resolution_stage="full",
        raw_anchor="鬼谷子",
        requested_access_policy=access_policy,
        resolution_status=status,
        candidate_knowledge_item_ids=[] if status != "ambiguous" else ["ki_1", "ki_2"],
        created_at=NOW,
        requested_version_hint=None,
        resolved_knowledge_item_id=item_id if status == "resolved" else None,
        resolved_knowledge_item_version_id=version_id if status == "resolved" else None,
        ambiguity_reason="Two editions match" if status == "ambiguous" else None,
        failure_reason="Unavailable" if status in {"not_found", "unavailable"} else None,
    )


def scope_binding(
    binding_id: str,
    resolution_id: str,
    *,
    item_id: str = "ki_1",
    version_id: str | None = "kiv_1",
    access_policy: AccessPolicy = AccessPolicy.required,
    role: AnalysisRole | None = AnalysisRole.primary,
    version_ref: str = "ksv_1",
) -> KnowledgeScopeSourceBindingResponse:
    return KnowledgeScopeSourceBindingResponse(
        knowledge_scope_source_binding_id=binding_id,
        knowledge_scope_version_id=version_ref,
        source_resolution_id=resolution_id,
        knowledge_item_id=item_id,
        knowledge_item_version_id=version_id,
        access_policy=access_policy,
        analysis_role=role,
        created_at=NOW,
    )


def scope_response(
    version_id: str = "ksv_1",
    *,
    version: int = 1,
    lifecycle_status: VersionLifecycleStatus = VersionLifecycleStatus.current,
    previous_version_id: str | None = None,
) -> KnowledgeScopeVersionResponse:
    return KnowledgeScopeVersionResponse(
        knowledge_scope_id="ks_1",
        knowledge_scope_version_id=version_id,
        research_case_id="case_1",
        version=version,
        lifecycle_status=lifecycle_status,
        scope_mode="evidence_only",
        default_access_policy="excluded",
        source_bindings=[
            scope_binding("kssb_1" if version == 1 else "kssb_2", "sr_1", version_ref=version_id),
            scope_binding(
                "kssb_ex_1" if version == 1 else "kssb_ex_2",
                "sr_excluded",
                item_id="ki_ex",
                version_id=None,
                access_policy=AccessPolicy.excluded,
                role=None,
                version_ref=version_id,
            ),
        ],
        created_by="user_1",
        created_at=NOW + timedelta(minutes=version),
        previous_version_id=previous_version_id,
    )


def requirement(binding_id: str = "kssb_1", requirement_id: str = "er_1") -> EvidenceRequirementResponse:
    return EvidenceRequirementResponse(
        evidence_requirement_id=requirement_id,
        requirement_type=OpenCodeValue(code="direct_support", registry_version="core-alpha-v1"),
        description="Find direct support.",
        required_knowledge_scope_source_binding_ids=[binding_id],
        counterevidence_required=True,
        alternative_interpretation_required=False,
        completion_condition="Required source reaches terminal coverage.",
        minimum_count=1,
    )


def plan_response(
    version_id: str = "rpv_1",
    *,
    version: int = 1,
    previous_version_id: str | None = None,
    binding_id: str = "kssb_1",
) -> ResearchPlanVersionResponse:
    return ResearchPlanVersionResponse(
        research_plan_id="rp_1",
        research_plan_version_id=version_id,
        research_case_id="case_1",
        knowledge_scope_version_id="ksv_1" if version == 1 else "ksv_2",
        version=version,
        lifecycle_status="current",
        research_mode="claim_evaluation",
        primary_objective="Evaluate the claim with bounded evidence.",
        evidence_requirements=[requirement(binding_id, f"er_{version}")],
        minimum_completion_condition="All mandatory requirements terminal.",
        created_at=NOW + timedelta(hours=version),
        previous_version_id=previous_version_id,
        stop_conditions=None,
        research_budget=None,
    )


class CoreAlphaCaseScopeRepositoryTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.database = CoreAlphaDatabase(Path(self.temp_dir.name) / "core-alpha.db")
        self.database.initialize()

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def seed_case(self) -> None:
        with UnitOfWork(self.database) as uow:
            uow.case_scope.create_case(
                research_case=case_response(),
                root_question=question_response(),
            )

    def seed_resolutions(self) -> None:
        self.seed_case()
        with UnitOfWork(self.database) as uow:
            uow.case_scope.add_source_resolutions(
                [
                    source_resolution("sr_1"),
                    source_resolution(
                        "sr_excluded",
                        access_policy="excluded",
                        item_id="ki_ex",
                        version_id=None,
                    ),
                ],
                expected_case_revision=1,
                updated_at=NOW + timedelta(minutes=1),
            )

    def seed_scope(self) -> None:
        self.seed_resolutions()
        with UnitOfWork(self.database) as uow:
            uow.case_scope.create_knowledge_scope(
                scope_response(),
                expected_case_revision=2,
                updated_at=NOW + timedelta(minutes=2),
            )

    def seed_adjusted_scope(self) -> None:
        self.seed_scope()
        with UnitOfWork(self.database) as uow:
            uow.case_scope.adjust_knowledge_scope(
                scope_response("ksv_2", version=2, previous_version_id="ksv_1"),
                expected_case_revision=3,
                updated_at=NOW + timedelta(minutes=3),
            )

    def test_create_case_and_add_question_with_revision_gate(self) -> None:
        self.seed_case()
        follow_up = question_response(
            research_question_id="rq_2",
            question_text="What is the strongest counterexample?",
            question_role=QuestionRole.follow_up,
            parent_question_id="rq_1",
            created_at=NOW + timedelta(minutes=1),
        )
        with UnitOfWork(self.database) as uow:
            updated = uow.case_scope.add_question(
                follow_up,
                expected_case_revision=1,
                updated_at=NOW + timedelta(minutes=1),
            )
            self.assertEqual(updated.revision, 2)
            self.assertEqual(updated.current_question_id, "rq_2")

        with UnitOfWork(self.database, write=False) as uow:
            questions = uow.case_scope.list_questions("case_1")
            self.assertEqual([question.research_question_id for question in questions], ["rq_1", "rq_2"])

        with self.assertRaises(ConcurrencyConflictError):
            with UnitOfWork(self.database) as uow:
                uow.case_scope.add_question(
                    question_response(
                        research_question_id="rq_3",
                        question_text="Stale write",
                        question_role=QuestionRole.follow_up,
                        parent_question_id="rq_1",
                        created_at=NOW + timedelta(minutes=2),
                    ),
                    expected_case_revision=1,
                    updated_at=NOW + timedelta(minutes=2),
                )
        with UnitOfWork(self.database, write=False) as uow:
            with self.assertRaises(RecordNotFoundError):
                uow.case_scope.get_question("rq_3")

    def test_source_resolution_records_are_immutable_and_advance_case_revision(self) -> None:
        self.seed_case()
        with UnitOfWork(self.database) as uow:
            case = uow.case_scope.add_source_resolutions(
                [source_resolution("sr_1"), source_resolution("sr_amb", status="ambiguous")],
                expected_case_revision=1,
                updated_at=NOW + timedelta(minutes=1),
            )
            self.assertEqual(case.revision, 2)

        with UnitOfWork(self.database, write=False) as uow:
            resolutions = uow.case_scope.list_source_resolutions("rq_1")
            self.assertEqual([resolution.source_resolution_id for resolution in resolutions], ["sr_1", "sr_amb"])
            self.assertEqual(resolutions[1].candidate_knowledge_item_ids, ["ki_1", "ki_2"])

        with self.assertRaises(ConcurrencyConflictError):
            with UnitOfWork(self.database) as uow:
                uow.case_scope.add_source_resolutions(
                    [source_resolution("sr_stale")],
                    expected_case_revision=1,
                    updated_at=NOW + timedelta(minutes=2),
                )
        with UnitOfWork(self.database, write=False) as uow:
            self.assertNotIn(
                "sr_stale",
                [resolution.source_resolution_id for resolution in uow.case_scope.list_source_resolutions("rq_1")],
            )

    def test_knowledge_scope_version_chain_updates_current_pointer_atomically(self) -> None:
        self.seed_resolutions()
        with UnitOfWork(self.database) as uow:
            case = uow.case_scope.create_knowledge_scope(
                scope_response(),
                expected_case_revision=2,
                updated_at=NOW + timedelta(minutes=2),
            )
            self.assertEqual(case.revision, 3)
            self.assertEqual(case.current_knowledge_scope_version_id, "ksv_1")

        with UnitOfWork(self.database) as uow:
            case = uow.case_scope.adjust_knowledge_scope(
                scope_response("ksv_2", version=2, previous_version_id="ksv_1"),
                expected_case_revision=3,
                updated_at=NOW + timedelta(minutes=3),
            )
            self.assertEqual(case.current_knowledge_scope_version_id, "ksv_2")
            old_scope = uow.case_scope.get_knowledge_scope_version("ksv_1")
            self.assertEqual(old_scope.lifecycle_status, VersionLifecycleStatus.superseded)
            current = uow.case_scope.get_current_knowledge_scope("ks_1")
            self.assertEqual(current.knowledge_scope_version_id, "ksv_2")

        with self.assertRaises(ConcurrencyConflictError):
            with UnitOfWork(self.database) as uow:
                uow.case_scope.adjust_knowledge_scope(
                    scope_response("ksv_3", version=3, previous_version_id="ksv_1"),
                    expected_case_revision=4,
                    updated_at=NOW + timedelta(minutes=4),
                )

    def test_scope_rejects_source_resolution_from_another_case(self) -> None:
        self.seed_resolutions()
        with UnitOfWork(self.database) as uow:
            uow.case_scope.create_case(
                research_case=case_response(
                    research_case_id="case_2",
                    root_question_id="rq_other",
                    current_question_id="rq_other",
                    title="Other case",
                ),
                root_question=question_response(
                    research_case_id="case_2",
                    research_question_id="rq_other",
                    question_text="Other question",
                ),
            )
            uow.case_scope.add_source_resolutions(
                [
                    source_resolution("sr_other").model_copy(
                        update={"research_question_id": "rq_other"}
                    )
                ],
                expected_case_revision=1,
                updated_at=NOW + timedelta(minutes=1),
            )

        foreign_scope = scope_response()
        foreign_scope = foreign_scope.model_copy(
            update={
                "source_bindings": [
                    foreign_scope.source_bindings[0].model_copy(
                        update={"source_resolution_id": "sr_other"}
                    )
                ]
            }
        )
        with self.assertRaises(ValueError):
            with UnitOfWork(self.database) as uow:
                uow.case_scope.create_knowledge_scope(
                    foreign_scope,
                    expected_case_revision=2,
                    updated_at=NOW + timedelta(minutes=2),
                )

    def test_research_plan_version_chain_preserves_historical_requirements(self) -> None:
        self.seed_adjusted_scope()
        with UnitOfWork(self.database) as uow:
            case = uow.case_scope.create_research_plan(
                plan_response(binding_id="kssb_1"),
                expected_case_revision=4,
                updated_at=NOW + timedelta(hours=1),
            )
            self.assertEqual(case.revision, 5)

        with UnitOfWork(self.database) as uow:
            case = uow.case_scope.adjust_research_plan(
                plan_response("rpv_2", version=2, previous_version_id="rpv_1", binding_id="kssb_2"),
                expected_case_revision=5,
                updated_at=NOW + timedelta(hours=2),
            )
            self.assertEqual(case.revision, 6)
            old_plan = uow.case_scope.get_research_plan_version("rpv_1")
            current = uow.case_scope.get_current_research_plan("rp_1")
            self.assertEqual(old_plan.lifecycle_status, VersionLifecycleStatus.superseded)
            self.assertEqual(old_plan.evidence_requirements[0].required_knowledge_scope_source_binding_ids, ["kssb_1"])
            self.assertEqual(current.research_plan_version_id, "rpv_2")
            self.assertEqual(current.evidence_requirements[0].required_knowledge_scope_source_binding_ids, ["kssb_2"])

        with self.assertRaises(ConcurrencyConflictError):
            with UnitOfWork(self.database) as uow:
                uow.case_scope.adjust_research_plan(
                    plan_response("rpv_3", version=3, previous_version_id="rpv_1", binding_id="kssb_2"),
                    expected_case_revision=6,
                    updated_at=NOW + timedelta(hours=3),
                )

    def test_plan_rejects_scope_from_another_case(self) -> None:
        self.seed_adjusted_scope()
        invalid = plan_response(binding_id="kssb_1").model_copy(
            update={"knowledge_scope_version_id": "missing_scope"}
        )
        with self.assertRaises(RecordNotFoundError):
            with UnitOfWork(self.database) as uow:
                uow.case_scope.create_research_plan(
                    invalid,
                    expected_case_revision=4,
                    updated_at=NOW,
                )

    def test_contract_validation_still_guards_bad_minimum_slice_plan(self) -> None:
        payload = plan_response().model_dump()
        payload["research_budget"] = {"max_tokens": 1000}
        with self.assertRaises(ValidationError):
            ResearchPlanVersionResponse(**payload)


if __name__ == "__main__":
    unittest.main()
