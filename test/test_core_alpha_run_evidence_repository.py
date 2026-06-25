from __future__ import annotations

import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

from metaos.core_alpha.contracts.common import OpenCodeValue
from metaos.core_alpha.contracts.execution import (
    EvidenceLocation,
    EvidenceUnitResponse,
    EvidenceValidityStatus,
    ExecutionCheckpointResponse,
    ResearchAttemptResponse,
    ResearchEvidenceUseResponse,
    ResearchRunOutcomeResponse,
    ResearchRunResponse,
    RetrievalRunResponse,
    RunExecutionSpecResponse,
)
from metaos.core_alpha.contracts.scope import (
    EvidenceRequirementResponse,
    KnowledgeScopeSourceBindingResponse,
    KnowledgeScopeVersionResponse,
    ResearchCaseResponse,
    ResearchPlanVersionResponse,
    ResearchQuestionResponse,
    SourceResolutionResponse,
)
from metaos.core_alpha.persistence import (
    ConcurrencyConflictError,
    CoreAlphaDatabase,
    IdempotencyConflictError,
    RecordNotFoundError,
    UnitOfWork,
)


NOW = datetime(2026, 6, 25, 8, 0, tzinfo=timezone.utc)


def code(value: str) -> OpenCodeValue:
    return OpenCodeValue(code=value, registry_version="core-alpha-v1")


def case_response() -> ResearchCaseResponse:
    return ResearchCaseResponse(
        research_case_id="case_1",
        title="Run evidence case",
        root_question_id="rq_1",
        current_question_id="rq_1",
        lifecycle_status="open",
        attention_status="active",
        revision=1,
        created_at=NOW,
        updated_at=NOW,
        current_knowledge_scope_version_id=None,
        current_judgment_card_version_id=None,
        current_research_disposition_id=None,
        parent_research_case_id=None,
        archived_at=None,
    )


def question_response() -> ResearchQuestionResponse:
    return ResearchQuestionResponse(
        research_question_id="rq_1",
        research_case_id="case_1",
        question_text="Evaluate the claim using the selected source.",
        question_role="root",
        created_by="user_1",
        created_at=NOW,
        parent_question_id=None,
    )


def source_resolution() -> SourceResolutionResponse:
    return SourceResolutionResponse(
        source_resolution_id="sr_1",
        research_question_id="rq_1",
        resolution_stage="full",
        raw_anchor="Guiguzi",
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


def scope_binding(binding_id: str = "kssb_1") -> KnowledgeScopeSourceBindingResponse:
    return KnowledgeScopeSourceBindingResponse(
        knowledge_scope_source_binding_id=binding_id,
        knowledge_scope_version_id="ksv_1",
        source_resolution_id="sr_1",
        knowledge_item_id="ki_1",
        knowledge_item_version_id="kiv_1",
        access_policy="required",
        analysis_role="primary",
        created_at=NOW,
    )


def scope_response() -> KnowledgeScopeVersionResponse:
    return KnowledgeScopeVersionResponse(
        knowledge_scope_id="ks_1",
        knowledge_scope_version_id="ksv_1",
        research_case_id="case_1",
        version=1,
        lifecycle_status="current",
        scope_mode="evidence_only",
        default_access_policy="excluded",
        source_bindings=[scope_binding()],
        created_by="user_1",
        created_at=NOW,
        previous_version_id=None,
    )


def requirement() -> EvidenceRequirementResponse:
    return EvidenceRequirementResponse(
        evidence_requirement_id="er_1",
        requirement_type=code("direct_support"),
        description="Find direct support.",
        required_knowledge_scope_source_binding_ids=["kssb_1"],
        counterevidence_required=True,
        alternative_interpretation_required=False,
        completion_condition="Required source reaches terminal coverage.",
        minimum_count=1,
    )


def plan_response() -> ResearchPlanVersionResponse:
    return ResearchPlanVersionResponse(
        research_plan_id="rp_1",
        research_plan_version_id="rpv_1",
        research_case_id="case_1",
        knowledge_scope_version_id="ksv_1",
        version=1,
        lifecycle_status="current",
        research_mode="claim_evaluation",
        primary_objective="Evaluate the claim.",
        evidence_requirements=[requirement()],
        minimum_completion_condition="Mandatory evidence terminal.",
        created_at=NOW,
        previous_version_id=None,
        stop_conditions=None,
        research_budget=None,
    )


def run_response(**updates: object) -> ResearchRunResponse:
    payload: dict[str, object] = {
        "research_run_id": "run_1",
        "research_case_id": "case_1",
        "research_question_id": "rq_1",
        "knowledge_scope_version_id": "ksv_1",
        "research_plan_version_id": "rpv_1",
        "run_execution_spec_id": "spec_1",
        "status": "running",
        "revision": 1,
        "created_at": NOW + timedelta(minutes=1),
        "started_at": NOW + timedelta(minutes=1),
        "ended_at": None,
        "superseded_by_run_id": None,
    }
    payload.update(updates)
    return ResearchRunResponse.model_validate(payload)


def execution_spec(**updates: object) -> RunExecutionSpecResponse:
    payload: dict[str, object] = {
        "run_execution_spec_id": "spec_1",
        "research_run_id": "run_1",
        "knowledge_scope_version_id": "ksv_1",
        "source_resolution_ids": ["sr_1"],
        "research_plan_version_id": "rpv_1",
        "source_version_ids": ["kiv_1"],
        "index_generation_ids": ["idx_1"],
        "retrieval_strategy_version": "core-alpha-v1-candidate",
        "context_strategy_version": "core-alpha-context-v1",
        "embedding_contract": {"provider": "local"},
        "reranker_contract": {"enabled": False},
        "capability_contracts": [{"capability": "fulltext"}],
        "allowed_implementations": ["sqlite-fts5"],
        "fallback_policy": {"fulltext_only": True},
        "prompt_version": "prompt-v1",
        "output_schema_version": "schema-v1",
        "audit_policy_version": "audit-v1",
        "decision_fitness_policy_version": "fitness-v1",
        "egress_policy_version": "egress-v1",
        "system_safety_limits": {"max_context_chunks": 20},
        "created_at": NOW + timedelta(minutes=1),
        "budget_snapshot_id": None,
    }
    payload.update(updates)
    return RunExecutionSpecResponse.model_validate(payload)


def attempt_response(**updates: object) -> ResearchAttemptResponse:
    payload: dict[str, object] = {
        "research_attempt_id": "attempt_1",
        "research_run_id": "run_1",
        "attempt_number": 1,
        "attempt_mode": "retrieval",
        "status": "completed",
        "created_at": NOW + timedelta(minutes=2),
        "previous_attempt_id": None,
        "started_at": NOW + timedelta(minutes=2),
        "ended_at": NOW + timedelta(minutes=3),
        "failure_category": None,
        "failure_reason": None,
    }
    payload.update(updates)
    return ResearchAttemptResponse.model_validate(payload)


def retrieval_response(**updates: object) -> RetrievalRunResponse:
    payload: dict[str, object] = {
        "retrieval_run_id": "retrieval_1",
        "research_attempt_id": "attempt_1",
        "knowledge_scope_source_binding_id": "kssb_1",
        "retrieval_channel": code("fulltext"),
        "query_ref": "query_1",
        "status": "completed",
        "retrieval_outcome": "completed_with_candidates",
        "created_at": NOW + timedelta(minutes=2),
        "index_generation_id": "idx_1",
        "started_at": NOW + timedelta(minutes=2),
        "ended_at": NOW + timedelta(minutes=3),
        "failure_reason": None,
    }
    payload.update(updates)
    return RetrievalRunResponse.model_validate(payload)


def evidence_unit(**updates: object) -> EvidenceUnitResponse:
    payload: dict[str, object] = {
        "evidence_unit_id": "eu_1",
        "knowledge_item_id": "ki_1",
        "knowledge_item_version_id": "kiv_1",
        "location": EvidenceLocation(
            section_path=["chapter_1"],
            page=1,
            timestamp_seconds=None,
            start_offset=10,
            end_offset=40,
        ),
        "excerpt": "The source sentence used as evidence.",
        "content_hash": "sha256:aaaaaaaa",
        "origin_type": code("retrieval"),
        "validity_status": "valid",
        "revision": 1,
        "created_at": NOW + timedelta(minutes=3),
        "updated_at": NOW + timedelta(minutes=3),
        "chunk_id": "chunk_1",
        "origin_retrieval_run_id": "retrieval_1",
    }
    payload.update(updates)
    return EvidenceUnitResponse.model_validate(payload)


def evidence_use(**updates: object) -> ResearchEvidenceUseResponse:
    payload: dict[str, object] = {
        "research_evidence_use_id": "reu_1",
        "research_run_id": "run_1",
        "research_attempt_id": "attempt_1",
        "evidence_unit_id": "eu_1",
        "evidence_revision": 1,
        "knowledge_scope_version_id": "ksv_1",
        "use_type": "retrieved",
        "validity_checked_at": NOW + timedelta(minutes=3),
        "validity_result": "valid",
        "created_at": NOW + timedelta(minutes=3),
        "retrieval_run_id": "retrieval_1",
    }
    payload.update(updates)
    return ResearchEvidenceUseResponse.model_validate(payload)


def outcome_response(**updates: object) -> ResearchRunOutcomeResponse:
    payload: dict[str, object] = {
        "research_run_outcome_id": "outcome_1",
        "research_run_id": "run_1",
        "outcome_type": "insufficient_evidence",
        "reason_code": code("required_source_no_evidence"),
        "reason_summary": "Required source reached terminal state without enough evidence.",
        "created_at": NOW + timedelta(minutes=4),
        "judgment_card_version_id": None,
    }
    payload.update(updates)
    return ResearchRunOutcomeResponse.model_validate(payload)


class CoreAlphaRunEvidenceRepositoryTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.database = CoreAlphaDatabase(Path(self.temp_dir.name) / "core-alpha.db")
        self.database.initialize()
        self.seed_case_scope_plan()

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

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

    def seed_run(self) -> None:
        with UnitOfWork(self.database) as uow:
            uow.run_evidence.create_research_run(
                research_run=run_response(),
                execution_spec=execution_spec(),
            )

    def seed_attempt_and_retrieval(self) -> None:
        self.seed_run()
        with UnitOfWork(self.database) as uow:
            uow.run_evidence.add_attempt(attempt_response())
            uow.run_evidence.add_retrieval_run(retrieval_response())

    def test_create_run_with_immutable_execution_spec(self) -> None:
        self.seed_run()
        with UnitOfWork(self.database, write=False) as uow:
            run = uow.run_evidence.get_research_run("run_1")
            spec = uow.run_evidence.get_run_execution_spec("spec_1")
            self.assertEqual(run.research_case_id, "case_1")
            self.assertEqual(spec.source_resolution_ids, ["sr_1"])
            self.assertEqual(spec.system_safety_limits["max_context_chunks"], 20)

        with self.assertRaises(ValueError):
            with UnitOfWork(self.database) as uow:
                uow.run_evidence.create_research_run(
                    research_run=run_response(
                        research_run_id="run_bad",
                        run_execution_spec_id="spec_bad",
                    ),
                    execution_spec=execution_spec(
                        run_execution_spec_id="spec_bad",
                        research_run_id="run_bad",
                        research_plan_version_id="missing_plan",
                    ),
                )

    def test_attempt_retrieval_and_binding_validation(self) -> None:
        self.seed_run()
        with UnitOfWork(self.database) as uow:
            uow.run_evidence.add_attempt(attempt_response())
            uow.run_evidence.add_retrieval_run(retrieval_response())

        with UnitOfWork(self.database, write=False) as uow:
            attempts = uow.run_evidence.list_attempts("run_1")
            retrievals = uow.run_evidence.list_retrieval_runs("attempt_1")
            self.assertEqual([attempt.research_attempt_id for attempt in attempts], ["attempt_1"])
            self.assertEqual([retrieval.retrieval_run_id for retrieval in retrievals], ["retrieval_1"])

        with self.assertRaises(RecordNotFoundError):
            with UnitOfWork(self.database) as uow:
                uow.run_evidence.add_retrieval_run(
                    retrieval_response(
                        retrieval_run_id="retrieval_bad",
                        knowledge_scope_source_binding_id="missing_binding",
                    )
                )

    def test_outcome_commit_is_atomic_with_terminal_run_state(self) -> None:
        self.seed_run()
        with self.assertRaises(ConcurrencyConflictError):
            with UnitOfWork(self.database) as uow:
                uow.run_evidence.commit_outcome(
                    outcome_response(),
                    expected_run_revision=9,
                    ended_at=NOW + timedelta(minutes=4),
                )
        with UnitOfWork(self.database, write=False) as uow:
            with self.assertRaises(RecordNotFoundError):
                uow.run_evidence.get_outcome("run_1")
            self.assertEqual(uow.run_evidence.get_research_run("run_1").status, "running")

        with UnitOfWork(self.database) as uow:
            run = uow.run_evidence.commit_outcome(
                outcome_response(),
                expected_run_revision=1,
                ended_at=NOW + timedelta(minutes=4),
            )
            self.assertEqual(run.status, "completed")
            self.assertEqual(run.revision, 2)

        with UnitOfWork(self.database, write=False) as uow:
            outcome = uow.run_evidence.get_outcome("run_1")
            self.assertEqual(outcome.outcome_type, "insufficient_evidence")

    def test_execution_checkpoint_is_idempotent(self) -> None:
        self.seed_attempt_and_retrieval()
        checkpoint = ExecutionCheckpointResponse(
            execution_checkpoint_id="checkpoint_1",
            research_run_id="run_1",
            checkpoint_type="retrieval_completed",
            input_revision=1,
            completed_at=NOW + timedelta(minutes=3),
            result_ref_id="retrieval_1",
            idempotency_key="checkpoint-idem-1",
            research_attempt_id="attempt_1",
        )
        with UnitOfWork(self.database) as uow:
            created = uow.run_evidence.put_checkpoint(checkpoint)
            replayed = uow.run_evidence.put_checkpoint(checkpoint)
            self.assertEqual(created, replayed)
            with self.assertRaises(IdempotencyConflictError):
                uow.run_evidence.put_checkpoint(
                    checkpoint.model_copy(update={"result_ref_id": "other_result"})
                )

    def test_evidence_unit_deduplicates_identity_and_tracks_validity_revision(self) -> None:
        self.seed_attempt_and_retrieval()
        with UnitOfWork(self.database) as uow:
            created = uow.run_evidence.create_evidence_unit(evidence_unit())
            duplicate = uow.run_evidence.create_evidence_unit(
                evidence_unit(evidence_unit_id="eu_duplicate")
            )
            self.assertEqual(created.evidence_unit_id, "eu_1")
            self.assertEqual(duplicate.evidence_unit_id, "eu_1")
            updated = uow.run_evidence.update_evidence_validity(
                "eu_1",
                expected_revision=1,
                validity_status=EvidenceValidityStatus.needs_review,
                updated_at=NOW + timedelta(minutes=5),
            )
            self.assertEqual(updated.revision, 2)
            self.assertEqual(updated.validity_status, "needs_review")

        with self.assertRaises(ConcurrencyConflictError):
            with UnitOfWork(self.database) as uow:
                uow.run_evidence.update_evidence_validity(
                    "eu_1",
                    expected_revision=1,
                    validity_status=EvidenceValidityStatus.invalid,
                    updated_at=NOW + timedelta(minutes=6),
                )

    def test_research_evidence_use_records_current_revision_snapshot(self) -> None:
        self.seed_attempt_and_retrieval()
        with UnitOfWork(self.database) as uow:
            uow.run_evidence.create_evidence_unit(evidence_unit())
            uow.run_evidence.add_research_evidence_use(evidence_use())
            uses = uow.run_evidence.list_research_evidence_uses("run_1")
            self.assertEqual([use.research_evidence_use_id for use in uses], ["reu_1"])
            self.assertEqual(uses[0].retrieval_run_id, "retrieval_1")

        with self.assertRaises(ConcurrencyConflictError):
            with UnitOfWork(self.database) as uow:
                uow.run_evidence.add_research_evidence_use(
                    evidence_use(
                        research_evidence_use_id="reu_stale",
                        evidence_revision=2,
                    )
                )

        with UnitOfWork(self.database) as uow:
            uow.run_evidence.add_attempt(
                attempt_response(
                    research_attempt_id="attempt_2",
                    attempt_number=2,
                    attempt_mode="reuse_existing_evidence",
                    previous_attempt_id="attempt_1",
                    created_at=NOW + timedelta(minutes=6),
                    started_at=NOW + timedelta(minutes=6),
                    ended_at=NOW + timedelta(minutes=7),
                )
            )
            uow.run_evidence.add_research_evidence_use(
                evidence_use(
                    research_evidence_use_id="reu_reused",
                    research_attempt_id="attempt_2",
                    use_type="reused",
                    retrieval_run_id=None,
                    created_at=NOW + timedelta(minutes=7),
                    validity_checked_at=NOW + timedelta(minutes=7),
                )
            )
            uses = uow.run_evidence.list_research_evidence_uses("run_1")
            self.assertEqual([use.use_type.value for use in uses], ["retrieved", "reused"])


if __name__ == "__main__":
    unittest.main()
