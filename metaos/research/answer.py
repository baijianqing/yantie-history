"""Research answer drafting and action adaptation."""

from __future__ import annotations

from datetime import datetime
from enum import Enum

from pydantic import BaseModel, Field, field_validator, model_validator

from metaos.compiler import ResearchCompilation
from metaos.core.schemas import Citation, new_id, utc_now
from metaos.ledger import Action, ActionSourceType, ActionStatus
from metaos.research.executor import EvidenceAssessment, ResearchExecutionDraft


class SourceStatus(str, Enum):
    cited = "cited"
    uncited = "uncited"


class AnswerStatement(BaseModel):
    text: str
    source_status: SourceStatus = SourceStatus.uncited
    citations: list[Citation] = Field(default_factory=list)

    @field_validator("text")
    @classmethod
    def validate_text(cls, value: str) -> str:
        text = value.strip()
        if not text:
            raise ValueError("text cannot be blank")
        return text

    @model_validator(mode="after")
    def validate_source_status(self):
        if self.citations and self.source_status != SourceStatus.cited:
            raise ValueError("statements with citations must use source_status=cited")
        return self


class ResearchAnswer(BaseModel):
    id: str = Field(default_factory=lambda: new_id("answer"))
    task_id: str
    fact_statements: list[AnswerStatement] = Field(default_factory=list)
    model_inferences: list[AnswerStatement] = Field(default_factory=list)
    disputed_views: list[AnswerStatement] = Field(default_factory=list)
    personal_reflections: list[AnswerStatement] = Field(default_factory=list)
    actions: list[Action] = Field(default_factory=list)
    no_action_reason: str | None = None
    citations: list[Citation] = Field(default_factory=list)
    audit_report_id: str | None = None
    created_at: datetime = Field(default_factory=utc_now)

    @field_validator("task_id")
    @classmethod
    def validate_task_id(cls, value: str) -> str:
        text = value.strip()
        if not text:
            raise ValueError("task_id cannot be blank")
        return text

    @field_validator("no_action_reason", "audit_report_id")
    @classmethod
    def clean_optional_text(cls, value: str | None) -> str | None:
        if value is None:
            return None
        return value.strip() or None

    @model_validator(mode="after")
    def validate_action_or_no_action(self):
        if not self.actions and not self.no_action_reason:
            raise ValueError("research answer requires actions or no_action_reason")
        return self


def draft_research_answer(
    compilation: ResearchCompilation,
    execution: ResearchExecutionDraft,
    *,
    conclusion: str,
    action_title: str | None = None,
    no_action_reason: str | None = None,
    personal_reflections: list[str] | None = None,
) -> ResearchAnswer:
    answer_id = new_id("answer")
    citations = collect_citations(execution)
    actions = build_actions(
        answer_id=answer_id,
        intent_id=compilation.research_task.intent_id,
        action_title=action_title,
    )
    return ResearchAnswer(
        id=answer_id,
        task_id=compilation.research_task.id,
        fact_statements=fact_statements(execution),
        model_inferences=[
            statement(conclusion, citations=citations if citations else [])
        ],
        disputed_views=disputed_statements(execution),
        personal_reflections=[
            statement(reflection)
            for reflection in personal_reflections or []
        ],
        actions=actions,
        no_action_reason=None if actions else no_action_reason or "No action proposed from current evidence.",
        citations=citations,
    )


def build_actions(
    *,
    answer_id: str,
    intent_id: str,
    action_title: str | None,
) -> list[Action]:
    title = action_title.strip() if action_title else ""
    if not title:
        return []
    return [
        Action(
            title=title,
            status=ActionStatus.proposed,
            source_type=ActionSourceType.research_answer,
            source_id=answer_id,
            intent_id=intent_id,
        )
    ]


def fact_statements(execution: ResearchExecutionDraft) -> list[AnswerStatement]:
    statements: list[AnswerStatement] = []
    for row in execution.evidence_matrix:
        for candidate in row.supporting_evidence:
            if candidate.citation is None:
                statements.append(statement(candidate.text))
            else:
                statements.append(statement(candidate.text, citations=[candidate.citation]))
    return statements


def disputed_statements(execution: ResearchExecutionDraft) -> list[AnswerStatement]:
    statements: list[AnswerStatement] = []
    for row in execution.evidence_matrix:
        if row.assessment != EvidenceAssessment.contested:
            continue
        for candidate in row.counter_evidence:
            if candidate.citation is None:
                statements.append(statement(candidate.text))
            else:
                statements.append(statement(candidate.text, citations=[candidate.citation]))
    return statements


def statement(text: str, *, citations: list[Citation] | None = None) -> AnswerStatement:
    cited = citations or []
    return AnswerStatement(
        text=text,
        source_status=SourceStatus.cited if cited else SourceStatus.uncited,
        citations=cited,
    )


def collect_citations(execution: ResearchExecutionDraft) -> list[Citation]:
    citations: list[Citation] = []
    seen: set[str] = set()
    for row in execution.evidence_matrix:
        for candidate in [*row.supporting_evidence, *row.counter_evidence]:
            if candidate.citation is None:
                continue
            key = candidate.citation.model_dump_json()
            if key in seen:
                continue
            seen.add(key)
            citations.append(candidate.citation)
    return citations
