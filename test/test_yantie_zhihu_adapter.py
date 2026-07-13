from __future__ import annotations

import unittest

import httpx
from fastapi import FastAPI
from fastapi.testclient import TestClient

from metaos.yantie import create_yantie_api_router, load_default_evidence_pack
from metaos.yantie.zhihu_adapter import ZhihuAdapterConfig, ZhihuExternalEchoAdapter


class YantieZhihuAdapterTests(unittest.TestCase):
    def setUp(self) -> None:
        self.pack = load_default_evidence_pack()

    def test_missing_secret_degrades_without_breaking_core_manifest(self) -> None:
        adapter = ZhihuExternalEchoAdapter(ZhihuAdapterConfig(access_secret=None))
        client = self._client(adapter)

        manifest = client.get("/api/yantie/manifest")
        self.assertEqual(manifest.status_code, 200)
        self.assertFalse(manifest.json()["data"]["features"]["external_echo_enabled"])
        self.assertFalse(manifest.json()["data"]["features"]["runtime_rag"])

        response = client.get("/api/yantie/external/zhihu/search", params={"q": "盐铁论", "count": 3})
        self.assertEqual(response.status_code, 401)
        body = response.json()
        self.assertEqual(body["error"]["code"], "external_auth_missing")
        self.assertFalse(body["error"]["retryable"])
        self.assertEqual(body["meta"]["pack_id"], "yantie_meeting_v1")

    def test_mock_search_marks_results_as_external_echo_and_does_not_mutate_pack(self) -> None:
        requests: list[httpx.Request] = []

        def handler(request: httpx.Request) -> httpx.Response:
            requests.append(request)
            self.assertEqual(request.headers["authorization"], "Bearer secret-test")
            self.assertEqual(request.headers["x-request-timestamp"], "1234567890")
            self.assertEqual(request.url.path, "/api/v1/content/zhihu_search")
            self.assertEqual(request.url.params["q"], "盐铁论")
            return httpx.Response(
                200,
                json={
                    "data": {
                        "items": [
                            {
                                "title": "盐铁论的当代讨论",
                                "url": "https://www.zhihu.com/question/example",
                                "summary": "这是一条当代讨论摘要，不属于历史证据。",
                            }
                        ]
                    }
                },
            )

        adapter = ZhihuExternalEchoAdapter(
            ZhihuAdapterConfig(access_secret="secret-test"),
            transport=httpx.MockTransport(handler),
            clock=lambda: 1234567890.0,
        )
        client = self._client(adapter)
        claim_count_before = len(self.pack.claims)
        evidence_count_before = len(self.pack.evidence_units)

        manifest = client.get("/api/yantie/manifest")
        self.assertEqual(manifest.status_code, 200)
        self.assertTrue(manifest.json()["data"]["features"]["external_echo_enabled"])

        response = client.get("/api/yantie/external/zhihu/search", params={"q": "盐铁论", "count": 3})
        self.assertEqual(response.status_code, 200)
        data = response.json()["data"]
        self.assertEqual(data["provider"], "zhihu")
        self.assertEqual(data["source_boundary"], "external_echo")
        self.assertFalse(data["can_support_claims"])
        self.assertFalse(data["writes_to_evidence_pack"])
        self.assertEqual(data["items"][0]["source_boundary"], "external_echo")
        self.assertEqual(data["items"][0]["provider"], "zhihu")
        self.assertEqual(data["items"][0]["title"], "盐铁论的当代讨论")
        self.assertEqual(len(requests), 1)
        self.assertEqual(len(self.pack.claims), claim_count_before)
        self.assertEqual(len(self.pack.evidence_units), evidence_count_before)

    def test_rate_limit_maps_to_retryable_external_error(self) -> None:
        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(429, json={"error": "rate limited"})

        adapter = ZhihuExternalEchoAdapter(
            ZhihuAdapterConfig(access_secret="secret-test"),
            transport=httpx.MockTransport(handler),
        )
        client = self._client(adapter)

        response = client.get("/api/yantie/external/global/search", params={"q": "国家与市场"})
        self.assertEqual(response.status_code, 429)
        body = response.json()
        self.assertEqual(body["error"]["code"], "external_rate_limited")
        self.assertTrue(body["error"]["retryable"])
        self.assertEqual(body["meta"]["schema_version"], "yantie_evidence_pack_v1")

    def _client(self, adapter: ZhihuExternalEchoAdapter) -> TestClient:
        app = FastAPI()
        app.include_router(create_yantie_api_router(pack=self.pack, external_echo_adapter=adapter))
        return TestClient(app)


if __name__ == "__main__":
    unittest.main()
