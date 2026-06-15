from __future__ import annotations

import shutil
import tempfile
import unittest
from datetime import date, datetime, timezone
from pathlib import Path

from fastapi.testclient import TestClient

from metaos.app.api import app
from metaos.core.schemas import Citation
from metaos.ledger import DailySummary
from metaos.workshop import (
    EpisodeReviewStatus,
    EpisodeSpec,
    VideoRenderStatus,
    generate_episode_assets,
    review_episode,
)


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

    def test_episode_review_endpoint_marks_episode_approved(self) -> None:
        episode = EpisodeSpec(
            id="episode_1",
            daily_summary_id="summary_1",
            title="Daily Build Review",
            angle="Review gate",
            facts=["Tests passed"],
        )
        reviewed_at = datetime(2026, 6, 16, 10, tzinfo=timezone.utc)

        response = self.client.patch(
            "/alpha/workshop/episodes/episode_1/review",
            json={
                "episode": episode.model_dump(mode="json"),
                "status": "approved",
                "reviewer_id": " reviewer ",
                "reviewed_at": reviewed_at.isoformat(),
                "review_notes": " Approved after checking citations. ",
            },
        )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["id"], "episode_1")
        self.assertEqual(payload["review_status"], "approved")
        self.assertEqual(payload["reviewer_id"], "reviewer")
        self.assertEqual(payload["review_notes"], "Approved after checking citations.")
        self.assertTrue(payload["updated_at"])

    def test_episode_review_endpoint_rejects_path_body_mismatch(self) -> None:
        episode = EpisodeSpec(
            id="episode_1",
            daily_summary_id="summary_1",
            title="Daily Build Review",
            angle="Review gate",
        )

        response = self.client.patch(
            "/alpha/workshop/episodes/episode_other/review",
            json={
                "episode": episode.model_dump(mode="json"),
                "status": "pending_review",
            },
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn("episode_id", response.json()["detail"])

    def test_episode_review_endpoint_rejects_terminal_status_without_reviewer(self) -> None:
        episode = EpisodeSpec(
            id="episode_1",
            daily_summary_id="summary_1",
            title="Daily Build Review",
            angle="Review gate",
        )

        response = self.client.patch(
            "/alpha/workshop/episodes/episode_1/review",
            json={
                "episode": episode.model_dump(mode="json"),
                "status": "approved",
            },
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn("reviewer_id", response.json()["detail"])

    def test_episode_assets_endpoint_writes_reviewable_files(self) -> None:
        episode = EpisodeSpec(
            id="episode_1",
            daily_summary_id="summary_1",
            title="Daily Build Review",
            angle="Turn the day into a verifiable account",
            facts=["Tests passed"],
            judgments=["Scope stayed narrow"],
            reflections=["Evidence stayed explicit"],
            actions=["Commit the task"],
        )

        with tempfile.TemporaryDirectory() as temp_dir:
            output_dir = Path(temp_dir) / "assets"
            response = self.client.post(
                "/alpha/workshop/episodes/episode_1/assets",
                json={
                    "episode": episode.model_dump(mode="json"),
                    "output_dir": str(output_dir),
                },
            )

            self.assertEqual(response.status_code, 200)
            payload = response.json()
            self.assertEqual(payload["episode_spec_id"], "episode_1")
            self.assertTrue(Path(payload["script_path"]).exists())
            self.assertTrue(Path(payload["voiceover_path"]).exists())
            self.assertTrue(Path(payload["subtitle_path"]).exists())
            self.assertTrue(Path(payload["cards_path"]).exists())
            self.assertTrue(Path(payload["remotion_props_path"]).exists())
            self.assertIn("Daily Build Review", Path(payload["script_path"]).read_text(encoding="utf-8"))
            self.assertIn("Tests passed", Path(payload["voiceover_path"]).read_text(encoding="utf-8"))

    def test_episode_assets_endpoint_rejects_path_body_mismatch(self) -> None:
        episode = EpisodeSpec(
            id="episode_1",
            daily_summary_id="summary_1",
            title="Daily Build Review",
            angle="Review gate",
        )

        response = self.client.post(
            "/alpha/workshop/episodes/episode_other/assets",
            json={"episode": episode.model_dump(mode="json")},
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn("episode_id", response.json()["detail"])

    def test_episode_render_endpoint_returns_failed_export_for_unapproved_episode(self) -> None:
        episode = EpisodeSpec(
            id="episode_1",
            daily_summary_id="summary_1",
            title="Daily Build Review",
            angle="Review gate",
            facts=["Tests passed"],
        )

        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            assets = generate_episode_assets(episode, root / "assets")
            response = self.client.post(
                "/alpha/workshop/episodes/episode_1/render",
                json={
                    "episode": episode.model_dump(mode="json"),
                    "assets": assets.model_dump(mode="json"),
                    "output_dir": str(root / "exports"),
                },
            )

            self.assertEqual(response.status_code, 200)
            payload = response.json()
            self.assertEqual(payload["episode_spec_id"], "episode_1")
            self.assertEqual(payload["render_status"], VideoRenderStatus.failed.value)
            self.assertIsNone(payload["mp4_path"])
            self.assertIn("approved", payload["error"])

    def test_episode_render_endpoint_rejects_asset_episode_mismatch(self) -> None:
        episode = EpisodeSpec(
            id="episode_1",
            daily_summary_id="summary_1",
            title="Daily Build Review",
            angle="Review gate",
            facts=["Tests passed"],
        )

        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            assets = generate_episode_assets(episode, root / "assets")
            asset_payload = assets.model_dump(mode="json")
            asset_payload["episode_spec_id"] = "episode_other"

            response = self.client.post(
                "/alpha/workshop/episodes/episode_1/render",
                json={
                    "episode": episode.model_dump(mode="json"),
                    "assets": asset_payload,
                    "output_dir": str(root / "exports"),
                },
            )

            self.assertEqual(response.status_code, 400)
            self.assertIn("assets episode_spec_id", response.json()["detail"])

    @unittest.skipIf(shutil.which("ffmpeg") is None, "ffmpeg is required for MP4 render API test")
    def test_episode_render_endpoint_creates_mp4_for_approved_episode(self) -> None:
        episode = review_episode(
            EpisodeSpec(
                id="episode_1",
                daily_summary_id="summary_1",
                title="Daily Build Review",
                angle="Review gate",
                facts=["Tests passed"],
            ),
            status=EpisodeReviewStatus.approved,
            reviewer_id="reviewer",
            reviewed_at=datetime(2026, 6, 16, 10, tzinfo=timezone.utc),
            review_notes="Approved for export",
        )

        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            assets = generate_episode_assets(episode, root / "assets")
            response = self.client.post(
                "/alpha/workshop/episodes/episode_1/render",
                json={
                    "episode": episode.model_dump(mode="json"),
                    "assets": assets.model_dump(mode="json"),
                    "output_dir": str(root / "exports"),
                },
            )

            self.assertEqual(response.status_code, 200)
            payload = response.json()
            self.assertEqual(payload["render_status"], VideoRenderStatus.succeeded.value)
            self.assertIsNotNone(payload["mp4_path"])
            mp4_path = Path(payload["mp4_path"])
            self.assertTrue(mp4_path.exists())
            self.assertGreater(mp4_path.stat().st_size, 0)


if __name__ == "__main__":
    unittest.main()
