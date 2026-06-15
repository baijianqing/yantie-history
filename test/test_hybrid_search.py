from __future__ import annotations

import unittest
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from metaos.core.schemas import Chunk, Citation
from metaos.search import hybrid_search


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


class HybridSearchTests(unittest.TestCase):
    def test_hybrid_search_fuses_full_text_and_vector_results_with_citations(self) -> None:
        retrieval = FakeVectorRetrieval(
            [
                self.vector_result("chunk_support", "src_alpha", 0.93, 0.07),
                self.vector_result("chunk_vector_only", "src_alpha", 0.88, 0.12),
            ]
        )

        fused = hybrid_search(
            "Alpha closure evidence",
            chunks=[
                self.chunk("chunk_support", "Alpha closure evidence supports action.", "src_alpha"),
                self.chunk("chunk_other", "Unrelated evidence should be filtered.", "src_other"),
            ],
            vector_retrieval=retrieval,
            filters={"source_id": "src_alpha"},
            top_k=5,
        )

        by_id = {candidate.chunk_id: candidate for candidate in fused}
        self.assertEqual(retrieval.calls, [{"query": "Alpha closure evidence", "top_k": 5}])
        self.assertIn("chunk_support", by_id)
        self.assertIn("chunk_vector_only", by_id)
        self.assertNotIn("chunk_other", by_id)
        self.assertEqual(by_id["chunk_support"].channel_ranks, {"full_text": 1, "vector": 1})
        self.assertEqual(by_id["chunk_support"].citation.source_id, "src_alpha")
        self.assertEqual(by_id["chunk_support"].citation.file_path, Path("src_alpha/chunk_support.md"))
        self.assertEqual(by_id["chunk_vector_only"].channel_ranks, {"vector": 2})

    def test_hybrid_search_can_run_full_text_only(self) -> None:
        fused = hybrid_search(
            "Alpha",
            chunks=[self.chunk("chunk_1", "Alpha evidence", "src_alpha")],
            top_k=3,
        )

        self.assertEqual(len(fused), 1)
        self.assertEqual(fused[0].channel_ranks, {"full_text": 1})
        self.assertEqual(fused[0].citation.source_id, "src_alpha")

    def test_hybrid_search_skips_empty_queries_without_calling_vector(self) -> None:
        retrieval = FakeVectorRetrieval([self.vector_result("chunk_1", "src_alpha", 0.9, 0.1)])

        fused = hybrid_search(
            " ",
            chunks=[self.chunk("chunk_1", "Alpha evidence", "src_alpha")],
            vector_retrieval=retrieval,
        )

        self.assertEqual(fused, [])
        self.assertEqual(retrieval.calls, [])

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
