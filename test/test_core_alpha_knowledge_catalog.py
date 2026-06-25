from __future__ import annotations

import hashlib
import tempfile
import unittest
from pathlib import Path

from metaos.core.schemas import (
    Asset,
    AssetKind,
    Chunk,
    Citation,
    KnowledgeCategory,
    KnowledgeItem,
    Source,
    SourceType,
)
from metaos.knowledge.catalog import (
    KnowledgeCatalogAdapter,
    KnowledgeCatalogIntegrityError,
    KnowledgeCatalogNotFoundError,
)
from metaos.workspace.catalog import (
    AssetRepository,
    ChunkRepository,
    KnowledgeRepository,
    SourceRepository,
)


def _sha256(payload: str) -> str:
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


class KnowledgeCatalogAdapterTests(unittest.TestCase):
    def _build_catalog(self, temp_dir: Path, *, content: str = "# Case\n\nEvidence.") -> tuple[Path, str, str]:
        database_path = temp_dir / "workspace.sqlite3"
        asset_path = temp_dir / "case.md"
        asset_path.write_text(content, encoding="utf-8")
        asset_sha = _sha256_file(asset_path)

        source = Source(
            id="src_case",
            type=SourceType.local_file,
            uri=asset_path.as_uri(),
            title="Case Source",
        )
        asset = Asset(
            id="asset_case",
            source_id=source.id,
            kind=AssetKind.markdown,
            path=asset_path,
            mime_type="text/markdown",
            sha256=asset_sha,
            size_bytes=len(content.encode("utf-8")),
        )
        item = KnowledgeItem(
            id="ki_case",
            title="Case",
            summary="A controlled knowledge item.",
            category=KnowledgeCategory.philosophy,
            tags=["Case Alias"],
            markdown_path=asset_path,
            citations=[
                Citation(
                    source_id=source.id,
                    asset_id=asset.id,
                    file_path=asset_path,
                    excerpt="Evidence.",
                )
            ],
            metadata={
                "source_id": source.id,
                "asset_id": asset.id,
                "language": "zh-Hans",
                "parser": "markdown-v1",
                "chunker": "test-chunker-v1",
                "index_version": "test-index-v1",
            },
        )
        chunks = [
            Chunk(
                id="chunk_case_1",
                knowledge_item_id=item.id,
                text="First evidence paragraph.",
                heading_path=["Case", "Part One"],
                ordinal=1,
                citation=Citation(source_id=source.id, asset_id=asset.id, file_path=asset_path, page=1),
            ),
            Chunk(
                id="chunk_case_2",
                knowledge_item_id=item.id,
                text="Second evidence paragraph.",
                heading_path=["Case", "Part Two"],
                ordinal=2,
                citation=Citation(source_id=source.id, asset_id=asset.id, file_path=asset_path, page=2),
            ),
        ]

        SourceRepository(database_path).add(source)
        AssetRepository(database_path).add(asset)
        KnowledgeRepository(database_path).add(item)
        ChunkRepository(database_path).add_many(chunks)
        return database_path, item.id, asset.id

    def test_projects_items_versions_chunks_and_index_metadata(self) -> None:
        with tempfile.TemporaryDirectory() as raw_temp_dir:
            database_path, item_id, _asset_id = self._build_catalog(Path(raw_temp_dir))
            adapter = KnowledgeCatalogAdapter(database_path)

            items = adapter.list_items()
            self.assertEqual([item.knowledge_item_id for item in items], [item_id])
            self.assertEqual(items[0].aliases, ["Case Alias"])
            self.assertEqual(items[0].language, "zh-Hans")

            version = adapter.get_current_version(item_id)
            self.assertEqual(version.knowledge_item_id, item_id)
            self.assertTrue(version.knowledge_item_version_id.startswith("kiv_"))
            self.assertEqual(version.availability_status, "available")
            self.assertEqual(version.chunker_version, "test-chunker-v1")
            self.assertEqual(version.index_strategy_version, "test-index-v1")
            self.assertEqual(adapter.list_versions(item_id), [version])
            self.assertEqual(adapter.get_version(version.knowledge_item_version_id), version)

            chunks = adapter.list_chunks(version.knowledge_item_version_id)
            self.assertEqual([chunk.chunk_id for chunk in chunks], ["chunk_case_1", "chunk_case_2"])
            self.assertEqual(chunks[0].knowledge_item_version_id, version.knowledge_item_version_id)
            self.assertIsNone(chunks[0].previous_chunk_id)
            self.assertEqual(chunks[0].next_chunk_id, "chunk_case_2")
            self.assertEqual(chunks[1].previous_chunk_id, "chunk_case_1")
            self.assertEqual(chunks[0].section_path, ["Case", "Part One"])
            self.assertGreater(chunks[0].token_count, 0)
            self.assertEqual(adapter.get_chunk("chunk_case_1"), chunks[0])

            generations = adapter.list_index_generations(version.knowledge_item_version_id)
            self.assertEqual(len(generations), 1)
            self.assertEqual(generations[0].knowledge_item_version_id, version.knowledge_item_version_id)
            self.assertEqual(generations[0].status, "ready")
            self.assertEqual(generations[0].expected_item_count, 2)
            self.assertEqual(generations[0].actual_item_count, 2)

    def test_version_identity_is_stable_and_adapter_does_not_modify_content(self) -> None:
        with tempfile.TemporaryDirectory() as raw_temp_dir:
            temp_dir = Path(raw_temp_dir)
            database_path, item_id, _asset_id = self._build_catalog(temp_dir)
            asset_path = temp_dir / "case.md"
            original_content = asset_path.read_text(encoding="utf-8")
            adapter = KnowledgeCatalogAdapter(database_path)

            first = adapter.get_current_version(item_id)
            second = adapter.get_current_version(item_id)

            self.assertEqual(first.knowledge_item_version_id, second.knowledge_item_version_id)
            self.assertEqual(asset_path.read_text(encoding="utf-8"), original_content)
            self.assertEqual(len(adapter.list_chunks(first.knowledge_item_version_id)), 2)

    def test_silent_asset_replacement_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as raw_temp_dir:
            temp_dir = Path(raw_temp_dir)
            database_path, item_id, _asset_id = self._build_catalog(temp_dir)
            (temp_dir / "case.md").write_text("# Case\n\nChanged evidence.", encoding="utf-8")

            with self.assertRaises(KnowledgeCatalogIntegrityError):
                KnowledgeCatalogAdapter(database_path).get_current_version(item_id)

    def test_missing_asset_file_projects_unavailable_version(self) -> None:
        with tempfile.TemporaryDirectory() as raw_temp_dir:
            temp_dir = Path(raw_temp_dir)
            database_path, item_id, _asset_id = self._build_catalog(temp_dir)
            (temp_dir / "case.md").unlink()

            version = KnowledgeCatalogAdapter(database_path).get_current_version(item_id)

            self.assertEqual(version.availability_status, "unavailable")
            self.assertTrue(version.content_hash.startswith("sha256:"))

    def test_unknown_id_raises_catalog_not_found(self) -> None:
        with tempfile.TemporaryDirectory() as raw_temp_dir:
            database_path, _item_id, _asset_id = self._build_catalog(Path(raw_temp_dir))
            adapter = KnowledgeCatalogAdapter(database_path)

            with self.assertRaises(KnowledgeCatalogNotFoundError):
                adapter.get_item("ki_missing")
            with self.assertRaises(KnowledgeCatalogNotFoundError):
                adapter.get_version("kiv_missing")
            with self.assertRaises(KnowledgeCatalogNotFoundError):
                adapter.get_chunk("chunk_missing")


if __name__ == "__main__":
    unittest.main()
