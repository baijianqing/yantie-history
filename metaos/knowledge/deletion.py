"""Knowledge item deletion orchestration."""

from __future__ import annotations

from dataclasses import dataclass

from metaos.core.schemas import KnowledgeItem
from metaos.retrieval.service import RetrievalService
from metaos.workspace.catalog import ChunkRepository, KnowledgeRepository
from metaos.workspace.paths import WorkspacePaths, ensure_workspace


@dataclass(frozen=True)
class KnowledgeDeletionResult:
    item_id: str
    title: str
    deleted_chunks: int
    deleted_index_entries: int

    def as_dict(self) -> dict[str, int | str]:
        return {
            "item_id": self.item_id,
            "title": self.title,
            "deleted_chunks": self.deleted_chunks,
            "deleted_index_entries": self.deleted_index_entries,
        }


class KnowledgeDeletionService:
    def __init__(
        self,
        paths: WorkspacePaths | None = None,
        knowledge_repository: KnowledgeRepository | None = None,
        chunk_repository: ChunkRepository | None = None,
        retrieval_service: RetrievalService | None = None,
    ):
        self.paths = paths or ensure_workspace()
        self.knowledge_repository = knowledge_repository or KnowledgeRepository(self.paths.database)
        self.chunk_repository = chunk_repository or ChunkRepository(self.paths.database)
        self.retrieval_service = retrieval_service or RetrievalService(self.paths)

    def delete(self, item_id: str) -> KnowledgeDeletionResult:
        item = self.knowledge_repository.get(item_id)
        deleted_chunks = self.chunk_repository.count_by_knowledge_item(item_id)
        deleted_index_entries = self.retrieval_service.delete_knowledge_item(item_id)
        self.chunk_repository.delete_by_knowledge_item(item_id)
        self.knowledge_repository.delete(item_id)
        return deletion_result(item, deleted_chunks, deleted_index_entries)


def deletion_result(
    item: KnowledgeItem,
    deleted_chunks: int,
    deleted_index_entries: int,
) -> KnowledgeDeletionResult:
    return KnowledgeDeletionResult(
        item_id=item.id,
        title=item.title,
        deleted_chunks=deleted_chunks,
        deleted_index_entries=deleted_index_entries,
    )
