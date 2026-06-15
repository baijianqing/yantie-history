from __future__ import annotations

import unittest
from datetime import date, datetime, timezone
from pathlib import Path

from metaos.core.schemas import Citation
from metaos.ledger import (
    Action,
    ActionStatus,
    DailyReview,
    Decision,
    WorkEvent,
    WorkEventSource,
    WorkEventType,
    generate_daily_summary,
)


class DailySummaryGenerationTests(unittest.TestCase):
    def test_generate_daily_summary_preserves_boundaries_and_dedupes_citations(self) -> None:
        summary_date = date(2026, 6, 15)
        event_citation = Citation(file_path=Path("notes.md"), excerpt="Implemented collectors")
        decision_citation = Citation(source_id="src_1", excerpt="Task boundary must stay narrow")
        review = DailyReview(
            date=summary_date,
            facts=["Collector tests passed"],
            judgments=["Ledger scope remains narrow"],
            reflections=["Keep source categories explicit"],
            actions_done=["Committed collector task"],
            actions_missed=["Install FFmpeg"],
            lessons=["Small records become useful evidence"],
        )
        today_event = WorkEvent(
            date=summary_date,
            event_type=WorkEventType.build,
            title="Implemented DailySummary generator",
            source=WorkEventSource.git_commit,
            source_ref="abc123",
            citations=[event_citation],
        )
        old_event = WorkEvent(
            date=date(2026, 6, 14),
            title="Old note",
            source=WorkEventSource.markdown_change,
            source_ref="old.md",
        )
        today_decision = Decision(
            title="Summary approach",
            options=["Rule-based", "LLM"],
            chosen_option="Rule-based",
            reasoning="Alpha needs schema-stable output first",
            evidence_links=[event_citation, decision_citation],
            decided_at=datetime(2026, 6, 15, 10, tzinfo=timezone.utc),
        )
        old_decision = Decision(
            title="Old decision",
            options=["A", "B"],
            chosen_option="A",
            decided_at=datetime(2026, 6, 14, 10, tzinfo=timezone.utc),
        )
        done_action = Action(title="Write summary tests", status=ActionStatus.done)
        no_action = Action(title="Do not add model call", status=ActionStatus.no_action)

        summary = generate_daily_summary(
            summary_date,
            review,
            work_events=[old_event, today_event],
            decisions=[old_decision, today_decision],
            actions=[done_action, no_action],
        )

        self.assertTrue(summary.id.startswith("summary_"))
        self.assertEqual(summary.source_review_id, review.id)
        self.assertIn("Collector tests passed", summary.fact_summary)
        self.assertIn("Implemented DailySummary generator", summary.fact_summary)
        self.assertNotIn("Old note", summary.fact_summary)
        self.assertIn("Ledger scope remains narrow", summary.judgment_summary)
        self.assertIn("Summary approach -> Rule-based", summary.judgment_summary)
        self.assertNotIn("Old decision", summary.judgment_summary)
        self.assertIn("Keep source categories explicit", summary.reflection_summary)
        self.assertIn("Small records become useful evidence", summary.reflection_summary)
        self.assertIn("Committed collector task", summary.action_summary)
        self.assertIn("Missed: Install FFmpeg", summary.action_summary)
        self.assertIn("Write summary tests [done]", summary.action_summary)
        self.assertIn("Do not add model call [no action]", summary.action_summary)
        self.assertEqual(
            [citation.excerpt for citation in summary.citations],
            ["Implemented collectors", "Task boundary must stay narrow"],
        )

    def test_generate_daily_summary_uses_fact_fallback_for_empty_day(self) -> None:
        summary_date = date(2026, 6, 15)
        review = DailyReview(date=summary_date)

        summary = generate_daily_summary(summary_date, review)

        self.assertEqual(summary.fact_summary, "No recorded facts for 2026-06-15.")
        self.assertEqual(summary.judgment_summary, "")
        self.assertEqual(summary.reflection_summary, "")
        self.assertEqual(summary.action_summary, "")

    def test_generate_daily_summary_requires_matching_review_date(self) -> None:
        with self.assertRaises(ValueError):
            generate_daily_summary(
                date(2026, 6, 15),
                DailyReview(date=date(2026, 6, 14), facts=["Different day"]),
            )


if __name__ == "__main__":
    unittest.main()
