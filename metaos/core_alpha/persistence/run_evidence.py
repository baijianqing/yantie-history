"""Repositories for the Core Alpha ResearchRun and Evidence slices."""

from __future__ import annotations

import json
import sqlite3
from datetime import datetime
from typing import Any

from metaos.core_alpha.contracts.common import OpenCodeValue
from metaos.core_alpha.contracts.execution import (
    EvidenceLocation,
    EvidenceUnitResponse,
    EvidenceUseType,
    EvidenceValidityStatus,
    ExecutionCheckpointResponse,
    ExecutionCheckpointType,
    ResearchAttemptResponse,
    ResearchRunOutcomeResponse,
    ResearchRunOutcomeType,
    ResearchRunResponse,
    ResearchRunStatus,
    ResearchEvidenceUseResponse,
    RetrievalRunResponse,
    RunExecutionSpecResponse,
)
from metaos.core_alpha.persistence.repositories import (
    ConcurrencyConflictError,
    IdempotencyConflictError,
    RecordNotFoundError,
    RepositoryBase,
    _canonical_json,
    _utc_iso,
)


def _json(value: Any) -> str:
    return _canonical_json(value)


def _load_json(value: str | None, default: Any) -> Any:
    return json.loads(value) if value is not None else default


def _dt(value: str | None) -> datetime | None:
    return datetime.fromisoformat(value) if value is not None else None


def _open_code(code: str, registry_version: str) -> OpenCodeValue:
    return OpenCodeValue(code=code, registry_version=registry_version)


class RunEvidenceRepository(RepositoryBase):
    table_name = "core_alpha_research_runs"
    id_column = "research_run_id"

    def create_research_run(
        self,
        *,
        research_run: ResearchRunResponse,
        execution_spec: RunExecutionSpecResponse,
    ) -> None:
        if research_run.research_run_id != execution_spec.research_run_id:
            raise ValueError("execution spec must belong to the research run")
        if research_run.run_execution_spec_id != execution_spec.run_execution_spec_id:
            raise ValueError("research run must reference the provided execution spec")
        if research_run.knowledge_scope_version_id != execution_spec.knowledge_scope_version_id:
            raise ValueError("execution spec scope must match the run scope")
        if research_run.research_plan_version_id != execution_spec.research_plan_version_id:
            raise ValueError("execution spec plan must match the run plan")
        self._validate_run_inputs(research_run)
        self.connection.execute(
            """
            INSERT INTO core_alpha_research_runs (
                research_run_id, research_case_id, research_question_id,
                knowledge_scope_version_id, research_plan_version_id,
                run_execution_spec_id, status, revision, created_at, started_at,
                ended_at, superseded_by_run_id
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            self._run_values(research_run),
        )
        self.connection.execute(
            """
            INSERT INTO core_alpha_run_execution_specs (
                run_execution_spec_id, research_run_id, knowledge_scope_version_id,
                source_resolution_ids_json, research_plan_version_id,
                source_version_ids_json, index_generation_ids_json,
                retrieval_strategy_version, context_strategy_version,
                embedding_contract_json, reranker_contract_json,
                capability_contracts_json, allowed_implementations_json,
                fallback_policy_json, prompt_version, output_schema_version,
                audit_policy_version, decision_fitness_policy_version,
                egress_policy_version, system_safety_limits_json, created_at,
                budget_snapshot_id
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            self._execution_spec_values(execution_spec),
        )

    def get_research_run(self, research_run_id: str) -> ResearchRunResponse:
        row = self.connection.execute(
            "SELECT * FROM core_alpha_research_runs WHERE research_run_id = ?",
            (research_run_id,),
        ).fetchone()
        if row is None:
            raise RecordNotFoundError(f"research run not found: {research_run_id}")
        return self._run(row)

    def get_run_execution_spec(self, run_execution_spec_id: str) -> RunExecutionSpecResponse:
        row = self.connection.execute(
            """
            SELECT * FROM core_alpha_run_execution_specs
            WHERE run_execution_spec_id = ?
            """,
            (run_execution_spec_id,),
        ).fetchone()
        if row is None:
            raise RecordNotFoundError(f"run execution spec not found: {run_execution_spec_id}")
        return self._execution_spec(row)

    def add_attempt(self, attempt: ResearchAttemptResponse) -> None:
        self.get_research_run(attempt.research_run_id)
        if attempt.attempt_number == 1:
            existing = self.connection.execute(
                """
                SELECT 1 FROM core_alpha_research_attempts
                WHERE research_run_id = ? AND attempt_number = 1
                """,
                (attempt.research_run_id,),
            ).fetchone()
            if existing is not None:
                raise ConcurrencyConflictError("first attempt already exists")
        else:
            previous = self.get_attempt(attempt.previous_attempt_id or "")
            if previous.research_run_id != attempt.research_run_id:
                raise ValueError("previous attempt must belong to the same run")
            if previous.attempt_number != attempt.attempt_number - 1:
                raise ValueError("previous attempt number must be contiguous")
        self.connection.execute(
            """
            INSERT INTO core_alpha_research_attempts (
                research_attempt_id, research_run_id, attempt_number, attempt_mode,
                status, created_at, previous_attempt_id, started_at, ended_at,
                failure_category_code, failure_category_registry_version, failure_reason
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            self._attempt_values(attempt),
        )

    def get_attempt(self, research_attempt_id: str) -> ResearchAttemptResponse:
        row = self.connection.execute(
            """
            SELECT * FROM core_alpha_research_attempts
            WHERE research_attempt_id = ?
            """,
            (research_attempt_id,),
        ).fetchone()
        if row is None:
            raise RecordNotFoundError(f"research attempt not found: {research_attempt_id}")
        return self._attempt(row)

    def list_attempts(self, research_run_id: str) -> list[ResearchAttemptResponse]:
        rows = self.connection.execute(
            """
            SELECT * FROM core_alpha_research_attempts
            WHERE research_run_id = ?
            ORDER BY attempt_number
            """,
            (research_run_id,),
        ).fetchall()
        return [self._attempt(row) for row in rows]

    def add_retrieval_run(self, retrieval_run: RetrievalRunResponse) -> None:
        attempt = self.get_attempt(retrieval_run.research_attempt_id)
        run = self.get_research_run(attempt.research_run_id)
        binding = self.connection.execute(
            """
            SELECT knowledge_scope_version_id
            FROM core_alpha_knowledge_scope_bindings
            WHERE knowledge_scope_source_binding_id = ?
            """,
            (retrieval_run.knowledge_scope_source_binding_id,),
        ).fetchone()
        if binding is None:
            raise RecordNotFoundError(
                "knowledge scope source binding not found: "
                f"{retrieval_run.knowledge_scope_source_binding_id}"
            )
        if binding["knowledge_scope_version_id"] != run.knowledge_scope_version_id:
            raise ValueError("retrieval binding must belong to the run scope version")
        self.connection.execute(
            """
            INSERT INTO core_alpha_retrieval_runs (
                retrieval_run_id, research_attempt_id,
                knowledge_scope_source_binding_id, retrieval_channel_code,
                retrieval_channel_registry_version, query_ref, status,
                retrieval_outcome, created_at, index_generation_id, started_at,
                ended_at, failure_reason
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            self._retrieval_values(retrieval_run),
        )

    def get_retrieval_run(self, retrieval_run_id: str) -> RetrievalRunResponse:
        row = self.connection.execute(
            "SELECT * FROM core_alpha_retrieval_runs WHERE retrieval_run_id = ?",
            (retrieval_run_id,),
        ).fetchone()
        if row is None:
            raise RecordNotFoundError(f"retrieval run not found: {retrieval_run_id}")
        return self._retrieval(row)

    def list_retrieval_runs(self, research_attempt_id: str) -> list[RetrievalRunResponse]:
        rows = self.connection.execute(
            """
            SELECT * FROM core_alpha_retrieval_runs
            WHERE research_attempt_id = ?
            ORDER BY created_at, retrieval_run_id
            """,
            (research_attempt_id,),
        ).fetchall()
        return [self._retrieval(row) for row in rows]

    def commit_outcome(
        self,
        outcome: ResearchRunOutcomeResponse,
        *,
        expected_run_revision: int,
        ended_at: datetime,
        superseded_by_run_id: str | None = None,
    ) -> ResearchRunResponse:
        run = self.get_research_run(outcome.research_run_id)
        terminal_status = self._terminal_status_for_outcome(outcome.outcome_type)
        if terminal_status == ResearchRunStatus.superseded:
            if superseded_by_run_id is None:
                raise ValueError("superseded outcomes require superseded_by_run_id")
        elif superseded_by_run_id is not None:
            raise ValueError("only superseded outcomes can include superseded_by_run_id")
        if run.status in {
            ResearchRunStatus.completed,
            ResearchRunStatus.failed,
            ResearchRunStatus.cancelled,
            ResearchRunStatus.superseded,
        }:
            raise ConcurrencyConflictError("research run is already terminal")
        existing = self.connection.execute(
            """
            SELECT 1 FROM core_alpha_research_run_outcomes
            WHERE research_run_id = ?
            """,
            (outcome.research_run_id,),
        ).fetchone()
        if existing is not None:
            raise ConcurrencyConflictError("research run outcome already exists")
        self.connection.execute(
            """
            INSERT INTO core_alpha_research_run_outcomes (
                research_run_outcome_id, research_run_id, outcome_type, reason_code,
                reason_registry_version, reason_summary, created_at,
                judgment_card_version_id
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            self._outcome_values(outcome),
        )
        self.compare_and_swap_revision(
            outcome.research_run_id,
            expected_revision=expected_run_revision,
            updates={
                "status": terminal_status.value,
                "ended_at": _utc_iso(ended_at),
                "superseded_by_run_id": superseded_by_run_id,
            },
        )
        return self.get_research_run(outcome.research_run_id)

    def get_outcome(self, research_run_id: str) -> ResearchRunOutcomeResponse:
        row = self.connection.execute(
            """
            SELECT * FROM core_alpha_research_run_outcomes
            WHERE research_run_id = ?
            """,
            (research_run_id,),
        ).fetchone()
        if row is None:
            raise RecordNotFoundError(f"research run outcome not found: {research_run_id}")
        return self._outcome(row)

    def put_checkpoint(self, checkpoint: ExecutionCheckpointResponse) -> ExecutionCheckpointResponse:
        existing = self.connection.execute(
            """
            SELECT * FROM core_alpha_execution_checkpoints
            WHERE idempotency_key = ?
            """,
            (checkpoint.idempotency_key,),
        ).fetchone()
        if existing is not None:
            record = self._checkpoint(existing)
            if record != checkpoint:
                raise IdempotencyConflictError(
                    "checkpoint idempotency key was already used with different data"
                )
            return record
        self.get_research_run(checkpoint.research_run_id)
        if checkpoint.research_attempt_id is not None:
            attempt = self.get_attempt(checkpoint.research_attempt_id)
            if attempt.research_run_id != checkpoint.research_run_id:
                raise ValueError("checkpoint attempt must belong to the research run")
        self.connection.execute(
            """
            INSERT INTO core_alpha_execution_checkpoints (
                execution_checkpoint_id, research_run_id, checkpoint_type,
                input_revision, completed_at, result_ref_id, idempotency_key,
                research_attempt_id
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            self._checkpoint_values(checkpoint),
        )
        return self.get_checkpoint(checkpoint.execution_checkpoint_id)

    def get_checkpoint(self, execution_checkpoint_id: str) -> ExecutionCheckpointResponse:
        row = self.connection.execute(
            """
            SELECT * FROM core_alpha_execution_checkpoints
            WHERE execution_checkpoint_id = ?
            """,
            (execution_checkpoint_id,),
        ).fetchone()
        if row is None:
            raise RecordNotFoundError(f"execution checkpoint not found: {execution_checkpoint_id}")
        return self._checkpoint(row)

    def create_evidence_unit(self, evidence_unit: EvidenceUnitResponse) -> EvidenceUnitResponse:
        if evidence_unit.origin_retrieval_run_id is not None:
            self.get_retrieval_run(evidence_unit.origin_retrieval_run_id)
        self.connection.execute(
            """
            INSERT OR IGNORE INTO core_alpha_evidence_units (
                evidence_unit_id, knowledge_item_id, knowledge_item_version_id,
                location_json, excerpt, content_hash, origin_type_code,
                origin_type_registry_version, validity_status, revision, created_at,
                updated_at, chunk_id, origin_retrieval_run_id
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            self._evidence_unit_values(evidence_unit),
        )
        return self._get_evidence_unit_by_identity(evidence_unit)

    def get_evidence_unit(self, evidence_unit_id: str) -> EvidenceUnitResponse:
        row = self.connection.execute(
            "SELECT * FROM core_alpha_evidence_units WHERE evidence_unit_id = ?",
            (evidence_unit_id,),
        ).fetchone()
        if row is None:
            raise RecordNotFoundError(f"evidence unit not found: {evidence_unit_id}")
        return self._evidence_unit(row)

    def update_evidence_validity(
        self,
        evidence_unit_id: str,
        *,
        expected_revision: int,
        validity_status: EvidenceValidityStatus,
        updated_at: datetime,
    ) -> EvidenceUnitResponse:
        self.compare_evidence_revision(
            evidence_unit_id,
            expected_revision=expected_revision,
            updates={
                "validity_status": validity_status.value,
                "updated_at": _utc_iso(updated_at),
            },
        )
        return self.get_evidence_unit(evidence_unit_id)

    def add_research_evidence_use(
        self,
        evidence_use: ResearchEvidenceUseResponse,
    ) -> None:
        run = self.get_research_run(evidence_use.research_run_id)
        attempt = self.get_attempt(evidence_use.research_attempt_id)
        if attempt.research_run_id != evidence_use.research_run_id:
            raise ValueError("evidence use attempt must belong to the research run")
        if evidence_use.knowledge_scope_version_id != run.knowledge_scope_version_id:
            raise ValueError("evidence use scope must match the research run scope")
        evidence = self.get_evidence_unit(evidence_use.evidence_unit_id)
        if evidence.revision != evidence_use.evidence_revision:
            raise ConcurrencyConflictError("evidence revision snapshot is stale")
        if evidence_use.use_type == EvidenceUseType.retrieved:
            retrieval = self.get_retrieval_run(evidence_use.retrieval_run_id or "")
            if retrieval.research_attempt_id != evidence_use.research_attempt_id:
                raise ValueError("retrieved evidence use must reference this attempt")
        elif evidence_use.retrieval_run_id is not None:
            raise ValueError("reused evidence use cannot reference a retrieval run")
        self.connection.execute(
            """
            INSERT INTO core_alpha_research_evidence_uses (
                research_evidence_use_id, research_run_id, research_attempt_id,
                evidence_unit_id, evidence_revision, knowledge_scope_version_id,
                use_type, validity_checked_at, validity_result, created_at,
                retrieval_run_id
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            self._evidence_use_values(evidence_use),
        )

    def get_research_evidence_use(
        self,
        research_evidence_use_id: str,
    ) -> ResearchEvidenceUseResponse:
        row = self.connection.execute(
            """
            SELECT * FROM core_alpha_research_evidence_uses
            WHERE research_evidence_use_id = ?
            """,
            (research_evidence_use_id,),
        ).fetchone()
        if row is None:
            raise RecordNotFoundError(
                f"research evidence use not found: {research_evidence_use_id}"
            )
        return self._evidence_use(row)

    def list_research_evidence_uses(self, research_run_id: str) -> list[ResearchEvidenceUseResponse]:
        rows = self.connection.execute(
            """
            SELECT * FROM core_alpha_research_evidence_uses
            WHERE research_run_id = ?
            ORDER BY created_at, research_evidence_use_id
            """,
            (research_run_id,),
        ).fetchall()
        return [self._evidence_use(row) for row in rows]

    def compare_evidence_revision(
        self,
        evidence_unit_id: str,
        *,
        expected_revision: int,
        updates: dict[str, Any],
    ) -> int:
        if "revision" in updates or "evidence_unit_id" in updates:
            raise ValueError("identity and revision cannot be supplied as update fields")
        assignments = [f"{column} = ?" for column in updates]
        assignments.append("revision = ?")
        next_revision = expected_revision + 1
        cursor = self.connection.execute(
            f"""
            UPDATE core_alpha_evidence_units
            SET {', '.join(assignments)}
            WHERE evidence_unit_id = ? AND revision = ?
            """,
            [*updates.values(), next_revision, evidence_unit_id, expected_revision],
        )
        if cursor.rowcount == 1:
            return next_revision
        exists = self.connection.execute(
            "SELECT 1 FROM core_alpha_evidence_units WHERE evidence_unit_id = ?",
            (evidence_unit_id,),
        ).fetchone()
        if exists is None:
            raise RecordNotFoundError(f"evidence unit not found: {evidence_unit_id}")
        raise ConcurrencyConflictError(
            f"evidence revision conflict for {evidence_unit_id}: expected {expected_revision}"
        )

    def _validate_run_inputs(self, research_run: ResearchRunResponse) -> None:
        question = self.connection.execute(
            """
            SELECT research_case_id FROM core_alpha_research_questions
            WHERE research_question_id = ?
            """,
            (research_run.research_question_id,),
        ).fetchone()
        if question is None:
            raise RecordNotFoundError(
                f"research question not found: {research_run.research_question_id}"
            )
        if question["research_case_id"] != research_run.research_case_id:
            raise ValueError("research question must belong to the research case")
        scope = self.connection.execute(
            """
            SELECT research_case_id FROM core_alpha_knowledge_scope_versions
            WHERE knowledge_scope_version_id = ?
            """,
            (research_run.knowledge_scope_version_id,),
        ).fetchone()
        if scope is None:
            raise RecordNotFoundError(
                f"knowledge scope version not found: {research_run.knowledge_scope_version_id}"
            )
        if scope["research_case_id"] != research_run.research_case_id:
            raise ValueError("knowledge scope must belong to the research case")
        plan = self.connection.execute(
            """
            SELECT research_case_id, knowledge_scope_version_id
            FROM core_alpha_research_plan_versions
            WHERE research_plan_version_id = ?
            """,
            (research_run.research_plan_version_id,),
        ).fetchone()
        if plan is None:
            raise RecordNotFoundError(
                f"research plan version not found: {research_run.research_plan_version_id}"
            )
        if plan["research_case_id"] != research_run.research_case_id:
            raise ValueError("research plan must belong to the research case")
        if plan["knowledge_scope_version_id"] != research_run.knowledge_scope_version_id:
            raise ValueError("research plan scope must match the research run scope")

    @staticmethod
    def _terminal_status_for_outcome(outcome_type: ResearchRunOutcomeType) -> ResearchRunStatus:
        if outcome_type in {
            ResearchRunOutcomeType.completed_with_judgment,
            ResearchRunOutcomeType.insufficient_evidence,
            ResearchRunOutcomeType.audit_blocked,
            ResearchRunOutcomeType.deferred_before_judgment,
        }:
            return ResearchRunStatus.completed
        if outcome_type == ResearchRunOutcomeType.execution_failed:
            return ResearchRunStatus.failed
        if outcome_type == ResearchRunOutcomeType.cancelled_by_user:
            return ResearchRunStatus.cancelled
        return ResearchRunStatus.superseded

    @staticmethod
    def _run_values(run: ResearchRunResponse) -> tuple[Any, ...]:
        return (
            run.research_run_id,
            run.research_case_id,
            run.research_question_id,
            run.knowledge_scope_version_id,
            run.research_plan_version_id,
            run.run_execution_spec_id,
            run.status.value,
            run.revision,
            _utc_iso(run.created_at),
            _utc_iso(run.started_at) if run.started_at else None,
            _utc_iso(run.ended_at) if run.ended_at else None,
            run.superseded_by_run_id,
        )

    @staticmethod
    def _execution_spec_values(spec: RunExecutionSpecResponse) -> tuple[Any, ...]:
        return (
            spec.run_execution_spec_id,
            spec.research_run_id,
            spec.knowledge_scope_version_id,
            _json(spec.source_resolution_ids),
            spec.research_plan_version_id,
            _json(spec.source_version_ids),
            _json(spec.index_generation_ids),
            spec.retrieval_strategy_version,
            spec.context_strategy_version,
            _json(spec.embedding_contract),
            _json(spec.reranker_contract),
            _json(spec.capability_contracts),
            _json(spec.allowed_implementations),
            _json(spec.fallback_policy),
            spec.prompt_version,
            spec.output_schema_version,
            spec.audit_policy_version,
            spec.decision_fitness_policy_version,
            spec.egress_policy_version,
            _json(spec.system_safety_limits),
            _utc_iso(spec.created_at),
            spec.budget_snapshot_id,
        )

    @staticmethod
    def _attempt_values(attempt: ResearchAttemptResponse) -> tuple[Any, ...]:
        failure_category = attempt.failure_category
        return (
            attempt.research_attempt_id,
            attempt.research_run_id,
            attempt.attempt_number,
            attempt.attempt_mode.value,
            attempt.status.value,
            _utc_iso(attempt.created_at),
            attempt.previous_attempt_id,
            _utc_iso(attempt.started_at) if attempt.started_at else None,
            _utc_iso(attempt.ended_at) if attempt.ended_at else None,
            failure_category.code if failure_category else None,
            failure_category.registry_version if failure_category else None,
            attempt.failure_reason,
        )

    @staticmethod
    def _retrieval_values(retrieval_run: RetrievalRunResponse) -> tuple[Any, ...]:
        return (
            retrieval_run.retrieval_run_id,
            retrieval_run.research_attempt_id,
            retrieval_run.knowledge_scope_source_binding_id,
            retrieval_run.retrieval_channel.code,
            retrieval_run.retrieval_channel.registry_version,
            retrieval_run.query_ref,
            retrieval_run.status.value,
            retrieval_run.retrieval_outcome.value if retrieval_run.retrieval_outcome else None,
            _utc_iso(retrieval_run.created_at),
            retrieval_run.index_generation_id,
            _utc_iso(retrieval_run.started_at) if retrieval_run.started_at else None,
            _utc_iso(retrieval_run.ended_at) if retrieval_run.ended_at else None,
            retrieval_run.failure_reason,
        )

    @staticmethod
    def _outcome_values(outcome: ResearchRunOutcomeResponse) -> tuple[Any, ...]:
        return (
            outcome.research_run_outcome_id,
            outcome.research_run_id,
            outcome.outcome_type.value,
            outcome.reason_code.code,
            outcome.reason_code.registry_version,
            outcome.reason_summary,
            _utc_iso(outcome.created_at),
            outcome.judgment_card_version_id,
        )

    @staticmethod
    def _checkpoint_values(checkpoint: ExecutionCheckpointResponse) -> tuple[Any, ...]:
        return (
            checkpoint.execution_checkpoint_id,
            checkpoint.research_run_id,
            checkpoint.checkpoint_type.value,
            checkpoint.input_revision,
            _utc_iso(checkpoint.completed_at),
            checkpoint.result_ref_id,
            checkpoint.idempotency_key,
            checkpoint.research_attempt_id,
        )

    @staticmethod
    def _evidence_unit_values(evidence_unit: EvidenceUnitResponse) -> tuple[Any, ...]:
        return (
            evidence_unit.evidence_unit_id,
            evidence_unit.knowledge_item_id,
            evidence_unit.knowledge_item_version_id,
            _json(evidence_unit.location.model_dump(mode="json")),
            evidence_unit.excerpt,
            evidence_unit.content_hash,
            evidence_unit.origin_type.code,
            evidence_unit.origin_type.registry_version,
            evidence_unit.validity_status.value,
            evidence_unit.revision,
            _utc_iso(evidence_unit.created_at),
            _utc_iso(evidence_unit.updated_at),
            evidence_unit.chunk_id,
            evidence_unit.origin_retrieval_run_id,
        )

    @staticmethod
    def _evidence_use_values(evidence_use: ResearchEvidenceUseResponse) -> tuple[Any, ...]:
        return (
            evidence_use.research_evidence_use_id,
            evidence_use.research_run_id,
            evidence_use.research_attempt_id,
            evidence_use.evidence_unit_id,
            evidence_use.evidence_revision,
            evidence_use.knowledge_scope_version_id,
            evidence_use.use_type.value,
            _utc_iso(evidence_use.validity_checked_at),
            evidence_use.validity_result.value,
            _utc_iso(evidence_use.created_at),
            evidence_use.retrieval_run_id,
        )

    def _get_evidence_unit_by_identity(
        self,
        evidence_unit: EvidenceUnitResponse,
    ) -> EvidenceUnitResponse:
        row = self.connection.execute(
            """
            SELECT * FROM core_alpha_evidence_units
            WHERE knowledge_item_version_id = ?
              AND location_json = ?
              AND content_hash = ?
            """,
            (
                evidence_unit.knowledge_item_version_id,
                _json(evidence_unit.location.model_dump(mode="json")),
                evidence_unit.content_hash,
            ),
        ).fetchone()
        if row is None:
            raise RecordNotFoundError("evidence unit identity was not persisted")
        return self._evidence_unit(row)

    @staticmethod
    def _run(row: sqlite3.Row) -> ResearchRunResponse:
        return ResearchRunResponse(
            research_run_id=row["research_run_id"],
            research_case_id=row["research_case_id"],
            research_question_id=row["research_question_id"],
            knowledge_scope_version_id=row["knowledge_scope_version_id"],
            research_plan_version_id=row["research_plan_version_id"],
            run_execution_spec_id=row["run_execution_spec_id"],
            status=row["status"],
            revision=row["revision"],
            created_at=datetime.fromisoformat(row["created_at"]),
            started_at=_dt(row["started_at"]),
            ended_at=_dt(row["ended_at"]),
            superseded_by_run_id=row["superseded_by_run_id"],
        )

    @staticmethod
    def _execution_spec(row: sqlite3.Row) -> RunExecutionSpecResponse:
        return RunExecutionSpecResponse(
            run_execution_spec_id=row["run_execution_spec_id"],
            research_run_id=row["research_run_id"],
            knowledge_scope_version_id=row["knowledge_scope_version_id"],
            source_resolution_ids=_load_json(row["source_resolution_ids_json"], []),
            research_plan_version_id=row["research_plan_version_id"],
            source_version_ids=_load_json(row["source_version_ids_json"], []),
            index_generation_ids=_load_json(row["index_generation_ids_json"], []),
            retrieval_strategy_version=row["retrieval_strategy_version"],
            context_strategy_version=row["context_strategy_version"],
            embedding_contract=_load_json(row["embedding_contract_json"], {}),
            reranker_contract=_load_json(row["reranker_contract_json"], {}),
            capability_contracts=_load_json(row["capability_contracts_json"], []),
            allowed_implementations=_load_json(row["allowed_implementations_json"], []),
            fallback_policy=_load_json(row["fallback_policy_json"], {}),
            prompt_version=row["prompt_version"],
            output_schema_version=row["output_schema_version"],
            audit_policy_version=row["audit_policy_version"],
            decision_fitness_policy_version=row["decision_fitness_policy_version"],
            egress_policy_version=row["egress_policy_version"],
            system_safety_limits=_load_json(row["system_safety_limits_json"], {}),
            created_at=datetime.fromisoformat(row["created_at"]),
            budget_snapshot_id=row["budget_snapshot_id"],
        )

    @staticmethod
    def _attempt(row: sqlite3.Row) -> ResearchAttemptResponse:
        failure_category = None
        if row["failure_category_code"] is not None:
            failure_category = _open_code(
                row["failure_category_code"],
                row["failure_category_registry_version"],
            )
        return ResearchAttemptResponse(
            research_attempt_id=row["research_attempt_id"],
            research_run_id=row["research_run_id"],
            attempt_number=row["attempt_number"],
            attempt_mode=row["attempt_mode"],
            status=row["status"],
            created_at=datetime.fromisoformat(row["created_at"]),
            previous_attempt_id=row["previous_attempt_id"],
            started_at=_dt(row["started_at"]),
            ended_at=_dt(row["ended_at"]),
            failure_category=failure_category,
            failure_reason=row["failure_reason"],
        )

    @staticmethod
    def _retrieval(row: sqlite3.Row) -> RetrievalRunResponse:
        return RetrievalRunResponse(
            retrieval_run_id=row["retrieval_run_id"],
            research_attempt_id=row["research_attempt_id"],
            knowledge_scope_source_binding_id=row["knowledge_scope_source_binding_id"],
            retrieval_channel=_open_code(
                row["retrieval_channel_code"],
                row["retrieval_channel_registry_version"],
            ),
            query_ref=row["query_ref"],
            status=row["status"],
            retrieval_outcome=row["retrieval_outcome"],
            created_at=datetime.fromisoformat(row["created_at"]),
            index_generation_id=row["index_generation_id"],
            started_at=_dt(row["started_at"]),
            ended_at=_dt(row["ended_at"]),
            failure_reason=row["failure_reason"],
        )

    @staticmethod
    def _outcome(row: sqlite3.Row) -> ResearchRunOutcomeResponse:
        return ResearchRunOutcomeResponse(
            research_run_outcome_id=row["research_run_outcome_id"],
            research_run_id=row["research_run_id"],
            outcome_type=row["outcome_type"],
            reason_code=_open_code(row["reason_code"], row["reason_registry_version"]),
            reason_summary=row["reason_summary"],
            created_at=datetime.fromisoformat(row["created_at"]),
            judgment_card_version_id=row["judgment_card_version_id"],
        )

    @staticmethod
    def _checkpoint(row: sqlite3.Row) -> ExecutionCheckpointResponse:
        return ExecutionCheckpointResponse(
            execution_checkpoint_id=row["execution_checkpoint_id"],
            research_run_id=row["research_run_id"],
            checkpoint_type=row["checkpoint_type"],
            input_revision=row["input_revision"],
            completed_at=datetime.fromisoformat(row["completed_at"]),
            result_ref_id=row["result_ref_id"],
            idempotency_key=row["idempotency_key"],
            research_attempt_id=row["research_attempt_id"],
        )

    @staticmethod
    def _evidence_unit(row: sqlite3.Row) -> EvidenceUnitResponse:
        return EvidenceUnitResponse(
            evidence_unit_id=row["evidence_unit_id"],
            knowledge_item_id=row["knowledge_item_id"],
            knowledge_item_version_id=row["knowledge_item_version_id"],
            location=EvidenceLocation.model_validate(_load_json(row["location_json"], {})),
            excerpt=row["excerpt"],
            content_hash=row["content_hash"],
            origin_type=_open_code(
                row["origin_type_code"],
                row["origin_type_registry_version"],
            ),
            validity_status=row["validity_status"],
            revision=row["revision"],
            created_at=datetime.fromisoformat(row["created_at"]),
            updated_at=datetime.fromisoformat(row["updated_at"]),
            chunk_id=row["chunk_id"],
            origin_retrieval_run_id=row["origin_retrieval_run_id"],
        )

    @staticmethod
    def _evidence_use(row: sqlite3.Row) -> ResearchEvidenceUseResponse:
        return ResearchEvidenceUseResponse(
            research_evidence_use_id=row["research_evidence_use_id"],
            research_run_id=row["research_run_id"],
            research_attempt_id=row["research_attempt_id"],
            evidence_unit_id=row["evidence_unit_id"],
            evidence_revision=row["evidence_revision"],
            knowledge_scope_version_id=row["knowledge_scope_version_id"],
            use_type=row["use_type"],
            validity_checked_at=datetime.fromisoformat(row["validity_checked_at"]),
            validity_result=row["validity_result"],
            created_at=datetime.fromisoformat(row["created_at"]),
            retrieval_run_id=row["retrieval_run_id"],
        )


__all__ = ["RunEvidenceRepository"]
