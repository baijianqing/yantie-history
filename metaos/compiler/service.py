"""Runtime issue compiler service for MetaOS Alpha."""

from __future__ import annotations

import json
from typing import Any, Protocol

from pydantic import BaseModel, field_validator

from metaos.compiler.schemas import (
    CognitiveOperator,
    EvidenceRequirement,
    EvidenceRequirementType,
    ResearchCompilation,
    ResearchDepth,
    ResearchPlan,
    ResearchPlanStep,
    ResearchScope,
    ResearchTask,
    ResearchTaskStatus,
    ResearchTimeRange,
    ThemeSpec,
)
from metaos.llm_gateway.client import ChatMessage, LLMGateway


PROMPT_VERSION = "issue_compiler_v1"


class CompileResearchRequest(BaseModel):
    question: str
    intent_id: str
    role_id: str | None = None
    attention_budget_id: str | None = None

    @field_validator("question", "intent_id")
    @classmethod
    def validate_required_text(cls, value: str) -> str:
        text = value.strip()
        if not text:
            raise ValueError("field cannot be blank")
        return text

    @field_validator("role_id", "attention_budget_id")
    @classmethod
    def clean_optional_text(cls, value: str | None) -> str | None:
        if value is None:
            return None
        return value.strip() or None


class CompilerModelProvider(Protocol):
    def compile_theme(self, payload: dict[str, Any]) -> dict[str, Any]:
        """Return a structured compiler payload."""


class LLMCompilerProvider:
    def __init__(self, llm: LLMGateway | None = None):
        self.llm = llm or LLMGateway()

    def compile_theme(self, payload: dict[str, Any]) -> dict[str, Any]:
        content = self.llm.chat_text(
            [
                ChatMessage(
                    role="system",
                    content=(
                        "You are the MetaOS issue compiler. Return only JSON matching "
                        "the requested schema. Do not answer the research question."
                    ),
                ),
                ChatMessage(role="user", content=json.dumps(payload, ensure_ascii=False)),
            ],
            temperature=0.1,
        )
        return extract_json_object(content)


class IssueCompiler:
    def __init__(self, provider: CompilerModelProvider):
        self.provider = provider

    def compile(self, request: CompileResearchRequest) -> ResearchCompilation:
        payload = compiler_payload(request)
        raw = self.provider.compile_theme(payload)
        return build_research_compilation(request, raw)


def compiler_payload(request: CompileResearchRequest) -> dict[str, Any]:
    return {
        "prompt_version": PROMPT_VERSION,
        "question": request.question,
        "intent_id": request.intent_id,
        "role_id": request.role_id,
        "attention_budget_id": request.attention_budget_id,
        "allowed_operators": [operator.value for operator in CognitiveOperator],
        "required_output": {
            "operator": "CognitiveOperator",
            "theme_spec": "ThemeSpec fields without task_id",
            "evidence_requirements": "list[EvidenceRequirement fields without task_id]",
            "research_scope": "ResearchScope fields without task_id",
            "research_plan": "ResearchPlan fields without task_id",
        },
    }


def build_research_compilation(
    request: CompileResearchRequest,
    raw: dict[str, Any],
) -> ResearchCompilation:
    operator = CognitiveOperator(raw.get("operator") or CognitiveOperator.causal_analysis.value)
    task = ResearchTask(
        question=request.question,
        intent_id=request.intent_id,
        role_id=request.role_id,
        attention_budget_id=request.attention_budget_id,
        operator=operator,
        status=ResearchTaskStatus.planned,
    )
    theme = build_theme_spec(task.id, raw.get("theme_spec") or {})
    requirements = [
        build_evidence_requirement(task.id, item)
        for item in raw.get("evidence_requirements") or []
    ]
    scope = build_research_scope(task.id, raw.get("research_scope") or {})
    plan = build_research_plan(
        task.id,
        raw.get("research_plan") or {},
        requirements=requirements,
    )
    task = ResearchTask(
        **{
            **task.model_dump(),
            "theme_spec_id": theme.id,
            "scope_id": scope.id,
        }
    )
    return ResearchCompilation(
        research_task=task,
        operator=operator,
        theme_spec=theme,
        evidence_requirements=requirements,
        research_scope=scope,
        research_plan=plan,
    )


def build_theme_spec(task_id: str, payload: dict[str, Any]) -> ThemeSpec:
    return ThemeSpec(
        task_id=task_id,
        theme_name=str(payload.get("theme_name") or ""),
        theme_description=str(payload.get("theme_description") or ""),
        key_terms=list(payload.get("key_terms") or []),
        synonyms=dict(payload.get("synonyms") or {}),
        positive_patterns=list(payload.get("positive_patterns") or []),
        negative_patterns=list(payload.get("negative_patterns") or []),
        required_dimensions=list(payload.get("required_dimensions") or []),
        excluded_dimensions=list(payload.get("excluded_dimensions") or []),
        evidence_preferences=dict(payload.get("evidence_preferences") or {}),
    )


def build_evidence_requirement(task_id: str, payload: dict[str, Any]) -> EvidenceRequirement:
    return EvidenceRequirement(
        task_id=task_id,
        requirement_type=EvidenceRequirementType(
            payload.get("requirement_type") or EvidenceRequirementType.primary_fact.value
        ),
        description=str(payload.get("description") or ""),
        required_count=int(payload.get("required_count") or 1),
        source_constraints=dict(payload.get("source_constraints") or {}),
        freshness=payload.get("freshness"),
        counterevidence_required=bool(payload.get("counterevidence_required", False)),
    )


def build_research_scope(task_id: str, payload: dict[str, Any]) -> ResearchScope:
    time_range_payload = payload.get("time_range")
    return ResearchScope(
        task_id=task_id,
        included_sources=list(payload.get("included_sources") or []),
        excluded_sources=list(payload.get("excluded_sources") or []),
        time_range=ResearchTimeRange.model_validate(time_range_payload)
        if time_range_payload
        else None,
        entity_filters=list(payload.get("entity_filters") or []),
        cost_limit=int(payload.get("cost_limit") or 0),
        depth=ResearchDepth(payload.get("depth") or ResearchDepth.standard.value),
    )


def build_research_plan(
    task_id: str,
    payload: dict[str, Any],
    *,
    requirements: list[EvidenceRequirement],
) -> ResearchPlan:
    steps = [
        ResearchPlanStep(
            order=int(item.get("order") or index),
            operator=CognitiveOperator(item.get("operator") or CognitiveOperator.fact_lookup.value),
            description=str(item.get("description") or ""),
            query_hints=list(item.get("query_hints") or []),
            expected_evidence=list(item.get("expected_evidence") or []),
        )
        for index, item in enumerate(payload.get("steps") or [], start=1)
    ]
    return ResearchPlan(
        task_id=task_id,
        steps=steps,
        query_plan=list(payload.get("query_plan") or []),
        evidence_requirements=requirements,
        stop_conditions=list(payload.get("stop_conditions") or []),
        prompt_version=str(payload.get("prompt_version") or PROMPT_VERSION),
    )


def extract_json_object(content: str) -> dict[str, Any]:
    try:
        parsed = json.loads(content)
    except json.JSONDecodeError:
        start = content.find("{")
        end = content.rfind("}")
        if start < 0 or end <= start:
            raise
        parsed = json.loads(content[start : end + 1])
    if not isinstance(parsed, dict):
        raise ValueError("compiler model output must be a JSON object")
    return parsed
