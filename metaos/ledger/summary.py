"""DailySummary generation for the MetaOS Alpha ledger."""

from __future__ import annotations

import json
from datetime import date

from metaos.core.schemas import Citation
from metaos.ledger.schemas import (
    Action,
    ActionStatus,
    DailyReview,
    DailySummary,
    Decision,
    WorkEvent,
)


def generate_daily_summary(
    summary_date: date,
    review: DailyReview,
    *,
    work_events: list[WorkEvent] | None = None,
    decisions: list[Decision] | None = None,
    actions: list[Action] | None = None,
) -> DailySummary:
    """Generate a schema-validated DailySummary from ledger records."""

    if review.date != summary_date:
        raise ValueError("review.date must match summary_date")

    same_day_events = [event for event in work_events or [] if event.date == summary_date]
    same_day_decisions = [
        decision
        for decision in decisions or []
        if decision.decided_at.date() == summary_date
    ]
    day_actions = list(actions or [])

    fact_lines = [*review.facts]
    fact_lines.extend(format_work_event(event) for event in same_day_events)

    judgment_lines = [*review.judgments]
    judgment_lines.extend(format_decision(decision) for decision in same_day_decisions)

    reflection_lines = [*review.reflections]
    reflection_lines.extend(review.lessons)

    action_lines = [*review.actions_done]
    action_lines.extend(f"Missed: {item}" for item in review.actions_missed)
    action_lines.extend(format_action(action) for action in day_actions)

    citations = dedupe_citations(
        [
            citation
            for event in same_day_events
            for citation in event.citations
        ]
        + [
            citation
            for decision in same_day_decisions
            for citation in decision.evidence_links
        ]
    )

    return DailySummary(
        date=summary_date,
        source_review_id=review.id,
        fact_summary=join_summary_lines(fact_lines, fallback=f"No recorded facts for {summary_date.isoformat()}."),
        judgment_summary=join_summary_lines(judgment_lines),
        reflection_summary=join_summary_lines(reflection_lines),
        action_summary=join_summary_lines(action_lines),
        citations=citations,
    )


def format_work_event(event: WorkEvent) -> str:
    source = event.source.value
    source_ref = f" ({event.source_ref})" if event.source_ref else ""
    return f"{event.title} [{event.event_type.value}, {source}{source_ref}]"


def format_decision(decision: Decision) -> str:
    reasoning = f": {decision.reasoning}" if decision.reasoning else ""
    return f"{decision.title} -> {decision.chosen_option}{reasoning}"


def format_action(action: Action) -> str:
    status = "no action" if action.status == ActionStatus.no_action else action.status.value.replace("_", " ")
    return f"{action.title} [{status}]"


def join_summary_lines(lines: list[str], *, fallback: str = "") -> str:
    cleaned = [line.strip() for line in lines if line.strip()]
    return "\n".join(f"- {line}" for line in cleaned) if cleaned else fallback


def dedupe_citations(citations: list[Citation]) -> list[Citation]:
    seen: set[str] = set()
    unique: list[Citation] = []
    for citation in citations:
        key = json.dumps(citation.model_dump(mode="json"), sort_keys=True, default=str)
        if key in seen:
            continue
        seen.add(key)
        unique.append(citation)
    return unique
