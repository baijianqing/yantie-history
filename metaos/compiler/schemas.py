"""Pydantic schemas for the MetaOS Alpha issue compiler."""

from __future__ import annotations

from datetime import date, datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field, field_validator, model_validator

from metaos.core.schemas import new_id, utc_now


class CognitiveOperator(str, Enum):
    fact_lookup = "fact_lookup"
    enumerate_pattern = "enumerate_pattern"
    compare = "compare"
    causal_analysis = "causal_analysis"
    decision_support = "decision_support"
    reflection = "reflection"
    recommend = "recommend"


class ResearchTaskStatus(str, Enum):
    draft = "draft"
    planned = "planned"
    running = "running"
    audit_required = "audit_required"
    completed = "completed"
    failed = "failed"


class EvidenceRequirementType(str, Enum):
    primary_fact = "primary_fact"
    pattern_case = "pattern_case"
    comparison = "comparison"
    causal_link = "causal_link"
    decision_criterion = "decision_criterion"
    counterevidence = "counterevidence"
    reflection_prompt = "reflection_prompt"


class ResearchDepth(str, Enum):
    quick = "quick"
    standard = "standard"
    deep = "deep"


def _clean_text(value: str, *, field_name: str) -> str:
    text = value.strip()
    if not text:
        raise ValueError(f"{field_name} cannot be blank")
    return text


def _clean_optional_text(value: str | None) -> str | None:
    if value is None:
        return None
    return value.strip() or None


def _clean_string_list(values: list[str]) -> list[str]:
    cleaned: list[str] = []
    for value in values:
        text = value.strip()
        if not text:
            raise ValueError("list items cannot be blank")
        cleaned.append(text)
    return cleaned


class CompilerRecord(BaseModel):
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)

    @model_validator(mode="after")
    def validate_update_time(self):
        if self.updated_at < self.created_at:
            raise ValueError("updated_at cannot be earlier than created_at")
        return self


class ResearchTask(CompilerRecord):
    id: str = Field(default_factory=lambda: new_id("task"))
    question: str
    intent_id: str
    role_id: str | None = None
    attention_budget_id: str | None = None
    operator: CognitiveOperator
    theme_spec_id: str | None = None
    scope_id: str | None = None
    status: ResearchTaskStatus = ResearchTaskStatus.draft

    @field_validator("question", "intent_id")
    @classmethod
    def validate_required_text(cls, value: str) -> str:
        return _clean_text(value, field_name="text")

    @field_validator("role_id", "attention_budget_id", "theme_spec_id", "scope_id")
    @classmethod
    def clean_optional_ids(cls, value: str | None) -> str | None:
        return _clean_optional_text(value)


class ThemeSpec(CompilerRecord):
    id: str = Field(default_factory=lambda: new_id("theme"))
    task_id: str
    theme_name: str
    theme_description: str
    key_terms: list[str] = Field(default_factory=list)
    synonyms: dict[str, list[str]] = Field(default_factory=dict)
    positive_patterns: list[str] = Field(default_factory=list)
    negative_patterns: list[str] = Field(default_factory=list)
    required_dimensions: list[str] = Field(default_factory=list)
    excluded_dimensions: list[str] = Field(default_factory=list)
    evidence_preferences: dict[str, Any] = Field(default_factory=dict)

    @field_validator("task_id", "theme_name", "theme_description")
    @classmethod
    def validate_required_text(cls, value: str) -> str:
        return _clean_text(value, field_name="text")

    @field_validator(
        "key_terms",
        "positive_patterns",
        "negative_patterns",
        "required_dimensions",
        "excluded_dimensions",
    )
    @classmethod
    def validate_string_lists(cls, values: list[str]) -> list[str]:
        return _clean_string_list(values)

    @field_validator("synonyms")
    @classmethod
    def validate_synonyms(cls, values: dict[str, list[str]]) -> dict[str, list[str]]:
        cleaned: dict[str, list[str]] = {}
        for key, terms in values.items():
            cleaned[_clean_text(key, field_name="synonym key")] = _clean_string_list(terms)
        return cleaned


class EvidenceRequirement(CompilerRecord):
    id: str = Field(default_factory=lambda: new_id("evreq"))
    task_id: str
    requirement_type: EvidenceRequirementType
    description: str
    required_count: int = Field(default=1, ge=1)
    source_constraints: dict[str, Any] = Field(default_factory=dict)
    freshness: str | None = None
    counterevidence_required: bool = False

    @field_validator("task_id", "description")
    @classmethod
    def validate_required_text(cls, value: str) -> str:
        return _clean_text(value, field_name="text")

    @field_validator("freshness")
    @classmethod
    def clean_freshness(cls, value: str | None) -> str | None:
        return _clean_optional_text(value)


class ResearchTimeRange(BaseModel):
    start: date | None = None
    end: date | None = None

    @model_validator(mode="after")
    def validate_time_range(self):
        if self.start is not None and self.end is not None and self.end < self.start:
            raise ValueError("end cannot be earlier than start")
        return self


class ResearchScope(CompilerRecord):
    id: str = Field(default_factory=lambda: new_id("scope"))
    task_id: str
    included_sources: list[str] = Field(default_factory=list)
    excluded_sources: list[str] = Field(default_factory=list)
    time_range: ResearchTimeRange | None = None
    entity_filters: list[str] = Field(default_factory=list)
    cost_limit: int = Field(default=0, ge=0)
    depth: ResearchDepth = ResearchDepth.standard

    @field_validator("task_id")
    @classmethod
    def validate_task_id(cls, value: str) -> str:
        return _clean_text(value, field_name="task_id")

    @field_validator("included_sources", "excluded_sources", "entity_filters")
    @classmethod
    def validate_string_lists(cls, values: list[str]) -> list[str]:
        return _clean_string_list(values)


class ResearchPlanStep(BaseModel):
    order: int = Field(ge=1)
    operator: CognitiveOperator
    description: str
    query_hints: list[str] = Field(default_factory=list)
    expected_evidence: list[str] = Field(default_factory=list)

    @field_validator("description")
    @classmethod
    def validate_description(cls, value: str) -> str:
        return _clean_text(value, field_name="description")

    @field_validator("query_hints", "expected_evidence")
    @classmethod
    def validate_string_lists(cls, values: list[str]) -> list[str]:
        return _clean_string_list(values)


class ResearchPlan(CompilerRecord):
    id: str = Field(default_factory=lambda: new_id("plan"))
    task_id: str
    steps: list[ResearchPlanStep] = Field(default_factory=list)
    query_plan: list[str] = Field(default_factory=list)
    evidence_requirements: list[EvidenceRequirement] = Field(default_factory=list)
    stop_conditions: list[str] = Field(default_factory=list)
    prompt_version: str = "compiler_schema_v1"

    @field_validator("task_id", "prompt_version")
    @classmethod
    def validate_required_text(cls, value: str) -> str:
        return _clean_text(value, field_name="text")

    @field_validator("query_plan", "stop_conditions")
    @classmethod
    def validate_string_lists(cls, values: list[str]) -> list[str]:
        return _clean_string_list(values)


class ResearchCompilation(BaseModel):
    research_task: ResearchTask
    operator: CognitiveOperator
    theme_spec: ThemeSpec
    evidence_requirements: list[EvidenceRequirement] = Field(default_factory=list)
    research_scope: ResearchScope
    research_plan: ResearchPlan

    @model_validator(mode="after")
    def validate_task_links(self):
        task_id = self.research_task.id
        linked_task_ids = [
            self.theme_spec.task_id,
            self.research_scope.task_id,
            self.research_plan.task_id,
            *(requirement.task_id for requirement in self.evidence_requirements),
            *(requirement.task_id for requirement in self.research_plan.evidence_requirements),
        ]
        if any(linked_task_id != task_id for linked_task_id in linked_task_ids):
            raise ValueError("compiled research objects must reference the research_task id")
        if self.operator != self.research_task.operator:
            raise ValueError("operator must match research_task.operator")
        return self
