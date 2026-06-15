"""Pydantic schemas for the MetaOS Alpha daily cognitive ledger."""

from __future__ import annotations

from datetime import date, datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field, field_validator, model_validator

from metaos.core.schemas import Citation, new_id, utc_now


class WorkEventSource(str, Enum):
    manual = "manual"
    git_commit = "git_commit"
    markdown_change = "markdown_change"
    research_task = "research_task"
    system = "system"


class WorkEventType(str, Enum):
    plan = "plan"
    build = "build"
    research = "research"
    review = "review"
    decision = "decision"
    action = "action"
    drift = "drift"
    note = "note"


class AdviceStatus(str, Enum):
    pending = "pending"
    accepted = "accepted"
    rejected = "rejected"
    deferred = "deferred"
    expired = "expired"


class DecisionReversibility(str, Enum):
    reversible = "reversible"
    costly_to_reverse = "costly_to_reverse"
    irreversible = "irreversible"
    unknown = "unknown"


class ActionStatus(str, Enum):
    proposed = "proposed"
    accepted = "accepted"
    in_progress = "in_progress"
    done = "done"
    canceled = "canceled"
    no_action = "no_action"


class ActionSourceType(str, Enum):
    manual = "manual"
    decision = "decision"
    research_answer = "research_answer"
    daily_review = "daily_review"
    chancellor_briefing = "chancellor_briefing"
    ministry_report = "ministry_report"


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


class LedgerRecord(BaseModel):
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)

    @model_validator(mode="after")
    def validate_update_time(self):
        if self.updated_at < self.created_at:
            raise ValueError("updated_at cannot be earlier than created_at")
        return self


class DailyPlan(LedgerRecord):
    id: str = Field(default_factory=lambda: new_id("plan"))
    date: date
    intent_id: str | None = None
    role_id: str | None = None
    focus_items: list[str] = Field(default_factory=list)
    deferred_items: list[str] = Field(default_factory=list)
    ignored_items: list[str] = Field(default_factory=list)
    budget_id: str | None = None

    @field_validator("intent_id", "role_id", "budget_id")
    @classmethod
    def clean_optional_ids(cls, value: str | None) -> str | None:
        return _clean_optional_text(value)

    @field_validator("focus_items", "deferred_items", "ignored_items")
    @classmethod
    def validate_string_lists(cls, values: list[str]) -> list[str]:
        return _clean_string_list(values)


class WorkEvent(LedgerRecord):
    id: str = Field(default_factory=lambda: new_id("we"))
    date: date
    event_type: WorkEventType = WorkEventType.note
    title: str
    description: str = ""
    source: WorkEventSource = WorkEventSource.manual
    source_ref: str | None = None
    started_at: datetime | None = None
    ended_at: datetime | None = None
    related_intent_id: str | None = None
    citations: list[Citation] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)

    @field_validator("title")
    @classmethod
    def validate_title(cls, value: str) -> str:
        return _clean_text(value, field_name="title")

    @field_validator("description")
    @classmethod
    def clean_description(cls, value: str) -> str:
        return value.strip()

    @field_validator("source_ref", "related_intent_id")
    @classmethod
    def clean_optional_ids(cls, value: str | None) -> str | None:
        return _clean_optional_text(value)

    @model_validator(mode="after")
    def validate_time_range(self):
        if self.started_at and self.ended_at and self.ended_at < self.started_at:
            raise ValueError("ended_at cannot be earlier than started_at")
        if self.source != WorkEventSource.manual and not self.source_ref:
            raise ValueError("non-manual work events require source_ref")
        return self


class Advice(LedgerRecord):
    id: str = Field(default_factory=lambda: new_id("advice"))
    source: WorkEventSource = WorkEventSource.manual
    advisor: str
    content: str
    evidence: list[Citation] = Field(default_factory=list)
    valid_until: datetime | None = None
    accepted_status: AdviceStatus = AdviceStatus.pending

    @field_validator("advisor", "content")
    @classmethod
    def validate_required_text(cls, value: str) -> str:
        return _clean_text(value, field_name="text")


class Decision(LedgerRecord):
    id: str = Field(default_factory=lambda: new_id("decision"))
    title: str
    context: str = ""
    options: list[str] = Field(min_length=1)
    chosen_option: str
    reasoning: str = ""
    evidence_links: list[Citation] = Field(default_factory=list)
    reversibility: DecisionReversibility = DecisionReversibility.unknown
    decided_at: datetime = Field(default_factory=utc_now)

    @field_validator("title", "chosen_option")
    @classmethod
    def validate_required_text(cls, value: str) -> str:
        return _clean_text(value, field_name="text")

    @field_validator("context", "reasoning")
    @classmethod
    def clean_optional_body(cls, value: str) -> str:
        return value.strip()

    @field_validator("options")
    @classmethod
    def validate_options(cls, values: list[str]) -> list[str]:
        return _clean_string_list(values)

    @model_validator(mode="after")
    def validate_choice(self):
        if self.chosen_option not in self.options:
            raise ValueError("chosen_option must be one of options")
        return self


class Action(LedgerRecord):
    id: str = Field(default_factory=lambda: new_id("action"))
    title: str
    description: str = ""
    status: ActionStatus = ActionStatus.proposed
    owner: str | None = None
    due_at: datetime | None = None
    source_type: ActionSourceType = ActionSourceType.manual
    source_id: str | None = None
    intent_id: str | None = None
    review_id: str | None = None

    @field_validator("title")
    @classmethod
    def validate_title(cls, value: str) -> str:
        return _clean_text(value, field_name="title")

    @field_validator("description")
    @classmethod
    def clean_description(cls, value: str) -> str:
        return value.strip()

    @field_validator("owner", "source_id", "intent_id", "review_id")
    @classmethod
    def clean_optional_ids(cls, value: str | None) -> str | None:
        return _clean_optional_text(value)

    @model_validator(mode="after")
    def validate_source_reference(self):
        if self.source_type != ActionSourceType.manual and not self.source_id:
            raise ValueError("non-manual actions require source_id")
        return self


class AttentionDrift(LedgerRecord):
    id: str = Field(default_factory=lambda: new_id("drift"))
    date: date
    trigger: str
    description: str = ""
    cost_minutes: int = Field(default=0, ge=0)
    detected_by: WorkEventSource = WorkEventSource.manual
    countermeasure: str | None = None

    @field_validator("trigger")
    @classmethod
    def validate_trigger(cls, value: str) -> str:
        return _clean_text(value, field_name="trigger")

    @field_validator("description")
    @classmethod
    def clean_description(cls, value: str) -> str:
        return value.strip()

    @field_validator("countermeasure")
    @classmethod
    def clean_countermeasure(cls, value: str | None) -> str | None:
        return _clean_optional_text(value)


class DailyReview(LedgerRecord):
    id: str = Field(default_factory=lambda: new_id("review"))
    date: date
    facts: list[str] = Field(default_factory=list)
    judgments: list[str] = Field(default_factory=list)
    reflections: list[str] = Field(default_factory=list)
    actions_done: list[str] = Field(default_factory=list)
    actions_missed: list[str] = Field(default_factory=list)
    lessons: list[str] = Field(default_factory=list)

    @field_validator(
        "facts",
        "judgments",
        "reflections",
        "actions_done",
        "actions_missed",
        "lessons",
    )
    @classmethod
    def validate_string_lists(cls, values: list[str]) -> list[str]:
        return _clean_string_list(values)


class DailySummary(LedgerRecord):
    id: str = Field(default_factory=lambda: new_id("summary"))
    date: date
    source_review_id: str
    fact_summary: str
    judgment_summary: str = ""
    reflection_summary: str = ""
    action_summary: str = ""
    citations: list[Citation] = Field(default_factory=list)

    @field_validator("source_review_id", "fact_summary")
    @classmethod
    def validate_required_text(cls, value: str) -> str:
        return _clean_text(value, field_name="text")

    @field_validator("judgment_summary", "reflection_summary", "action_summary")
    @classmethod
    def clean_summary_text(cls, value: str) -> str:
        return value.strip()

