from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from metaos.knowledge.catalog import KnowledgeCatalogAdapter
from metaos.knowledge.core_alpha_ingest import ingest_uploaded_text_document
from metaos.workspace.paths import ensure_workspace


class CoreAlphaIngestTests(unittest.TestCase):
    def test_ingests_text_as_versioned_catalog_entry_without_vector_index(self) -> None:
        with tempfile.TemporaryDirectory() as raw_temp_dir:
            paths = ensure_workspace(Path(raw_temp_dir) / "library")

            result = ingest_uploaded_text_document(
                filename="guiguzi.md",
                content=(
                    "# 鬼谷子\n\n"
                    "捭阖者，道之大化，说之变也。\n\n"
                    "这是用于 Core Alpha 调试的固定文本。"
                ).encode("utf-8"),
                paths=paths,
            )

            adapter = KnowledgeCatalogAdapter(paths.database)
            item = adapter.get_item(result.knowledge_item_id)
            version = adapter.get_current_version(result.knowledge_item_id)
            chunks = adapter.list_chunks(result.knowledge_item_version_id)
            generations = adapter.list_index_generations(result.knowledge_item_version_id)

            self.assertEqual(item.current_knowledge_item_version_id, result.knowledge_item_version_id)
            self.assertEqual(version.knowledge_item_version_id, result.knowledge_item_version_id)
            self.assertEqual(len(chunks), result.active_chunk_count)
            self.assertGreater(result.active_chunk_count, 0)
            self.assertEqual(
                [generation.index_generation_id for generation in generations],
                list(result.index_generation_ids.values()),
            )
            self.assertEqual(generations[0].status, "ready")
            self.assertFalse((paths.index / "chroma").exists())

    def test_rejects_pdf_uploads_for_now(self) -> None:
        with tempfile.TemporaryDirectory() as raw_temp_dir:
            paths = ensure_workspace(Path(raw_temp_dir) / "library")

            with self.assertRaises(ValueError):
                ingest_uploaded_text_document(
                    filename="book.pdf",
                    content=b"%PDF-1.4",
                    paths=paths,
                )


if __name__ == "__main__":
    unittest.main()
