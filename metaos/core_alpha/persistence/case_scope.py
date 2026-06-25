"""Repositories for the Core Alpha ResearchCase aggregate slice."""

from __future__ import annotations

import json
import sqlite3
from datetime import datetime
from typing import Any

from metaos.core_alpha.contracts.common import OpenCodeValue, ResourceReference
from metaos.core_alpha.contracts.scope import (
    EvidenceRequirementResponse,
    KnowledgeScopeSourceBindingResponse,
    KnowledgeScopeVersionResponse,
    ResearchCaseResponse,
    ResearchPlanVersionResponse,
    ResearchQuestionResponse,
    SourceResolutionResponse,
)
from metaos.core_alpha.persistence.repositories import (
    ConcurrencyConflictError,
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


class CaseScopeRepository(RepositoryBase):
    table_name = "core_alpha_research_cases"
    id_column = "research_case_id"

    def create_case(
        self,
        *,
        research_case: ResearchCaseResponse,
        root_question: ResearchQuestionResponse,
    ) -> None:
        if research_case.research_case_id != root_question.research_case_id:
            raise ValueError("root question must belong to the research case")
        if research_case.root_question_id != root_question.research_question_id:
            raise ValueError("research case must reference the provided root question")
        if research_case.current_question_id != root_question.research_question_id:
            raise ValueError("new case current question must be the root question")
        self.connection.execute(
            """
            INSERT INTO core_alpha_research_cases (
                research_case_id, title, root_question_id, current_question_id,
                lifecycle_status, attention_status, revision, created_at, updated_at,
                current_knowledge_scope_version_id, current_judgment_card_version_id,
                current_research_disposition_id, parent_research_case_id, archived_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            self._case_values(research_case),
        )
        self._insert_question(root_question)

    def add_question(
        self,
        question: ResearchQuestionResponse,
        *,
        expected_case_revision: int,
        updated_at: datetime,
    ) -> ResearchCaseResponse:
        self.get_case(question.research_case_id)
        self._insert_question(question)
        self.compare_and_swap_revision(
            question.research_case_id,
            expected_revision=expected_case_revision,
            updates={
                "current_question_id": question.research_question_id,
                "updated_at": _utc_iso(updated_at),
            },
        )
        return self.get_case(question.research_case_id)

    def get_case(self, research_case_id: str) -> ResearchCaseResponse:
        row = self.connection.execute(
            "SELECT * FROM core_alpha_research_cases WHERE research_case_id = ?",
            (research_case_id,),
        ).fetchone()
        if row is None:
            raise RecordNotFoundError(f"research case not found: {research_case_id}")
        return self._case(row)

    def get_question(self, research_question_id: str) -> ResearchQuestionResponse:
        row = self.connection.execute(
            "SELECT * FROM core_alpha_research_questions WHERE research_question_id = ?",
            (research_question_id,),
        ).fetchone()
        if row is None:
            raise RecordNotFoundError(f"research question not found: {research_question_id}")
        return self._question(row)

    def list_questions(self, research_case_id: str) -> list[ResearchQuestionResponse]:
        rows = self.connection.execute(
            """
            SELECT * FROM core_alpha_research_questions
            WHERE research_case_id = ?
            ORDER BY created_at, research_question_id
            """,
            (research_case_id,),
        ).fetchall()
        return [self._question(row) for row in rows]

    def add_source_resolutions(
        self,
        resolutions: list[SourceResolutionResponse],
        *,
        expected_case_revision: int,
        updated_at: datetime,
    ) -> ResearchCaseResponse:
        if not resolutions:
            raise ValueError("at least one source resolution is required")
        question_ids = {resolution.research_question_id for resolution in resolutions}
        if len(question_ids) != 1:
            raise ValueError("one command can only add resolutions for one question")
        question = self.get_question(next(iter(question_ids)))
        for resolution in resolutions:
            self.connection.execute(
                """
                INSERT INTO core_alpha_source_resolutions (
                    source_resolution_id, research_question_id, resolution_stage,
                    raw_anchor, requested_access_policy, resolution_status,
                    candidate_knowledge_item_ids_json, created_at, requested_version_hint,
                    resolved_knowledge_item_id, resolved_knowledge_item_version_id,
                    ambiguity_reason, failure_reason
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                self._source_resolution_values(resolution),
            )
        self.compare_and_swap_revision(
            question.research_case_id,
            expected_revision=expected_case_revision,
            updates={"updated_at": _utc_iso(updated_at)},
        )
        return self.get_case(question.research_case_id)

    def list_source_resolutions(self, research_question_id: str) -> list[SourceResolutionResponse]:
        rows = self.connection.execute(
            """
            SELECT * FROM core_alpha_source_resolutions
            WHERE research_question_id = ?
            ORDER BY created_at, source_resolution_id
            """,
            (research_question_id,),
        ).fetchall()
        return [self._source_resolution(row) for row in rows]

    def create_knowledge_scope(
        self,
        scope: KnowledgeScopeVersionResponse,
        *,
        expected_case_revision: int,
        updated_at: datetime,
    ) -> ResearchCaseResponse:
        if scope.version != 1 or scope.previous_version_id is not None:
            raise ValueError("create_knowledge_scope requires the initial version")
        self.get_case(scope.research_case_id)
        self._validate_scope_bindings_belong_to_case(scope)
        self.connection.execute(
            """
            INSERT INTO core_alpha_knowledge_scopes (
                knowledge_scope_id, research_case_id, current_version_id
            ) VALUES (?, ?, ?)
            """,
            (
                scope.knowledge_scope_id,
                scope.research_case_id,
                scope.knowledge_scope_version_id,
            ),
        )
        self._insert_scope_version(scope)
        self.compare_and_swap_revision(
            scope.research_case_id,
            expected_revision=expected_case_revision,
            updates={
                "current_knowledge_scope_version_id": scope.knowledge_scope_version_id,
                "updated_at": _utc_iso(updated_at),
            },
        )
        return self.get_case(scope.research_case_id)

    def adjust_knowledge_scope(
        self,
        scope: KnowledgeScopeVersionResponse,
        *,
        expected_case_revision: int,
        updated_at: datetime,
    ) -> ResearchCaseResponse:
        if scope.version <= 1 or scope.previous_version_id is None:
            raise ValueError("adjust_knowledge_scope requires a later version")
        current = self.connection.execute(
            """
            SELECT current_version_id FROM core_alpha_knowledge_scopes
            WHERE knowledge_scope_id = ? AND research_case_id = ?
            """,
            (scope.knowledge_scope_id, scope.research_case_id),
        ).fetchone()
        if current is None:
            raise RecordNotFoundError(f"knowledge scope not found: {scope.knowledge_scope_id}")
        if current["current_version_id"] != scope.previous_version_id:
            raise ConcurrencyConflictError("scope previous_version_id is not current")
        self._validate_scope_bindings_belong_to_case(scope)
        self.connection.execute(
            """
            UPDATE core_alpha_knowledge_scope_versions
            SET lifecycle_status = 'superseded'
            WHERE knowledge_scope_version_id = ? AND lifecycle_status = 'current'
            """,
            (scope.previous_version_id,),
        )
        self._insert_scope_version(scope)
        self.connection.execute(
            """
            UPDATE core_alpha_knowledge_scopes
            SET current_version_id = ?
            WHERE knowledge_scope_id = ?
            """,
            (scope.knowledge_scope_version_id, scope.knowledge_scope_id),
        )
        self.compare_and_swap_revision(
            scope.research_case_id,
            expected_revision=expected_case_revision,
            updates={
                "current_knowledge_scope_version_id": scope.knowledge_scope_version_id,
                "updated_at": _utc_iso(updated_at),
            },
        )
        return self.get_case(scope.research_case_id)

    def get_knowledge_scope_version(self, version_id: str) -> KnowledgeScopeVersionResponse:
        row = self.connection.execute(
            """
            SELECT * FROM core_alpha_knowledge_scope_versions
            WHERE knowledge_scope_version_id = ?
            """,
            (version_id,),
        ).fetchone()
        if row is None:
            raise RecordNotFoundError(f"knowledge scope version not found: {version_id}")
        return self._scope_version(row)

    def get_current_knowledge_scope(self, knowledge_scope_id: str) -> KnowledgeScopeVersionResponse:
        row = self.connection.execute(
            """
            SELECT current_version_id FROM core_alpha_knowledge_scopes
            WHERE knowledge_scope_id = ?
            """,
            (knowledge_scope_id,),
        ).fetchone()
        if row is None:
            raise RecordNotFoundError(f"knowledge scope not found: {knowledge_scope_id}")
        return self.get_knowledge_scope_version(row["current_version_id"])

    def get_current_knowledge_scope_for_case(self, research_case_id: str) -> KnowledgeScopeVersionResponse | None:
        current_id = self.get_case(research_case_id).current_knowledge_scope_version_id
        return self.get_knowledge_scope_version(current_id) if current_id else None

    def create_research_plan(
        self,
        plan: ResearchPlanVersionResponse,
        *,
        expected_case_revision: int,
        updated_at: datetime,
    ) -> ResearchCaseResponse:
        if plan.version != 1 or plan.previous_version_id is not None:
            raise ValueError("create_research_plan requires the initial version")
        self.get_case(plan.research_case_id)
        scope = self.get_knowledge_scope_version(plan.knowledge_scope_version_id)
        if scope.research_case_id != plan.research_case_id:
            raise ValueError("research plan scope must belong to the same case")
        self.connection.execute(
            """
            INSERT INTO core_alpha_research_plans (
                research_plan_id, research_case_id, current_version_id
            ) VALUES (?, ?, ?)
            """,
            (plan.research_plan_id, plan.research_case_id, plan.research_plan_version_id),
        )
        self._insert_plan_version(plan)
        self.compare_and_swap_revision(
            plan.research_case_id,
            expected_revision=expected_case_revision,
            updates={"updated_at": _utc_iso(updated_at)},
        )
        return self.get_case(plan.research_case_id)

    def adjust_research_plan(
        self,
        plan: ResearchPlanVersionResponse,
        *,
        expected_case_revision: int,
        updated_at: datetime,
    ) -> ResearchCaseResponse:
        if plan.version <= 1 or plan.previous_version_id is None:
            raise ValueError("adjust_research_plan requires a later version")
        current = self.connection.execute(
            """
            SELECT current_version_id FROM core_alpha_research_plans
            WHERE research_plan_id = ? AND research_case_id = ?
            """,
            (plan.research_plan_id, plan.research_case_id),
        ).fetchone()
        if current is None:
            raise RecordNotFoundError(f"research plan not found: {plan.research_plan_id}")
        if current["current_version_id"] != plan.previous_version_id:
            raise ConcurrencyConflictError("plan previous_version_id is not current")
        scope = self.get_knowledge_scope_version(plan.knowledge_scope_version_id)
        if scope.research_case_id != plan.research_case_id:
            raise ValueError("research plan scope must belong to the same case")
        self.connection.execute(
            """
            UPDATE core_alpha_research_plan_versions
            SET lifecycle_status = 'superseded'
            WHERE research_plan_version_id = ? AND lifecycle_status = 'current'
            """,
            (plan.previous_version_id,),
        )
        self._insert_plan_version(plan)
        self.connection.execute(
            """
            UPDATE core_alpha_research_plans
            SET current_version_id = ?
            WHERE research_plan_id = ?
            """,
            (plan.research_plan_version_id, plan.research_plan_id),
        )
        self.compare_and_swap_revision(
            plan.research_case_id,
            expected_revision=expected_case_revision,
            updates={"updated_at": _utc_iso(updated_at)},
        )
        return self.get_case(plan.research_case_id)

    def get_research_plan_version(self, version_id: str) -> ResearchPlanVersionResponse:
        row = self.connection.execute(
            """
            SELECT * FROM core_alpha_research_plan_versions
            WHERE research_plan_version_id = ?
            """,
            (version_id,),
        ).fetchone()
        if row is None:
            raise RecordNotFoundError(f"research plan version not found: {version_id}")
        return self._plan_version(row)

    def get_current_research_plan(self, research_plan_id: str) -> ResearchPlanVersionResponse:
        row = self.connection.execute(
            """
            SELECT current_version_id FROM core_alpha_research_plans
            WHERE research_plan_id = ?
            """,
            (research_plan_id,),
        ).fetchone()
        if row is None:
            raise RecordNotFoundError(f"research plan not found: {research_plan_id}")
        return self.get_research_plan_version(row["current_version_id"])

    def _insert_question(self, question: ResearchQuestionResponse) -> None:
        self.connection.execute(
            """
            INSERT INTO core_alpha_research_questions (
                research_question_id, research_case_id, question_text, question_role,
                created_by, created_at, parent_question_id
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                question.research_question_id,
                question.research_case_id,
                question.question_text,
                question.question_role.value,
                question.created_by,
                _utc_iso(question.created_at),
                question.parent_question_id,
            ),
        )

    def _validate_scope_bindings_belong_to_case(
        self,
        scope: KnowledgeScopeVersionResponse,
    ) -> None:
        for binding in scope.source_bindings:
            row = self.connection.execute(
                """
                SELECT q.research_case_id
                FROM core_alpha_source_resolutions sr
                JOIN core_alpha_research_questions q
                  ON q.research_question_id = sr.research_question_id
                WHERE sr.source_resolution_id = ?
                """,
                (binding.source_resolution_id,),
            ).fetchone()
            if row is None:
                raise RecordNotFoundError(
                    f"source resolution not found: {binding.source_resolution_id}"
                )
            if row["research_case_id"] != scope.research_case_id:
                raise ValueError("scope binding source resolution belongs to another case")

    def _insert_scope_version(self, scope: KnowledgeScopeVersionResponse) -> None:
        self.connection.execute(
            """
            INSERT INTO core_alpha_knowledge_scope_versions (
                knowledge_scope_version_id, knowledge_scope_id, research_case_id,
                version, lifecycle_status, scope_mode, default_access_policy,
                created_by, created_at, previous_version_id
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                scope.knowledge_scope_version_id,
                scope.knowledge_scope_id,
                scope.research_case_id,
                scope.version,
                scope.lifecycle_status.value,
                scope.scope_mode.value,
                scope.default_access_policy.value,
                scope.created_by,
                _utc_iso(scope.created_at),
                scope.previous_version_id,
            ),
        )
        for binding in scope.source_bindings:
            self.connection.execute(
                """
                INSERT INTO core_alpha_knowledge_scope_bindings (
                    knowledge_scope_source_binding_id, knowledge_scope_version_id,
                    source_resolution_id, knowledge_item_id, knowledge_item_version_id,
                    access_policy, analysis_role, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    binding.knowledge_scope_source_binding_id,
                    binding.knowledge_scope_version_id,
                    binding.source_resolution_id,
                    binding.knowledge_item_id,
                    binding.knowledge_item_version_id,
                    binding.access_policy.value,
                    binding.analysis_role.value if binding.analysis_role else None,
                    _utc_iso(binding.created_at),
                ),
            )

    def _insert_plan_version(self, plan: ResearchPlanVersionResponse) -> None:
        self.connection.execute(
            """
            INSERT INTO core_alpha_research_plan_versions (
                research_plan_version_id, research_plan_id, research_case_id,
                knowledge_scope_version_id, version, lifecycle_status, research_mode,
                primary_objective, minimum_completion_condition, created_at,
                previous_version_id, stop_conditions_json, research_budget_json
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                plan.research_plan_version_id,
                plan.research_plan_id,
                plan.research_case_id,
                plan.knowledge_scope_version_id,
                plan.version,
                plan.lifecycle_status.value,
                plan.research_mode.value,
                plan.primary_objective,
                plan.minimum_completion_condition,
                _utc_iso(plan.created_at),
                plan.previous_version_id,
                _json(plan.stop_conditions) if plan.stop_conditions is not None else None,
                _json(plan.research_budget) if plan.research_budget is not None else None,
            ),
        )
        for requirement in plan.evidence_requirements:
            self.connection.execute(
                """
                INSERT INTO core_alpha_evidence_requirements (
                    evidence_requirement_id, research_plan_version_id,
                    requirement_type_code, requirement_type_registry_version,
                    description, required_binding_ids_json, counterevidence_required,
                    alternative_interpretation_required, completion_condition,
                    minimum_count
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    requirement.evidence_requirement_id,
                    plan.research_plan_version_id,
                    requirement.requirement_type.code,
                    requirement.requirement_type.registry_version,
                    requirement.description,
                    _json(requirement.required_knowledge_scope_source_binding_ids),
                    1 if requirement.counterevidence_required else 0,
                    1 if requirement.alternative_interpretation_required else 0,
                    requirement.completion_condition,
                    requirement.minimum_count,
                ),
            )

    @staticmethod
    def _case_values(case: ResearchCaseResponse) -> tuple[Any, ...]:
        return (
            case.research_case_id,
            case.title,
            case.root_question_id,
            case.current_question_id,
            case.lifecycle_status.value,
            case.attention_status.value,
            case.revision,
            _utc_iso(case.created_at),
            _utc_iso(case.updated_at),
            case.current_knowledge_scope_version_id,
            case.current_judgment_card_version_id,
            case.current_research_disposition_id,
            case.parent_research_case_id,
            _utc_iso(case.archived_at) if case.archived_at else None,
        )

    @staticmethod
    def _source_resolution_values(resolution: SourceResolutionResponse) -> tuple[Any, ...]:
        return (
            resolution.source_resolution_id,
            resolution.research_question_id,
            resolution.resolution_stage.value,
            resolution.raw_anchor,
            resolution.requested_access_policy.value,
            resolution.resolution_status.value,
            _json(resolution.candidate_knowledge_item_ids),
            _utc_iso(resolution.created_at),
            resolution.requested_version_hint,
            resolution.resolved_knowledge_item_id,
            resolution.resolved_knowledge_item_version_id,
            resolution.ambiguity_reason,
            resolution.failure_reason,
        )

    def _scope_version(self, row: sqlite3.Row) -> KnowledgeScopeVersionResponse:
        bindings = self.connection.execute(
            """
            SELECT * FROM core_alpha_knowledge_scope_bindings
            WHERE knowledge_scope_version_id = ?
            ORDER BY created_at, knowledge_scope_source_binding_id
            """,
            (row["knowledge_scope_version_id"],),
        ).fetchall()
        return KnowledgeScopeVersionResponse(
            knowledge_scope_id=row["knowledge_scope_id"],
            knowledge_scope_version_id=row["knowledge_scope_version_id"],
            research_case_id=row["research_case_id"],
            version=row["version"],
            lifecycle_status=row["lifecycle_status"],
            scope_mode=row["scope_mode"],
            default_access_policy=row["default_access_policy"],
            source_bindings=[self._scope_binding(binding) for binding in bindings],
            created_by=row["created_by"],
            created_at=datetime.fromisoformat(row["created_at"]),
            previous_version_id=row["previous_version_id"],
        )

    @staticmethod
    def _scope_binding(row: sqlite3.Row) -> KnowledgeScopeSourceBindingResponse:
        return KnowledgeScopeSourceBindingResponse(
            knowledge_scope_source_binding_id=row["knowledge_scope_source_binding_id"],
            knowledge_scope_version_id=row["knowledge_scope_version_id"],
            source_resolution_id=row["source_resolution_id"],
            knowledge_item_id=row["knowledge_item_id"],
            knowledge_item_version_id=row["knowledge_item_version_id"],
            access_policy=row["access_policy"],
            analysis_role=row["analysis_role"],
            created_at=datetime.fromisoformat(row["created_at"]),
        )

    def _plan_version(self, row: sqlite3.Row) -> ResearchPlanVersionResponse:
        requirements = self.connection.execute(
            """
            SELECT * FROM core_alpha_evidence_requirements
            WHERE research_plan_version_id = ?
            ORDER BY evidence_requirement_id
            """,
            (row["research_plan_version_id"],),
        ).fetchall()
        return ResearchPlanVersionResponse(
            research_plan_id=row["research_plan_id"],
            research_plan_version_id=row["research_plan_version_id"],
            research_case_id=row["research_case_id"],
            knowledge_scope_version_id=row["knowledge_scope_version_id"],
            version=row["version"],
            lifecycle_status=row["lifecycle_status"],
            research_mode=row["research_mode"],
            primary_objective=row["primary_objective"],
            evidence_requirements=[self._requirement(requirement) for requirement in requirements],
            minimum_completion_condition=row["minimum_completion_condition"],
            created_at=datetime.fromisoformat(row["created_at"]),
            previous_version_id=row["previous_version_id"],
            stop_conditions=_load_json(row["stop_conditions_json"], None),
            research_budget=_load_json(row["research_budget_json"], None),
        )

    @staticmethod
    def _requirement(row: sqlite3.Row) -> EvidenceRequirementResponse:
        return EvidenceRequirementResponse(
            evidence_requirement_id=row["evidence_requirement_id"],
            requirement_type=OpenCodeValue(
                code=row["requirement_type_code"],
                registry_version=row["requirement_type_registry_version"],
            ),
            description=row["description"],
            required_knowledge_scope_source_binding_ids=_load_json(
                row["required_binding_ids_json"],
                [],
            ),
            counterevidence_required=bool(row["counterevidence_required"]),
            alternative_interpretation_required=bool(row["alternative_interpretation_required"]),
            completion_condition=row["completion_condition"],
            minimum_count=row["minimum_count"],
        )

    @staticmethod
    def _case(row: sqlite3.Row) -> ResearchCaseResponse:
        return ResearchCaseResponse(
            research_case_id=row["research_case_id"],
            title=row["title"],
            root_question_id=row["root_question_id"],
            current_question_id=row["current_question_id"],
            lifecycle_status=row["lifecycle_status"],
            attention_status=row["attention_status"],
            revision=row["revision"],
            created_at=datetime.fromisoformat(row["created_at"]),
            updated_at=datetime.fromisoformat(row["updated_at"]),
            current_knowledge_scope_version_id=row["current_knowledge_scope_version_id"],
            current_judgment_card_version_id=row["current_judgment_card_version_id"],
            current_research_disposition_id=row["current_research_disposition_id"],
            parent_research_case_id=row["parent_research_case_id"],
            archived_at=_dt(row["archived_at"]),
        )

    @staticmethod
    def _question(row: sqlite3.Row) -> ResearchQuestionResponse:
        return ResearchQuestionResponse(
            research_question_id=row["research_question_id"],
            research_case_id=row["research_case_id"],
            question_text=row["question_text"],
            question_role=row["question_role"],
            created_by="system" if row["created_by"] is None else row["created_by"],
            created_at=datetime.fromisoformat(row["created_at"]),
            parent_question_id=row["parent_question_id"],
        )

    @staticmethod
    def _source_resolution(row: sqlite3.Row) -> SourceResolutionResponse:
        return SourceResolutionResponse(
            source_resolution_id=row["source_resolution_id"],
            research_question_id=row["research_question_id"],
            resolution_stage=row["resolution_stage"],
            raw_anchor=row["raw_anchor"],
            requested_access_policy=row["requested_access_policy"],
            resolution_status=row["resolution_status"],
            candidate_knowledge_item_ids=_load_json(
                row["candidate_knowledge_item_ids_json"],
                [],
            ),
            created_at=datetime.fromisoformat(row["created_at"]),
            requested_version_hint=row["requested_version_hint"],
            resolved_knowledge_item_id=row["resolved_knowledge_item_id"],
            resolved_knowledge_item_version_id=row["resolved_knowledge_item_version_id"],
            ambiguity_reason=row["ambiguity_reason"],
            failure_reason=row["failure_reason"],
        )


__all__ = ["CaseScopeRepository"]
