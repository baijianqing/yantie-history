from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from metaos.core.schemas import Asset, AssetKind, Source, SourceType
from metaos.documents.service import ParsedDocument
from metaos.knowledge import standardize_document


class DocumentVersioningTests(unittest.TestCase):
    def test_standardize_document_generates_stable_ids_for_repeated_ingest(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "book.md"
            source = Source(id="src_a", type=SourceType.local_file, uri="file:///book.md")
            asset = Asset(id="asset_a", source_id=source.id, kind=AssetKind.markdown, path=path)
            document = self.document(
                """
                # Book

                ## A

                Stable paragraph.

                ## B

                Another paragraph.
                """
            )

            first = standardize_document(source=source, asset=asset, document=document)
            second = standardize_document(source=source, asset=asset, document=document)

            self.assertEqual(first.document_version.id, second.document_version.id)
            self.assertEqual(first.document_version.stable_id, second.document_version.stable_id)
            self.assertEqual(
                [chunk.id for chunk in first.chunks],
                [chunk.id for chunk in second.chunks],
            )

    def test_local_content_change_only_changes_related_chunk_id(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "book.md"
            source = Source(id="src_a", type=SourceType.local_file, uri="file:///book.md")
            asset = Asset(id="asset_a", source_id=source.id, kind=AssetKind.markdown, path=path)
            original = standardize_document(
                source=source,
                asset=asset,
                document=self.document(
                    """
                    # Book

                    ## A

                    Stable paragraph.

                    ## B

                    Original paragraph.
                    """
                ),
            )
            changed = standardize_document(
                source=source,
                asset=asset,
                document=self.document(
                    """
                    # Book

                    ## A

                    Stable paragraph.

                    ## B

                    Changed paragraph.
                    """
                ),
            )

            original_a = self.chunk_for_heading(original.chunks, "A")
            changed_a = self.chunk_for_heading(changed.chunks, "A")
            original_b = self.chunk_for_heading(original.chunks, "B")
            changed_b = self.chunk_for_heading(changed.chunks, "B")

            self.assertNotEqual(original.document_version.id, changed.document_version.id)
            self.assertEqual(
                original.document_version.stable_id,
                changed.document_version.stable_id,
            )
            self.assertEqual(
                original.document_version.structure_sha256,
                changed.document_version.structure_sha256,
            )
            self.assertEqual(original_a.id, changed_a.id)
            self.assertNotEqual(original_b.id, changed_b.id)

    def test_stable_chunks_include_links_and_original_citations(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "book.md"
            source = Source(id="src_a", type=SourceType.local_file, uri="file:///book.md")
            asset = Asset(id="asset_a", source_id=source.id, kind=AssetKind.markdown, path=path)

            standardized = standardize_document(
                source=source,
                asset=asset,
                document=self.document(
                    """
                    # Book

                    ## A

                    Stable paragraph.

                    ## B

                    Another paragraph.
                    """
                ),
            )

            self.assertEqual(len(standardized.chunks), 2)
            first, second = standardized.chunks
            self.assertIsNone(first.previous_chunk_id)
            self.assertEqual(first.next_chunk_id, second.id)
            self.assertEqual(second.previous_chunk_id, first.id)
            self.assertIsNone(second.next_chunk_id)
            self.assertTrue(first.parent_chunk_id)
            self.assertEqual(first.citation.file_path, path)
            self.assertEqual(first.citation.source_id, source.id)
            self.assertEqual(first.citation.asset_id, asset.id)

    def document(self, text: str) -> ParsedDocument:
        normalized = "\n".join(line.strip() for line in text.strip().splitlines())
        return ParsedDocument(
            title="Book",
            text=normalized,
            source_path=Path("book.md"),
            extension=".md",
        )

    def chunk_for_heading(self, chunks, heading: str):
        for chunk in chunks:
            if heading in chunk.heading_path:
                return chunk
        raise AssertionError(f"chunk not found for heading: {heading}")


if __name__ == "__main__":
    unittest.main()
