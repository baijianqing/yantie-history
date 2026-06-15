from __future__ import annotations

import unittest
from pathlib import Path

from metaos.core.schemas import Citation
from metaos.search import (
    FullTextSearchResult,
    SearchCandidate,
    rrf_fuse,
)


class RrfSearchTests(unittest.TestCase):
    def test_rrf_fuse_combines_channels_with_stable_ranking(self) -> None:
        citation = Citation(source_id="src_1", asset_id="asset_1", file_path=Path("notes.md"))
        vector = [
            self.candidate("chunk_a", "Vector first", citation=citation),
            self.candidate("chunk_b", "Appears in both", citation=citation),
        ]
        full_text = [
            FullTextSearchResult(
                chunk_id="chunk_b",
                knowledge_item_id="item_1",
                text="Appears in both",
                heading_path=["B"],
                ordinal=2,
                score=0.9,
                citation=citation,
            ),
            FullTextSearchResult(
                chunk_id="chunk_c",
                knowledge_item_id="item_1",
                text="Text only",
                heading_path=["C"],
                ordinal=3,
                score=0.8,
                citation=citation,
            ),
        ]

        results = rrf_fuse({"vector": vector, "full_text": full_text}, top_k=3)

        self.assertEqual([result.chunk_id for result in results], ["chunk_b", "chunk_a", "chunk_c"])
        self.assertEqual(results[0].channel_ranks, {"vector": 2, "full_text": 1})
        self.assertGreater(results[0].fused_score, results[1].fused_score)

    def test_rrf_fuse_applies_metadata_filters(self) -> None:
        source_1 = Citation(source_id="src_1", asset_id="asset_1", file_path=Path("one.md"))
        source_2 = Citation(source_id="src_2", asset_id="asset_2", file_path=Path("two.md"))

        results = rrf_fuse(
            {
                "vector": [
                    self.candidate("chunk_a", "A", citation=source_1),
                    self.candidate("chunk_b", "B", citation=source_2),
                ],
                "full_text": [
                    self.candidate("chunk_c", "C", citation=source_2),
                ],
            },
            filters={"source_id": "src_2"},
            top_k=5,
        )

        self.assertEqual([result.chunk_id for result in results], ["chunk_b", "chunk_c"])
        self.assertTrue(all(result.citation.source_id == "src_2" for result in results))

    def test_rrf_fuse_preserves_citation_when_duplicate_first_lacks_it(self) -> None:
        citation = Citation(source_id="src_1", asset_id="asset_1", file_path=Path("notes.md"))

        results = rrf_fuse(
            {
                "vector": [
                    self.candidate("chunk_a", "Shared", citation=None),
                ],
                "full_text": [
                    self.candidate("chunk_a", "Shared", citation=citation),
                ],
            }
        )

        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].citation.source_id, "src_1")
        self.assertEqual(set(results[0].channel_scores), {"vector", "full_text"})

    def test_rrf_fuse_returns_empty_for_zero_top_k(self) -> None:
        results = rrf_fuse({"vector": [self.candidate("chunk_a", "A")]}, top_k=0)

        self.assertEqual(results, [])

    def candidate(
        self,
        chunk_id: str,
        text: str,
        *,
        citation: Citation | None = None,
    ) -> SearchCandidate:
        return SearchCandidate(
            chunk_id=chunk_id,
            knowledge_item_id="item_1",
            text=text,
            heading_path=[chunk_id],
            score=0.5,
            citation=citation,
        )


if __name__ == "__main__":
    unittest.main()
