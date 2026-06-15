"""Pydantic schemas for the MetaOS Alpha user sovereignty layer."""

from __future__ import annotations

from datetime import date, datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field, field_validator, model_validator

from metaos.core.schemas import new_id, utc_now


class IntentHorizon(str, Enum):
    day = "day"
    week = "week"
    month = "month"
    quarter = "quarter"
    year = "year"
    project = "project"


class IntentStatus(str, Enum):
    draft = "draft"
    active = "active"
    paused = "paused"
    completed = "completed"
    abandoned = "abandoned"


class NotToDoScope(str, Enum):
    global_scope = "global"
    intent = "intent"
    role = "role"
    project = "project"
    topic = "topic"
    source = "source"


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


class SovereigntyRecord(BaseModel):
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)

    @model_validator(mode="after")
    def validate_update_time(self):
        if self.updated_at < self.created_at:
            raise ValueError("updated_at cannot be earlier than created_at")
        return self


class CognitiveConstitution(SovereigntyRecord):
    id: str = Field(default_factory=lambda: new_id("cc"))
    version: int = Field(default=1, ge=1)
    principles: list[str] = Field(min_length=1)
    decision_rules: list[str] = Field(default_factory=list)
    attention_rules: list[str] = Field(default_factory=list)
    not_to_do_defaults: list[str] = Field(default_factory=list)
    risk_preferences: dict[str, Any] = Field(default_factory=dict)

    @field_validator(
        "principles",
        "decision_rules",
        "attention_rules",
        "not_to_do_defaults",
    )
    @classmethod
    def validate_string_lists(cls, values: list[str]) -> list[str]:
        return _clean_string_list(values)


class Intent(SovereigntyRecord):
    id: str = Field(default_factory=lambda: new_id("intent"))
    title: str
    description: str = ""
    horizon: IntentHorizon = IntentHorizon.quarter
    status: IntentStatus = IntentStatus.draft
    priority: int = Field(default=3, ge=1, le=5)
    success_criteria: list[str] = Field(default_factory=list)
    constraints: list[str] = Field(default_factory=list)
    constitution_id: str | None = None

    @field_validator("title")
    @classmethod
    def validate_title(cls, value: str) -> str:
        return _clean_text(value, field_name="title")

    @field_validator("description")
    @classmethod
    def clean_description(cls, value: str) -> str:
        return value.strip()

    @field_validator("constitution_id")
    @classmethod
    def clean_constitution_id(cls, value: str | None) -> str | None:
        return _clean_optional_text(value)

    @field_validator("success_criteria", "constraints")
    @classmethod
    def validate_string_lists(cls, values: list[str]) -> list[str]:
        return _clean_string_list(values)


class CurrentRole(SovereigntyRecord):
    id: str = Field(default_factory=lambda: new_id("role"))
    name: str
    responsibilities: list[str] = Field(default_factory=list)
    allowed_focus: list[str] = Field(default_factory=list)
    forbidden_focus: list[str] = Field(default_factory=list)
    active_from: datetime = Field(default_factory=utc_now)
    active_to: datetime | None = None

    @field_validator("name")
    @classmethod
    def validate_name(cls, value: str) -> str:
        return _clean_text(value, field_name="name")

    @field_validator("responsibilities", "allowed_focus", "forbidden_focus")
    @classmethod
    def validate_string_lists(cls, values: list[str]) -> list[str]:
        return _clean_string_list(values)

    @model_validator(mode="after")
    def validate_active_range(self):
        if self.active_to is not None and self.active_to <= self.active_from:
            raise ValueError("active_to must be later than active_from")
        return self


class AttentionBudget(SovereigntyRecord):
    id: str = Field(default_factory=lambda: new_id("budget"))
    date: date
    total_minutes: int = Field(default=480, ge=0)
    research_minutes: int = Field(default=0, ge=0)
    build_minutes: int = Field(default=0, ge=0)
    review_minutes: int = Field(default=0, ge=0)
    content_minutes: int = Field(default=0, ge=0)
    hard_limits: dict[str, int] = Field(default_factory=dict)

    @field_validator("hard_limits")
    @classmethod
    def validate_hard_limits(cls, value: dict[str, int]) -> dict[str, int]:
        cleaned: dict[str, int] = {}
        for raw_key, minutes in value.items():
            key = raw_key.strip()
            if not key:
                raise ValueError("hard_limits keys cannot be blank")
            if minutes < 0:
                raise ValueError("hard_limits values cannot be negative")
            cleaned[key] = minutes
        return cleaned

    @model_validator(mode="after")
    def validate_allocated_minutes(self):
        allocated = (
            self.research_minutes
            + self.build_minutes
            + self.review_minutes
            + self.content_minutes
        )
        if allocated > self.total_minutes:
            raise ValueError("allocated attention minutes cannot exceed total_minutes")
        return self


class NotToDoItem(SovereigntyRecord):
    id: str = Field(default_factory=lambda: new_id("ntd"))
    title: str
    reason: str = ""
    scope: NotToDoScope = NotToDoScope.global_scope
    active: bool = True
    expires_at: datetime | None = None
    related_intent_id: str | None = None

    @field_validator("title")
    @classmethod
    def validate_title(cls, value: str) -> str:
        return _clean_text(value, field_name="title")

    @field_validator("reason")
    @classmethod
    def clean_reason(cls, value: str) -> str:
        return value.strip()

    @field_validator("related_intent_id")
    @classmethod
    def clean_related_intent_id(cls, value: str | None) -> str | None:
        return _clean_optional_text(value)

    @model_validator(mode="after")
    def validate_scope_reference(self):
        if self.scope == NotToDoScope.intent and not self.related_intent_id:
            raise ValueError("intent-scoped not-to-do items require related_intent_id")
        return self

