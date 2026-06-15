from __future__ import annotations

import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

from pydantic import ValidationError

from metaos.core.schemas import Citation
from metaos.workshop import EpisodeReviewStatus, EpisodeSpec, assert_episode_can_export


class WorkshopSchemaTests(unittest.TestCase):
    def test_episode_spec_cleans_fields_and_defaults_to_not_exportable(self) -> None:
        episode = EpisodeSpec(
            daily_summary_id=" summary_1 ",
            title=" Daily Build Review ",
            angle="Convert the day into a verifiable account",
            facts=[" tests passed "],
            judgments=[" scope stayed narrow "],
            reflections=[" evidence should stay explicit "],
            actions=[" commit the task "],
            citations=[Citation(file_path=Path("DOMAIN_MODEL.md"), excerpt="DailySummary")],
        )

        self.assertTrue(episode.id.startswith("episode_"))
        self.assertEqual(episode.daily_summary_id, "summary_1")
        self.assertEqual(episode.title, "Daily Build Review")
        self.assertEqual(episode.facts, ["tests passed"])
        self.assertEqual(episode.review_status, EpisodeReviewStatus.draft)
        self.assertFalse(episode.ready_for_final_export)
        with self.assertRaises(ValueError):
            assert_episode_can_export(episode)

    def test_episode_spec_validates_required_text_and_list_items(self) -> None:
        with self.assertRaises(ValidationError):
            EpisodeSpec(
                daily_summary_id="   ",
                title="Valid",
                angle="Valid",
            )

        with self.assertRaises(ValidationError):
            EpisodeSpec(
                daily_summary_id="summary_1",
                title="Valid",
                angle="Valid",
                facts=["   "],
            )

    def test_terminal_review_status_requires_review_metadata(self) -> None:
        with self.assertRaises(ValidationError):
            EpisodeSpec(
                daily_summary_id="summary_1",
                title="Needs metadata",
                angle="Review gate",
                review_status=EpisodeReviewStatus.approved,
            )

        reviewed_at = datetime(2026, 6, 15, 10, tzinfo=timezone.utc)
        episode = EpisodeSpec(
            daily_summary_id="summary_1",
            title="Approved episode",
            angle="Review gate",
            review_status=EpisodeReviewStatus.approved,
            reviewer_id=" reviewer ",
            reviewed_at=reviewed_at,
            review_notes=" Approved after checking citations. ",
        )

        self.assertTrue(episode.ready_for_final_export)
        self.assertEqual(episode.reviewer_id, "reviewer")
        self.assertEqual(episode.review_notes, "Approved after checking citations.")
        assert_episode_can_export(episode)

    def test_updated_at_cannot_be_earlier_than_created_at(self) -> None:
        created_at = datetime(2026, 6, 15, 10, tzinfo=timezone.utc)

        with self.assertRaises(ValidationError):
            EpisodeSpec(
                daily_summary_id="summary_1",
                title="Bad time",
                angle="Review gate",
                created_at=created_at,
                updated_at=created_at - timedelta(seconds=1),
            )


if __name__ == "__main__":
    unittest.main()
