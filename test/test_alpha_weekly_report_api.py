from __future__ import annotations

import unittest
from datetime import date, datetime, timezone
from pathlib import Path

from fastapi.testclient import TestClient

from metaos.app.api import app
from metaos.chancellor import ChancellorBriefing
from metaos.ledger import Action, ActionSourceType, DailySummary
from metaos.research import AnswerStatement, ResearchAnswer
from metaos.sovereignty import Intent
from metaos.workshop import VideoExport, VideoRenderStatus


class AlphaWeeklyReportApiTests(unittest.TestCase):
    def setUp(self) -> None:
        self.client = TestClient(app)

    def test_weekly_report_endpoint_returns_schema_valid_report(self) -> None:
        intent = Intent(id="intent_alpha", title="Ship MetaOS Alpha")
        summary = DailySummary(
            id="summary_1",
            date=date(2026, 6, 16),
            source_review_id="review_1",
            fact_summary="- Weekly API test passed",
        )
        briefing = ChancellorBriefing(
            id="briefing_1",
            date=date(2026, 6, 16),
            intent_id=intent.id,
            today_focus=["Wire weekly report API"],
            cognitive_traps=["Keep uncited claims out of facts."],
        )
        answer = ResearchAnswer(
            id="answer_1",
            task_id="task_1",
            fact_statements=[AnswerStatement(text="Weekly report keeps source ids.")],
            actions=[
                Action(
                    title="Wire weekly report API",
                    source_type=ActionSourceType.research_answer,
                    source_id="answer_1",
                    intent_id=intent.id,
                )
            ],
            created_at=datetime(2026, 6, 16, 9, tzinfo=timezone.utc),
        )
        export = VideoExport(
            id="export_1",
            episode_spec_id="episode_1",
            script_path=Path("assets/script.md"),
            voiceover_path=Path("assets/voiceover.txt"),
            subtitle_path=Path("assets/subtitles.srt"),
            cards_path=Path("assets/cards.json"),
            remotion_props_path=Path("assets/remotion-props.json"),
            mp4_path=Path("exports/week.mp4"),
            render_status=VideoRenderStatus.succeeded,
            created_at=datetime(2026, 6, 16, 10, tzinfo=timezone.utc),
            updated_at=datetime(2026, 6, 16, 10, tzinfo=timezone.utc),
        )

        response = self.client.post(
            "/alpha/chancellor/weekly-reports",
            json={
                "week_start": "2026-06-15",
                "week_end": "2026-06-21",
                "intent": intent.model_dump(mode="json"),
                "daily_summaries": [summary.model_dump(mode="json")],
                "briefings": [briefing.model_dump(mode="json")],
                "research_answers": [answer.model_dump(mode="json")],
                "video_exports": [export.model_dump(mode="json")],
            },
        )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertTrue(payload["id"].startswith("weekly_"))
        self.assertEqual(payload["intent_id"], intent.id)
        self.assertEqual(payload["daily_summary_ids"], ["summary_1"])
        self.assertEqual(payload["briefing_ids"], ["briefing_1"])
        self.assertEqual(payload["research_answer_ids"], ["answer_1"])
        self.assertEqual(payload["video_export_ids"], ["export_1"])
        self.assertIn("Weekly API test passed", payload["evidence_highlights"])
        self.assertIn("Wire weekly report API", payload["pending_actions"])
        self.assertEqual(payload["content_exports"], ["exports/week.mp4"])

    def test_weekly_report_endpoint_returns_400_for_invalid_week_range(self) -> None:
        response = self.client.post(
            "/alpha/chancellor/weekly-reports",
            json={
                "week_start": "2026-06-22",
                "week_end": "2026-06-21",
                "intent": Intent(id="intent_alpha", title="Ship MetaOS Alpha").model_dump(mode="json"),
            },
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn("week_end", response.json()["detail"])


if __name__ == "__main__":
    unittest.main()
