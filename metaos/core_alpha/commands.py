"""Application command orchestration for Core Alpha.

This module is intentionally infrastructure-facing: it coordinates
idempotency, trace events, outbox writes, lifecycle checks, and feature flag
audit records without implementing a concrete business use case.
"""

from __future__ import annotations

import copy
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Callable, Mapping

from metaos.core_alpha.contracts.common import CommandContext, OpenCodeValue, ResourceReference
from metaos.core_alpha.contracts.internal import (
    CandidateSubmissionStatus,
    SubmitCandidateResultCommandRequest,
    SubmitCandidateResultData,
)
from metaos.core_alpha.persistence import (
    CoreAlphaDatabase,
    RecordNotFoundError,
    StaleLifecycleError,
    TraceEventRecord,
    UnitOfWork,
)
from metaos.core_alpha.persistence.repositories import (
    _canonical_json,
    _payload_hash,
)


CORE_ALPHA_REGISTRY_VERSION = "core-alpha-v1"


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _response_hash(value: Mapping[str, Any]) -> str:
    return _payload_hash(_canonical_json(value))


@dataclass(frozen=True)
class OutboxMessage:
    outbox_id: str
    topic: str
    payload: Mapping[str, Any]
    idempotency_key: str
    available_at: datetime


@dataclass(frozen=True)
class CommandOutcome:
    data: Mapping[str, Any]
    primary_aggregate_type: str
    primary_aggregate_id: str
    primary_aggregate_revision: int
    response_status: int = 200
    event_type_code: str = "application_command_completed"
    event_payload: Mapping[str, Any] | None = None
    outbox_messages: tuple[OutboxMessage, ...] = ()


@dataclass(frozen=True)
class CommandExecution:
    status_code: int
    response_body: Mapping[str, Any]
    idempotent_replay: bool


CommandCallback = Callable[[UnitOfWork], CommandOutcome]


class ApplicationCommandHandler:
    """Single transactional entry point for state-changing commands."""

    def __init__(self, database: CoreAlphaDatabase):
        self.database = database

    def execute(
        self,
        *,
        scope: str,
        idempotency_key: str,
        request_body: Mapping[str, Any],
        context: CommandContext,
        callback: CommandCallback,
    ) -> CommandExecution:
        request_json = _canonical_json(request_body)
        request_hash = _payload_hash(request_json)
        with UnitOfWork(self.database) as uow:
            record, replay = uow.idempotency.begin(
                scope=scope,
                idempotency_key=idempotency_key,
                request_hash=request_hash,
                command_id=context.command_id,
                created_at=_now(),
            )
            if replay:
                if record.status != "completed" or record.response_body is None:
                    raise RuntimeError("idempotent command is already in progress")
                body = copy.deepcopy(record.response_body)
                body["command"]["idempotent_replay"] = True
                return CommandExecution(
                    status_code=record.response_status or 200,
                    response_body=body,
                    idempotent_replay=True,
                )

            outcome = callback(uow)
            body = self._response_body(outcome=outcome, context=context)
            event_payload = dict(outcome.event_payload or {"data": outcome.data})
            event_payload["response_status"] = outcome.response_status
            uow.events.append(
                self._event(
                    context=context,
                    aggregate_type=outcome.primary_aggregate_type,
                    aggregate_id=outcome.primary_aggregate_id,
                    aggregate_revision=outcome.primary_aggregate_revision,
                    event_type_code=outcome.event_type_code,
                    payload=event_payload,
                )
            )
            for message in outcome.outbox_messages:
                uow.outbox.enqueue(
                    outbox_id=message.outbox_id,
                    topic=message.topic,
                    payload=message.payload,
                    idempotency_key=message.idempotency_key,
                    available_at=message.available_at,
                    created_at=_now(),
                )
            completed = uow.idempotency.complete(
                scope=scope,
                idempotency_key=idempotency_key,
                request_hash=request_hash,
                response_status=outcome.response_status,
                response_body=body,
                completed_at=_now(),
            )
            return CommandExecution(
                status_code=completed.response_status or outcome.response_status,
                response_body=completed.response_body or body,
                idempotent_replay=False,
            )

    @staticmethod
    def _response_body(
        *,
        outcome: CommandOutcome,
        context: CommandContext,
    ) -> dict[str, Any]:
        return {
            "data": dict(outcome.data),
            "command": {
                "command_id": context.command_id,
                "trace_id": context.trace_id,
                "idempotency_key": context.idempotency_key,
                "idempotent_replay": False,
            },
            "consistency": {
                "source": "authoritative_store",
                "primary_aggregate": {
                    "aggregate_type": outcome.primary_aggregate_type,
                    "aggregate_id": outcome.primary_aggregate_id,
                    "revision": outcome.primary_aggregate_revision,
                },
                "affected_aggregates": [],
                "projection_checkpoint": None,
                "is_stale": False,
                "observed_at": _now().isoformat(),
            },
        }

    @staticmethod
    def _event(
        *,
        context: CommandContext,
        aggregate_type: str,
        aggregate_id: str,
        aggregate_revision: int,
        event_type_code: str,
        payload: Mapping[str, Any],
    ) -> TraceEventRecord:
        payload_dict = dict(payload)
        return TraceEventRecord(
            event_id=f"event_{uuid.uuid4().hex}",
            event_key=f"{context.command_id}:{event_type_code}",
            event_type_code=event_type_code,
            event_type_registry_version=CORE_ALPHA_REGISTRY_VERSION,
            aggregate_type=aggregate_type,
            aggregate_id=aggregate_id,
            aggregate_revision=aggregate_revision,
            actor_type_code=context.actor_type.code,
            actor_type_registry_version=context.actor_type.registry_version,
            actor_id=context.actor_id,
            correlation_id=context.correlation_id,
            causation_id=context.causation_id,
            trace_id=context.trace_id,
            payload_hash=_response_hash(payload_dict),
            payload=payload_dict,
            occurred_at=_now(),
        )


class CandidateResultCommandHandler:
    """Internal adapter for worker/capability candidate submissions."""

    def __init__(self, command_handler: ApplicationCommandHandler):
        self.command_handler = command_handler

    def submit(
        self,
        request: SubmitCandidateResultCommandRequest,
        *,
        context: CommandContext,
    ) -> CommandExecution:
        body = request.model_dump(mode="json")
        return self.command_handler.execute(
            scope=f"internal:candidate-result:{request.research_run_id}:{request.operation_type.code}",
            idempotency_key=context.idempotency_key,
            request_body=body,
            context=context,
            callback=lambda uow: self._handle(uow, request),
        )

    def _handle(
        self,
        uow: UnitOfWork,
        request: SubmitCandidateResultCommandRequest,
    ) -> CommandOutcome:
        status = CandidateSubmissionStatus.accepted_for_domain_processing
        candidate_result_id: str | None = f"candidate_result_{uuid.uuid4().hex}"
        follow_up_commands: list[ResourceReference] = []
        aggregate_revision = request.input_versions.research_run_revision

        tombstoned = self._is_tombstoned(uow, "research_run", request.research_run_id)
        if tombstoned:
            status = CandidateSubmissionStatus.rejected_tombstoned
            candidate_result_id = None
        else:
            try:
                uow.lifecycle.assert_current(
                    "research_run",
                    request.research_run_id,
                    request.lifecycle_generation,
                )
                run = uow.run_evidence.get_research_run(request.research_run_id)
                attempt = uow.run_evidence.get_attempt(request.research_attempt_id)
                spec = uow.run_evidence.get_run_execution_spec(
                    request.run_execution_spec_id,
                )
                aggregate_revision = run.revision
                if attempt.research_run_id != request.research_run_id:
                    status = CandidateSubmissionStatus.rejected_schema
                    candidate_result_id = None
                elif run.revision != request.input_versions.research_run_revision:
                    status = CandidateSubmissionStatus.rejected_version_mismatch
                    candidate_result_id = None
                elif spec.research_run_id != request.research_run_id:
                    status = CandidateSubmissionStatus.rejected_version_mismatch
                    candidate_result_id = None
                elif spec.knowledge_scope_version_id != (
                    request.input_versions.knowledge_scope_version_id
                ) or spec.research_plan_version_id != (
                    request.input_versions.research_plan_version_id
                ):
                    status = CandidateSubmissionStatus.rejected_version_mismatch
                    candidate_result_id = None
            except StaleLifecycleError:
                status = CandidateSubmissionStatus.rejected_lifecycle
                candidate_result_id = None
            except RecordNotFoundError:
                status = CandidateSubmissionStatus.rejected_schema
                candidate_result_id = None

        data = SubmitCandidateResultData(
            submission_status=status,
            capability_candidate_result_id=candidate_result_id,
            follow_up_commands=follow_up_commands,
        )
        data_payload = data.model_dump(mode="json")
        return CommandOutcome(
            data=data_payload,
            primary_aggregate_type="research_run",
            primary_aggregate_id=request.research_run_id,
            primary_aggregate_revision=aggregate_revision,
            event_type_code="candidate_result_submitted",
            event_payload={
                "operation_type": request.operation_type.model_dump(mode="json"),
                "submission": data_payload,
            },
        )

    @staticmethod
    def _is_tombstoned(
        uow: UnitOfWork,
        entity_type: str,
        entity_id: str,
    ) -> bool:
        row = uow.connection.execute(
            """
            SELECT generation FROM core_alpha_lifecycle_generations
            WHERE entity_type = ? AND entity_id = ?
            """,
            (entity_type, entity_id),
        ).fetchone()
        if row is None:
            return False
        tombstone = uow.connection.execute(
            """
            SELECT 1 FROM core_alpha_tombstones
            WHERE entity_type = ? AND entity_id = ? AND lifecycle_generation = ?
            """,
            (entity_type, entity_id, row["generation"]),
        ).fetchone()
        return tombstone is not None


@dataclass(frozen=True)
class FeatureFlagDefinition:
    flag_key: str
    description: str
    default_enabled: bool = False


@dataclass(frozen=True)
class FeatureFlagSnapshot:
    flag_key: str
    enabled: bool
    default_enabled: bool
    overridden: bool
    description: str


class StaticFeatureFlagRegistry:
    """In-process static flag registry with audited override events."""

    def __init__(self, definitions: tuple[FeatureFlagDefinition, ...]):
        if len({definition.flag_key for definition in definitions}) != len(definitions):
            raise ValueError("feature flag keys must be unique")
        self._definitions = {definition.flag_key: definition for definition in definitions}
        self._overrides: dict[str, bool] = {}

    @classmethod
    def core_alpha_defaults(cls) -> "StaticFeatureFlagRegistry":
        return cls(
            (
                FeatureFlagDefinition(
                    flag_key="core_alpha.asynchronous_execution",
                    description="Allow asynchronous ResearchRun execution.",
                    default_enabled=False,
                ),
                FeatureFlagDefinition(
                    flag_key="core_alpha.developer_diagnostics",
                    description="Expose developer diagnostics surfaces.",
                    default_enabled=False,
                ),
                FeatureFlagDefinition(
                    flag_key="core_alpha.complete_capabilities",
                    description="Enable Core Alpha Complete capability entry points.",
                    default_enabled=False,
                ),
            )
        )

    def get(self, flag_key: str) -> FeatureFlagSnapshot:
        definition = self._definition(flag_key)
        overridden = flag_key in self._overrides
        return FeatureFlagSnapshot(
            flag_key=flag_key,
            enabled=self._overrides.get(flag_key, definition.default_enabled),
            default_enabled=definition.default_enabled,
            overridden=overridden,
            description=definition.description,
        )

    def list(self) -> list[FeatureFlagSnapshot]:
        return [self.get(flag_key) for flag_key in sorted(self._definitions)]

    def set_override(
        self,
        *,
        uow: UnitOfWork,
        context: CommandContext,
        flag_key: str,
        enabled: bool,
        reason: str,
        occurred_at: datetime | None = None,
    ) -> FeatureFlagSnapshot:
        definition = self._definition(flag_key)
        occurred_at = occurred_at or _now()
        payload = {
            "flag_key": flag_key,
            "enabled": enabled,
            "default_enabled": definition.default_enabled,
            "reason": reason,
        }
        uow.events.append(
            TraceEventRecord(
                event_id=f"event_{uuid.uuid4().hex}",
                event_key=f"{context.command_id}:feature_flag_override",
                event_type_code="feature_flag_override",
                event_type_registry_version=CORE_ALPHA_REGISTRY_VERSION,
                aggregate_type="feature_flag",
                aggregate_id=flag_key,
                aggregate_revision=1,
                actor_type_code=context.actor_type.code,
                actor_type_registry_version=context.actor_type.registry_version,
                actor_id=context.actor_id,
                correlation_id=context.correlation_id,
                causation_id=context.causation_id,
                trace_id=context.trace_id,
                payload_hash=_response_hash(payload),
                payload=payload,
                occurred_at=occurred_at,
            )
        )
        self._overrides[flag_key] = enabled
        return self.get(flag_key)

    def _definition(self, flag_key: str) -> FeatureFlagDefinition:
        try:
            return self._definitions[flag_key]
        except KeyError as exc:
            raise KeyError(f"unknown feature flag: {flag_key}") from exc


__all__ = [
    "ApplicationCommandHandler",
    "CandidateResultCommandHandler",
    "CommandExecution",
    "CommandOutcome",
    "FeatureFlagDefinition",
    "FeatureFlagSnapshot",
    "OutboxMessage",
    "StaticFeatureFlagRegistry",
]
