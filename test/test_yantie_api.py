from __future__ import annotations

import unittest

from fastapi import FastAPI
from fastapi.testclient import TestClient

from metaos.yantie import create_yantie_api_router, load_default_evidence_pack


class YantieApiTests(unittest.TestCase):
    def setUp(self) -> None:
        self.pack = load_default_evidence_pack()
        self.app = FastAPI()
        self.app.include_router(create_yantie_api_router(pack=self.pack))
        self.client = TestClient(self.app)

    def test_manifest_theme_and_collections_are_readable_offline(self) -> None:
        manifest = self.client.get("/api/yantie/manifest")
        self.assertEqual(manifest.status_code, 200)
        manifest_body = manifest.json()
        self.assertEqual(manifest_body["data"]["pack_id"], "yantie_meeting_v1")
        self.assertFalse(manifest_body["data"]["features"]["runtime_rag"])
        self.assertFalse(manifest_body["data"]["features"]["vector_store"])
        self.assertEqual(manifest_body["meta"]["schema_version"], "yantie_evidence_pack_v1")

        theme = self.client.get("/api/yantie/theme")
        self.assertEqual(theme.status_code, 200)
        self.assertEqual(theme.json()["data"]["theme_id"], "theme_yantie_meeting")

        sources = self.client.get("/api/yantie/sources", params={"source_type": "primary_text"})
        self.assertEqual(sources.status_code, 200)
        self.assertTrue(sources.json()["data"]["items"])
        self.assertTrue(
            all(source["source_type"] == "primary_text" for source in sources.json()["data"]["items"])
        )

        actors = self.client.get("/api/yantie/actors", params={"include": "evidence_summary"})
        self.assertEqual(actors.status_code, 200)
        self.assertIn("evidence_summary", actors.json()["data"]["items"][0])

        map_layers = self.client.get("/api/yantie/map-layers")
        self.assertEqual(map_layers.status_code, 200)
        self.assertGreaterEqual(map_layers.json()["data"]["total"], 3)

    def test_search_route_returns_verified_evidence_and_archive_insufficient(self) -> None:
        fiscal = self.client.get(
            "/api/yantie/evidence/search",
            params={"q": "桑弘羊 财政", "limit": 5},
        )
        self.assertEqual(fiscal.status_code, 200)
        fiscal_data = fiscal.json()["data"]
        self.assertEqual(fiscal_data["archive_status"], "ok")
        self.assertIn(
            "ev:src_yantielun:juan01_benyi:border_finance:1a2b3c4d",
            [item["evidence"]["evidence_id"] for item in fiscal_data["items"]],
        )

        chronicle = self.client.get(
            "/api/yantie/evidence/search",
            params={"q": "会议 结果", "source_type": "chronicle"},
        )
        self.assertEqual(chronicle.status_code, 200)
        self.assertTrue(chronicle.json()["data"]["items"])
        self.assertTrue(
            all(item["source"]["source_type"] == "chronicle" for item in chronicle.json()["data"]["items"])
        )

        insufficient = self.client.get(
            "/api/yantie/evidence/search",
            params={"q": "唐朝 科举"},
        )
        self.assertEqual(insufficient.status_code, 200)
        self.assertEqual(insufficient.json()["data"]["archive_status"], "archive_insufficient")
        self.assertEqual(insufficient.json()["data"]["items"], [])

    def test_evidence_claim_relation_and_path_routes_are_filterable(self) -> None:
        evidence_id = "ev:src_hanshu_zhaodi:juan007:abolish_liquor_office:ddccbbaa"
        evidence = self.client.get(f"/api/yantie/evidence/{evidence_id}")
        self.assertEqual(evidence.status_code, 200)
        self.assertEqual(evidence.json()["data"]["evidence_id"], evidence_id)

        missing = self.client.get("/api/yantie/evidence/ev:missing:bad:bad:00000000")
        self.assertEqual(missing.status_code, 404)
        self.assertEqual(missing.json()["error"]["code"], "not_found")

        claims = self.client.get(
            "/api/yantie/claims",
            params={"display_zone": "evidence_room"},
        )
        self.assertEqual(claims.status_code, 200)
        self.assertEqual(claims.json()["data"]["items"][0]["display_zone"], "evidence_room")

        relations = self.client.get(
            "/api/yantie/relations",
            params={"from_id": "actor_sang_hongyang"},
        )
        self.assertEqual(relations.status_code, 200)
        self.assertTrue(relations.json()["data"]["items"])
        self.assertTrue(
            all(relation["from_id"] == "actor_sang_hongyang" for relation in relations.json()["data"]["items"])
        )

        path = self.client.get("/api/yantie/curated-paths/path_power_network")
        self.assertEqual(path.status_code, 200)
        self.assertEqual(path.json()["data"]["path_id"], "path_power_network")

        missing_path = self.client.get("/api/yantie/curated-paths/path_missing")
        self.assertEqual(missing_path.status_code, 404)

    def test_judgment_card_is_local_and_does_not_mutate_pack(self) -> None:
        claim_count_before = len(self.pack.claims)
        response = self.client.post(
            "/api/yantie/judgment-cards",
            json={
                "selected_claim_ids": ["claim_literati_oppose_monopoly"],
                "selected_evidence_ids": ["ev:src_yantielun:juan01_benyi:literati_abolish:0a1b2c3d"],
                "personal_reflection": "先理解价值冲突，再判断制度取舍。",
                "disposition": "modern_analogy_with_caution",
            },
        )

        self.assertEqual(response.status_code, 200)
        data = response.json()["data"]
        self.assertTrue(data["judgment_card_id"].startswith("local_judgment:"))
        self.assertFalse(data["writes_to_evidence_pack"])
        self.assertEqual(data["history_boundary"], "Personal reflection is not historical evidence.")
        self.assertIsNotNone(data["caution"])
        self.assertEqual(len(self.pack.claims), claim_count_before)

    def test_judgment_card_rejects_unknown_claims(self) -> None:
        response = self.client.post(
            "/api/yantie/judgment-cards",
            json={
                "selected_claim_ids": ["claim_missing"],
                "selected_evidence_ids": [],
                "disposition": "continue_research",
            },
        )

        self.assertEqual(response.status_code, 404)
        self.assertEqual(response.json()["error"]["code"], "not_found")


if __name__ == "__main__":
    unittest.main()
