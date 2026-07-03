from __future__ import annotations

import unittest

from fastapi.testclient import TestClient

from metaos.yantie import create_yantie_web_app


class YantieWebUiTests(unittest.TestCase):
    def setUp(self) -> None:
        self.client = TestClient(create_yantie_web_app())

    def test_yantie_page_serves_playable_experience(self) -> None:
        response = self.client.get("/yantie")

        self.assertEqual(response.status_code, 200)
        self.assertIn("text/html", response.headers["content-type"])
        html = response.text
        self.assertIn("<h1>盐铁会议历史复原</h1>", html)
        self.assertIn('id="hanMap"', html)
        self.assertIn('id="actorSeats"', html)
        self.assertIn('id="claimList"', html)
        self.assertIn('id="evidenceResults"', html)
        self.assertIn('id="powerNetwork"', html)
        self.assertIn('id="judgmentOutput"', html)

    def test_yantie_page_uses_only_yantie_api_surface(self) -> None:
        html = self.client.get("/yantie").text

        self.assertIn('const apiBase = "/api/yantie";', html)
        self.assertIn('getJson("/manifest")', html)
        self.assertIn('getJson("/claims")', html)
        self.assertIn('/judgment-cards"', html)
        self.assertNotIn("/alpha/", html)
        self.assertNotIn("zhihu", html.lower())

    def test_standalone_app_serves_ui_and_api_together(self) -> None:
        ui_response = self.client.get("/")
        self.assertEqual(ui_response.status_code, 200)
        self.assertEqual(str(ui_response.url).rstrip("/"), "http://testserver/yantie")

        manifest = self.client.get("/api/yantie/manifest")
        self.assertEqual(manifest.status_code, 200)
        self.assertEqual(manifest.json()["data"]["pack_id"], "yantie_meeting_v1")

        search = self.client.get("/api/yantie/evidence/search", params={"q": "会议 结果", "limit": 3})
        self.assertEqual(search.status_code, 200)
        self.assertEqual(search.json()["data"]["archive_status"], "ok")


if __name__ == "__main__":
    unittest.main()
