"""Case Management command/query handlers for Core Alpha."""

from __future__ import annotations

import uuid
from collections.abc import Callable, Mapping
from datetime import datetime, timezone
from typing import Any

from metaos.core_alpha.commands import ApplicationCommandHandler, CommandExecution, CommandOutcome
from metaos.core_alpha.contracts.common import CommandContext, ResourceReference
from metaos.core_alpha.contracts.scope import (
    AddResearchQuestionRequest,
    AttentionStatus,
    CreateResearchCaseData,
    CreateResearchCaseRequest,
    DeriveResearchCaseData,
    DeriveResearchCaseRequest,
    QuestionRole,
    ResearchCaseLifecycleStatus,
    ResearchCaseResponse,
    ResearchQuestionResponse,
)
from metaos.core_alpha.persistence import (
    ConcurrencyConflictError,
    CoreAlphaDatabase,
    UnitOfWork,
)
from metaos.core_alpha.persistence.repositories import _utc_iso


Clock = Callable[[], datetime]


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _new_id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex}"


class ResearchCaseCommandHandler:
    """Application command facade for the ResearchCase aggregate."""

    def __init__(self, command_handler: ApplicationCommandHandler, *, clock: Clock | None = None):
        self.command_handler = command_handler
        self.clock = clock or _now

    def create_case(
        self,
        request: CreateResearchCaseRequest,
        *,
        context: CommandContext,
    ) -> CommandExecution:
        now = self._now()
        case_id = _new_id("case")
        question_id = _new_id("rq")
        body = request.model_dump(mode="json")
        return self.command_handler.execute(
            scope=f"{context.actor_id}:POST:/alpha/research-cases",
            idempotency_key=context.idempotency_key,
            request_body=body,
            context=context,
            callback=lambda uow: self._create_case(
                uow=uow,
                request=request,
                context=context,
                case_id=case_id,
                question_id=question_id,
                now=now,
            ),
        )

    def add_question(
        self,
        research_case_id: str,
        request: AddResearchQuestionRequest,
        *,
        context: CommandContext,
    ) -> CommandExecution:
        now = self._now()
        question_id = _new_id("rq")
        body = request.model_dump(mode="json")
        return self.command_handler.execute(
            scope=f"{context.actor_id}:POST:/alpha/research-cases/{research_case_id}/questions",
            idempotency_key=context.idempotency_key,
            request_body=body,
            context=context,
            callback=lambda uow: self._add_question(
                uow=uow,
                research_case_id=research_case_id,
                request=request,
                context=context,
                question_id=question_id,
                now=now,
            ),
        )

    def archive_case(
        self,
        research_case_id: str,
        *,
        expected_revision: int,
        context: CommandContext,
    ) -> CommandExecution:
        now = self._now()
        body = {"expected_revision": expected_revision}
        return self.command_handler.execute(
            scope=f"{context.actor_id}:POST:/alpha/research-cases/{research_case_id}/commands/archive",
            idempotency_key=context.idempotency_key,
            request_body=body,
            context=context,
            callback=lambda uow: self._set_archive_state(
                uow=uow,
                research_case_id=research_case_id,
                expected_revision=expected_revision,
                archive=True,
                now=now,
            ),
        )

    def reopen_case(
        self,
        research_case_id: str,
        *,
        expected_revision: int,
        context: CommandContext,
    ) -> CommandExecution:
        now = self._now()
        body = {"expected_revision": expected_revision}
        return self.command_handler.execute(
            scope=f"{context.actor_id}:POST:/alpha/research-cases/{research_case_id}/commands/reopen",
            idempotency_key=context.idempotency_key,
            request_body=body,
            context=context,
            callback=lambda uow: self._set_archive_state(
                uow=uow,
                research_case_id=research_case_id,
                expected_revision=expected_revision,
                archive=False,
                now=now,
            ),
        )

    def derive_case(
        self,
        source_research_case_id: str,
        request: DeriveResearchCaseRequest,
        *,
        context: CommandContext,
    ) -> CommandExecution:
        now = self._now()
        case_id = _new_id("case")
        question_id = _new_id("rq")
        body = request.model_dump(mode="json")
        return self.command_handler.execute(
            scope=f"{context.actor_id}:POST:/alpha/research-cases/{source_research_case_id}/commands/derive",
            idempotency_key=context.idempotency_key,
            request_body=body,
            context=context,
            callback=lambda uow: self._derive_case(
                uow=uow,
                source_research_case_id=source_research_case_id,
                request=request,
                context=context,
                case_id=case_id,
                question_id=question_id,
                now=now,
            ),
        )

    def _create_case(
        self,
        *,
        uow: UnitOfWork,
        request: CreateResearchCaseRequest,
        context: CommandContext,
        case_id: str,
        question_id: str,
        now: datetime,
    ) -> CommandOutcome:
        case = ResearchCaseResponse(
            research_case_id=case_id,
            title=request.title,
            root_question_id=question_id,
            current_question_id=question_id,
            lifecycle_status=ResearchCaseLifecycleStatus.open,
            attention_status=AttentionStatus.active,
            revision=1,
            created_at=now,
            updated_at=now,
            current_knowledge_scope_version_id=None,
            current_judgment_card_version_id=None,
            current_research_disposition_id=None,
            parent_research_case_id=None,
            archived_at=None,
        )
        question = ResearchQuestionResponse(
            research_question_id=question_id,
            research_case_id=case_id,
            question_text=request.question_text,
            question_role=QuestionRole.root,
            created_by=context.actor_id,
            created_at=now,
            parent_question_id=None,
        )
        uow.case_scope.create_case(research_case=case, root_question=question)
        uow.lifecycle.ensure("research_case", case_id, now=now)
        data = CreateResearchCaseData(research_case=case, research_question=question)
        return self._case_outcome(
            data=data.model_dump(mode="json"),
            case=case,
            response_status=201,
            event_type_code="research_case_created",
        )

    def _add_question(
        self,
        *,
        uow: UnitOfWork,
        research_case_id: str,
        request: AddResearchQuestionRequest,
        context: CommandContext,
        question_id: str,
        now: datetime,
    ) -> CommandOutcome:
        case = uow.case_scope.get_case(research_case_id)
        self._ensure_open(case)
        parent_question_id = request.parent_question_id or case.current_question_id
        parent = uow.case_scope.get_question(parent_question_id)
        if parent.research_case_id != research_case_id:
            raise ValueError("parent question must belong to the same research case")
        question = ResearchQuestionResponse(
            research_question_id=question_id,
            research_case_id=research_case_id,
            question_text=request.question_text,
            question_role=request.question_role,
            created_by=context.actor_id,
            created_at=now,
            parent_question_id=parent_question_id,
        )
        updated = uow.case_scope.add_question(
            question,
            expected_case_revision=request.expected_revision,
            updated_at=now,
        )
        data = {
            "research_case": updated.model_dump(mode="json"),
            "research_question": question.model_dump(mode="json"),
        }
        return self._case_outcome(
            data=data,
            case=updated,
            event_type_code="research_question_added",
        )

    def _set_archive_state(
        self,
        *,
        uow: UnitOfWork,
        research_case_id: str,
        expected_revision: int,
        archive: bool,
        now: datetime,
    ) -> CommandOutcome:
        case = uow.case_scope.get_case(research_case_id)
        if archive and case.lifecycle_status == ResearchCaseLifecycleStatus.archived:
            raise ValueError("research case is already archived")
        if not archive and case.lifecycle_status == ResearchCaseLifecycleStatus.open:
            raise ValueError("research case is already open")
        updates: dict[str, Any] = {
            "lifecycle_status": (
                ResearchCaseLifecycleStatus.archived.value
                if archive
                else ResearchCaseLifecycleStatus.open.value
            ),
            "attention_status": AttentionStatus.closed.value if archive else AttentionStatus.active.value,
            "updated_at": _utc_iso(now),
            "archived_at": _utc_iso(now) if archive else None,
        }
        uow.case_scope.compare_and_swap_revision(
            research_case_id,
            expected_revision=expected_revision,
            updates=updates,
        )
        updated = uow.case_scope.get_case(research_case_id)
        return self._case_outcome(
            data={"research_case": updated.model_dump(mode="json")},
            case=updated,
            event_type_code="research_case_archived" if archive else "research_case_reopened",
        )

    def _derive_case(
        self,
        *,
        uow: UnitOfWork,
        source_research_case_id: str,
        request: DeriveResearchCaseRequest,
        context: CommandContext,
        case_id: str,
        question_id: str,
        now: datetime,
    ) -> CommandOutcome:
        source_case = uow.case_scope.get_case(source_research_case_id)
        if source_case.revision != request.expected_revision:
            raise ConcurrencyConflictError(
                f"revision conflict for {source_research_case_id}: expected {request.expected_revision}"
            )
        parent_question_id = request.source_question_id
        if parent_question_id is not None:
            source_question = uow.case_scope.get_question(parent_question_id)
            if source_question.research_case_id != source_research_case_id:
                raise ValueError("source question must belong to the source research case")

        case = ResearchCaseResponse(
            research_case_id=case_id,
            title=request.title,
            root_question_id=question_id,
            current_question_id=question_id,
            lifecycle_status=ResearchCaseLifecycleStatus.open,
            attention_status=AttentionStatus.active,
            revision=1,
            created_at=now,
            updated_at=now,
            current_knowledge_scope_version_id=None,
            current_judgment_card_version_id=None,
            current_research_disposition_id=None,
            parent_research_case_id=source_research_case_id,
            archived_at=None,
        )
        question = ResearchQuestionResponse(
            research_question_id=question_id,
            research_case_id=case_id,
            question_text=request.question_text,
            question_role=QuestionRole.derived,
            created_by=context.actor_id,
            created_at=now,
            parent_question_id=parent_question_id,
        )
        uow.case_scope.create_case(research_case=case, root_question=question)
        uow.lifecycle.ensure("research_case", case_id, now=now)
        data = DeriveResearchCaseData(
            source_research_case_ref=ResourceReference(
                resource_type="research_case",
                resource_id=source_research_case_id,
            ),
            research_case=case,
            research_question=question,
        )
        return self._case_outcome(
            data=data.model_dump(mode="json"),
            case=case,
            response_status=201,
            event_type_code="research_case_derived",
        )

    def _now(self) -> datetime:
        value = self.clock()
        if value.utcoffset() is None or value.utcoffset().total_seconds() != 0:
            raise ValueError("case management clock must return UTC datetimes")
        return value.astimezone(timezone.utc)

    @staticmethod
    def _ensure_open(case: ResearchCaseResponse) -> None:
        if case.lifecycle_status != ResearchCaseLifecycleStatus.open:
            raise ValueError("research case is not open")

    @staticmethod
    def _case_outcome(
        *,
        data: Mapping[str, Any],
        case: ResearchCaseResponse,
        event_type_code: str,
        response_status: int = 200,
    ) -> CommandOutcome:
        return CommandOutcome(
            data=data,
            primary_aggregate_type="research_case",
            primary_aggregate_id=case.research_case_id,
            primary_aggregate_revision=case.revision,
            response_status=response_status,
            event_type_code=event_type_code,
            event_payload={"research_case_id": case.research_case_id},
        )


class ResearchCaseQueryHandler:
    """Read-side facade for ResearchCase data."""

    def __init__(self, database: CoreAlphaDatabase):
        self.database = database

    def get_case(self, research_case_id: str) -> ResearchCaseResponse:
        with UnitOfWork(self.database, write=False) as uow:
            return uow.case_scope.get_case(research_case_id)

    def list_questions(self, research_case_id: str) -> list[ResearchQuestionResponse]:
        with UnitOfWork(self.database, write=False) as uow:
            uow.case_scope.get_case(research_case_id)
            return uow.case_scope.list_questions(research_case_id)


__all__ = [
    "ResearchCaseCommandHandler",
    "ResearchCaseQueryHandler",
]
