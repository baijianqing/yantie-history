"""Chancellor daily briefing for MetaOS Alpha."""

from __future__ import annotations

from datetime import date, datetime

from pydantic import BaseModel, Field, field_validator

from metaos.core.schemas import new_id, utc_now
from metaos.ledger import DailyReview
from metaos.ministries import MinistryReport, NO_REPORT
from metaos.research import ResearchAnswer, SourceStatus
from metaos.sovereignty import AttentionBudget, CurrentRole, Intent


class ChancellorBriefing(BaseModel):
    id: str = Field(default_factory=lambda: new_id("briefing"))
    date: date
    intent_id: str
    role_id: str | None = None
    today_focus: list[str] = Field(default_factory=list)
    deferred_items: list[str] = Field(default_factory=list)
    ignored_items: list[str] = Field(default_factory=list)
    cognitive_traps: list[str] = Field(default_factory=list)
    source_research_ids: list[str] = Field(default_factory=list)
    source_review_id: str | None = None
    created_at: datetime = Field(default_factory=utc_now)

    @field_validator("intent_id")
    @classmethod
    def validate_intent_id(cls, value: str) -> str:
        text = value.strip()
        if not text:
            raise ValueError("intent_id cannot be blank")
        return text

    @field_validator("role_id", "source_review_id")
    @classmethod
    def clean_optional_text(cls, value: str | None) -> str | None:
        if value is None:
            return None
        return value.strip() or None

    @field_validator("today_focus", "deferred_items", "ignored_items", "cognitive_traps", "source_research_ids")
    @classmethod
    def validate_string_lists(cls, values: list[str]) -> list[str]:
        cleaned: list[str] = []
        for value in values:
            text = value.strip()
            if not text:
                raise ValueError("list items cannot be blank")
            cleaned.append(text)
        return cleaned


def generate_chancellor_briefing(
    briefing_date: date,
    *,
    intent: Intent,
    role: CurrentRole | None,
    attention_budget: AttentionBudget,
    daily_review: DailyReview | None = None,
    research_answers: list[ResearchAnswer] | None = None,
    ministry_reports: list[MinistryReport] | None = None,
) -> ChancellorBriefing:
    answers = research_answers or []
    reports = ministry_reports or []
    focus = build_focus(intent, attention_budget, answers, reports)
    deferred = build_deferred_items(answers, daily_review)
    ignored = build_ignored_items(role, reports)
    traps = build_cognitive_traps(attention_budget, answers, reports)
    return ChancellorBriefing(
        date=briefing_date,
        intent_id=intent.id,
        role_id=role.id if role else None,
        today_focus=focus,
        deferred_items=deferred,
        ignored_items=ignored,
        cognitive_traps=traps,
        source_research_ids=[answer.id for answer in answers],
        source_review_id=daily_review.id if daily_review else None,
    )


def build_focus(
    intent: Intent,
    attention_budget: AttentionBudget,
    answers: list[ResearchAnswer],
    reports: list[MinistryReport],
) -> list[str]:
    focus: list[str] = [f"Intent: {intent.title}"]
    for answer in answers:
        focus.extend(action.title for action in answer.actions)
    for report in reports:
        focus.extend(item.suggested_action for item in report.items)
    limit = focus_limit(attention_budget)
    return dedupe(focus)[:limit]


def build_deferred_items(
    answers: list[ResearchAnswer],
    daily_review: DailyReview | None,
) -> list[str]:
    deferred: list[str] = []
    if daily_review:
        deferred.extend(daily_review.actions_missed)
    for answer in answers:
        if answer.no_action_reason:
            deferred.append(f"No action: {answer.no_action_reason}")
    return dedupe(deferred)


def build_ignored_items(
    role: CurrentRole | None,
    reports: list[MinistryReport],
) -> list[str]:
    ignored: list[str] = []
    if role:
        ignored.extend(role.forbidden_focus)
    for report in reports:
        if report.empty_reason == NO_REPORT:
            ignored.append(f"{report.ministry.value}: do not force a recommendation today")
    return dedupe(ignored)


def build_cognitive_traps(
    attention_budget: AttentionBudget,
    answers: list[ResearchAnswer],
    reports: list[MinistryReport],
) -> list[str]:
    traps: list[str] = []
    if attention_budget.total_minutes <= 0:
        traps.append("No attention budget remains; avoid starting new work.")
    for answer in answers:
        if any(statement.source_status == SourceStatus.uncited for statement in answer.model_inferences):
            traps.append("Uncited inference present; keep it out of fact statements.")
    if all(not report.items for report in reports) and reports:
        traps.append("All ministries are empty; avoid manufacturing recommendations.")
    return dedupe(traps)


def focus_limit(attention_budget: AttentionBudget) -> int:
    if attention_budget.total_minutes <= 0:
        return 1
    return max(1, min(5, attention_budget.total_minutes // 60 or 1))


def dedupe(values: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for value in values:
        text = value.strip()
        if not text or text in seen:
            continue
        seen.add(text)
        result.append(text)
    return result
