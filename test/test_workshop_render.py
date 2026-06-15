from __future__ import annotations

import json
import shutil
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

from metaos.workshop import (
    EpisodeReviewStatus,
    EpisodeSpec,
    VideoRenderStatus,
    generate_episode_assets,
    render_episode_video,
    review_episode,
)


class WorkshopRenderTests(unittest.TestCase):
    def test_generate_episode_assets_writes_reviewable_files(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            episode = self.make_episode()

            assets = generate_episode_assets(episode, Path(temp_dir))

            self.assertTrue(assets.script_path.exists())
            self.assertTrue(assets.voiceover_path.exists())
            self.assertTrue(assets.subtitle_path.exists())
            self.assertTrue(assets.cards_path.exists())
            self.assertTrue(assets.remotion_props_path.exists())
            self.assertIn("# Daily Build Review", assets.script_path.read_text(encoding="utf-8"))
            self.assertIn("00:00:00,000 --> 00:00:04,000", assets.subtitle_path.read_text(encoding="utf-8"))
            cards = json.loads(assets.cards_path.read_text(encoding="utf-8"))
            self.assertEqual(cards[0], {"type": "fact", "text": "Tests passed"})
            remotion_props = json.loads(assets.remotion_props_path.read_text(encoding="utf-8"))
            self.assertEqual(remotion_props["reviewStatus"], EpisodeReviewStatus.draft.value)

    def test_render_episode_video_returns_failed_export_for_unapproved_episode(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            episode = self.make_episode()
            assets = generate_episode_assets(episode, root / "assets")

            export = render_episode_video(episode, assets, root / "exports")

            self.assertEqual(export.render_status, VideoRenderStatus.failed)
            self.assertIn("approved", export.error or "")
            self.assertIsNone(export.mp4_path)

    def test_render_episode_video_returns_failed_export_when_ffmpeg_fails(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            episode = self.approved_episode()
            assets = generate_episode_assets(episode, root / "assets")

            export = render_episode_video(
                episode,
                assets,
                root / "exports",
                ffmpeg_binary="ffmpeg-command-that-does-not-exist",
            )

            self.assertEqual(export.render_status, VideoRenderStatus.failed)
            self.assertTrue(export.error)

    @unittest.skipIf(shutil.which("ffmpeg") is None, "ffmpeg is required for MP4 render test")
    def test_render_episode_video_creates_mp4_for_approved_episode(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            episode = self.approved_episode()
            assets = generate_episode_assets(episode, root / "assets")

            export = render_episode_video(episode, assets, root / "exports")

            self.assertEqual(export.render_status, VideoRenderStatus.succeeded)
            self.assertIsNotNone(export.mp4_path)
            assert export.mp4_path is not None
            self.assertTrue(export.mp4_path.exists())
            self.assertGreater(export.mp4_path.stat().st_size, 0)

    def make_episode(self) -> EpisodeSpec:
        return EpisodeSpec(
            daily_summary_id="summary_1",
            title="Daily Build Review",
            angle="Turn the day into a verifiable account",
            facts=["Tests passed"],
            judgments=["Scope stayed narrow"],
            reflections=["Evidence remained explicit"],
            actions=["Commit the task"],
        )

    def approved_episode(self) -> EpisodeSpec:
        return review_episode(
            self.make_episode(),
            status=EpisodeReviewStatus.approved,
            reviewer_id="reviewer",
            reviewed_at=datetime(2026, 6, 15, 10, tzinfo=timezone.utc),
            review_notes="Approved for export",
        )


if __name__ == "__main__":
    unittest.main()
