from __future__ import annotations

import unittest
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

from pydantic import ValidationError

from metaos.core.schemas import Citation
from metaos.ledger import (
    Action,
    ActionSourceType,
    ActionStatus,
    Advice,
    AttentionDrift,
    DailyPlan,
    DailyReview,
    DailySummary,
    Decision,
    DecisionReversibility,
    WorkEvent,
    WorkEventSource,
    WorkEventType,
)


class LedgerSchemaTests(unittest.TestCase):
    def test_daily_plan_cleans_focus_and_optional_ids(self) -> None:
        plan = DailyPlan(
            date=date(2026, 6, 15),
            intent_id=" intent_alpha ",
            role_id=" role_builder ",
            focus_items=[" ship sovereignty API "],
            deferred_items=["recommendations"],
            ignored_items=["generic news"],
            budget_id=" budget_today ",
        )

        self.assertTrue(plan.id.startswith("plan_"))
        self.assertEqual(plan.intent_id, "intent_alpha")
        self.assertEqual(plan.focus_items, ["ship sovereignty API"])

        with self.assertRaises(ValidationError):
            DailyPlan(date=date(2026, 6, 15), focus_items=["   "])

    def test_work_event_requires_source_ref_for_collected_sources_and_valid_time_range(self) -> None:
        started = datetime(2026, 6, 15, 9, tzinfo=timezone.utc)
        event = WorkEvent(
            date=date(2026, 6, 15),
            event_type=WorkEventType.build,
            title=" Implement ledger schemas ",
            source=WorkEventSource.git_commit,
            source_ref="abc123",
            started_at=started,
            ended_at=started + timedelta(hours=1),
            citations=[Citation(file_path=Path("notes.md"), excerpt="implemented schemas")],
        )

        self.assertTrue(event.id.startswith("we_"))
        self.assertEqual(event.title, "Implement ledger schemas")
        self.assertEqual(event.source_ref, "abc123")

        with self.assertRaises(ValidationError):
            WorkEvent(
                date=date(2026, 6, 15),
                title="Missing source ref",
                source=WorkEventSource.markdown_change,
            )

        with self.assertRaises(ValidationError):
            WorkEvent(
                date=date(2026, 6, 15),
                title="Bad time",
                started_at=started,
                ended_at=started - timedelta(minutes=1),
            )

    def test_advice_requires_advisor_and_content(self) -> None:
        advice = Advice(
            advisor="Reviewer",
            content="Keep the task boundary narrow",
            evidence=[Citation(excerpt="one module and one test")],
        )

        self.assertTrue(advice.id.startswith("advice_"))
        self.assertEqual(advice.content, "Keep the task boundary narrow")

        with self.assertRaises(ValidationError):
            Advice(advisor="   ", content="valid")

    def test_decision_requires_chosen_option_from_options(self) -> None:
        decision = Decision(
            title="Storage approach",
            options=["SQLite first", "PostgreSQL now"],
            chosen_option="SQLite first",
            reasoning="Lower risk for Alpha",
            reversibility=DecisionReversibility.reversible,
        )

        self.assertTrue(decision.id.startswith("decision_"))
        self.assertEqual(decision.chosen_option, "SQLite first")

        with self.assertRaises(ValidationError):
            Decision(title="Bad", options=["A", "B"], chosen_option="C")

    def test_action_status_and_non_manual_source_reference(self) -> None:
        action = Action(
            title="Write API tests",
            status=ActionStatus.accepted,
            source_type=ActionSourceType.decision,
            source_id="decision_1",
            intent_id="intent_alpha",
        )

        self.assertTrue(action.id.startswith("action_"))
        self.assertEqual(action.status, ActionStatus.accepted)

        with self.assertRaises(ValidationError):
            Action(title="Missing source", source_type=ActionSourceType.research_answer)

    def test_attention_drift_requires_non_negative_cost(self) -> None:
        drift = AttentionDrift(
            date=date(2026, 6, 15),
            trigger="Open-ended browsing",
            cost_minutes=12,
            countermeasure="Return to DailyPlan",
        )

        self.assertTrue(drift.id.startswith("drift_"))
        self.assertEqual(drift.cost_minutes, 12)

        with self.assertRaises(ValidationError):
            AttentionDrift(
                date=date(2026, 6, 15),
                trigger="Bad",
                cost_minutes=-1,
            )

    def test_daily_review_and_summary_keep_fact_judgment_reflection_action_boundaries(self) -> None:
        review = DailyReview(
            date=date(2026, 6, 15),
            facts=["A1 API routes were added"],
            judgments=["Task boundary remained narrow"],
            reflections=["Need to keep citations explicit"],
            actions_done=["Ran pytest"],
            actions_missed=["Install FFmpeg"],
            lessons=["Small contracts compound"],
        )
        summary = DailySummary(
            date=review.date,
            source_review_id=review.id,
            fact_summary=" A1 API routes were added. ",
            judgment_summary="Task boundary remained narrow.",
            reflection_summary="Need to keep citations explicit.",
            action_summary="Ran pytest.",
            citations=[Citation(excerpt="25 passed")],
        )

        self.assertTrue(review.id.startswith("review_"))
        self.assertTrue(summary.id.startswith("summary_"))
        self.assertEqual(summary.source_review_id, review.id)
        self.assertEqual(summary.fact_summary, "A1 API routes were added.")

        with self.assertRaises(ValidationError):
            DailySummary(
                date=review.date,
                source_review_id="   ",
                fact_summary="valid",
            )


if __name__ == "__main__":
    unittest.main()

