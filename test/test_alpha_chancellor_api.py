from __future__ import annotations

import unittest
from datetime import date

from fastapi.testclient import TestClient

from metaos.app.api import app
from metaos.ledger import Action, ActionSourceType, DailyReview
from metaos.ministries import Ministry, MinistryReport, NO_REPORT
from metaos.research import AnswerStatement, ResearchAnswer, SourceStatus
from metaos.sovereignty import AttentionBudget, CurrentRole, Intent


class AlphaChancellorApiTests(unittest.TestCase):
    def setUp(self) -> None:
        self.client = TestClient(app)

    def test_chancellor_briefing_endpoint_returns_schema_valid_briefing(self) -> None:
        intent = Intent(id="intent_alpha", title="Ship MetaOS Alpha")
        role = CurrentRole(
            id="role_builder",
            name="Builder",
            forbidden_focus=["generic news feed"],
        )
        budget = AttentionBudget(date=date(2026, 6, 16), total_minutes=180)
        review = DailyReview(
            id="review_1",
            date=date(2026, 6, 16),
            actions_missed=["Draft weekly report"],
        )
        answer = ResearchAnswer(
            id="answer_1",
            task_id="task_1",
            model_inferences=[
                AnswerStatement(text="Likely useful", source_status=SourceStatus.uncited)
            ],
            actions=[
                Action(
                    title="Wire chancellor API",
                    source_type=ActionSourceType.research_answer,
                    source_id="answer_1",
                    intent_id=intent.id,
                )
            ],
        )
        report = MinistryReport(
            id="report_1",
            date=date(2026, 6, 16),
            ministry=Ministry.cognition,
            empty_reason=NO_REPORT,
        )

        response = self.client.post(
            "/alpha/chancellor/daily-briefings",
            json={
                "date": "2026-06-16",
                "intent": intent.model_dump(mode="json"),
                "role": role.model_dump(mode="json"),
                "attention_budget": budget.model_dump(mode="json"),
                "daily_review": review.model_dump(mode="json"),
                "research_answers": [answer.model_dump(mode="json")],
                "ministry_reports": [report.model_dump(mode="json")],
            },
        )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertTrue(payload["id"].startswith("briefing_"))
        self.assertEqual(payload["intent_id"], intent.id)
        self.assertEqual(payload["role_id"], role.id)
        self.assertIn("Intent: Ship MetaOS Alpha", payload["today_focus"])
        self.assertIn("Wire chancellor API", payload["today_focus"])
        self.assertIn("Draft weekly report", payload["deferred_items"])
        self.assertIn("generic news feed", payload["ignored_items"])
        self.assertIn("cognition: do not force a recommendation today", payload["ignored_items"])
        self.assertIn(
            "Uncited inference present; keep it out of fact statements.",
            payload["cognitive_traps"],
        )
        self.assertEqual(payload["source_research_ids"], ["answer_1"])
        self.assertEqual(payload["source_review_id"], "review_1")

    def test_chancellor_briefing_endpoint_rejects_invalid_payload(self) -> None:
        response = self.client.post(
            "/alpha/chancellor/daily-briefings",
            json={
                "date": "2026-06-16",
                "intent": {"id": "intent_alpha", "title": "Ship MetaOS Alpha"},
                "attention_budget": {"date": "2026-06-16", "total_minutes": -1},
            },
        )

        self.assertEqual(response.status_code, 422)


if __name__ == "__main__":
    unittest.main()
