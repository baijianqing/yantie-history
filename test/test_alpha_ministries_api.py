from __future__ import annotations

import unittest
from datetime import date

from fastapi.testclient import TestClient

from metaos.app.api import app
from metaos.ministries import MAX_ITEMS_PER_MINISTRY, MAX_ITEMS_TOTAL, NO_REPORT, Ministry, RecommendationCandidate
from metaos.sovereignty import AttentionBudget, Intent


class AlphaMinistriesApiTests(unittest.TestCase):
    def setUp(self) -> None:
        self.client = TestClient(app)

    def test_ministry_reports_endpoint_returns_limited_reports(self) -> None:
        intent = Intent(id="intent_alpha", title="Ship MetaOS Alpha")
        budget = AttentionBudget(date=date(2026, 6, 16), total_minutes=120, research_minutes=25)
        candidates = [
            self.candidate(Ministry.technology, "tech 1", cost=5, score=0.99),
            self.candidate(Ministry.technology, "tech 2", cost=5, score=0.98),
            self.candidate(Ministry.technology, "tech 3", cost=5, score=0.97),
            self.candidate(Ministry.technology, "tech 4", cost=5, score=0.96),
            self.candidate(Ministry.cognition, "cog 1", cost=5, score=0.95),
            self.candidate(Ministry.business, "biz 1", cost=5, score=0.94),
            self.candidate(Ministry.business, "wrong intent", intent_id="other", cost=1, score=1.0),
            self.candidate(Ministry.cognition, "too expensive", cost=30, score=0.93),
        ]

        response = self.client.post(
            "/alpha/ministries/daily-reports",
            json={
                "date": "2026-06-16",
                "intent": intent.model_dump(mode="json"),
                "attention_budget": budget.model_dump(mode="json"),
                "candidates": [candidate.model_dump(mode="json") for candidate in candidates],
            },
        )

        self.assertEqual(response.status_code, 200)
        reports = response.json()
        self.assertEqual({report["ministry"] for report in reports}, {"technology", "cognition", "business"})
        total_items = sum(len(report["items"]) for report in reports)
        self.assertLessEqual(total_items, MAX_ITEMS_TOTAL)
        self.assertTrue(all(len(report["items"]) <= MAX_ITEMS_PER_MINISTRY for report in reports))
        titles = [item["title"] for report in reports for item in report["items"]]
        self.assertIn("tech 1", titles)
        self.assertIn("cog 1", titles)
        self.assertNotIn("tech 4", titles)
        self.assertNotIn("wrong intent", titles)
        self.assertNotIn("too expensive", titles)

    def test_ministry_reports_endpoint_returns_no_report_for_empty_candidates(self) -> None:
        intent = Intent(id="intent_alpha", title="Ship MetaOS Alpha")
        budget = AttentionBudget(date=date(2026, 6, 16), total_minutes=30, research_minutes=10)

        response = self.client.post(
            "/alpha/ministries/daily-reports",
            json={
                "date": "2026-06-16",
                "intent": intent.model_dump(mode="json"),
                "attention_budget": budget.model_dump(mode="json"),
                "candidates": [],
            },
        )

        self.assertEqual(response.status_code, 200)
        reports = response.json()
        self.assertEqual(len(reports), 3)
        self.assertTrue(all(report["items"] == [] for report in reports))
        self.assertEqual({report["empty_reason"] for report in reports}, {NO_REPORT})

    def test_ministry_reports_endpoint_rejects_invalid_candidate_payload(self) -> None:
        response = self.client.post(
            "/alpha/ministries/daily-reports",
            json={
                "date": "2026-06-16",
                "intent": {"id": "intent_alpha", "title": "Ship MetaOS Alpha"},
                "attention_budget": {"date": "2026-06-16", "total_minutes": 30},
                "candidates": [
                    {
                        "ministry": "technology",
                        "title": "",
                        "reason": "Useful",
                        "intent_alignment": "Aligned",
                        "reading_cost_minutes": 1,
                        "cost_of_ignoring": "Miss signal",
                        "suggested_action": "Review",
                    }
                ],
            },
        )

        self.assertEqual(response.status_code, 422)

    def candidate(
        self,
        ministry: Ministry,
        title: str,
        *,
        cost: int,
        score: float,
        intent_id: str | None = None,
    ) -> RecommendationCandidate:
        return RecommendationCandidate(
            ministry=ministry,
            title=title,
            reason="Useful for current intent",
            intent_alignment="Aligned with Ship Alpha",
            reading_cost_minutes=cost,
            cost_of_ignoring="Miss a relevant signal",
            suggested_action="Review and decide",
            score=score,
            intent_id=intent_id,
        )


if __name__ == "__main__":
    unittest.main()
