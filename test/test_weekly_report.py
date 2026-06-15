from __future__ import annotations

import unittest
from datetime import date, datetime, timezone
from pathlib import Path

from metaos.chancellor import ChancellorBriefing, WeeklyReport, generate_weekly_report
from metaos.ledger import Action, ActionSourceType, ActionStatus, DailySummary
from metaos.research import AnswerStatement, ResearchAnswer
from metaos.sovereignty import Intent
from metaos.workshop import VideoExport, VideoRenderStatus


class WeeklyReportTests(unittest.TestCase):
    def test_generate_weekly_report_packages_week_closure_inputs(self) -> None:
        intent = Intent(id="intent_alpha", title="Ship MetaOS Alpha")
        summary = DailySummary(
            id="summary_1",
            date=date(2026, 6, 18),
            source_review_id="review_1",
            fact_summary="- Retrieval tests passed\n- Citation audit passed",
            action_summary="Close weekly packaging [done]",
        )
        old_summary = DailySummary(
            id="summary_old",
            date=date(2026, 6, 14),
            source_review_id="review_old",
            fact_summary="Old fact",
        )
        briefing = ChancellorBriefing(
            id="briefing_1",
            date=date(2026, 6, 20),
            intent_id=intent.id,
            today_focus=["Ship weekly report", "Wire next orchestration task"],
            cognitive_traps=["Do not inflate evidence beyond citations."],
        )
        old_briefing = ChancellorBriefing(
            id="briefing_old",
            date=date(2026, 6, 14),
            intent_id=intent.id,
            today_focus=["Old focus"],
            cognitive_traps=["Old trap"],
        )
        answer = ResearchAnswer(
            id="answer_1",
            task_id="task_1",
            fact_statements=[AnswerStatement(text="Evidence matrix preserved citations.")],
            disputed_views=[AnswerStatement(text="Durable orchestration remains partial.")],
            actions=[
                Action(
                    title="Close weekly packaging",
                    status=ActionStatus.done,
                    source_type=ActionSourceType.research_answer,
                    source_id="answer_1",
                    intent_id=intent.id,
                ),
                Action(
                    title="Wire next orchestration task",
                    status=ActionStatus.in_progress,
                    source_type=ActionSourceType.research_answer,
                    source_id="answer_1",
                    intent_id=intent.id,
                ),
            ],
            created_at=datetime(2026, 6, 19, 9, tzinfo=timezone.utc),
        )
        no_action_answer = ResearchAnswer(
            id="answer_2",
            task_id="task_2",
            no_action_reason="Evidence is insufficient for a production claim.",
            created_at=datetime(2026, 6, 20, 9, tzinfo=timezone.utc),
        )
        old_answer = ResearchAnswer(
            id="answer_old",
            task_id="task_old",
            no_action_reason="Old reason",
            created_at=datetime(2026, 6, 14, 9, tzinfo=timezone.utc),
        )
        succeeded_export = VideoExport(
            id="export_1",
            episode_spec_id="episode_1",
            script_path=Path("assets/script.md"),
            voiceover_path=Path("assets/voiceover.txt"),
            subtitle_path=Path("assets/subtitles.srt"),
            cards_path=Path("assets/cards.json"),
            remotion_props_path=Path("assets/remotion-props.json"),
            mp4_path=Path("exports/week.mp4"),
            render_status=VideoRenderStatus.succeeded,
            created_at=datetime(2026, 6, 20, 10, tzinfo=timezone.utc),
            updated_at=datetime(2026, 6, 20, 10, tzinfo=timezone.utc),
        )
        failed_export = VideoExport(
            id="export_2",
            episode_spec_id="episode_2",
            script_path=Path("assets/script.md"),
            voiceover_path=Path("assets/voiceover.txt"),
            subtitle_path=Path("assets/subtitles.srt"),
            cards_path=Path("assets/cards.json"),
            remotion_props_path=Path("assets/remotion-props.json"),
            render_status=VideoRenderStatus.failed,
            error="ffmpeg unavailable",
            created_at=datetime(2026, 6, 20, 11, tzinfo=timezone.utc),
            updated_at=datetime(2026, 6, 20, 11, tzinfo=timezone.utc),
        )

        report = generate_weekly_report(
            date(2026, 6, 15),
            date(2026, 6, 21),
            intent=intent,
            daily_summaries=[summary, old_summary],
            briefings=[briefing, old_briefing],
            research_answers=[answer, no_action_answer, old_answer],
            video_exports=[succeeded_export, failed_export],
        )

        self.assertIsInstance(report, WeeklyReport)
        self.assertEqual(report.intent_id, intent.id)
        self.assertEqual(report.daily_summary_ids, ["summary_1"])
        self.assertEqual(report.briefing_ids, ["briefing_1"])
        self.assertEqual(report.research_answer_ids, ["answer_1", "answer_2"])
        self.assertEqual(report.video_export_ids, ["export_1", "export_2"])
        self.assertEqual(report.completed_actions, ["Close weekly packaging"])
        self.assertEqual(report.pending_actions, ["Wire next orchestration task"])
        self.assertIn("Retrieval tests passed", report.evidence_highlights)
        self.assertIn("Evidence matrix preserved citations.", report.evidence_highlights)
        self.assertIn("Durable orchestration remains partial.", report.disputed_or_risk_items)
        self.assertIn(
            "No action: Evidence is insufficient for a production claim.",
            report.disputed_or_risk_items,
        )
        self.assertIn("Video export failed: ffmpeg unavailable", report.disputed_or_risk_items)
        self.assertEqual(report.cognitive_traps, ["Do not inflate evidence beyond citations."])
        self.assertEqual(report.content_exports, ["exports/week.mp4"])
        self.assertEqual(
            report.next_week_focus,
            ["Ship weekly report", "Wire next orchestration task"],
        )

    def test_generate_weekly_report_rejects_invalid_week_range(self) -> None:
        with self.assertRaises(ValueError):
            generate_weekly_report(
                date(2026, 6, 22),
                date(2026, 6, 21),
                intent=Intent(id="intent_alpha", title="Ship MetaOS Alpha"),
            )


if __name__ == "__main__":
    unittest.main()
