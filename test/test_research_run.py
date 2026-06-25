from __future__ import annotations

import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

from metaos.core_alpha.commands import ApplicationCommandHandler
from metaos.core_alpha.contracts.common import CommandContext, OpenCodeValue
from metaos.core_alpha.contracts.execution import (
    CancelResearchRunRequest,
    CreateResearchRunRequest,
    ExecutionMode,
    ResearchAttemptMode,
    ResearchRunOutcomeType,
    RetrievalOutcome,
    RetrievalRunStatus,
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
    RecordNotFoundError,
    UnitOfWork,
)
from metaos.core_alpha.research_execution import (
    CreateRetrievalRunRequest,
    ResearchExecutionCommandHandler,
    ResearchExecutionQueryHandler,
    SubmitResearchAttemptResultRequest,
)


NOW = datetime(2026, 6, 25, 10, 0, tzinfo=timezone.utc)


def code(value: str) -> OpenCodeValue:
    return OpenCodeValue(code=value, registry_version="core-alpha-v1")


def context(command_id: str, *, idempotency_key: str) -> CommandContext:
    return CommandContext(
        command_id=command_id,
        actor_type=code("user"),
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
        value = NOW + timedelta(minutes=self.offset)
        self.offset += 1
        return value


def case_response(**updates: object) -> ResearchCaseResponse:
    payload: dict[str, object] = {
        "research_case_id": "case_1",
        "title": "Run lifecycle case",
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


def question_response() -> ResearchQuestionResponse:
    return ResearchQuestionResponse(
        research_question_id="rq_1",
        research_case_id="case_1",
        question_text="Evaluate the claim using this source.",
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
        raw_anchor="source one",
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


def scope_binding() -> KnowledgeScopeSourceBindingResponse:
    return KnowledgeScopeSourceBindingResponse(
        knowledge_scope_source_binding_id="kssb_1",
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


class ResearchExecutionTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.database = CoreAlphaDatabase(Path(self.temp_dir.name) / "core-alpha.db")
        self.database.initialize()
        self.clock = FixedClock()
        self.commands = ResearchExecutionCommandHandler(
            ApplicationCommandHandler(self.database),
            clock=self.clock,
        )
        self.queries = ResearchExecutionQueryHandler(self.database)
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

    def start_run(
        self,
        *,
        idempotency_key: str = "idem_start_run",
        initial_attempt_mode: ResearchAttemptMode = ResearchAttemptMode.retrieval,
    ) -> dict:
        response = self.commands.start_research_run(
            "case_1",
            CreateResearchRunRequest(
                expected_research_case_revision=4,
                research_question_id="rq_1",
                knowledge_scope_version_id="ksv_1",
                research_plan_version_id="rpv_1",
                execution_mode=ExecutionMode.synchronous,
            ),
            context=context(f"cmd_start_{idempotency_key}", idempotency_key=idempotency_key),
            initial_attempt_mode=initial_attempt_mode,
        )
        self.assertEqual(response.status_code, 201)
        return dict(response.response_body["data"])

    def submit_insufficient(
        self,
        run_id: str,
        attempt_id: str,
        *,
        expected_revision: int = 1,
        idempotency_key: str = "idem_submit_result",
    ) -> dict:
        response = self.commands.submit_attempt_result(
            run_id,
            SubmitResearchAttemptResultRequest(
                expected_run_revision=expected_revision,
                research_attempt_id=attempt_id,
                outcome_type=ResearchRunOutcomeType.insufficient_evidence,
                reason_code=code("required_source_no_evidence"),
                reason_summary="Required source reached terminal state without enough evidence.",
            ),
            context=context(f"cmd_submit_{idempotency_key}", idempotency_key=idempotency_key),
        )
        self.assertEqual(response.status_code, 200)
        return dict(response.response_body["data"])

    def test_start_run_is_idempotent_and_creates_spec_attempt_checkpoint(self) -> None:
        first = self.commands.start_research_run(
            "case_1",
            CreateResearchRunRequest(
                expected_research_case_revision=4,
                research_question_id="rq_1",
                knowledge_scope_version_id="ksv_1",
                research_plan_version_id="rpv_1",
                execution_mode=ExecutionMode.synchronous,
            ),
            context=context("cmd_start_1", idempotency_key="idem_start_once"),
        )
        replay = self.commands.start_research_run(
            "case_1",
            CreateResearchRunRequest(
                expected_research_case_revision=4,
                research_question_id="rq_1",
                knowledge_scope_version_id="ksv_1",
                research_plan_version_id="rpv_1",
                execution_mode=ExecutionMode.synchronous,
            ),
            context=context("cmd_start_2", idempotency_key="idem_start_once"),
        )

        self.assertEqual(first.status_code, 201)
        self.assertEqual(replay.status_code, 201)
        self.assertFalse(first.response_body["command"]["idempotent_replay"])
        self.assertTrue(replay.response_body["command"]["idempotent_replay"])
        self.assertEqual(first.response_body["data"], replay.response_body["data"])

        run = first.response_body["data"]["research_run"]
        spec = first.response_body["data"]["run_execution_spec"]
        attempt = first.response_body["data"]["research_attempt"]
        self.assertEqual(run["status"], "running")
        self.assertEqual(spec["source_resolution_ids"], ["sr_1"])
        self.assertEqual(spec["source_version_ids"], ["kiv_1"])
        self.assertEqual(attempt["attempt_number"], 1)
        self.assertEqual(attempt["status"], "running")

        trace = self.queries.get_public_trace(run["research_run_id"])
        self.assertEqual(len(trace.attempts), 1)
        self.assertEqual(len(trace.execution_checkpoints), 1)
        self.assertEqual(trace.execution_checkpoints[0].checkpoint_type.value, "run_started")
        with UnitOfWork(self.database, write=False) as uow:
            events = uow.events.list_for_aggregate("research_run", run["research_run_id"])
            self.assertEqual([event.event_type_code for event in events], ["research_run_started"])
            lifecycle = uow.lifecycle.get("research_run", run["research_run_id"])
            self.assertEqual(lifecycle.generation, 1)

    def test_start_run_rejects_stale_case_revision_or_archived_case(self) -> None:
        with self.assertRaises(ConcurrencyConflictError):
            self.commands.start_research_run(
                "case_1",
                CreateResearchRunRequest(
                    expected_research_case_revision=3,
                    research_question_id="rq_1",
                    knowledge_scope_version_id="ksv_1",
                    research_plan_version_id="rpv_1",
                ),
                context=context("cmd_stale_start", idempotency_key="idem_stale_start"),
            )

        with UnitOfWork(self.database) as uow:
            uow.case_scope.compare_and_swap_revision(
                "case_1",
                expected_revision=4,
                updates={
                    "lifecycle_status": "archived",
                    "attention_status": "closed",
                    "updated_at": (NOW + timedelta(minutes=1)).isoformat(),
                    "archived_at": (NOW + timedelta(minutes=1)).isoformat(),
                },
            )
        with self.assertRaises(ValueError):
            self.commands.start_research_run(
                "case_1",
                CreateResearchRunRequest(
                    expected_research_case_revision=5,
                    research_question_id="rq_1",
                    knowledge_scope_version_id="ksv_1",
                    research_plan_version_id="rpv_1",
                ),
                context=context("cmd_archived_start", idempotency_key="idem_archived_start"),
            )

    def test_record_retrieval_run_is_idempotent_and_binding_checked(self) -> None:
        data = self.start_run()
        run = data["research_run"]
        attempt = data["research_attempt"]
        request = CreateRetrievalRunRequest(
            expected_run_revision=1,
            research_attempt_id=attempt["research_attempt_id"],
            knowledge_scope_source_binding_id="kssb_1",
            retrieval_channel=code("fulltext"),
            query_ref="query_1",
            status=RetrievalRunStatus.completed,
            retrieval_outcome=RetrievalOutcome.no_evidence,
            index_generation_id="idx_1",
        )

        first = self.commands.record_retrieval_run(
            run["research_run_id"],
            request,
            context=context("cmd_retrieval_1", idempotency_key="idem_retrieval_once"),
        )
        replay = self.commands.record_retrieval_run(
            run["research_run_id"],
            request,
            context=context("cmd_retrieval_2", idempotency_key="idem_retrieval_once"),
        )

        self.assertFalse(first.response_body["command"]["idempotent_replay"])
        self.assertTrue(replay.response_body["command"]["idempotent_replay"])
        self.assertEqual(first.response_body["data"], replay.response_body["data"])
        retrievals = self.queries.list_retrieval_runs(attempt["research_attempt_id"])
        self.assertEqual(len(retrievals), 1)
        self.assertEqual(retrievals[0].retrieval_outcome.value, "no_evidence")

        with self.assertRaises(RecordNotFoundError):
            self.commands.record_retrieval_run(
                run["research_run_id"],
                request.model_copy(update={"knowledge_scope_source_binding_id": "missing"}),
                context=context("cmd_bad_retrieval", idempotency_key="idem_bad_retrieval"),
            )

    def test_submit_result_commits_outcome_atomically_and_rejects_stale(self) -> None:
        data = self.start_run()
        run_id = data["research_run"]["research_run_id"]
        attempt_id = data["research_attempt"]["research_attempt_id"]

        with self.assertRaises(ConcurrencyConflictError):
            self.submit_insufficient(
                run_id,
                attempt_id,
                expected_revision=9,
                idempotency_key="idem_submit_stale",
            )
        self.assertIsNone(self.queries.get_outcome(run_id))
        self.assertEqual(self.queries.list_attempts(run_id)[0].status.value, "running")

        result = self.submit_insufficient(run_id, attempt_id)
        self.assertEqual(result["research_run"]["status"], "completed")
        self.assertEqual(result["research_run"]["revision"], 2)
        self.assertEqual(result["research_attempt"]["status"], "completed")
        self.assertEqual(result["research_run_outcome"]["outcome_type"], "insufficient_evidence")

        trace = self.queries.get_public_trace(run_id)
        self.assertEqual(trace.research_run_outcome.outcome_type.value, "insufficient_evidence")
        self.assertEqual(
            [checkpoint.checkpoint_type.value for checkpoint in trace.execution_checkpoints],
            ["run_started", "outcome_committed"],
        )
        with self.assertRaises(ConcurrencyConflictError):
            self.submit_insufficient(
                run_id,
                attempt_id,
                expected_revision=2,
                idempotency_key="idem_submit_after_terminal",
            )

    def test_cancel_marks_run_and_active_attempts_cancelled(self) -> None:
        data = self.start_run()
        run_id = data["research_run"]["research_run_id"]
        response = self.commands.cancel_run(
            run_id,
            CancelResearchRunRequest(
                expected_revision=1,
                reason="User cancelled the run.",
            ),
            context=context("cmd_cancel", idempotency_key="idem_cancel"),
        )

        self.assertEqual(response.status_code, 200)
        payload = response.response_body["data"]
        self.assertEqual(payload["research_run"]["status"], "cancelled")
        self.assertEqual(payload["research_run_outcome"]["outcome_type"], "cancelled_by_user")
        attempts = self.queries.list_attempts(run_id)
        self.assertEqual(attempts[0].status.value, "cancelled")

    def test_zero_retrieval_reuse_attempt_is_legal_and_traceable(self) -> None:
        data = self.start_run(initial_attempt_mode=ResearchAttemptMode.reuse_existing_evidence)
        run_id = data["research_run"]["research_run_id"]
        attempt_id = data["research_attempt"]["research_attempt_id"]
        self.submit_insufficient(run_id, attempt_id)

        trace = self.queries.get_public_trace(run_id)
        self.assertEqual(trace.attempts[0].attempt_mode.value, "reuse_existing_evidence")
        self.assertEqual(trace.retrieval_runs, [])
        self.assertEqual(trace.research_run.status.value, "completed")


if __name__ == "__main__":
    unittest.main()
