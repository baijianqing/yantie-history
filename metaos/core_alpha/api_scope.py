"""FastAPI router for Core Alpha Knowledge, Case, Scope, and Plan APIs."""

from __future__ import annotations

import uuid
from collections.abc import Callable
from datetime import datetime, timezone
from typing import Annotated, Any

from fastapi import APIRouter, Header, Query, Request
from fastapi.responses import JSONResponse

from metaos.core_alpha.case_management import (
    ResearchCaseCommandHandler,
    ResearchCaseQueryHandler,
)
from metaos.core_alpha.commands import ApplicationCommandHandler, CommandExecution
from metaos.core_alpha.contracts.common import CommandContext, OpenCodeValue
from metaos.core_alpha.contracts.scope import (
    AddResearchQuestionRequest,
    AdjustKnowledgeScopeRequest,
    AdjustResearchPlanRequest,
    CreateKnowledgeScopeRequest,
    CreateResearchCaseRequest,
    CreateResearchPlanRequest,
    CreateSourceResolutionsRequest,
    DeriveResearchCaseRequest,
    ExpectedRevisionRequest,
)
from metaos.core_alpha.persistence import (
    ConcurrencyConflictError,
    CoreAlphaDatabase,
    IdempotencyConflictError,
    RecordNotFoundError,
)
from metaos.core_alpha.scope_governance import (
    ScopeGovernanceCommandHandler,
    ScopeGovernanceQueryHandler,
)
from metaos.knowledge.catalog import (
    KnowledgeCatalogAdapter,
    KnowledgeCatalogNotFoundError,
)


REGISTRY_VERSION = "core-alpha-v1"
IdempotencyHeader = Annotated[str, Header(alias="Idempotency-Key", min_length=1)]


def create_scope_api_router(
    *,
    database: CoreAlphaDatabase,
    catalog: KnowledgeCatalogAdapter,
) -> APIRouter:
    """Build the A1-API-001A router without mounting it on the public app."""

    router = APIRouter(prefix="/alpha", tags=["core-alpha-scope"])
    app_commands = ApplicationCommandHandler(database)
    case_commands = ResearchCaseCommandHandler(app_commands)
    case_queries = ResearchCaseQueryHandler(database)
    scope_commands = ScopeGovernanceCommandHandler(app_commands, catalog)
    scope_queries = ScopeGovernanceQueryHandler(database)

    @router.get("/knowledge-items")
    def list_knowledge_items(
        limit: Annotated[int, Query(ge=1, le=200)] = 50,
    ) -> dict[str, Any]:
        items = [_knowledge_item(item) for item in catalog.list_items(limit=limit)]
        return _list_response(items)

    @router.get("/knowledge-items/{knowledge_item_id}")
    def get_knowledge_item(knowledge_item_id: str) -> Any:
        try:
            item = catalog.get_item(knowledge_item_id)
            return _query_response(
                _knowledge_item(item),
                aggregate_type="knowledge_item",
                aggregate_id=item.knowledge_item_id,
                revision=item.revision,
            )
        except KnowledgeCatalogNotFoundError as exc:
            return _error_response(404, "resource_not_found", str(exc))

    @router.get("/knowledge-items/{knowledge_item_id}/versions")
    def list_knowledge_item_versions(
        knowledge_item_id: str,
        limit: Annotated[int, Query(ge=1, le=200)] = 50,
    ) -> Any:
        try:
            versions = [
                _knowledge_item_version(version)
                for version in catalog.list_versions(knowledge_item_id)[:limit]
            ]
            return _list_response(versions)
        except KnowledgeCatalogNotFoundError as exc:
            return _error_response(404, "resource_not_found", str(exc))

    @router.get("/knowledge-item-versions/{knowledge_item_version_id}")
    def get_knowledge_item_version(
        knowledge_item_version_id: str,
    ) -> Any:
        try:
            version = catalog.get_version(knowledge_item_version_id)
            return _query_response(
                _knowledge_item_version(version),
                aggregate_type="knowledge_item_version",
                aggregate_id=version.knowledge_item_version_id,
                revision=version.version,
            )
        except KnowledgeCatalogNotFoundError as exc:
            return _error_response(404, "resource_not_found", str(exc))

    @router.get("/knowledge-item-versions/{knowledge_item_version_id}/chunks")
    def list_knowledge_item_chunks(
        knowledge_item_version_id: str,
        limit: Annotated[int, Query(ge=1, le=200)] = 50,
    ) -> Any:
        try:
            chunks = [
                _knowledge_chunk(chunk)
                for chunk in catalog.list_chunks(knowledge_item_version_id, limit=limit)
            ]
            return _list_response(chunks)
        except KnowledgeCatalogNotFoundError as exc:
            return _error_response(404, "resource_not_found", str(exc))

    @router.post("/research-cases")
    def create_research_case(
        payload: CreateResearchCaseRequest,
        request: Request,
        idempotency_key: IdempotencyHeader,
    ) -> Any:
        return _command_response(
            lambda: case_commands.create_case(
                payload,
                context=_command_context(request, idempotency_key),
            )
        )

    @router.get("/research-cases")
    def list_research_cases(
        limit: Annotated[int, Query(ge=1, le=200)] = 50,
        lifecycle_status: str | None = None,
        attention_status: str | None = None,
    ) -> dict[str, Any]:
        cases = [
            case.model_dump(mode="json")
            for case in case_queries.list_cases(
                limit=limit,
                lifecycle_status=lifecycle_status,
                attention_status=attention_status,
            )
        ]
        return _list_response(cases)

    @router.get("/research-cases/{research_case_id}")
    def get_research_case(research_case_id: str) -> Any:
        try:
            case = case_queries.get_case(research_case_id)
            return _query_response(
                case.model_dump(mode="json"),
                aggregate_type="research_case",
                aggregate_id=case.research_case_id,
                revision=case.revision,
            )
        except RecordNotFoundError as exc:
            return _error_response(404, "resource_not_found", str(exc))

    @router.post("/research-cases/{research_case_id}/questions")
    def add_research_question(
        research_case_id: str,
        payload: AddResearchQuestionRequest,
        request: Request,
        idempotency_key: IdempotencyHeader,
    ) -> Any:
        return _command_response(
            lambda: case_commands.add_question(
                research_case_id,
                payload,
                context=_command_context(request, idempotency_key),
            )
        )

    @router.post("/research-cases/{research_case_id}/commands/archive")
    def archive_research_case(
        research_case_id: str,
        payload: ExpectedRevisionRequest,
        request: Request,
        idempotency_key: IdempotencyHeader,
    ) -> Any:
        return _command_response(
            lambda: case_commands.archive_case(
                research_case_id,
                expected_revision=payload.expected_revision,
                context=_command_context(request, idempotency_key),
            )
        )

    @router.post("/research-cases/{research_case_id}/commands/reopen")
    def reopen_research_case(
        research_case_id: str,
        payload: ExpectedRevisionRequest,
        request: Request,
        idempotency_key: IdempotencyHeader,
    ) -> Any:
        return _command_response(
            lambda: case_commands.reopen_case(
                research_case_id,
                expected_revision=payload.expected_revision,
                context=_command_context(request, idempotency_key),
            )
        )

    @router.post("/research-cases/{research_case_id}/commands/derive")
    def derive_research_case(
        research_case_id: str,
        payload: DeriveResearchCaseRequest,
        request: Request,
        idempotency_key: IdempotencyHeader,
    ) -> Any:
        return _command_response(
            lambda: case_commands.derive_case(
                research_case_id,
                payload,
                context=_command_context(request, idempotency_key),
            )
        )

    @router.post("/research-cases/{research_case_id}/source-resolutions")
    def create_source_resolutions(
        research_case_id: str,
        payload: CreateSourceResolutionsRequest,
        request: Request,
        idempotency_key: IdempotencyHeader,
    ) -> Any:
        return _command_response(
            lambda: scope_commands.create_source_resolutions(
                research_case_id,
                payload,
                context=_command_context(request, idempotency_key),
            )
        )

    @router.get("/research-cases/{research_case_id}/source-resolutions")
    def list_source_resolutions(research_case_id: str) -> Any:
        try:
            case = case_queries.get_case(research_case_id)
            resolutions: list[dict[str, Any]] = []
            for question in case_queries.list_questions(research_case_id):
                resolutions.extend(
                    resolution.model_dump(mode="json")
                    for resolution in scope_queries.list_source_resolutions(
                        question.research_question_id
                    )
                )
            return _list_response(resolutions, aggregate_type="research_case", revision=case.revision)
        except RecordNotFoundError as exc:
            return _error_response(404, "resource_not_found", str(exc))

    @router.post("/research-cases/{research_case_id}/knowledge-scopes")
    def create_knowledge_scope(
        research_case_id: str,
        payload: CreateKnowledgeScopeRequest,
        request: Request,
        idempotency_key: IdempotencyHeader,
    ) -> Any:
        return _command_response(
            lambda: scope_commands.create_knowledge_scope(
                research_case_id,
                payload,
                context=_command_context(request, idempotency_key),
            )
        )

    @router.get("/research-cases/{research_case_id}/knowledge-scopes/current")
    def get_current_knowledge_scope(
        research_case_id: str,
    ) -> Any:
        try:
            case = case_queries.get_case(research_case_id)
            scope = scope_queries.get_current_knowledge_scope_for_case(research_case_id)
            return _query_response(
                scope.model_dump(mode="json") if scope else None,
                aggregate_type="research_case",
                aggregate_id=research_case_id,
                revision=case.revision,
            )
        except RecordNotFoundError as exc:
            return _error_response(404, "resource_not_found", str(exc))

    @router.get("/knowledge-scope-versions/{knowledge_scope_version_id}")
    def get_knowledge_scope_version(
        knowledge_scope_version_id: str,
    ) -> Any:
        try:
            scope = scope_queries.get_knowledge_scope_version(knowledge_scope_version_id)
            return _query_response(
                scope.model_dump(mode="json"),
                aggregate_type="knowledge_scope",
                aggregate_id=scope.knowledge_scope_id,
                revision=scope.version,
            )
        except RecordNotFoundError as exc:
            return _error_response(404, "resource_not_found", str(exc))

    @router.post("/knowledge-scope-versions/{knowledge_scope_version_id}/commands/adjust")
    def adjust_knowledge_scope(
        knowledge_scope_version_id: str,
        payload: AdjustKnowledgeScopeRequest,
        request: Request,
        idempotency_key: IdempotencyHeader,
    ) -> Any:
        return _command_response(
            lambda: scope_commands.adjust_knowledge_scope(
                knowledge_scope_version_id,
                payload,
                context=_command_context(request, idempotency_key),
            )
        )

    @router.post("/research-cases/{research_case_id}/research-plans")
    def create_research_plan(
        research_case_id: str,
        payload: CreateResearchPlanRequest,
        request: Request,
        idempotency_key: IdempotencyHeader,
    ) -> Any:
        return _command_response(
            lambda: scope_commands.create_research_plan(
                research_case_id,
                payload,
                context=_command_context(request, idempotency_key),
            )
        )

    @router.get("/research-cases/{research_case_id}/research-plans")
    def list_research_plans(
        research_case_id: str,
    ) -> Any:
        try:
            case = case_queries.get_case(research_case_id)
            plans = [
                plan.model_dump(mode="json")
                for plan in scope_queries.list_research_plans_for_case(research_case_id)
            ]
            return _list_response(plans, aggregate_type="research_case", revision=case.revision)
        except RecordNotFoundError as exc:
            return _error_response(404, "resource_not_found", str(exc))

    @router.get("/research-plans/{research_plan_id}/current")
    def get_current_research_plan(research_plan_id: str) -> Any:
        try:
            plan = scope_queries.get_current_research_plan(research_plan_id)
            return _query_response(
                plan.model_dump(mode="json"),
                aggregate_type="research_plan",
                aggregate_id=plan.research_plan_id,
                revision=plan.version,
            )
        except RecordNotFoundError as exc:
            return _error_response(404, "resource_not_found", str(exc))

    @router.get("/research-plan-versions/{research_plan_version_id}")
    def get_research_plan_version(
        research_plan_version_id: str,
    ) -> Any:
        try:
            plan = scope_queries.get_research_plan_version(research_plan_version_id)
            return _query_response(
                plan.model_dump(mode="json"),
                aggregate_type="research_plan",
                aggregate_id=plan.research_plan_id,
                revision=plan.version,
            )
        except RecordNotFoundError as exc:
            return _error_response(404, "resource_not_found", str(exc))

    @router.post("/research-plan-versions/{research_plan_version_id}/commands/adjust")
    def adjust_research_plan(
        research_plan_version_id: str,
        payload: AdjustResearchPlanRequest,
        request: Request,
        idempotency_key: IdempotencyHeader,
    ) -> Any:
        return _command_response(
            lambda: scope_commands.adjust_research_plan(
                research_plan_version_id,
                payload,
                context=_command_context(request, idempotency_key),
            )
        )

    return router


def _command_response(callback: Callable[[], CommandExecution]) -> JSONResponse:
    try:
        execution = callback()
        return JSONResponse(
            status_code=execution.status_code,
            content=execution.response_body,
        )
    except IdempotencyConflictError as exc:
        return _error_response(409, "idempotency_conflict", str(exc))
    except ConcurrencyConflictError as exc:
        return _error_response(409, "concurrency_conflict", str(exc))
    except (RecordNotFoundError, KnowledgeCatalogNotFoundError) as exc:
        return _error_response(404, "resource_not_found", str(exc))
    except ValueError as exc:
        code = "source_binding_conflict" if "binding" in str(exc) else "lifecycle_conflict"
        return _error_response(409, code, str(exc))


def _command_context(request: Request, idempotency_key: str) -> CommandContext:
    actor_id = request.headers.get("X-Actor-Id", "user_local")
    trace_id = request.headers.get("X-Trace-Id", f"trace_{uuid.uuid4().hex}")
    return CommandContext(
        command_id=f"cmd_{uuid.uuid4().hex}",
        actor_type=OpenCodeValue(code="user", registry_version=REGISTRY_VERSION),
        actor_id=actor_id,
        idempotency_key=idempotency_key,
        correlation_id=request.headers.get("X-Correlation-Id", f"corr_{uuid.uuid4().hex}"),
        causation_id=request.headers.get("X-Causation-Id", f"cause_{uuid.uuid4().hex}"),
        trace_id=trace_id,
    )


def _query_response(
    data: Any,
    *,
    aggregate_type: str,
    aggregate_id: str,
    revision: int,
) -> dict[str, Any]:
    return {
        "data": data,
        "consistency": _authoritative_consistency(
            aggregate_type=aggregate_type,
            aggregate_id=aggregate_id,
            revision=revision,
        ),
    }


def _list_response(
    data: list[Any],
    *,
    aggregate_type: str | None = None,
    revision: int | None = None,
) -> dict[str, Any]:
    return {
        "data": data,
        "page": {"next_cursor": None},
        "consistency": {
            "source": "projection",
            "primary_aggregate": None,
            "affected_aggregates": [],
            "projection_checkpoint": f"checkpoint_{uuid.uuid4().hex}",
            "is_stale": False,
            "observed_at": _now_iso(),
        },
    }


def _authoritative_consistency(
    *,
    aggregate_type: str,
    aggregate_id: str,
    revision: int,
) -> dict[str, Any]:
    return {
        "source": "authoritative_store",
        "primary_aggregate": {
            "aggregate_type": aggregate_type,
            "aggregate_id": aggregate_id,
            "revision": revision,
        },
        "affected_aggregates": [],
        "projection_checkpoint": None,
        "is_stale": False,
        "observed_at": _now_iso(),
    }


def _error_response(
    status_code: int,
    code: str,
    message: str,
    *,
    retryable: bool = False,
) -> JSONResponse:
    return JSONResponse(
        status_code=status_code,
        content={
            "error": {
                "code": code,
                "message": message,
                "details": {},
                "trace_id": f"trace_{uuid.uuid4().hex}",
                "retryable": retryable,
            }
        },
    )


def _knowledge_item(item: Any) -> dict[str, Any]:
    payload = item.model_dump(mode="json")
    return {
        "knowledge_item_id": payload["knowledge_item_id"],
        "title": payload["title"],
        "item_type": {"code": payload["item_type"], "registry_version": REGISTRY_VERSION},
        "language": payload["language"],
        "owner_scope": payload["owner_scope"],
        "lifecycle_status": payload["lifecycle_status"],
        "revision": payload["revision"],
        "created_at": payload["created_at"],
        "updated_at": payload["updated_at"],
        "current_knowledge_item_version_id": payload["current_knowledge_item_version_id"],
    }


def _knowledge_item_version(version: Any) -> dict[str, Any]:
    payload = version.model_dump(mode="json")
    return {
        "knowledge_item_version_id": payload["knowledge_item_version_id"],
        "knowledge_item_id": payload["knowledge_item_id"],
        "version": payload["version"],
        "content_hash": payload["content_hash"],
        "structure_hash": payload["structure_hash"],
        "parser_version": payload["parser_version"],
        "language": payload["language"],
        "availability_status": payload["availability_status"],
        "created_at": payload["created_at"],
        "previous_version_id": payload["previous_version_id"],
    }


def _knowledge_chunk(chunk: Any) -> dict[str, Any]:
    payload = chunk.model_dump(mode="json")
    return {
        "chunk_id": payload["chunk_id"],
        "knowledge_item_version_id": payload["knowledge_item_version_id"],
        "position": payload["position"],
        "content_hash": payload["content_hash"],
        "location": {
            "section_path": payload["section_path"],
            "page": payload["page"],
            "timestamp_seconds": payload["timestamp_seconds"],
            "start_offset": payload["start_offset"],
            "end_offset": payload["end_offset"],
        },
        "token_count": payload["token_count"],
        "char_count": payload["char_count"],
        "text_preview": payload["text_preview"],
    }


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


__all__ = ["create_scope_api_router"]
