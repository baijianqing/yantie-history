from __future__ import annotations

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
        self.assertIn("const conflictActs = [", html)
        self.assertIn("const issueMatrix = [", html)
        self.assertIn("const scenes = [...historicalPrelude, ...conflictActs, judgmentScene].map", html)
        self.assertIn('"map"', html)
        self.assertIn('"court"', html)
        self.assertIn('"network"', html)
        self.assertIn('"judgment"', html)
        self.assertIn("choice-range", html)
        self.assertIn("state.userChoices", html)
        self.assertNotIn('class="tabs"', html)
        self.assertNotIn('id="claimTabs"', html)

    def test_yantie_page_stages_background_before_five_conflict_acts(self) -> None:
        html = self.client.get("/yantie").text

        for keyword in ["武帝余响", "诏问民疾苦", "财政先声", "民生反击", "义利显形", "治道复杂化", "权力遮蔽", "退朝"]:
            self.assertIn(keyword, html)

        for visual_mode in [
            "background-map",
            "meeting-open",
            "fiscal-ascendant",
            "livelihood-counter",
            "yi-li-clash",
            "statecraft-complexity",
            "power-shadow",
            "archive-closure",
        ]:
            self.assertIn(visual_mode, html)

        self.assertEqual(html.count('"visualMode":'), 8)
        self.assertEqual(html.count('"revealedConflict":'), 8)
        self.assertEqual(html.count('"choicePrompt":'), 5)
        self.assertGreaterEqual(html.count('"historicalEvidence": ['), 8)
        self.assertGreaterEqual(html.count('"philosophyLens": ['), 8)
        self.assertIn("evidence-seal", html)
        self.assertIn("issue-pill", html)
        self.assertIn("退朝案牍", html)

    def test_yantie_page_exposes_issue_matrix_without_chapter_player(self) -> None:
        html = self.client.get("/yantie").text

        for issue in ["盐铁", "酒榷", "均输", "平准", "边防", "农桑", "商工", "奢俭", "吏治", "教化", "义利", "权力", "后世评价"]:
            self.assertIn(issue, html)

        self.assertIn("ev:src_lunyu_liren:liren04:yi_li_lens:aa110001", html)
        self.assertIn("ev:src_xunzi_fuguo:fuguo:jieyong_yumin:aa110003", html)
        self.assertIn("五幕显影选择", html)
        self.assertNotIn("第60回合", html)
        self.assertNotIn("yantielunChapters", html)

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
