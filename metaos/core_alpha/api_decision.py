"""FastAPI router for Core Alpha Decision and trusted internal APIs."""

from __future__ import annotations

import uuid
from collections.abc import Callable
from datetime import datetime, timezone
from typing import Annotated, Any

from fastapi import APIRouter, Header, Request
from fastapi.responses import JSONResponse

from metaos.core_alpha.commands import (
    ApplicationCommandHandler,
    CandidateResultCommandHandler,
    CommandExecution,
)
from metaos.core_alpha.contracts.common import CommandContext, OpenCodeValue
from metaos.core_alpha.contracts.decision import (
    AcceptDispositionProposalRequest,
    AdjustDispositionProposalRequest,
    RejectDispositionProposalRequest,
)
from metaos.core_alpha.contracts.internal import SubmitCandidateResultCommandRequest
from metaos.core_alpha.persistence import (
    ConcurrencyConflictError,
    CoreAlphaDatabase,
    IdempotencyConflictError,
    RecordNotFoundError,
)
from metaos.core_alpha.research_disposition import (
    ResearchDispositionCommandHandler,
    ResearchDispositionQueryHandler,
)


REGISTRY_VERSION = "core-alpha-v1"
IdempotencyHeader = Annotated[str, Header(alias="Idempotency-Key", min_length=1)]
ServiceActorHeader = Annotated[str | None, Header(alias="X-Service-Actor-Id")]


def create_decision_api_router(*, database: CoreAlphaDatabase) -> APIRouter:
    """Build the A1-API-001C router without mounting it on the public app."""

    router = APIRouter(tags=["core-alpha-decision"])
    app_commands = ApplicationCommandHandler(database)
    disposition_commands = ResearchDispositionCommandHandler(app_commands)
    disposition_queries = ResearchDispositionQueryHandler(database)
    candidate_commands = CandidateResultCommandHandler(app_commands)

    @router.get("/alpha/research-cases/{research_case_id}/disposition-proposals")
    def list_current_disposition_proposals(research_case_id: str) -> Any:
        try:
            proposals = [
                proposal.model_dump(mode="json")
                for proposal in (
                    disposition_queries.list_current_disposition_proposals_for_case(
                        research_case_id
                    )
                )
            ]
            return _list_response(proposals)
        except RecordNotFoundError as exc:
            return _error_response(404, "resource_not_found", str(exc))

    @router.get("/alpha/disposition-proposals/{disposition_proposal_id}/current")
    def get_current_disposition_proposal(disposition_proposal_id: str) -> Any:
        try:
            proposal = disposition_queries.get_current_disposition_proposal(
                disposition_proposal_id
            )
            return _query_response(
                proposal.model_dump(mode="json"),
                aggregate_type="disposition_proposal",
                aggregate_id=proposal.disposition_proposal_id,
                revision=proposal.revision,
            )
        except RecordNotFoundError as exc:
            return _error_response(404, "resource_not_found", str(exc))

    @router.get("/alpha/disposition-proposal-versions/{disposition_proposal_version_id}")
    def get_disposition_proposal_version(disposition_proposal_version_id: str) -> Any:
        try:
            proposal = disposition_queries.get_disposition_proposal_version(
                disposition_proposal_version_id
            )
            return _query_response(
                proposal.model_dump(mode="json"),
                aggregate_type="disposition_proposal",
                aggregate_id=proposal.disposition_proposal_id,
                revision=proposal.revision,
            )
        except RecordNotFoundError as exc:
            return _error_response(404, "resource_not_found", str(exc))

    @router.post(
        "/alpha/disposition-proposal-versions/{disposition_proposal_version_id}/commands/accept"
    )
    def accept_disposition_proposal(
        disposition_proposal_version_id: str,
        payload: AcceptDispositionProposalRequest,
        request: Request,
        idempotency_key: IdempotencyHeader,
    ) -> Any:
        return _command_response(
            lambda: disposition_commands.accept_disposition_proposal(
                disposition_proposal_version_id,
                payload,
                context=_user_command_context(request, idempotency_key),
            )
        )

    @router.post(
        "/alpha/disposition-proposal-versions/{disposition_proposal_version_id}/commands/adjust"
    )
    def adjust_disposition_proposal(
        disposition_proposal_version_id: str,
        payload: AdjustDispositionProposalRequest,
        request: Request,
        idempotency_key: IdempotencyHeader,
    ) -> Any:
        return _command_response(
            lambda: disposition_commands.adjust_disposition_proposal(
                disposition_proposal_version_id,
                payload,
                context=_user_command_context(request, idempotency_key),
            )
        )

    @router.post(
        "/alpha/disposition-proposal-versions/{disposition_proposal_version_id}/commands/reject"
    )
    def reject_disposition_proposal(
        disposition_proposal_version_id: str,
        payload: RejectDispositionProposalRequest,
        request: Request,
        idempotency_key: IdempotencyHeader,
    ) -> Any:
        return _command_response(
            lambda: disposition_commands.reject_disposition_proposal(
                disposition_proposal_version_id,
                payload,
                context=_user_command_context(request, idempotency_key),
            )
        )

    @router.get("/alpha/research-dispositions/{research_disposition_id}")
    def get_research_disposition(research_disposition_id: str) -> Any:
        try:
            disposition = disposition_queries.get_research_disposition(
                research_disposition_id
            )
            return _query_response(
                disposition.model_dump(mode="json"),
                aggregate_type="research_disposition",
                aggregate_id=disposition.research_disposition_id,
                revision=1,
            )
        except RecordNotFoundError as exc:
            return _error_response(404, "resource_not_found", str(exc))

    @router.post("/internal/alpha/candidate-results")
    def submit_candidate_result(
        payload: SubmitCandidateResultCommandRequest,
        request: Request,
        idempotency_key: IdempotencyHeader,
        service_actor_id: ServiceActorHeader = None,
    ) -> Any:
        if service_actor_id is None:
            return _error_response(
                401,
                "authentication_required",
                "internal candidate result submission requires service identity",
            )
        return _command_response(
            lambda: candidate_commands.submit(
                payload,
                context=_service_command_context(
                    request,
                    idempotency_key,
                    service_actor_id,
                ),
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
    except RecordNotFoundError as exc:
        return _error_response(404, "resource_not_found", str(exc))
    except ValueError as exc:
        return _error_response(409, "lifecycle_conflict", str(exc))


def _user_command_context(request: Request, idempotency_key: str) -> CommandContext:
    return _command_context(
        request,
        idempotency_key,
        actor_type="user",
        actor_id=request.headers.get("X-Actor-Id", "user_local"),
    )


def _service_command_context(
    request: Request,
    idempotency_key: str,
    service_actor_id: str,
) -> CommandContext:
    return _command_context(
        request,
        idempotency_key,
        actor_type="service",
        actor_id=service_actor_id,
    )


def _command_context(
    request: Request,
    idempotency_key: str,
    *,
    actor_type: str,
    actor_id: str,
) -> CommandContext:
    return CommandContext(
        command_id=f"cmd_{uuid.uuid4().hex}",
        actor_type=OpenCodeValue(code=actor_type, registry_version=REGISTRY_VERSION),
        actor_id=actor_id,
        idempotency_key=idempotency_key,
        correlation_id=request.headers.get("X-Correlation-Id", f"corr_{uuid.uuid4().hex}"),
        causation_id=request.headers.get("X-Causation-Id", f"cause_{uuid.uuid4().hex}"),
        trace_id=request.headers.get("X-Trace-Id", f"trace_{uuid.uuid4().hex}"),
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
            revision=max(revision, 1),
        ),
    }


def _list_response(data: list[Any]) -> dict[str, Any]:
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


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


__all__ = ["create_decision_api_router"]
