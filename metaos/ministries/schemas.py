"""Limited ministry recommendations for MetaOS Alpha."""

from __future__ import annotations

from datetime import date, datetime
from enum import Enum

from pydantic import BaseModel, Field, field_validator, model_validator

from metaos.core.schemas import Citation, new_id, utc_now
from metaos.sovereignty import AttentionBudget, Intent


MAX_ITEMS_PER_MINISTRY = 3
MAX_ITEMS_TOTAL = 5
NO_REPORT = "今日无事上奏"


class Ministry(str, Enum):
    technology = "technology"
    cognition = "cognition"
    business = "business"


class RecommendationCandidate(BaseModel):
    ministry: Ministry
    title: str
    reason: str
    intent_alignment: str
    reading_cost_minutes: int = Field(default=0, ge=0)
    cost_of_ignoring: str
    suggested_action: str
    valid_until: datetime | None = None
    citations: list[Citation] = Field(default_factory=list)
    score: float = Field(default=0.5, ge=0, le=1)
    intent_id: str | None = None

    @field_validator(
        "title",
        "reason",
        "intent_alignment",
        "cost_of_ignoring",
        "suggested_action",
    )
    @classmethod
    def validate_required_text(cls, value: str) -> str:
        text = value.strip()
        if not text:
            raise ValueError("field cannot be blank")
        return text

    @field_validator("intent_id")
    @classmethod
    def clean_intent_id(cls, value: str | None) -> str | None:
        if value is None:
            return None
        return value.strip() or None


class RecommendationItem(BaseModel):
    id: str = Field(default_factory=lambda: new_id("rec"))
    ministry: Ministry
    title: str
    reason: str
    intent_alignment: str
    reading_cost_minutes: int = Field(default=0, ge=0)
    cost_of_ignoring: str
    suggested_action: str
    valid_until: datetime | None = None
    citations: list[Citation] = Field(default_factory=list)
    score: float = Field(default=0.5, ge=0, le=1)

    @field_validator(
        "title",
        "reason",
        "intent_alignment",
        "cost_of_ignoring",
        "suggested_action",
    )
    @classmethod
    def validate_required_text(cls, value: str) -> str:
        text = value.strip()
        if not text:
            raise ValueError("field cannot be blank")
        return text


class MinistryReport(BaseModel):
    id: str = Field(default_factory=lambda: new_id("ministry"))
    date: date
    ministry: Ministry
    items: list[RecommendationItem] = Field(default_factory=list)
    empty_reason: str | None = None
    created_at: datetime = Field(default_factory=utc_now)

    @field_validator("empty_reason")
    @classmethod
    def clean_empty_reason(cls, value: str | None) -> str | None:
        if value is None:
            return None
        return value.strip() or None

    @model_validator(mode="after")
    def validate_item_limits(self):
        if len(self.items) > MAX_ITEMS_PER_MINISTRY:
            raise ValueError("ministry report cannot contain more than 3 items")
        if not self.items and not self.empty_reason:
            raise ValueError("empty ministry report requires empty_reason")
        if self.items and self.empty_reason:
            raise ValueError("non-empty ministry report cannot have empty_reason")
        for item in self.items:
            if item.ministry != self.ministry:
                raise ValueError("recommendation item ministry must match report ministry")
        return self


def generate_ministry_reports(
    report_date: date,
    *,
    intent: Intent,
    attention_budget: AttentionBudget,
    candidates: list[RecommendationCandidate],
) -> list[MinistryReport]:
    remaining_minutes = recommendation_budget_minutes(attention_budget)
    eligible = [
        candidate
        for candidate in candidates
        if candidate.intent_id in {None, intent.id}
    ]
    ranked = sorted(
        eligible,
        key=lambda candidate: (-candidate.score, candidate.reading_cost_minutes, candidate.title),
    )
    selected: list[RecommendationCandidate] = []
    per_ministry_counts = {ministry: 0 for ministry in Ministry}
    for candidate in ranked:
        if len(selected) >= MAX_ITEMS_TOTAL:
            break
        if candidate.reading_cost_minutes > remaining_minutes:
            continue
        if per_ministry_counts[candidate.ministry] >= MAX_ITEMS_PER_MINISTRY:
            continue
        selected.append(candidate)
        per_ministry_counts[candidate.ministry] += 1
        remaining_minutes -= candidate.reading_cost_minutes

    reports: list[MinistryReport] = []
    for ministry in Ministry:
        items = [
            item_from_candidate(candidate)
            for candidate in selected
            if candidate.ministry == ministry
        ]
        reports.append(
            MinistryReport(
                date=report_date,
                ministry=ministry,
                items=items,
                empty_reason=None if items else NO_REPORT,
            )
        )
    return reports


def item_from_candidate(candidate: RecommendationCandidate) -> RecommendationItem:
    return RecommendationItem(
        ministry=candidate.ministry,
        title=candidate.title,
        reason=candidate.reason,
        intent_alignment=candidate.intent_alignment,
        reading_cost_minutes=candidate.reading_cost_minutes,
        cost_of_ignoring=candidate.cost_of_ignoring,
        suggested_action=candidate.suggested_action,
        valid_until=candidate.valid_until,
        citations=candidate.citations,
        score=candidate.score,
    )


def recommendation_budget_minutes(attention_budget: AttentionBudget) -> int:
    return attention_budget.research_minutes or attention_budget.total_minutes
