"""Developer diagnostics queries for the Core Alpha Minimum Slice."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Annotated, Any

from fastapi import APIRouter, Header, Query
from fastapi.responses import JSONResponse

from metaos.core_alpha.api import DeveloperExtensionRegistry
from metaos.core_alpha.persistence import (
    CoreAlphaDatabase,
    RecordNotFoundError,
    TraceEventRecord,
    UnitOfWork,
)
from metaos.core_alpha.research_execution import ResearchExecutionQueryHandler
from metaos.knowledge.catalog import KnowledgeCatalogAdapter, KnowledgeCatalogNotFoundError


DeveloperActorHeader = Annotated[str | None, Header(alias="X-Developer-Actor-Id")]


class DiagnosticsQueryHandler:
    """Read-only technical projections for developer-only surfaces."""

    def __init__(self, database: CoreAlphaDatabase, catalog: KnowledgeCatalogAdapter):
        self.database = database
        self.catalog = catalog
        self.execution_queries = ResearchExecutionQueryHandler(database)

    def get_developer_research_trace(self, research_run_id: str) -> dict[str, Any]:
        trace = self.execution_queries.get_public_trace(research_run_id)
        with UnitOfWork(self.database, write=False) as uow:
            events = uow.events.list_for_aggregate("research_run", research_run_id)
            manifests = uow.material_manifests.list_for_research_run(research_run_id)
        return {
            "research_trace": trace.model_dump(mode="json"),
            "trace_events": [_trace_event(event) for event in events],
            "material_manifest_refs": [
                {
                    "material_manifest_id": manifest.material_manifest_id,
                    "provider": manifest.provider,
                    "purpose": manifest.purpose.model_dump(mode="json"),
                    "policy_decision": manifest.policy_decision,
                    "created_at": manifest.created_at.isoformat(),
                }
                for manifest in manifests
            ],
        }

    def list_material_manifests(
        self,
        *,
        research_run_id: str | None,
        provider: str | None,
        purpose_code: str | None,
    ) -> list[dict[str, Any]]:
        with UnitOfWork(self.database, write=False) as uow:
            rows = uow.connection.execute(
                """
                SELECT material_manifest_id
                FROM core_alpha_material_manifests
                WHERE (? IS NULL OR research_run_id = ?)
                  AND (? IS NULL OR provider = ?)
                  AND (? IS NULL OR purpose_code = ?)
                ORDER BY created_at, material_manifest_id
                """,
                (
                    research_run_id,
                    research_run_id,
                    provider,
                    provider,
                    purpose_code,
                    purpose_code,
                ),
            ).fetchall()
            manifests = [
                uow.material_manifests.get(row["material_manifest_id"])
                for row in rows
            ]
        return [_material_manifest(manifest.model_dump(mode="json")) for manifest in manifests]

    def list_index_generations(
        self,
        knowledge_item_version_id: str,
    ) -> list[dict[str, Any]]:
        return [
            generation.model_dump(mode="json")
            for generation in self.catalog.list_index_generations(knowledge_item_version_id)
        ]

    def list_projection_status(self) -> list[dict[str, Any]]:
        with UnitOfWork(self.database, write=False) as uow:
            rows = uow.connection.execute(
                """
                SELECT projection_name
                FROM core_alpha_projection_checkpoints
                ORDER BY projection_name
                """
            ).fetchall()
            records = [
                uow.projection_checkpoints.get(row["projection_name"])
                for row in rows
            ]
        return [
            {
                "projection_name": record.projection_name,
                "checkpoint": record.checkpoint,
                "revision": record.revision,
                "updated_at": record.updated_at.isoformat(),
                "lag_summary": "not_computed",
            }
            for record in records
        ]


def register_diagnostics_developer_routes(
    registry: DeveloperExtensionRegistry,
    *,
    database: CoreAlphaDatabase,
    catalog: KnowledgeCatalogAdapter,
) -> None:
    registry.register(create_diagnostics_developer_router(database=database, catalog=catalog))


def create_diagnostics_developer_router(
    *,
    database: CoreAlphaDatabase,
    catalog: KnowledgeCatalogAdapter,
) -> APIRouter:
    """Create an unmounted developer router for A1-DIAGNOSTICS-002 assembly."""

    router = APIRouter(tags=["core-alpha-developer-diagnostics"])
    queries = DiagnosticsQueryHandler(database, catalog)

    @router.get("/research-runs/{research_run_id}/trace")
    def get_developer_trace(
        research_run_id: str,
        developer_actor_id: DeveloperActorHeader = None,
    ) -> Any:
        auth_error = _require_developer(developer_actor_id)
        if auth_error is not None:
            return auth_error
        try:
            return {"data": queries.get_developer_research_trace(research_run_id)}
        except RecordNotFoundError as exc:
            return _error_response(404, "resource_not_found", str(exc))

    @router.get("/material-manifests")
    def list_material_manifests(
        research_run_id: str | None = None,
        provider: str | None = None,
        purpose_code: str | None = None,
        developer_actor_id: DeveloperActorHeader = None,
    ) -> Any:
        auth_error = _require_developer(developer_actor_id)
        if auth_error is not None:
            return auth_error
        return _list_response(
            queries.list_material_manifests(
                research_run_id=research_run_id,
                provider=provider,
                purpose_code=purpose_code,
            )
        )

    @router.get("/index-generations")
    def list_index_generations(
        knowledge_item_version_id: Annotated[str, Query(min_length=1)],
        developer_actor_id: DeveloperActorHeader = None,
    ) -> Any:
        auth_error = _require_developer(developer_actor_id)
        if auth_error is not None:
            return auth_error
        try:
            return _list_response(queries.list_index_generations(knowledge_item_version_id))
        except KnowledgeCatalogNotFoundError as exc:
            return _error_response(404, "resource_not_found", str(exc))

    @router.get("/projections/status")
    def list_projection_status(
        developer_actor_id: DeveloperActorHeader = None,
    ) -> Any:
        auth_error = _require_developer(developer_actor_id)
        if auth_error is not None:
            return auth_error
        return _list_response(queries.list_projection_status())

    return router


def _require_developer(developer_actor_id: str | None) -> JSONResponse | None:
    if developer_actor_id is None:
        return _error_response(
            401,
            "authentication_required",
            "developer diagnostics require developer identity",
        )
    return None


def _trace_event(event: TraceEventRecord) -> dict[str, Any]:
    return {
        "event_id": event.event_id,
        "event_type": {
            "code": event.event_type_code,
            "registry_version": event.event_type_registry_version,
        },
        "aggregate_type": event.aggregate_type,
        "aggregate_id": event.aggregate_id,
        "aggregate_revision": event.aggregate_revision,
        "actor_type": {
            "code": event.actor_type_code,
            "registry_version": event.actor_type_registry_version,
        },
        "actor_id": event.actor_id,
        "correlation_id": event.correlation_id,
        "causation_id": event.causation_id,
        "trace_id": event.trace_id,
        "payload_hash": event.payload_hash,
        "occurred_at": event.occurred_at.isoformat(),
    }


def _material_manifest(manifest: dict[str, Any]) -> dict[str, Any]:
    return {
        "material_manifest_id": manifest["material_manifest_id"],
        "invocation_type": manifest["invocation_type"],
        "invocation_id": manifest["invocation_id"],
        "provider": manifest["provider"],
        "purpose": manifest["purpose"],
        "policy_version": manifest["policy_version"],
        "policy_decision": manifest["policy_decision"],
        "decision_reason": manifest["decision_reason"],
        "materials": [
            {
                "material_ref": material["material_ref"],
                "source_version_id": material["source_version_id"],
                "content_hash": material["content_hash"],
                "location": material["location"],
                "length": material["length"],
                "sensitivity_level": material["sensitivity_level"],
                "redacted_preview": material["redacted_preview"],
            }
            for material in manifest["materials"]
        ],
        "contains_profile_data": manifest["contains_profile_data"],
        "created_at": manifest["created_at"],
        "research_case_id": manifest["research_case_id"],
        "research_run_id": manifest["research_run_id"],
        "research_attempt_id": manifest["research_attempt_id"],
        "capability_invocation_id": manifest["capability_invocation_id"],
        "intake_or_import_context_ref": manifest["intake_or_import_context_ref"],
        "correlation_id": manifest["correlation_id"],
        "causation_id": manifest["causation_id"],
        "trace_id": manifest["trace_id"],
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
            "observed_at": datetime.now(timezone.utc).isoformat(),
        },
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


__all__ = [
    "DiagnosticsQueryHandler",
    "create_diagnostics_developer_router",
    "register_diagnostics_developer_routes",
]
