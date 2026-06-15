"""Chancellor daily briefing for MetaOS Alpha."""

from __future__ import annotations

from datetime import date, datetime

from pydantic import BaseModel, Field, field_validator, model_validator

from metaos.core.schemas import new_id, utc_now
from metaos.ledger import ActionStatus, DailyReview, DailySummary
from metaos.ministries import MinistryReport, NO_REPORT
from metaos.research import ResearchAnswer, SourceStatus
from metaos.sovereignty import AttentionBudget, CurrentRole, Intent
from metaos.workshop import VideoExport, VideoRenderStatus


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


class WeeklyReport(BaseModel):
    id: str = Field(default_factory=lambda: new_id("weekly"))
    week_start: date
    week_end: date
    intent_id: str
    daily_summary_ids: list[str] = Field(default_factory=list)
    briefing_ids: list[str] = Field(default_factory=list)
    research_answer_ids: list[str] = Field(default_factory=list)
    video_export_ids: list[str] = Field(default_factory=list)
    completed_actions: list[str] = Field(default_factory=list)
    pending_actions: list[str] = Field(default_factory=list)
    evidence_highlights: list[str] = Field(default_factory=list)
    disputed_or_risk_items: list[str] = Field(default_factory=list)
    cognitive_traps: list[str] = Field(default_factory=list)
    content_exports: list[str] = Field(default_factory=list)
    next_week_focus: list[str] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=utc_now)

    @field_validator("intent_id")
    @classmethod
    def validate_weekly_intent_id(cls, value: str) -> str:
        text = value.strip()
        if not text:
            raise ValueError("intent_id cannot be blank")
        return text

    @field_validator(
        "daily_summary_ids",
        "briefing_ids",
        "research_answer_ids",
        "video_export_ids",
        "completed_actions",
        "pending_actions",
        "evidence_highlights",
        "disputed_or_risk_items",
        "cognitive_traps",
        "content_exports",
        "next_week_focus",
    )
    @classmethod
    def validate_weekly_string_lists(cls, values: list[str]) -> list[str]:
        cleaned: list[str] = []
        for value in values:
            text = value.strip()
            if not text:
                raise ValueError("list items cannot be blank")
            cleaned.append(text)
        return cleaned

    @model_validator(mode="after")
    def validate_week_range(self):
        if self.week_end < self.week_start:
            raise ValueError("week_end cannot be before week_start")
        return self


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


def generate_weekly_report(
    week_start: date,
    week_end: date,
    *,
    intent: Intent,
    daily_summaries: list[DailySummary] | None = None,
    briefings: list[ChancellorBriefing] | None = None,
    research_answers: list[ResearchAnswer] | None = None,
    video_exports: list[VideoExport] | None = None,
) -> WeeklyReport:
    if week_end < week_start:
        raise ValueError("week_end cannot be before week_start")

    summaries = [
        summary
        for summary in daily_summaries or []
        if date_in_range(summary.date, week_start, week_end)
    ]
    active_briefings = [
        briefing
        for briefing in briefings or []
        if date_in_range(briefing.date, week_start, week_end)
    ]
    answers = [
        answer
        for answer in research_answers or []
        if date_in_range(answer.created_at.date(), week_start, week_end)
    ]
    exports = [
        export
        for export in video_exports or []
        if date_in_range(export.created_at.date(), week_start, week_end)
    ]

    completed_actions = actions_by_status(answers, {ActionStatus.done})
    pending_actions = actions_by_status(
        answers,
        {ActionStatus.proposed, ActionStatus.accepted, ActionStatus.in_progress},
    )

    return WeeklyReport(
        week_start=week_start,
        week_end=week_end,
        intent_id=intent.id,
        daily_summary_ids=[summary.id for summary in summaries],
        briefing_ids=[briefing.id for briefing in active_briefings],
        research_answer_ids=[answer.id for answer in answers],
        video_export_ids=[export.id for export in exports],
        completed_actions=completed_actions,
        pending_actions=pending_actions,
        evidence_highlights=weekly_evidence_highlights(summaries, answers),
        disputed_or_risk_items=weekly_risks(answers, exports),
        cognitive_traps=weekly_cognitive_traps(active_briefings),
        content_exports=weekly_content_exports(exports),
        next_week_focus=weekly_next_focus(active_briefings, pending_actions),
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


def date_in_range(value: date, start: date, end: date) -> bool:
    return start <= value <= end


def actions_by_status(answers: list[ResearchAnswer], statuses: set[ActionStatus]) -> list[str]:
    actions: list[str] = []
    for answer in answers:
        for action in answer.actions:
            if action.status in statuses:
                actions.append(action.title)
    return dedupe(actions)


def weekly_evidence_highlights(
    summaries: list[DailySummary],
    answers: list[ResearchAnswer],
) -> list[str]:
    highlights: list[str] = []
    for summary in summaries:
        highlights.extend(summary_lines(summary.fact_summary))
    for answer in answers:
        highlights.extend(statement.text for statement in answer.fact_statements)
    return dedupe(highlights)


def weekly_risks(
    answers: list[ResearchAnswer],
    exports: list[VideoExport],
) -> list[str]:
    risks: list[str] = []
    for answer in answers:
        risks.extend(statement.text for statement in answer.disputed_views)
        if answer.no_action_reason:
            risks.append(f"No action: {answer.no_action_reason}")
        for action in answer.actions:
            if action.status == ActionStatus.canceled:
                risks.append(f"Canceled action: {action.title}")
            if action.status == ActionStatus.no_action:
                risks.append(f"No action: {action.title}")
    for export in exports:
        if export.render_status == VideoRenderStatus.failed and export.error:
            risks.append(f"Video export failed: {export.error}")
    return dedupe(risks)


def weekly_cognitive_traps(briefings: list[ChancellorBriefing]) -> list[str]:
    traps: list[str] = []
    for briefing in briefings:
        traps.extend(briefing.cognitive_traps)
    return dedupe(traps)


def weekly_content_exports(exports: list[VideoExport]) -> list[str]:
    paths: list[str] = []
    for export in exports:
        if export.render_status == VideoRenderStatus.succeeded and export.mp4_path is not None:
            paths.append(export.mp4_path.as_posix())
    return dedupe(paths)


def weekly_next_focus(
    briefings: list[ChancellorBriefing],
    pending_actions: list[str],
) -> list[str]:
    focus: list[str] = []
    for briefing in sorted(briefings, key=lambda value: value.date, reverse=True):
        focus.extend(briefing.today_focus)
    focus.extend(pending_actions)
    return dedupe(focus)[:7]


def summary_lines(text: str) -> list[str]:
    lines: list[str] = []
    for line in text.splitlines():
        stripped = line.strip().lstrip("-* ").strip()
        if stripped:
            lines.append(stripped)
    return lines
