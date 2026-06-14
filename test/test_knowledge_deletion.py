from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from metaos.core.errors import KnowledgeItemNotFoundError
from metaos.core.schemas import Chunk, Citation, KnowledgeCategory, KnowledgeItem
from metaos.knowledge.deletion import KnowledgeDeletionService
from metaos.workspace.catalog import ChunkRepository, KnowledgeRepository
from metaos.workspace.database import initialize_database
from metaos.workspace.paths import WorkspacePaths


class FakeRetrievalService:
    def __init__(self, deleted_count: int = 2):
        self.deleted_count = deleted_count
        self.deleted_item_ids: list[str] = []

    def delete_knowledge_item(self, item_id: str) -> int:
        self.deleted_item_ids.append(item_id)
        return self.deleted_count


class KnowledgeDeletionTests(unittest.TestCase):
    def test_delete_removes_item_chunks_and_index(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            database_path = root / "metaos.sqlite3"
            initialize_database(database_path)
            paths = WorkspacePaths(
                root=root,
                library=root,
                raw=root / "raw",
                audio=root / "audio",
                transcripts=root / "transcripts",
                markdown=root / "markdown",
                index=root / "index",
                exports=root / "exports",
                database=database_path,
            )
            knowledge_repo = KnowledgeRepository(database_path)
            chunk_repo = ChunkRepository(database_path)
            item = KnowledgeItem(
                id="ki_delete_me",
                title="待删除条目",
                summary="summary",
                category=KnowledgeCategory.philosophy,
            )
            knowledge_repo.add(item)
            chunk_repo.add_many(
                [
                    Chunk(
                        id="chunk_1",
                        knowledge_item_id=item.id,
                        text="first chunk",
                        ordinal=0,
                        citation=Citation(file_path=root / "source.md"),
                    ),
                    Chunk(
                        id="chunk_2",
                        knowledge_item_id=item.id,
                        text="second chunk",
                        ordinal=1,
                    ),
                ]
            )
            retrieval = FakeRetrievalService(deleted_count=2)
            service = KnowledgeDeletionService(
                paths,
                knowledge_repository=knowledge_repo,
                chunk_repository=chunk_repo,
                retrieval_service=retrieval,  # type: ignore[arg-type]
            )

            result = service.delete(item.id)

            self.assertEqual(result.item_id, item.id)
            self.assertEqual(result.title, item.title)
            self.assertEqual(result.deleted_chunks, 2)
            self.assertEqual(result.deleted_index_entries, 2)
            self.assertEqual(retrieval.deleted_item_ids, [item.id])
            self.assertEqual(chunk_repo.count_by_knowledge_item(item.id), 0)
            with self.assertRaises(KnowledgeItemNotFoundError):
                knowledge_repo.get(item.id)


if __name__ == "__main__":
    unittest.main()
