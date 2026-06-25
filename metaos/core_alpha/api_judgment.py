"""FastAPI router for Core Alpha Run, Evidence, Judgment, and Audit APIs."""

from __future__ import annotations

import uuid
from collections.abc import Callable
from datetime import datetime, timezone
from typing import Annotated, Any

from fastapi import APIRouter, Header, Request
from fastapi.responses import JSONResponse

from metaos.core_alpha.commands import ApplicationCommandHandler, CommandExecution
from metaos.core_alpha.contracts.common import CommandContext, OpenCodeValue
from metaos.core_alpha.contracts.execution import (
    CancelResearchRunRequest,
    CreateResearchRunRequest,
    ExecutionMode,
)
from metaos.core_alpha.contracts.judgment import (
    AcknowledgeAuditFindingRequest,
    SetClaimUserAttitudeRequest,
)
from metaos.core_alpha.judgment_audit import (
    JudgmentAuditCommandHandler,
    JudgmentAuditQueryHandler,
)
from metaos.core_alpha.judgment_domain import (
    JudgmentDomainCommandHandler,
    JudgmentDomainQueryHandler,
)
from metaos.core_alpha.persistence import (
    ConcurrencyConflictError,
    CoreAlphaDatabase,
    IdempotencyConflictError,
    RecordNotFoundError,
)
from metaos.core_alpha.research_execution import (
    ResearchExecutionCommandHandler,
    ResearchExecutionQueryHandler,
)


REGISTRY_VERSION = "core-alpha-v1"
IdempotencyHeader = Annotated[str, Header(alias="Idempotency-Key", min_length=1)]


def create_judgment_api_router(*, database: CoreAlphaDatabase) -> APIRouter:
    """Build the A1-API-001B router without mounting it on the public app."""

    router = APIRouter(prefix="/alpha", tags=["core-alpha-judgment"])
    app_commands = ApplicationCommandHandler(database)
    execution_commands = ResearchExecutionCommandHandler(app_commands)
    execution_queries = ResearchExecutionQueryHandler(database)
    judgment_commands = JudgmentDomainCommandHandler(app_commands)
    judgment_queries = JudgmentDomainQueryHandler(database)
    audit_commands = JudgmentAuditCommandHandler(app_commands)
    audit_queries = JudgmentAuditQueryHandler(database)

    @router.post("/research-cases/{research_case_id}/research-runs")
    def start_research_run(
        research_case_id: str,
        payload: CreateResearchRunRequest,
        request: Request,
        idempotency_key: IdempotencyHeader,
    ) -> Any:
        if payload.execution_mode == ExecutionMode.asynchronous:
            return _error_response(
                503,
                "async_execution_unavailable",
                "asynchronous execution is not enabled for this slice",
                retryable=True,
            )
        return _command_response(
            lambda: execution_commands.start_research_run(
                research_case_id,
                payload,
                context=_command_context(request, idempotency_key),
            ),
            transform=_start_run_data,
        )

    @router.get("/research-runs/{research_run_id}")
    def get_research_run(research_run_id: str) -> Any:
        try:
            run = execution_queries.get_research_run(research_run_id)
            return _query_response(
                run.model_dump(mode="json"),
                aggregate_type="research_run",
                aggregate_id=run.research_run_id,
                revision=run.revision,
            )
        except RecordNotFoundError as exc:
            return _error_response(404, "resource_not_found", str(exc))

    @router.post("/research-runs/{research_run_id}/commands/cancel")
    def cancel_research_run(
        research_run_id: str,
        payload: CancelResearchRunRequest,
        request: Request,
        idempotency_key: IdempotencyHeader,
    ) -> Any:
        return _command_response(
            lambda: execution_commands.cancel_run(
                research_run_id,
                payload,
                context=_command_context(request, idempotency_key),
            )
        )

    @router.get("/research-runs/{research_run_id}/outcome")
    def get_research_run_outcome(research_run_id: str) -> Any:
        try:
            run = execution_queries.get_research_run(research_run_id)
            outcome = execution_queries.get_outcome(research_run_id)
            return _query_response(
                outcome.model_dump(mode="json") if outcome else None,
                aggregate_type="research_run",
                aggregate_id=research_run_id,
                revision=run.revision,
            )
        except RecordNotFoundError as exc:
            return _error_response(404, "resource_not_found", str(exc))

    @router.get("/research-runs/{research_run_id}/attempts")
    def list_research_attempts(research_run_id: str) -> Any:
        try:
            attempts = [
                attempt.model_dump(mode="json")
                for attempt in execution_queries.list_attempts(research_run_id)
            ]
            return _list_response(attempts)
        except RecordNotFoundError as exc:
            return _error_response(404, "resource_not_found", str(exc))

    @router.get("/research-attempts/{research_attempt_id}/retrieval-runs")
    def list_retrieval_runs(research_attempt_id: str) -> Any:
        try:
            retrievals = [
                retrieval.model_dump(mode="json")
                for retrieval in execution_queries.list_retrieval_runs(research_attempt_id)
            ]
            return _list_response(retrievals)
        except RecordNotFoundError as exc:
            return _error_response(404, "resource_not_found", str(exc))

    @router.get("/research-runs/{research_run_id}/evidence-uses")
    def list_research_evidence_uses(research_run_id: str) -> Any:
        try:
            uses = [
                use.model_dump(mode="json")
                for use in execution_queries.list_research_evidence_uses(research_run_id)
            ]
            return _list_response(uses)
        except RecordNotFoundError as exc:
            return _error_response(404, "resource_not_found", str(exc))

    @router.get("/evidence-units/{evidence_unit_id}")
    def get_evidence_unit(evidence_unit_id: str) -> Any:
        try:
            evidence = execution_queries.get_evidence_unit(evidence_unit_id)
            return _query_response(
                evidence.model_dump(mode="json"),
                aggregate_type="evidence_unit",
                aggregate_id=evidence.evidence_unit_id,
                revision=evidence.revision,
            )
        except RecordNotFoundError as exc:
            return _error_response(404, "resource_not_found", str(exc))

    @router.get("/research-evidence-uses/{research_evidence_use_id}")
    def get_research_evidence_use(research_evidence_use_id: str) -> Any:
        try:
            use = execution_queries.get_research_evidence_use(research_evidence_use_id)
            return _query_response(
                use.model_dump(mode="json"),
                aggregate_type="research_evidence_use",
                aggregate_id=use.research_evidence_use_id,
                revision=use.evidence_revision,
            )
        except RecordNotFoundError as exc:
            return _error_response(404, "resource_not_found", str(exc))

    @router.get("/research-cases/{research_case_id}/judgment-cards/current")
    def get_current_judgment_card_for_case(research_case_id: str) -> Any:
        try:
            judgment = judgment_queries.get_current_judgment_card_for_case(research_case_id)
            return _query_response(
                judgment.model_dump(mode="json") if judgment else None,
                aggregate_type="research_case",
                aggregate_id=research_case_id,
                revision=1,
            )
        except RecordNotFoundError as exc:
            return _error_response(404, "resource_not_found", str(exc))

    @router.get("/judgment-card-versions/{judgment_card_version_id}")
    def get_judgment_card_version(judgment_card_version_id: str) -> Any:
        try:
            judgment = judgment_queries.get_judgment_card_version(judgment_card_version_id)
            return _query_response(
                judgment.model_dump(mode="json"),
                aggregate_type="judgment_card",
                aggregate_id=judgment.judgment_card_id,
                revision=judgment.revision,
            )
        except RecordNotFoundError as exc:
            return _error_response(404, "resource_not_found", str(exc))

    @router.get("/judgment-card-versions/{judgment_card_version_id}/claims")
    def list_judgment_claims(judgment_card_version_id: str) -> Any:
        try:
            judgment = judgment_queries.get_judgment_card_version(judgment_card_version_id)
            rows = []
            for claim in judgment_queries.list_claims(judgment_card_version_id):
                rationale = (
                    judgment_queries.get_judgment_rationale(claim.judgment_rationale_id)
                    if claim.judgment_rationale_id
                    else None
                )
                rows.append(
                    {
                        "claim": claim.model_dump(mode="json"),
                        "rationale": rationale.model_dump(mode="json") if rationale else None,
                        "evidence_links": [
                            link.model_dump(mode="json")
                            for link in judgment_queries.list_claim_evidence_links(
                                claim.claim_version_id
                            )
                        ],
                    }
                )
            return _query_response(
                {"claims": rows},
                aggregate_type="judgment_card",
                aggregate_id=judgment.judgment_card_id,
                revision=judgment.revision,
            )
        except RecordNotFoundError as exc:
            return _error_response(404, "resource_not_found", str(exc))

    @router.get("/claims/{claim_id}/current")
    def get_current_claim(claim_id: str) -> Any:
        try:
            claim = judgment_queries.get_current_claim(claim_id)
            return _query_response(
                claim.model_dump(mode="json"),
                aggregate_type="claim",
                aggregate_id=claim.claim_id,
                revision=claim.version,
            )
        except RecordNotFoundError as exc:
            return _error_response(404, "resource_not_found", str(exc))

    @router.get("/claim-versions/{claim_version_id}")
    def get_claim_version(claim_version_id: str) -> Any:
        try:
            claim = judgment_queries.get_claim_version(claim_version_id)
            return _query_response(
                claim.model_dump(mode="json"),
                aggregate_type="claim",
                aggregate_id=claim.claim_id,
                revision=claim.version,
            )
        except RecordNotFoundError as exc:
            return _error_response(404, "resource_not_found", str(exc))

    @router.post("/claim-versions/{claim_version_id}/commands/set-user-attitude")
    def set_claim_user_attitude(
        claim_version_id: str,
        payload: SetClaimUserAttitudeRequest,
        request: Request,
        idempotency_key: IdempotencyHeader,
    ) -> Any:
        return _command_response(
            lambda: judgment_commands.set_claim_user_attitude(
                claim_version_id,
                payload,
                context=_command_context(request, idempotency_key),
            )
        )

    @router.get("/judgment-card-versions/{judgment_card_version_id}/audits")
    def list_judgment_audits(judgment_card_version_id: str) -> Any:
        try:
            audits = [
                audit.model_dump(mode="json")
                for audit in audit_queries.list_judgment_audits(judgment_card_version_id)
            ]
            return _list_response(audits)
        except RecordNotFoundError as exc:
            return _error_response(404, "resource_not_found", str(exc))

    @router.get("/judgment-card-versions/{judgment_card_version_id}/audits/current")
    def get_current_judgment_audit(judgment_card_version_id: str) -> Any:
        try:
            audit = audit_queries.get_current_judgment_audit(judgment_card_version_id)
            return _query_response(
                audit.model_dump(mode="json") if audit else None,
                aggregate_type="judgment_card",
                aggregate_id=judgment_card_version_id,
                revision=1,
            )
        except RecordNotFoundError as exc:
            return _error_response(404, "resource_not_found", str(exc))

    @router.get("/judgment-audits/{judgment_audit_id}")
    def get_judgment_audit(judgment_audit_id: str) -> Any:
        try:
            audit = audit_queries.get_judgment_audit(judgment_audit_id)
            findings = [
                finding.model_dump(mode="json")
                for finding in audit_queries.list_audit_findings(judgment_audit_id)
            ]
            return _query_response(
                {
                    "judgment_audit": audit.model_dump(mode="json"),
                    "audit_findings": findings,
                },
                aggregate_type="judgment_audit",
                aggregate_id=audit.judgment_audit_id,
                revision=1,
            )
        except RecordNotFoundError as exc:
            return _error_response(404, "resource_not_found", str(exc))

    @router.post("/audit-findings/{audit_finding_id}/commands/acknowledge")
    def acknowledge_audit_finding(
        audit_finding_id: str,
        payload: AcknowledgeAuditFindingRequest,
        request: Request,
        idempotency_key: IdempotencyHeader,
    ) -> Any:
        return _command_response(
            lambda: audit_commands.acknowledge_warning(
                audit_finding_id,
                payload,
                context=_command_context(request, idempotency_key),
            )
        )

    @router.get("/judgment-card-versions/{judgment_card_version_id}/decision-fitness/current")
    def get_current_decision_fitness(judgment_card_version_id: str) -> Any:
        try:
            fitness = audit_queries.get_current_decision_fitness(judgment_card_version_id)
            return _query_response(
                fitness.model_dump(mode="json") if fitness else None,
                aggregate_type="judgment_card",
                aggregate_id=judgment_card_version_id,
                revision=1,
            )
        except RecordNotFoundError as exc:
            return _error_response(404, "resource_not_found", str(exc))

    @router.get("/decision-fitness/{decision_fitness_id}")
    def get_decision_fitness(decision_fitness_id: str) -> Any:
        try:
            fitness = audit_queries.get_decision_fitness(decision_fitness_id)
            return _query_response(
                fitness.model_dump(mode="json"),
                aggregate_type="decision_fitness",
                aggregate_id=fitness.decision_fitness_id,
                revision=1,
            )
        except RecordNotFoundError as exc:
            return _error_response(404, "resource_not_found", str(exc))

    @router.get("/research-runs/{research_run_id}/trace")
    def get_public_research_trace(research_run_id: str) -> Any:
        try:
            trace = execution_queries.get_public_trace(research_run_id)
            return _query_response(
                trace.model_dump(mode="json"),
                aggregate_type="research_run",
                aggregate_id=trace.research_run.research_run_id,
                revision=trace.research_run.revision,
            )
        except RecordNotFoundError as exc:
            return _error_response(404, "resource_not_found", str(exc))

    return router


def _command_response(
    callback: Callable[[], CommandExecution],
    *,
    transform: Callable[[dict[str, Any]], dict[str, Any]] | None = None,
) -> JSONResponse:
    try:
        execution = callback()
        body = dict(execution.response_body)
        if transform is not None:
            body = transform(body)
        return JSONResponse(status_code=execution.status_code, content=body)
    except IdempotencyConflictError as exc:
        return _error_response(409, "idempotency_conflict", str(exc))
    except ConcurrencyConflictError as exc:
        return _error_response(409, "concurrency_conflict", str(exc))
    except RecordNotFoundError as exc:
        return _error_response(404, "resource_not_found", str(exc))
    except ValueError as exc:
        return _error_response(409, "lifecycle_conflict", str(exc))


def _start_run_data(body: dict[str, Any]) -> dict[str, Any]:
    data = dict(body["data"])
    body["data"] = {
        "research_run": data["research_run"],
        "research_run_outcome": data.get("research_run_outcome"),
        "judgment_card": None,
    }
    return body


def _command_context(request: Request, idempotency_key: str) -> CommandContext:
    return CommandContext(
        command_id=f"cmd_{uuid.uuid4().hex}",
        actor_type=OpenCodeValue(code="user", registry_version=REGISTRY_VERSION),
        actor_id=request.headers.get("X-Actor-Id", "user_local"),
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


__all__ = ["create_judgment_api_router"]
