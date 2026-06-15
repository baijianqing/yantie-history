from __future__ import annotations

import unittest
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from fastapi.testclient import TestClient

import metaos.app.api as api
from metaos.core.schemas import Chunk, Citation


@dataclass(frozen=True)
class FakeVectorResult:
    chunk_id: str
    knowledge_item_id: str
    text: str
    heading_path: list[str]
    ordinal: int
    score: float
    distance: float
    source_id: str
    asset_id: str
    file_path: str


class FakeChunkRepository:
    def __init__(self, chunks: list[Chunk]) -> None:
        self.chunks = chunks
        self.calls: list[int] = []

    def list_all(self, limit: int = 10000) -> list[Chunk]:
        self.calls.append(limit)
        return self.chunks


class FakeRetrievalService:
    def __init__(self, results: list[FakeVectorResult]) -> None:
        self.results = results
        self.calls: list[dict] = []

    def search(self, query: str, top_k: int = 5) -> list[FakeVectorResult]:
        self.calls.append({"query": query, "top_k": top_k})
        return self.results


class AlphaSearchApiTests(unittest.TestCase):
    def setUp(self) -> None:
        self.chunk_repository = FakeChunkRepository(
            [
                self.chunk("chunk_support", "Alpha closure evidence supports action.", "src_alpha"),
                self.chunk("chunk_other", "Alpha closure evidence from another source.", "src_other"),
            ]
        )
        self.retrieval = FakeRetrievalService(
            [
                self.vector_result("chunk_support", "src_alpha", 0.93, 0.07),
                self.vector_result("chunk_vector_only", "src_alpha", 0.88, 0.12),
            ]
        )
        self.original_chunk_repo: Callable = api.chunk_repo
        self.original_retrieval_service: Callable = api.retrieval_service
        api.chunk_repo = lambda: self.chunk_repository
        api.retrieval_service = lambda: self.retrieval
        self.client = TestClient(api.app)

    def tearDown(self) -> None:
        api.chunk_repo = self.original_chunk_repo
        api.retrieval_service = self.original_retrieval_service

    def test_alpha_search_returns_fused_evidence_candidates(self) -> None:
        response = self.client.post(
            "/alpha/search",
            json={
                "query": "Alpha closure evidence",
                "top_k": 5,
                "filters": {"source_id": "src_alpha"},
            },
        )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        by_id = {item["chunk_id"]: item for item in payload}
        self.assertEqual(self.chunk_repository.calls, [10000])
        self.assertEqual(self.retrieval.calls, [{"query": "Alpha closure evidence", "top_k": 5}])
        self.assertIn("chunk_support", by_id)
        self.assertIn("chunk_vector_only", by_id)
        self.assertNotIn("chunk_other", by_id)
        self.assertEqual(by_id["chunk_support"]["channel_ranks"], {"full_text": 1, "vector": 1})
        self.assertEqual(by_id["chunk_support"]["citation"]["source_id"], "src_alpha")
        self.assertEqual(
            by_id["chunk_support"]["citation"]["file_path"].replace("\\", "/"),
            "src_alpha/chunk_support.md",
        )

    def test_alpha_search_can_disable_vector_channel(self) -> None:
        api.retrieval_service = self.fail_if_called

        response = self.client.post(
            "/alpha/search",
            json={
                "query": "Alpha",
                "top_k": 3,
                "include_vector": False,
                "filters": {"source_id": "src_alpha"},
            },
        )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(len(payload), 1)
        self.assertEqual(payload[0]["chunk_id"], "chunk_support")
        self.assertEqual(payload[0]["channel_ranks"], {"full_text": 1})

    def test_alpha_search_rejects_empty_query(self) -> None:
        response = self.client.post("/alpha/search", json={"query": "   "})

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["detail"], "Search query cannot be empty.")
        self.assertEqual(self.chunk_repository.calls, [])
        self.assertEqual(self.retrieval.calls, [])

    def fail_if_called(self):
        raise AssertionError("retrieval_service should not be called")

    def chunk(self, chunk_id: str, text: str, source_id: str) -> Chunk:
        return Chunk(
            id=chunk_id,
            knowledge_item_id="ki_alpha",
            text=text,
            heading_path=["Alpha"],
            ordinal=1,
            citation=Citation(
                source_id=source_id,
                asset_id=f"asset_{source_id}",
                file_path=Path(f"{source_id}/{chunk_id}.md"),
                excerpt=text,
            ),
        )

    def vector_result(
        self,
        chunk_id: str,
        source_id: str,
        score: float,
        distance: float,
    ) -> FakeVectorResult:
        return FakeVectorResult(
            chunk_id=chunk_id,
            knowledge_item_id="ki_alpha",
            text=f"Vector evidence for {chunk_id}",
            heading_path=["Alpha"],
            ordinal=1,
            score=score,
            distance=distance,
            source_id=source_id,
            asset_id=f"asset_{source_id}",
            file_path=f"{source_id}/{chunk_id}.md",
        )


if __name__ == "__main__":
    unittest.main()
