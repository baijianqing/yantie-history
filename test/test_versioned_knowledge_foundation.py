from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from metaos.core.schemas import Asset, AssetKind, Source, SourceType
from metaos.documents.service import ParsedDocument
from metaos.knowledge import (
    build_index_generation_manifest,
    build_versioned_knowledge_foundation,
)


class VersionedKnowledgeFoundationTests(unittest.TestCase):
    def test_repeated_build_has_stable_chunk_set_and_generation_ids(self) -> None:
        source, asset, document = self.fixture_document()

        first = build_versioned_knowledge_foundation(
            source=source,
            asset=asset,
            document=document,
            index_types=("fts", "vector"),
            embedding_model="bge-m3",
            embedding_dimension=1024,
        )
        second = build_versioned_knowledge_foundation(
            source=source,
            asset=asset,
            document=document,
            index_types=("fts", "vector"),
            embedding_model="bge-m3",
            embedding_dimension=1024,
        )

        self.assertEqual(first.document.document_version.id, second.document.document_version.id)
        self.assertEqual(first.chunk_set.id, second.chunk_set.id)
        self.assertEqual(first.chunk_set.active_chunk_ids, second.chunk_set.active_chunk_ids)
        self.assertEqual(
            [generation.id for generation in first.index_generations],
            [generation.id for generation in second.index_generations],
        )
        self.assertEqual(set(first.current_index_generation_ids), {"fts", "vector"})

    def test_different_chunk_strategy_creates_parallel_chunk_set(self) -> None:
        source, asset, document = self.fixture_document()

        v1 = build_versioned_knowledge_foundation(
            source=source,
            asset=asset,
            document=document,
            chunker_version="v1",
        )
        v2 = build_versioned_knowledge_foundation(
            source=source,
            asset=asset,
            document=document,
            chunker_version="v2",
        )

        self.assertNotEqual(v1.document.document_version.id, v2.document.document_version.id)
        self.assertNotEqual(v1.chunk_set.id, v2.chunk_set.id)
        self.assertEqual(v1.document.document_version.stable_id, v2.document.document_version.stable_id)
        self.assertEqual(v1.chunk_set.chunk_strategy_version, "v1")
        self.assertEqual(v2.chunk_set.chunk_strategy_version, "v2")
        self.assertTrue(v1.chunk_set.active_chunk_ids)
        self.assertTrue(v2.chunk_set.active_chunk_ids)

    def test_index_rebuild_creates_new_generation_without_mutating_chunk_set(self) -> None:
        source, asset, document = self.fixture_document()
        foundation = build_versioned_knowledge_foundation(
            source=source,
            asset=asset,
            document=document,
            index_strategy_version="index_v1",
            index_types=("vector",),
            embedding_model="bge-m3",
            embedding_dimension=1024,
        )

        rebuilt = build_index_generation_manifest(
            foundation.document,
            foundation.chunk_set,
            index_type="vector",
            index_strategy_version="index_v2",
            embedding_model="bge-m3",
            embedding_dimension=1024,
        )

        self.assertNotEqual(foundation.index_generations[0].id, rebuilt.id)
        self.assertEqual(foundation.index_generations[0].chunk_set_manifest_id, rebuilt.chunk_set_manifest_id)
        self.assertEqual(rebuilt.expected_item_count, foundation.chunk_set.active_chunk_count)
        self.assertEqual(rebuilt.actual_item_count, foundation.chunk_set.active_chunk_count)

    def test_content_change_creates_new_version_and_chunk_set(self) -> None:
        source, asset, document = self.fixture_document()
        changed = ParsedDocument(
            title=document.title,
            source_path=document.source_path,
            extension=document.extension,
            text=document.text.replace("Stable paragraph.", "Changed paragraph."),
        )

        original = build_versioned_knowledge_foundation(
            source=source,
            asset=asset,
            document=document,
        )
        revised = build_versioned_knowledge_foundation(
            source=source,
            asset=asset,
            document=changed,
        )

        self.assertNotEqual(original.document.document_version.id, revised.document.document_version.id)
        self.assertEqual(
            original.document.document_version.stable_id,
            revised.document.document_version.stable_id,
        )
        self.assertNotEqual(original.chunk_set.id, revised.chunk_set.id)
        self.assertNotEqual(
            original.chunk_set.active_chunk_set_hash,
            revised.chunk_set.active_chunk_set_hash,
        )

    def fixture_document(self) -> tuple[Source, Asset, ParsedDocument]:
        temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(temp_dir.cleanup)
        path = Path(temp_dir.name) / "book.md"
        path.write_text("# Book\n\n## A\n\nStable paragraph.\n\n## B\n\nAnother paragraph.\n", encoding="utf-8")
        source = Source(id="src_a", type=SourceType.local_file, uri="file:///book.md")
        asset = Asset(
            id="asset_a",
            source_id=source.id,
            kind=AssetKind.markdown,
            path=path,
        )
        document = ParsedDocument(
            title="Book",
            source_path=path,
            extension=".md",
            text=path.read_text(encoding="utf-8"),
        )
        return source, asset, document


if __name__ == "__main__":
    unittest.main()
