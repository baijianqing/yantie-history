from __future__ import annotations

import re
import unittest

from fastapi.testclient import TestClient

from metaos.yantie import create_yantie_web_app


class YantieWebUiTests(unittest.TestCase):
    def setUp(self) -> None:
        self.client = TestClient(create_yantie_web_app())

    def test_yantie_page_serves_immersive_scene_runtime(self) -> None:
        response = self.client.get("/yantie")

        self.assertEqual(response.status_code, 200)
        self.assertIn("text/html", response.headers["content-type"])
        html = response.text
        self.assertIn('data-testid="immersive-yantie-scene"', html)
        self.assertIn('id="sceneCanvas"', html)
        self.assertIn('id="hanMapScene"', html)
        self.assertIn('id="courtScene"', html)
        self.assertIn('id="powerNetworkScene"', html)
        self.assertIn('id="debateHud"', html)
        self.assertIn('id="evidenceRibbon"', html)
        self.assertIn('id="judgmentForm"', html)
        self.assertIn('id="soundToggle"', html)

    def test_yantie_page_is_guided_not_tab_driven(self) -> None:
        html = self.client.get("/yantie").text

        self.assertIn('id="advanceScene"', html)
        self.assertIn('id="revealEvidence"', html)
        self.assertIn('id="rewindScene"', html)
        self.assertIn("const historicalPrelude = [", html)
        self.assertIn("const yantielunChapters = [", html)
        self.assertIn("const debateRounds = yantielunChapters.map", html)
        self.assertIn("const scenes = [...historicalPrelude, ...debateRounds, judgmentScene];", html)
        self.assertIn('"map"', html)
        self.assertIn('"court"', html)
        self.assertIn('"network"', html)
        self.assertIn('"judgment"', html)
        self.assertNotIn('class="tabs"', html)
        self.assertNotIn('id="claimTabs"', html)

    def test_yantie_page_stages_background_before_sixty_ordered_chapter_rounds(self) -> None:
        html = self.client.get("/yantie").text

        for keyword in ["武帝余响", "诏问民疾苦", "本議第一", "雜論第六十", "退朝"]:
            self.assertIn(keyword, html)

        for visual_mode in [
            "background-map",
            "meeting-open",
            "map-pressure",
            "seat-opposition",
            "value-clash",
            "power-shadow",
            "archive-closure",
        ]:
            self.assertIn(visual_mode, html)

        chapter_ids = re.findall(r'"evidenceId": "(ev:src_yantielun:chapter_\d{3}:text_order:[0-9a-f]{8})"', html)
        self.assertEqual(len(chapter_ids), 60)
        self.assertEqual(len(set(chapter_ids)), 60)
        self.assertIn('document.getElementById("timelineRail").style.gridTemplateColumns = `repeat(${scenes.length}, minmax(0, 1fr))`;', html)
        self.assertIn("chapter.order).padStart", html)
        self.assertIn("evidence-seal", html)
        self.assertIn("退朝案牍", html)
        self.assertNotIn("ev:src_yantielun:juan01_benyi:literati_abolish", html)

    def test_yantie_page_uses_only_yantie_api_surface_and_local_audio(self) -> None:
        html = self.client.get("/yantie").text

        self.assertIn('const apiBase = "/api/yantie";', html)
        self.assertIn('getData("/manifest")', html)
        self.assertIn('getData("/claims")', html)
        self.assertIn('/judgment-cards"', html)
        self.assertIn("new AudioContext()", html)
        self.assertNotIn("/alpha/", html)
        self.assertNotIn("zhihu", html.lower())
        self.assertNotIn("elevenlabs", html.lower())
        self.assertNotIn("suno", html.lower())

    def test_standalone_app_serves_ui_and_api_together(self) -> None:
        ui_response = self.client.get("/")
        self.assertEqual(ui_response.status_code, 200)
        self.assertEqual(str(ui_response.url).rstrip("/"), "http://testserver/yantie")

        manifest = self.client.get("/api/yantie/manifest")
        self.assertEqual(manifest.status_code, 200)
        self.assertEqual(manifest.json()["data"]["pack_id"], "yantie_meeting_v1")

        search = self.client.get(
            "/api/yantie/evidence/search",
            params={"q": "\u4f1a\u8bae \u7ed3\u679c", "limit": 3},
        )
        self.assertEqual(search.status_code, 200)
        self.assertEqual(search.json()["data"]["archive_status"], "ok")


if __name__ == "__main__":
    unittest.main()
