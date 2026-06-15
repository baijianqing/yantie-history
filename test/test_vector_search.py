from __future__ import annotations

import unittest
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from metaos.search import rrf_fuse, vector_search


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


class FakeVectorRetrieval:
    def __init__(self, results: list[FakeVectorResult]) -> None:
        self.results = results
        self.calls: list[dict[str, Any]] = []

    def search(self, query: str, top_k: int = 5) -> list[FakeVectorResult]:
        self.calls.append({"query": query, "top_k": top_k})
        return self.results


class VectorSearchAdapterTests(unittest.TestCase):
    def test_vector_search_adapts_retrieval_results_with_citations_and_filters(self) -> None:
        retrieval = FakeVectorRetrieval(
            [
                self.result("chunk_1", "src_alpha", 0.92, 0.08),
                self.result("chunk_2", "src_other", 0.91, 0.09),
                self.result("chunk_3", "src_alpha", 0.85, 0.15),
            ]
        )

        candidates = vector_search(
            "  Alpha closure  ",
            retrieval=retrieval,
            filters={"source_id": "src_alpha"},
            top_k=2,
        )

        self.assertEqual(retrieval.calls, [{"query": "Alpha closure", "top_k": 2}])
        self.assertEqual([candidate.chunk_id for candidate in candidates], ["chunk_1", "chunk_3"])
        self.assertEqual(candidates[0].citation.source_id, "src_alpha")
        self.assertEqual(candidates[0].citation.asset_id, "asset_chunk_1")
        self.assertEqual(candidates[0].citation.file_path, Path("evidence/chunk_1.md"))
        self.assertEqual(candidates[0].citation.excerpt, "Evidence for chunk_1")
        self.assertEqual(candidates[0].metadata["channel"], "vector")
        self.assertEqual(candidates[0].metadata["distance"], 0.08)

    def test_vector_search_candidates_can_feed_rrf_fusion(self) -> None:
        candidates = vector_search(
            "Alpha",
            retrieval=FakeVectorRetrieval([self.result("chunk_1", "src_alpha", 0.92, 0.08)]),
        )

        fused = rrf_fuse({"vector": candidates}, top_k=5)

        self.assertEqual(len(fused), 1)
        self.assertEqual(fused[0].chunk_id, "chunk_1")
        self.assertEqual(fused[0].channel_ranks, {"vector": 1})
        self.assertEqual(fused[0].citation.source_id, "src_alpha")

    def test_vector_search_skips_empty_queries(self) -> None:
        retrieval = FakeVectorRetrieval([self.result("chunk_1", "src_alpha", 0.92, 0.08)])

        self.assertEqual(vector_search("  ", retrieval=retrieval), [])
        self.assertEqual(retrieval.calls, [])

    def result(
        self,
        chunk_id: str,
        source_id: str,
        score: float,
        distance: float,
    ) -> FakeVectorResult:
        return FakeVectorResult(
            chunk_id=chunk_id,
            knowledge_item_id="ki_alpha",
            text=f"Evidence for {chunk_id}",
            heading_path=["Alpha"],
            ordinal=1,
            score=score,
            distance=distance,
            source_id=source_id,
            asset_id=f"asset_{chunk_id}",
            file_path=f"evidence/{chunk_id}.md",
        )


if __name__ == "__main__":
    unittest.main()
