from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from typing import Any

from metaos.core.schemas import Chunk, KnowledgeCategory, KnowledgeItem
from metaos.retrieval.service import RetrievalService
from metaos.workspace.catalog import ChunkRepository, KnowledgeRepository
from metaos.workspace.database import initialize_database
from metaos.workspace.paths import WorkspacePaths


class FakeEmbeddingProvider:
    name = "fake"
    model = "fake-model"
    batch_size = 2
    timeout = 1
    num_gpu = None

    def __init__(self) -> None:
        self.embed_calls: list[list[str]] = []

    @property
    def dimensions(self) -> int:
        return 3

    def embed(self, texts: list[str]) -> list[list[float]]:
        self.embed_calls.append(list(texts))
        return [[1.0, 0.0, 0.0] for _ in texts]


class FakeCollection:
    def __init__(self, entries: dict[str, dict[str, Any]] | None = None) -> None:
        self.entries = entries or {}
        self.metadata: dict[str, Any] = {
            "embedding_provider": "fake",
            "embedding_model": "fake-model",
            "embedding_dimensions": 3,
        }
        self.deleted_ids: list[str] = []
        self.deleted_wheres: list[dict[str, Any]] = []
        self.upserted_ids: list[str] = []

    def count(self) -> int:
        return len(self.entries)

    def get(self, include: list[str] | None = None, **kwargs: Any) -> dict[str, list[str]]:
        ids = list(self.entries)
        where = kwargs.get("where")
        if where:
            ids = [
                chunk_id
                for chunk_id in ids
                if all(self.entries[chunk_id].get("metadata", {}).get(key) == value for key, value in where.items())
            ]
        offset = int(kwargs.get("offset") or 0)
        limit = kwargs.get("limit")
        if limit is not None:
            ids = ids[offset : offset + int(limit)]
        return {"ids": ids}

    def upsert(
        self,
        *,
        ids: list[str],
        documents: list[str],
        embeddings: list[list[float]],
        metadatas: list[dict[str, Any]],
    ) -> None:
        self.upserted_ids.extend(ids)
        for index, chunk_id in enumerate(ids):
            self.entries[chunk_id] = {
                "document": documents[index],
                "embedding": embeddings[index],
                "metadata": metadatas[index],
            }

    def delete(
        self,
        *,
        ids: list[str] | None = None,
        where: dict[str, Any] | None = None,
    ) -> None:
        if ids:
            self.deleted_ids.extend(ids)
            for chunk_id in ids:
                self.entries.pop(chunk_id, None)
            return
        if where:
            self.deleted_wheres.append(dict(where))
            for chunk_id in list(self.entries):
                metadata = self.entries[chunk_id].get("metadata", {})
                if all(metadata.get(key) == value for key, value in where.items()):
                    self.entries.pop(chunk_id, None)

    def modify(self, *, metadata: dict[str, Any]) -> None:
        self.metadata.update(metadata)


def make_paths(root: Path) -> WorkspacePaths:
    database_path = root / "metaos.sqlite3"
    initialize_database(database_path)
    return WorkspacePaths(
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


def make_service(
    paths: WorkspacePaths,
    collection: FakeCollection,
    provider: FakeEmbeddingProvider,
) -> RetrievalService:
    service = RetrievalService.__new__(RetrievalService)
    service.paths = paths
    service.embedding_provider = provider
    service.upsert_batch_size = 1
    service.chunk_repository = ChunkRepository(paths.database)
    service.knowledge_repository = KnowledgeRepository(paths.database)
    service.collection = lambda: collection  # type: ignore[method-assign]
    return service


def seed_item(paths: WorkspacePaths, chunk_ids: list[str]) -> tuple[KnowledgeItem, ChunkRepository]:
    item = KnowledgeItem(
        id="ki_resume",
        title="Resume Test",
        category=KnowledgeCategory.uncategorized,
    )
    knowledge_repo = KnowledgeRepository(paths.database)
    chunk_repo = ChunkRepository(paths.database)
    knowledge_repo.add(item)
    chunk_repo.add_many(
        [
            Chunk(
                id=chunk_id,
                knowledge_item_id=item.id,
                text=f"text for {chunk_id}",
                ordinal=index,
            )
            for index, chunk_id in enumerate(chunk_ids)
        ]
    )
    return item, chunk_repo


def embedding_ids(chunk_repo: ChunkRepository, item_id: str) -> dict[str, str | None]:
    return {
        chunk.id: chunk.embedding_id
        for chunk in chunk_repo.list_by_knowledge_item(item_id, limit=100)
    }


class RetrievalResumeTests(unittest.TestCase):
    def test_index_resume_skips_existing_chunks_and_indexes_missing_chunks(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            paths = make_paths(Path(temp_dir))
            item, chunk_repo = seed_item(paths, ["chunk_1", "chunk_2", "chunk_3"])
            collection = FakeCollection(
                {
                    "chunk_1": {
                        "metadata": {"knowledge_item_id": item.id},
                    }
                }
            )
            provider = FakeEmbeddingProvider()
            service = make_service(paths, collection, provider)
            progress: list[tuple[int, int]] = []

            stats = service.index_knowledge_item(
                item.id,
                progress_callback=lambda done, total: progress.append((done, total)),
            )

            self.assertEqual(stats.target_chunks, 3)
            self.assertEqual(stats.skipped_chunks, 1)
            self.assertEqual(stats.indexed_chunks, 2)
            self.assertEqual(stats.deleted_index_entries, 0)
            self.assertEqual(collection.deleted_ids, [])
            self.assertEqual(set(collection.entries), {"chunk_1", "chunk_2", "chunk_3"})
            self.assertEqual(provider.embed_calls, [["text for chunk_2", "text for chunk_3"]])
            self.assertEqual(progress[0], (1, 3))
            self.assertEqual(progress[-1], (3, 3))
            self.assertEqual(
                embedding_ids(chunk_repo, item.id),
                {"chunk_1": "chunk_1", "chunk_2": "chunk_2", "chunk_3": "chunk_3"},
            )

    def test_index_resume_deletes_stale_chunk_ids_for_item(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            paths = make_paths(Path(temp_dir))
            item, chunk_repo = seed_item(paths, ["chunk_1"])
            collection = FakeCollection(
                {
                    "chunk_1": {"metadata": {"knowledge_item_id": item.id}},
                    "chunk_old": {"metadata": {"knowledge_item_id": item.id}},
                    "chunk_other": {"metadata": {"knowledge_item_id": "other"}},
                }
            )
            provider = FakeEmbeddingProvider()
            service = make_service(paths, collection, provider)

            stats = service.index_knowledge_item(item.id)

            self.assertEqual(stats.indexed_chunks, 0)
            self.assertEqual(stats.skipped_chunks, 1)
            self.assertEqual(stats.deleted_index_entries, 1)
            self.assertEqual(collection.deleted_ids, ["chunk_old"])
            self.assertEqual(set(collection.entries), {"chunk_1", "chunk_other"})
            self.assertEqual(provider.embed_calls, [])
            self.assertEqual(embedding_ids(chunk_repo, item.id), {"chunk_1": "chunk_1"})

    def test_force_rebuild_deletes_item_entries_before_indexing(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            paths = make_paths(Path(temp_dir))
            item, chunk_repo = seed_item(paths, ["chunk_1", "chunk_2"])
            collection = FakeCollection(
                {
                    "chunk_1": {"metadata": {"knowledge_item_id": item.id}},
                    "chunk_old": {"metadata": {"knowledge_item_id": item.id}},
                    "chunk_other": {"metadata": {"knowledge_item_id": "other"}},
                }
            )
            provider = FakeEmbeddingProvider()
            service = make_service(paths, collection, provider)

            stats = service.index_knowledge_item(item.id, force_rebuild=True)

            self.assertEqual(stats.force_rebuild, True)
            self.assertEqual(stats.indexed_chunks, 2)
            self.assertEqual(stats.skipped_chunks, 0)
            self.assertEqual(stats.deleted_index_entries, 2)
            self.assertEqual(collection.deleted_wheres, [{"knowledge_item_id": item.id}])
            self.assertEqual(set(collection.entries), {"chunk_1", "chunk_2", "chunk_other"})
            self.assertEqual(
                embedding_ids(chunk_repo, item.id),
                {"chunk_1": "chunk_1", "chunk_2": "chunk_2"},
            )


if __name__ == "__main__":
    unittest.main()
