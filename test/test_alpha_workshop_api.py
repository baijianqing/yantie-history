from __future__ import annotations

import unittest
from datetime import date
from pathlib import Path

from fastapi.testclient import TestClient

from metaos.app.api import app
from metaos.core.schemas import Citation
from metaos.ledger import DailySummary


class AlphaWorkshopApiTests(unittest.TestCase):
    def setUp(self) -> None:
        self.client = TestClient(app)

    def test_episode_endpoint_returns_schema_valid_episode_spec(self) -> None:
        summary = DailySummary(
            id="summary_1",
            date=date(2026, 6, 16),
            source_review_id="review_1",
            fact_summary="- Tests passed\n- Citation audit passed",
            judgment_summary="- Scope stayed narrow",
            reflection_summary="- Keep evidence explicit",
            action_summary="- Commit the task",
            citations=[Citation(file_path=Path("notes.md"), excerpt="Tests passed")],
        )

        response = self.client.post(
            "/alpha/workshop/episodes",
            json={
                "daily_summary": summary.model_dump(mode="json"),
                "title": "Daily Build Review",
                "angle": "Turn the day into a verifiable account",
            },
        )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertTrue(payload["id"].startswith("episode_"))
        self.assertEqual(payload["daily_summary_id"], "summary_1")
        self.assertEqual(payload["title"], "Daily Build Review")
        self.assertEqual(payload["angle"], "Turn the day into a verifiable account")
        self.assertEqual(payload["facts"], ["Tests passed", "Citation audit passed"])
        self.assertEqual(payload["judgments"], ["Scope stayed narrow"])
        self.assertEqual(payload["reflections"], ["Keep evidence explicit"])
        self.assertEqual(payload["actions"], ["Commit the task"])
        self.assertEqual(payload["review_status"], "draft")
        self.assertEqual(payload["citations"][0]["file_path"].replace("\\", "/"), "notes.md")

    def test_episode_endpoint_uses_default_title_and_angle(self) -> None:
        summary = DailySummary(
            id="summary_2",
            date=date(2026, 6, 17),
            source_review_id="review_2",
            fact_summary="No recorded facts beyond smoke test.",
        )

        response = self.client.post(
            "/alpha/workshop/episodes",
            json={"daily_summary": summary.model_dump(mode="json")},
        )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["title"], "Daily Review 2026-06-17")
        self.assertEqual(payload["angle"], "Daily cognitive review")

    def test_episode_endpoint_rejects_invalid_summary_payload(self) -> None:
        response = self.client.post(
            "/alpha/workshop/episodes",
            json={
                "daily_summary": {
                    "id": "summary_bad",
                    "date": "2026-06-16",
                    "source_review_id": "review_1",
                    "fact_summary": "",
                }
            },
        )

        self.assertEqual(response.status_code, 422)


if __name__ == "__main__":
    unittest.main()
