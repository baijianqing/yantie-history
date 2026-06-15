from __future__ import annotations

import unittest
from pathlib import Path

from metaos.core.schemas import Chunk, Citation
from metaos.search import FullTextSearchFilters, full_text_search


class FullTextSearchTests(unittest.TestCase):
    def test_full_text_search_returns_matching_chunk_with_citation(self) -> None:
        chunks = self.make_chunks()

        results = full_text_search("retention", chunks=chunks, top_k=3)

        self.assertEqual([result.chunk_id for result in results], ["chunk_2"])
        self.assertEqual(results[0].knowledge_item_id, "item_1")
        self.assertEqual(results[0].heading_path, ["Business", "Retention"])
        self.assertGreater(results[0].score, 0)
        self.assertEqual(results[0].citation.file_path, Path("notes.md"))
        self.assertEqual(results[0].citation.excerpt, "retention evidence")

    def test_full_text_search_applies_metadata_filters(self) -> None:
        chunks = self.make_chunks()

        blocked = full_text_search(
            "pricing",
            chunks=chunks,
            filters=FullTextSearchFilters(source_id="src_2"),
        )
        allowed = full_text_search(
            "pricing",
            chunks=chunks,
            filters={"source_id": "src_1", "asset_id": "asset_1"},
        )

        self.assertEqual(blocked, [])
        self.assertEqual([result.chunk_id for result in allowed], ["chunk_1"])

    def test_full_text_search_honors_top_k_and_file_path_filter(self) -> None:
        chunks = self.make_chunks()

        results = full_text_search(
            "evidence",
            chunks=chunks,
            filters={"file_path": "notes.md"},
            top_k=1,
        )

        self.assertEqual(len(results), 1)
        self.assertIn(results[0].chunk_id, {"chunk_1", "chunk_2"})

    def test_full_text_search_returns_empty_for_blank_query_or_no_chunks(self) -> None:
        self.assertEqual(full_text_search("   ", chunks=self.make_chunks()), [])
        self.assertEqual(full_text_search("pricing", chunks=[]), [])

    def make_chunks(self) -> list[Chunk]:
        return [
            Chunk(
                id="chunk_1",
                knowledge_item_id="item_1",
                text="Pricing evidence shows a subscription model.",
                heading_path=["Business", "Pricing"],
                ordinal=1,
                citation=Citation(
                    source_id="src_1",
                    asset_id="asset_1",
                    file_path=Path("notes.md"),
                    excerpt="pricing evidence",
                ),
            ),
            Chunk(
                id="chunk_2",
                knowledge_item_id="item_1",
                text="Retention evidence highlights onboarding and activation.",
                heading_path=["Business", "Retention"],
                ordinal=2,
                citation=Citation(
                    source_id="src_1",
                    asset_id="asset_1",
                    file_path=Path("notes.md"),
                    excerpt="retention evidence",
                ),
            ),
            Chunk(
                id="chunk_3",
                knowledge_item_id="item_2",
                text="Vector search handles semantic recall.",
                heading_path=["Technology"],
                ordinal=1,
                citation=Citation(
                    source_id="src_2",
                    asset_id="asset_2",
                    file_path=Path("tech.md"),
                    excerpt="semantic recall",
                ),
            ),
        ]


if __name__ == "__main__":
    unittest.main()
