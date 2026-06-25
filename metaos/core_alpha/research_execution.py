"""Research Execution command/query handlers for Core Alpha."""

from __future__ import annotations

import uuid
from collections.abc import Callable, Mapping
from datetime import datetime, timezone
from typing import Any

from pydantic import Field

from metaos.core_alpha.commands import ApplicationCommandHandler, CommandExecution, CommandOutcome
from metaos.core_alpha.contracts.common import (
    CommandContext,
    NonEmptyString,
    OpenCodeValue,
    ResourceId,
    Revision,
    StrictContractModel,
)
from metaos.core_alpha.contracts.execution import (
    CancelResearchRunRequest,
    CreateResearchRunRequest,
    ExecutionCheckpointResponse,
    ExecutionCheckpointType,
    ResearchAttemptMode,
    ResearchAttemptResponse,
    ResearchAttemptStatus,
    ResearchRunOutcomeResponse,
    ResearchRunOutcomeType,
    ResearchRunResponse,
    ResearchRunStatus,
    RetrievalOutcome,
    RetrievalRunResponse,
    RetrievalRunStatus,
    RunExecutionSpecResponse,
)
from metaos.core_alpha.contracts.scope import (
    ResearchCaseLifecycleStatus,
    VersionLifecycleStatus,
)
from metaos.core_alpha.persistence import (
    ConcurrencyConflictError,
    CoreAlphaDatabase,
    RecordNotFoundError,
    UnitOfWork,
)
from metaos.core_alpha.persistence.repositories import _utc_iso


Clock = Callable[[], datetime]


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _new_id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex}"


def _code(value: str) -> OpenCodeValue:
    return OpenCodeValue(code=value, registry_version="core-alpha-v1")


class StartResearchAttemptRequest(StrictContractModel):
    expected_run_revision: Revision
    attempt_mode: ResearchAttemptMode


class CreateRetrievalRunRequest(StrictContractModel):
    expected_run_revision: Revision
    research_attempt_id: ResourceId
    knowledge_scope_source_binding_id: ResourceId
    retrieval_channel: OpenCodeValue
    query_ref: ResourceId
    status: RetrievalRunStatus
    retrieval_outcome: RetrievalOutcome | None = None
    index_generation_id: ResourceId | None = None
    failure_reason: NonEmptyString | None = None


class SubmitResearchAttemptResultRequest(StrictContractModel):
    expected_run_revision: Revision
    research_attempt_id: ResourceId
    outcome_type: ResearchRunOutcomeType
    reason_code: OpenCodeValue
    reason_summary: NonEmptyString
    judgment_card_version_id: ResourceId | None = None
    failure_category: OpenCodeValue | None = None
    failure_reason: NonEmptyString | None = None


class ResearchRunCommandData(StrictContractModel):
    research_run: ResearchRunResponse
    run_execution_spec: RunExecutionSpecResponse
    research_attempt: ResearchAttemptResponse | None = None
    execution_checkpoint: ExecutionCheckpointResponse | None = None
    research_run_outcome: ResearchRunOutcomeResponse | None = None


class ResearchAttemptCommandData(StrictContractModel):
    research_run: ResearchRunResponse
    research_attempt: ResearchAttemptResponse


class RetrievalRunCommandData(StrictContractModel):
    research_run: ResearchRunResponse
    research_attempt: ResearchAttemptResponse
    retrieval_run: RetrievalRunResponse


class ResearchRunTraceData(StrictContractModel):
    research_run: ResearchRunResponse
    run_execution_spec: RunExecutionSpecResponse
    attempts: list[ResearchAttemptResponse]
    retrieval_runs: list[RetrievalRunResponse]
    execution_checkpoints: list[ExecutionCheckpointResponse]
    research_run_outcome: ResearchRunOutcomeResponse | None


class ResearchExecutionCommandHandler:
    """Application facade for ResearchRun, Attempt, RetrievalRun, and Outcome."""

    def __init__(
        self,
        command_handler: ApplicationCommandHandler,
        *,
        clock: Clock | None = None,
    ):
        self.command_handler = command_handler
        self.clock = clock or _now

    def start_research_run(
        self,
        research_case_id: str,
        request: CreateResearchRunRequest,
        *,
        context: CommandContext,
        initial_attempt_mode: ResearchAttemptMode = ResearchAttemptMode.retrieval,
    ) -> CommandExecution:
        now = self._now()
        run_id = _new_id("run")
        spec_id = _new_id("rex")
        attempt_id = _new_id("rat")
        checkpoint_id = _new_id("chk")
        body = {
            "request": request.model_dump(mode="json"),
            "initial_attempt_mode": initial_attempt_mode.value,
        }
        return self.command_handler.execute(
            scope=f"{context.actor_id}:POST:/alpha/research-cases/{research_case_id}/research-runs",
            idempotency_key=context.idempotency_key,
            request_body=body,
            context=context,
            callback=lambda uow: self._start_research_run(
                uow=uow,
                research_case_id=research_case_id,
                request=request,
                context=context,
                initial_attempt_mode=initial_attempt_mode,
                run_id=run_id,
                spec_id=spec_id,
                attempt_id=attempt_id,
                checkpoint_id=checkpoint_id,
                now=now,
            ),
        )

    def start_attempt(
        self,
        research_run_id: str,
        request: StartResearchAttemptRequest,
        *,
        context: CommandContext,
    ) -> CommandExecution:
        now = self._now()
        attempt_id = _new_id("rat")
        body = request.model_dump(mode="json")
        return self.command_handler.execute(
            scope=f"{context.actor_id}:POST:/alpha/research-runs/{research_run_id}/attempts",
            idempotency_key=context.idempotency_key,
            request_body=body,
            context=context,
            callback=lambda uow: self._start_attempt(
                uow=uow,
                research_run_id=research_run_id,
                request=request,
                attempt_id=attempt_id,
                now=now,
            ),
        )

    def record_retrieval_run(
        self,
        research_run_id: str,
        request: CreateRetrievalRunRequest,
        *,
        context: CommandContext,
    ) -> CommandExecution:
        now = self._now()
        retrieval_run_id = _new_id("rr")
        body = request.model_dump(mode="json")
        return self.command_handler.execute(
            scope=f"{context.actor_id}:POST:/alpha/research-runs/{research_run_id}/retrieval-runs",
            idempotency_key=context.idempotency_key,
            request_body=body,
            context=context,
            callback=lambda uow: self._record_retrieval_run(
                uow=uow,
                research_run_id=research_run_id,
                request=request,
                retrieval_run_id=retrieval_run_id,
                now=now,
            ),
        )

    def submit_attempt_result(
        self,
        research_run_id: str,
        request: SubmitResearchAttemptResultRequest,
        *,
        context: CommandContext,
    ) -> CommandExecution:
        now = self._now()
        outcome_id = _new_id("rro")
        checkpoint_id = _new_id("chk")
        body = request.model_dump(mode="json")
        return self.command_handler.execute(
            scope=f"{context.actor_id}:POST:/alpha/research-runs/{research_run_id}/commands/submit-result",
            idempotency_key=context.idempotency_key,
            request_body=body,
            context=context,
            callback=lambda uow: self._submit_attempt_result(
                uow=uow,
                research_run_id=research_run_id,
                request=request,
                outcome_id=outcome_id,
                checkpoint_id=checkpoint_id,
                now=now,
            ),
        )

    def cancel_run(
        self,
        research_run_id: str,
        request: CancelResearchRunRequest,
        *,
        context: CommandContext,
    ) -> CommandExecution:
        now = self._now()
        outcome_id = _new_id("rro")
        checkpoint_id = _new_id("chk")
        body = request.model_dump(mode="json")
        return self.command_handler.execute(
            scope=f"{context.actor_id}:POST:/alpha/research-runs/{research_run_id}/commands/cancel",
            idempotency_key=context.idempotency_key,
            request_body=body,
            context=context,
            callback=lambda uow: self._cancel_run(
                uow=uow,
                research_run_id=research_run_id,
                request=request,
                outcome_id=outcome_id,
                checkpoint_id=checkpoint_id,
                now=now,
            ),
        )

    def _start_research_run(
        self,
        *,
        uow: UnitOfWork,
        research_case_id: str,
        request: CreateResearchRunRequest,
        context: CommandContext,
        initial_attempt_mode: ResearchAttemptMode,
        run_id: str,
        spec_id: str,
        attempt_id: str,
        checkpoint_id: str,
        now: datetime,
    ) -> CommandOutcome:
        case = uow.case_scope.get_case(research_case_id)
        self._ensure_open(case)
        if case.revision != request.expected_research_case_revision:
            raise ConcurrencyConflictError(
                f"revision conflict for {research_case_id}: "
                f"expected {request.expected_research_case_revision}"
            )
        question = uow.case_scope.get_question(request.research_question_id)
        if question.research_case_id != research_case_id:
            raise ValueError("research run question must belong to the research case")
        scope = uow.case_scope.get_knowledge_scope_version(request.knowledge_scope_version_id)
        if scope.research_case_id != research_case_id:
            raise ValueError("research run scope must belong to the research case")
        if scope.lifecycle_status != VersionLifecycleStatus.current:
            raise ValueError("research run must bind the current knowledge scope version")
        plan = uow.case_scope.get_research_plan_version(request.research_plan_version_id)
        if plan.research_case_id != research_case_id:
            raise ValueError("research run plan must belong to the research case")
        if plan.knowledge_scope_version_id != scope.knowledge_scope_version_id:
            raise ValueError("research run plan scope must match the bound scope")
        if plan.lifecycle_status != VersionLifecycleStatus.current:
            raise ValueError("research run must bind the current research plan version")

        run = ResearchRunResponse(
            research_run_id=run_id,
            research_case_id=research_case_id,
            research_question_id=request.research_question_id,
            knowledge_scope_version_id=request.knowledge_scope_version_id,
            research_plan_version_id=request.research_plan_version_id,
            run_execution_spec_id=spec_id,
            status=ResearchRunStatus.running,
            revision=1,
            created_at=now,
            started_at=now,
            ended_at=None,
            superseded_by_run_id=None,
        )
        spec = self._execution_spec(
            run=run,
            scope=scope,
            plan_version_id=request.research_plan_version_id,
            spec_id=spec_id,
            execution_mode=request.execution_mode.value,
            created_at=now,
        )
        attempt = ResearchAttemptResponse(
            research_attempt_id=attempt_id,
            research_run_id=run_id,
            attempt_number=1,
            attempt_mode=initial_attempt_mode,
            status=ResearchAttemptStatus.running,
            created_at=now,
            previous_attempt_id=None,
            started_at=now,
            ended_at=None,
            failure_category=None,
            failure_reason=None,
        )
        checkpoint = self._checkpoint(
            checkpoint_id=checkpoint_id,
            run_id=run_id,
            attempt_id=None,
            checkpoint_type=ExecutionCheckpointType.run_started,
            input_revision=run.revision,
            result_ref_id=run_id,
            idempotency_key=f"{context.idempotency_key}:run_started",
            completed_at=now,
        )
        uow.run_evidence.create_research_run(research_run=run, execution_spec=spec)
        uow.run_evidence.add_attempt(attempt)
        uow.run_evidence.put_checkpoint(checkpoint)
        uow.lifecycle.ensure("research_run", run_id, now=now)
        data = ResearchRunCommandData(
            research_run=run,
            run_execution_spec=spec,
            research_attempt=attempt,
            execution_checkpoint=checkpoint,
            research_run_outcome=None,
        )
        return self._run_outcome(
            data=data.model_dump(mode="json"),
            research_run=run,
            event_type_code="research_run_started",
            response_status=201,
        )

    def _start_attempt(
        self,
        *,
        uow: UnitOfWork,
        research_run_id: str,
        request: StartResearchAttemptRequest,
        attempt_id: str,
        now: datetime,
    ) -> CommandOutcome:
        run = uow.run_evidence.get_research_run(research_run_id)
        self._ensure_run_active(run)
        if run.revision != request.expected_run_revision:
            raise ConcurrencyConflictError(
                f"revision conflict for {research_run_id}: expected {request.expected_run_revision}"
            )
        attempts = uow.run_evidence.list_attempts(research_run_id)
        if attempts and attempts[-1].status not in self._terminal_attempt_statuses():
            raise ValueError("cannot start a new attempt while the latest attempt is active")
        previous = attempts[-1] if attempts else None
        attempt = ResearchAttemptResponse(
            research_attempt_id=attempt_id,
            research_run_id=research_run_id,
            attempt_number=1 if previous is None else previous.attempt_number + 1,
            attempt_mode=request.attempt_mode,
            status=ResearchAttemptStatus.running,
            created_at=now,
            previous_attempt_id=previous.research_attempt_id if previous else None,
            started_at=now,
            ended_at=None,
            failure_category=None,
            failure_reason=None,
        )
        uow.run_evidence.add_attempt(attempt)
        next_revision = uow.run_evidence.compare_and_swap_revision(
            research_run_id,
            expected_revision=request.expected_run_revision,
            updates={"status": ResearchRunStatus.running.value},
        )
        updated_run = uow.run_evidence.get_research_run(research_run_id)
        data = ResearchAttemptCommandData(research_run=updated_run, research_attempt=attempt)
        return self._run_outcome(
            data=data.model_dump(mode="json"),
            research_run=updated_run,
            event_type_code="research_attempt_started",
            aggregate_revision=next_revision,
        )

    def _record_retrieval_run(
        self,
        *,
        uow: UnitOfWork,
        research_run_id: str,
        request: CreateRetrievalRunRequest,
        retrieval_run_id: str,
        now: datetime,
    ) -> CommandOutcome:
        run = uow.run_evidence.get_research_run(research_run_id)
        self._ensure_run_active(run)
        if run.revision != request.expected_run_revision:
            raise ConcurrencyConflictError(
                f"revision conflict for {research_run_id}: expected {request.expected_run_revision}"
            )
        attempt = uow.run_evidence.get_attempt(request.research_attempt_id)
        if attempt.research_run_id != research_run_id:
            raise ValueError("retrieval attempt must belong to the research run")
        if attempt.status != ResearchAttemptStatus.running:
            raise ValueError("retrieval records can only be added to a running attempt")
        retrieval_started = now if request.status != RetrievalRunStatus.created else None
        retrieval_ended = (
            now
            if request.status
            in {RetrievalRunStatus.completed, RetrievalRunStatus.failed, RetrievalRunStatus.cancelled}
            else None
        )
        retrieval = RetrievalRunResponse(
            retrieval_run_id=retrieval_run_id,
            research_attempt_id=request.research_attempt_id,
            knowledge_scope_source_binding_id=request.knowledge_scope_source_binding_id,
            retrieval_channel=request.retrieval_channel,
            query_ref=request.query_ref,
            status=request.status,
            retrieval_outcome=request.retrieval_outcome,
            created_at=now,
            index_generation_id=request.index_generation_id,
            started_at=retrieval_started,
            ended_at=retrieval_ended,
            failure_reason=request.failure_reason,
        )
        uow.run_evidence.add_retrieval_run(retrieval)
        data = RetrievalRunCommandData(
            research_run=run,
            research_attempt=attempt,
            retrieval_run=retrieval,
        )
        return self._run_outcome(
            data=data.model_dump(mode="json"),
            research_run=run,
            event_type_code="retrieval_run_recorded",
        )

    def _submit_attempt_result(
        self,
        *,
        uow: UnitOfWork,
        research_run_id: str,
        request: SubmitResearchAttemptResultRequest,
        outcome_id: str,
        checkpoint_id: str,
        now: datetime,
    ) -> CommandOutcome:
        run = uow.run_evidence.get_research_run(research_run_id)
        self._ensure_run_active(run)
        if run.revision != request.expected_run_revision:
            raise ConcurrencyConflictError(
                f"revision conflict for {research_run_id}: expected {request.expected_run_revision}"
            )
        attempt = uow.run_evidence.get_attempt(request.research_attempt_id)
        if attempt.research_run_id != research_run_id:
            raise ValueError("attempt result must belong to the research run")
        if attempt.status != ResearchAttemptStatus.running:
            raise ValueError("only a running attempt can submit a result")
        if request.outcome_type == ResearchRunOutcomeType.execution_failed:
            failure_category = request.failure_category or request.reason_code
            failure_reason = request.failure_reason or request.reason_summary
            self._finish_attempt(
                uow=uow,
                attempt_id=attempt.research_attempt_id,
                status=ResearchAttemptStatus.failed,
                ended_at=now,
                failure_category=failure_category,
                failure_reason=failure_reason,
            )
        else:
            self._finish_attempt(
                uow=uow,
                attempt_id=attempt.research_attempt_id,
                status=ResearchAttemptStatus.completed,
                ended_at=now,
                failure_category=None,
                failure_reason=None,
            )
        outcome = ResearchRunOutcomeResponse(
            research_run_outcome_id=outcome_id,
            research_run_id=research_run_id,
            outcome_type=request.outcome_type,
            reason_code=request.reason_code,
            reason_summary=request.reason_summary,
            created_at=now,
            judgment_card_version_id=request.judgment_card_version_id,
        )
        updated_run = uow.run_evidence.commit_outcome(
            outcome,
            expected_run_revision=request.expected_run_revision,
            ended_at=now,
        )
        checkpoint = self._checkpoint(
            checkpoint_id=checkpoint_id,
            run_id=research_run_id,
            attempt_id=attempt.research_attempt_id,
            checkpoint_type=ExecutionCheckpointType.outcome_committed,
            input_revision=request.expected_run_revision,
            result_ref_id=outcome.research_run_outcome_id,
            idempotency_key=f"{outcome.research_run_outcome_id}:outcome_committed",
            completed_at=now,
        )
        uow.run_evidence.put_checkpoint(checkpoint)
        spec = uow.run_evidence.get_run_execution_spec(run.run_execution_spec_id)
        finished_attempt = uow.run_evidence.get_attempt(attempt.research_attempt_id)
        data = ResearchRunCommandData(
            research_run=updated_run,
            run_execution_spec=spec,
            research_attempt=finished_attempt,
            execution_checkpoint=checkpoint,
            research_run_outcome=outcome,
        )
        return self._run_outcome(
            data=data.model_dump(mode="json"),
            research_run=updated_run,
            event_type_code="research_run_result_submitted",
        )

    def _cancel_run(
        self,
        *,
        uow: UnitOfWork,
        research_run_id: str,
        request: CancelResearchRunRequest,
        outcome_id: str,
        checkpoint_id: str,
        now: datetime,
    ) -> CommandOutcome:
        run = uow.run_evidence.get_research_run(research_run_id)
        self._ensure_run_active(run)
        if run.revision != request.expected_revision:
            raise ConcurrencyConflictError(
                f"revision conflict for {research_run_id}: expected {request.expected_revision}"
            )
        for attempt in uow.run_evidence.list_attempts(research_run_id):
            if attempt.status not in self._terminal_attempt_statuses():
                self._finish_attempt(
                    uow=uow,
                    attempt_id=attempt.research_attempt_id,
                    status=ResearchAttemptStatus.cancelled,
                    ended_at=now,
                    failure_category=None,
                    failure_reason=None,
                )
        outcome = ResearchRunOutcomeResponse(
            research_run_outcome_id=outcome_id,
            research_run_id=research_run_id,
            outcome_type=ResearchRunOutcomeType.cancelled_by_user,
            reason_code=_code("cancelled_by_user"),
            reason_summary=request.reason,
            created_at=now,
            judgment_card_version_id=None,
        )
        updated_run = uow.run_evidence.commit_outcome(
            outcome,
            expected_run_revision=request.expected_revision,
            ended_at=now,
        )
        checkpoint = self._checkpoint(
            checkpoint_id=checkpoint_id,
            run_id=research_run_id,
            attempt_id=None,
            checkpoint_type=ExecutionCheckpointType.outcome_committed,
            input_revision=request.expected_revision,
            result_ref_id=outcome.research_run_outcome_id,
            idempotency_key=f"{outcome.research_run_outcome_id}:outcome_committed",
            completed_at=now,
        )
        uow.run_evidence.put_checkpoint(checkpoint)
        spec = uow.run_evidence.get_run_execution_spec(run.run_execution_spec_id)
        data = ResearchRunCommandData(
            research_run=updated_run,
            run_execution_spec=spec,
            research_attempt=None,
            execution_checkpoint=checkpoint,
            research_run_outcome=outcome,
        )
        return self._run_outcome(
            data=data.model_dump(mode="json"),
            research_run=updated_run,
            event_type_code="research_run_cancelled",
        )

    @staticmethod
    def _execution_spec(
        *,
        run: ResearchRunResponse,
        scope: Any,
        plan_version_id: str,
        spec_id: str,
        execution_mode: str,
        created_at: datetime,
    ) -> RunExecutionSpecResponse:
        source_resolution_ids = [
            binding.source_resolution_id for binding in scope.source_bindings
        ]
        source_version_ids = [
            binding.knowledge_item_version_id
            for binding in scope.source_bindings
            if binding.knowledge_item_version_id is not None
        ]
        return RunExecutionSpecResponse(
            run_execution_spec_id=spec_id,
            research_run_id=run.research_run_id,
            knowledge_scope_version_id=run.knowledge_scope_version_id,
            source_resolution_ids=source_resolution_ids,
            research_plan_version_id=plan_version_id,
            source_version_ids=source_version_ids,
            index_generation_ids=[],
            retrieval_strategy_version="core-alpha-v1-candidate",
            context_strategy_version="core-alpha-context-v1",
            embedding_contract={"implementation": "not_selected"},
            reranker_contract={"enabled": False},
            capability_contracts=[],
            allowed_implementations=[],
            fallback_policy={"execution_mode": execution_mode},
            prompt_version="prompt-not-bound",
            output_schema_version="schema-not-bound",
            audit_policy_version="audit-not-bound",
            decision_fitness_policy_version="decision-fitness-not-bound",
            egress_policy_version="egress-not-bound",
            system_safety_limits={"max_context_chunks": 20},
            created_at=created_at,
            budget_snapshot_id=None,
        )

    @staticmethod
    def _checkpoint(
        *,
        checkpoint_id: str,
        run_id: str,
        attempt_id: str | None,
        checkpoint_type: ExecutionCheckpointType,
        input_revision: int,
        result_ref_id: str,
        idempotency_key: str,
        completed_at: datetime,
    ) -> ExecutionCheckpointResponse:
        return ExecutionCheckpointResponse(
            execution_checkpoint_id=checkpoint_id,
            research_run_id=run_id,
            checkpoint_type=checkpoint_type,
            input_revision=input_revision,
            completed_at=completed_at,
            result_ref_id=result_ref_id,
            idempotency_key=idempotency_key,
            research_attempt_id=attempt_id,
        )

    @staticmethod
    def _finish_attempt(
        *,
        uow: UnitOfWork,
        attempt_id: str,
        status: ResearchAttemptStatus,
        ended_at: datetime,
        failure_category: OpenCodeValue | None,
        failure_reason: str | None,
    ) -> None:
        if status == ResearchAttemptStatus.failed and (
            failure_category is None or failure_reason is None
        ):
            raise ValueError("failed attempts require failure details")
        if status != ResearchAttemptStatus.failed and (
            failure_category is not None or failure_reason is not None
        ):
            raise ValueError("failure details are only valid for failed attempts")
        terminal = {status.value for status in ResearchExecutionCommandHandler._terminal_attempt_statuses()}
        cursor = uow.connection.execute(
            f"""
            UPDATE core_alpha_research_attempts
            SET status = ?, ended_at = ?,
                failure_category_code = ?,
                failure_category_registry_version = ?,
                failure_reason = ?
            WHERE research_attempt_id = ?
              AND status NOT IN ({','.join('?' for _ in terminal)})
            """,
            (
                status.value,
                _utc_iso(ended_at),
                failure_category.code if failure_category else None,
                failure_category.registry_version if failure_category else None,
                failure_reason,
                attempt_id,
                *terminal,
            ),
        )
        if cursor.rowcount != 1:
            try:
                uow.run_evidence.get_attempt(attempt_id)
            except RecordNotFoundError:
                raise
            raise ConcurrencyConflictError("research attempt is already terminal")

    @staticmethod
    def _ensure_open(case: Any) -> None:
        if case.lifecycle_status != ResearchCaseLifecycleStatus.open:
            raise ValueError("research case is not open")

    @staticmethod
    def _ensure_run_active(run: ResearchRunResponse) -> None:
        if run.status in {
            ResearchRunStatus.completed,
            ResearchRunStatus.failed,
            ResearchRunStatus.cancelled,
            ResearchRunStatus.superseded,
        }:
            raise ConcurrencyConflictError("research run is already terminal")

    @staticmethod
    def _terminal_attempt_statuses() -> set[ResearchAttemptStatus]:
        return {
            ResearchAttemptStatus.completed,
            ResearchAttemptStatus.failed,
            ResearchAttemptStatus.cancelled,
            ResearchAttemptStatus.stale,
        }

    def _now(self) -> datetime:
        value = self.clock()
        if value.utcoffset() is None or value.utcoffset().total_seconds() != 0:
            raise ValueError("research execution clock must return UTC datetimes")
        return value.astimezone(timezone.utc)

    @staticmethod
    def _run_outcome(
        *,
        data: Mapping[str, Any],
        research_run: ResearchRunResponse,
        event_type_code: str,
        response_status: int = 200,
        aggregate_revision: int | None = None,
    ) -> CommandOutcome:
        return CommandOutcome(
            data=data,
            primary_aggregate_type="research_run",
            primary_aggregate_id=research_run.research_run_id,
            primary_aggregate_revision=aggregate_revision or research_run.revision,
            response_status=response_status,
            event_type_code=event_type_code,
            event_payload={"research_run_id": research_run.research_run_id},
        )


class ResearchExecutionQueryHandler:
    """Read-side facade for ResearchRun execution records and public trace."""

    def __init__(self, database: CoreAlphaDatabase):
        self.database = database

    def get_research_run(self, research_run_id: str) -> ResearchRunResponse:
        with UnitOfWork(self.database, write=False) as uow:
            return uow.run_evidence.get_research_run(research_run_id)

    def get_run_execution_spec(self, run_execution_spec_id: str) -> RunExecutionSpecResponse:
        with UnitOfWork(self.database, write=False) as uow:
            return uow.run_evidence.get_run_execution_spec(run_execution_spec_id)

    def list_attempts(self, research_run_id: str) -> list[ResearchAttemptResponse]:
        with UnitOfWork(self.database, write=False) as uow:
            uow.run_evidence.get_research_run(research_run_id)
            return uow.run_evidence.list_attempts(research_run_id)

    def list_retrieval_runs(self, research_attempt_id: str) -> list[RetrievalRunResponse]:
        with UnitOfWork(self.database, write=False) as uow:
            uow.run_evidence.get_attempt(research_attempt_id)
            return uow.run_evidence.list_retrieval_runs(research_attempt_id)

    def get_outcome(self, research_run_id: str) -> ResearchRunOutcomeResponse | None:
        with UnitOfWork(self.database, write=False) as uow:
            try:
                return uow.run_evidence.get_outcome(research_run_id)
            except RecordNotFoundError:
                return None

    def get_public_trace(self, research_run_id: str) -> ResearchRunTraceData:
        with UnitOfWork(self.database, write=False) as uow:
            run = uow.run_evidence.get_research_run(research_run_id)
            spec = uow.run_evidence.get_run_execution_spec(run.run_execution_spec_id)
            attempts = uow.run_evidence.list_attempts(research_run_id)
            retrievals: list[RetrievalRunResponse] = []
            for attempt in attempts:
                retrievals.extend(uow.run_evidence.list_retrieval_runs(attempt.research_attempt_id))
            checkpoints = self._list_checkpoints(uow, research_run_id)
            try:
                outcome = uow.run_evidence.get_outcome(research_run_id)
            except RecordNotFoundError:
                outcome = None
            return ResearchRunTraceData(
                research_run=run,
                run_execution_spec=spec,
                attempts=attempts,
                retrieval_runs=retrievals,
                execution_checkpoints=checkpoints,
                research_run_outcome=outcome,
            )

    @staticmethod
    def _list_checkpoints(
        uow: UnitOfWork,
        research_run_id: str,
    ) -> list[ExecutionCheckpointResponse]:
        rows = uow.connection.execute(
            """
            SELECT execution_checkpoint_id
            FROM core_alpha_execution_checkpoints
            WHERE research_run_id = ?
            ORDER BY completed_at, execution_checkpoint_id
            """,
            (research_run_id,),
        ).fetchall()
        return [
            uow.run_evidence.get_checkpoint(row["execution_checkpoint_id"])
            for row in rows
        ]


__all__ = [
    "CreateRetrievalRunRequest",
    "ResearchExecutionCommandHandler",
    "ResearchExecutionQueryHandler",
    "ResearchRunCommandData",
    "ResearchRunTraceData",
    "RetrievalRunCommandData",
    "StartResearchAttemptRequest",
    "SubmitResearchAttemptResultRequest",
]
