"""Chroma-backed chunk indexing and retrieval."""

from __future__ import annotations

import json
import time
from dataclasses import dataclass
from typing import Any, Callable

import chromadb
from chromadb.config import Settings

from metaos.core.config import get_settings
from metaos.core.errors import EmbeddingProviderError
from metaos.core.schemas import Chunk
from metaos.retrieval.embeddings import EmbeddingProvider, make_embedding_provider
from metaos.workspace.catalog import ChunkRepository, KnowledgeRepository
from metaos.workspace.paths import WorkspacePaths, ensure_workspace


COLLECTION_NAME = "metaos_chunks"
DEFAULT_UPSERT_BATCH_SIZE = 128
ProgressCallback = Callable[[int, int], None]


@dataclass(frozen=True)
class IndexStats:
    indexed_chunks: int
    collection_count: int
    embedding_provider: str
    embedding_model: str
    embedding_dimensions: int | None
    target_chunks: int = 0
    skipped_chunks: int = 0
    deleted_index_entries: int = 0
    force_rebuild: bool = False
    collection_name: str = COLLECTION_NAME
    embed_seconds: float = 0.0
    upsert_seconds: float = 0.0
    metadata_seconds: float = 0.0
    total_index_seconds: float = 0.0
    batch_count: int = 0
    embed_batch_count: int = 0
    upsert_batch_count: int = 0
    avg_batch_size: float = 0.0
    avg_embed_batch_size: float = 0.0
    avg_upsert_batch_size: float = 0.0
    chunks_per_second: float = 0.0
    embed_seconds_per_chunk: float = 0.0
    upsert_seconds_per_chunk: float = 0.0
    embedding_batch_size: int | None = None
    embedding_num_gpu: int | None = None
    chroma_upsert_batch_size: int | None = None

    def as_dict(self) -> dict[str, Any]:
        return {
            "indexed_chunks": self.indexed_chunks,
            "collection_count": self.collection_count,
            "collection_name": self.collection_name,
            "embedding_provider": self.embedding_provider,
            "embedding_model": self.embedding_model,
            "embedding_dimensions": self.embedding_dimensions,
            "target_chunks": self.target_chunks,
            "skipped_chunks": self.skipped_chunks,
            "deleted_index_entries": self.deleted_index_entries,
            "force_rebuild": self.force_rebuild,
            "embed_seconds": self.embed_seconds,
            "upsert_seconds": self.upsert_seconds,
            "metadata_seconds": self.metadata_seconds,
            "total_index_seconds": self.total_index_seconds,
            "batch_count": self.batch_count,
            "embed_batch_count": self.embed_batch_count,
            "upsert_batch_count": self.upsert_batch_count,
            "avg_batch_size": self.avg_batch_size,
            "avg_embed_batch_size": self.avg_embed_batch_size,
            "avg_upsert_batch_size": self.avg_upsert_batch_size,
            "chunks_per_second": self.chunks_per_second,
            "embed_seconds_per_chunk": self.embed_seconds_per_chunk,
            "upsert_seconds_per_chunk": self.upsert_seconds_per_chunk,
            "embedding_batch_size": self.embedding_batch_size,
            "embedding_num_gpu": self.embedding_num_gpu,
            "chroma_upsert_batch_size": self.chroma_upsert_batch_size,
        }


@dataclass(frozen=True)
class SearchResult:
    chunk_id: str
    knowledge_item_id: str
    text: str
    heading_path: list[str]
    ordinal: int | None
    score: float
    distance: float | None
    source_id: str | None = None
    asset_id: str | None = None
    file_path: str | None = None

    def as_dict(self) -> dict[str, Any]:
        return {
            "chunk_id": self.chunk_id,
            "knowledge_item_id": self.knowledge_item_id,
            "text": self.text,
            "heading_path": self.heading_path,
            "ordinal": self.ordinal,
            "score": self.score,
            "distance": self.distance,
            "source_id": self.source_id,
            "asset_id": self.asset_id,
            "file_path": self.file_path,
        }


class RetrievalService:
    def __init__(
        self,
        paths: WorkspacePaths | None = None,
        embedding_provider: EmbeddingProvider | None = None,
    ):
        self.paths = paths or ensure_workspace()
        self.embedding_provider = embedding_provider or make_embedding_provider()
        settings = get_settings()
        self._ensure_chroma_version(settings.chroma_required_version)
        self.upsert_batch_size = max(
            1,
            min(settings.chroma_upsert_batch_size, DEFAULT_UPSERT_BATCH_SIZE),
        )
        self.chunk_repository = ChunkRepository(self.paths.database)
        self.knowledge_repository = KnowledgeRepository(self.paths.database)
        self.chroma_path = self.paths.index / "chroma"
        self.chroma_path.mkdir(parents=True, exist_ok=True)
        self.client = chromadb.PersistentClient(
            path=str(self.chroma_path),
            settings=Settings(anonymized_telemetry=False),
        )

    def _ensure_chroma_version(self, required_version: str) -> None:
        current_version = getattr(chromadb, "__version__", "unknown")
        if required_version and current_version != required_version:
            raise EmbeddingProviderError(
                "ChromaDB 版本不匹配。"
                f"当前版本是 {current_version}，要求版本是 {required_version}。"
                "请使用 .venv311 运行索引、检索和 RAG。"
            )

    def index_knowledge_item(
        self,
        item_id: str,
        progress_callback: ProgressCallback | None = None,
        *,
        force_rebuild: bool = False,
    ) -> IndexStats:
        self.knowledge_repository.get(item_id)
        chunks = self.chunk_repository.list_by_knowledge_item(item_id, limit=100000)
        collection = self.collection()
        if int(collection.count()) > 0:
            self._ensure_collection_compatible(collection, self._ensure_provider_dimensions())
        current_chunk_ids = {chunk.id for chunk in chunks}
        if force_rebuild:
            deleted_entries = self._delete_knowledge_item(collection, item_id, ignore_errors=False)
            self.chunk_repository.clear_embedding_ids_by_knowledge_item(item_id)
            already_indexed_ids: set[str] = set()
        else:
            already_indexed_ids = self._indexed_chunk_ids(collection, item_id=item_id)
            stale_ids = sorted(already_indexed_ids - current_chunk_ids)
            deleted_entries = self._delete_chunk_ids(collection, stale_ids, ignore_errors=False)
            already_indexed_ids.difference_update(stale_ids)
            if already_indexed_ids:
                self.chunk_repository.update_embedding_ids(sorted(already_indexed_ids))

        chunks_to_index = [chunk for chunk in chunks if chunk.id not in already_indexed_ids]
        return self._index_chunks(
            chunks_to_index,
            collection,
            progress_callback=progress_callback,
            progress_offset=len(already_indexed_ids),
            progress_total=len(chunks),
            skipped_chunks=len(already_indexed_ids),
            deleted_index_entries=deleted_entries,
            force_rebuild=force_rebuild,
        )

    def rebuild_all(
        self,
        progress_callback: ProgressCallback | None = None,
        *,
        force_rebuild: bool = False,
    ) -> IndexStats:
        chunks = self.chunk_repository.list_all(limit=100000)
        if force_rebuild:
            deleted_entries = int(self.collection().count())
            self.reset_collection()
            self.chunk_repository.clear_all_embedding_ids()
            collection = self.collection()
            already_indexed_ids: set[str] = set()
        else:
            collection = self.collection()
            if int(collection.count()) > 0:
                self._ensure_collection_compatible(collection, self._ensure_provider_dimensions())
            current_chunk_ids = {chunk.id for chunk in chunks}
            already_indexed_ids = self._indexed_chunk_ids(collection)
            stale_ids = sorted(already_indexed_ids - current_chunk_ids)
            deleted_entries = self._delete_chunk_ids(collection, stale_ids, ignore_errors=False)
            already_indexed_ids.difference_update(stale_ids)
            if already_indexed_ids:
                self.chunk_repository.update_embedding_ids(sorted(already_indexed_ids))

        chunks_to_index = [chunk for chunk in chunks if chunk.id not in already_indexed_ids]
        return self._index_chunks(
            chunks_to_index,
            collection,
            progress_callback=progress_callback,
            progress_offset=len(already_indexed_ids),
            progress_total=len(chunks),
            skipped_chunks=len(already_indexed_ids),
            deleted_index_entries=deleted_entries,
            force_rebuild=force_rebuild,
        )

    def delete_knowledge_item(self, item_id: str) -> int:
        collection = self.collection()
        return self._delete_knowledge_item(collection, item_id, ignore_errors=False)

    def search(self, query: str, top_k: int = 5) -> list[SearchResult]:
        query = query.strip()
        if not query:
            return []
        query_embeddings = self.embedding_provider.embed([query])
        dimensions = len(query_embeddings[0]) if query_embeddings else None
        collection = self.collection()
        collection_count = int(collection.count())
        if collection_count <= 0:
            return []
        self._ensure_collection_compatible(collection, dimensions)
        result = collection.query(
            query_embeddings=query_embeddings,
            n_results=max(1, min(top_k, 20, collection_count)),
            include=["documents", "metadatas", "distances"],
        )
        return self._parse_search_results(result)

    def collection_count(self) -> int:
        return int(self.collection().count())

    def embedding_status(self) -> dict[str, Any]:
        settings = get_settings()
        collection = self.collection()
        return {
            "embedding_provider": self.embedding_provider.name,
            "embedding_model": self.embedding_provider.model,
            "embedding_dimensions": self.embedding_provider.dimensions,
            "embedding_batch_size": getattr(self.embedding_provider, "batch_size", None),
            "embedding_timeout": getattr(self.embedding_provider, "timeout", None),
            "embedding_num_gpu": getattr(self.embedding_provider, "num_gpu", None),
            "chroma_upsert_batch_size": self.upsert_batch_size,
            "index_job_timeout_seconds": settings.index_job_timeout_seconds,
            "rebuild_index_job_timeout_seconds": settings.rebuild_index_job_timeout_seconds,
            "collection_name": COLLECTION_NAME,
            "collection_count": int(collection.count()),
            "collection_metadata": dict(collection.metadata or {}),
        }

    def collection(self):
        return self.client.get_or_create_collection(
            COLLECTION_NAME,
            metadata=self.collection_metadata(),
            embedding_function=None,
        )

    def reset_collection(self) -> None:
        names = {getattr(collection, "name", str(collection)) for collection in self.client.list_collections()}
        if COLLECTION_NAME in names:
            self.client.delete_collection(COLLECTION_NAME)

    def _index_chunks(
        self,
        chunks: list[Chunk],
        collection,
        progress_callback: ProgressCallback | None = None,
        *,
        progress_offset: int = 0,
        progress_total: int | None = None,
        skipped_chunks: int = 0,
        deleted_index_entries: int = 0,
        force_rebuild: bool = False,
    ) -> IndexStats:
        indexed_ids: list[str] = []
        total = len(chunks)
        progress_target = total if progress_total is None else progress_total
        total_start = time.perf_counter()
        embed_seconds = 0.0
        upsert_seconds = 0.0
        metadata_seconds = 0.0
        embed_batch_count = 0
        upsert_batch_count = 0
        embed_item_count = 0
        upsert_item_count = 0
        dimensions: int | None = None
        embed_batch_size = max(
            1,
            int(getattr(self.embedding_provider, "batch_size", self.upsert_batch_size) or 1),
        )
        pending_ids: list[str] = []
        pending_documents: list[str] = []
        pending_embeddings: list[list[float]] = []
        pending_metadatas: list[dict[str, str | int]] = []

        def flush_upserts(*, force: bool = False) -> None:
            nonlocal metadata_seconds
            nonlocal upsert_seconds
            nonlocal upsert_batch_count
            nonlocal upsert_item_count

            while pending_ids and (force or len(pending_ids) >= self.upsert_batch_size):
                take = min(len(pending_ids), self.upsert_batch_size)
                ids = pending_ids[:take]
                documents = pending_documents[:take]
                embeddings = pending_embeddings[:take]
                metadatas = pending_metadatas[:take]

                self._ensure_collection_compatible(collection, dimensions)
                upsert_start = time.perf_counter()
                collection.upsert(
                    ids=ids,
                    documents=documents,
                    embeddings=embeddings,
                    metadatas=metadatas,
                )
                upsert_seconds += time.perf_counter() - upsert_start
                upsert_batch_count += 1
                upsert_item_count += len(ids)

                metadata_start = time.perf_counter()
                self._update_collection_metadata(collection, dimensions)
                self.chunk_repository.update_embedding_ids(ids)
                metadata_seconds += time.perf_counter() - metadata_start

                indexed_ids.extend(ids)
                del pending_ids[:take]
                del pending_documents[:take]
                del pending_embeddings[:take]
                del pending_metadatas[:take]

                if progress_callback:
                    progress_callback(progress_offset + len(indexed_ids), progress_target)

                if force:
                    continue

        if progress_callback:
            progress_callback(progress_offset, progress_target)
        for start in range(0, total, embed_batch_size):
            batch = chunks[start : start + embed_batch_size]
            embed_batch_count += 1
            embed_item_count += len(batch)
            metadata_start = time.perf_counter()
            ids = [chunk.id for chunk in batch]
            documents = [chunk.text for chunk in batch]
            metadatas = [chunk_metadata(chunk) for chunk in batch]
            metadata_seconds += time.perf_counter() - metadata_start

            embed_start = time.perf_counter()
            embeddings = self.embedding_provider.embed(documents)
            embed_seconds += time.perf_counter() - embed_start

            dimensions = len(embeddings[0]) if embeddings else dimensions
            pending_ids.extend(ids)
            pending_documents.extend(documents)
            pending_embeddings.extend(embeddings)
            pending_metadatas.extend(metadatas)
            flush_upserts()

        flush_upserts(force=True)

        total_index_seconds = time.perf_counter() - total_start
        indexed_count = len(indexed_ids)
        return IndexStats(
            indexed_chunks=indexed_count,
            collection_count=int(collection.count()),
            embedding_provider=self.embedding_provider.name,
            embedding_model=self.embedding_provider.model,
            embedding_dimensions=self.embedding_provider.dimensions,
            target_chunks=progress_target,
            skipped_chunks=skipped_chunks,
            deleted_index_entries=deleted_index_entries,
            force_rebuild=force_rebuild,
            embed_seconds=round(embed_seconds, 3),
            upsert_seconds=round(upsert_seconds, 3),
            metadata_seconds=round(metadata_seconds, 3),
            total_index_seconds=round(total_index_seconds, 3),
            batch_count=upsert_batch_count,
            embed_batch_count=embed_batch_count,
            upsert_batch_count=upsert_batch_count,
            avg_batch_size=round(upsert_item_count / upsert_batch_count, 2)
            if upsert_batch_count
            else 0.0,
            avg_embed_batch_size=round(embed_item_count / embed_batch_count, 2)
            if embed_batch_count
            else 0.0,
            avg_upsert_batch_size=round(upsert_item_count / upsert_batch_count, 2)
            if upsert_batch_count
            else 0.0,
            chunks_per_second=round(indexed_count / total_index_seconds, 4)
            if total_index_seconds > 0
            else 0.0,
            embed_seconds_per_chunk=round(embed_seconds / indexed_count, 4)
            if indexed_count
            else 0.0,
            upsert_seconds_per_chunk=round(upsert_seconds / indexed_count, 4)
            if indexed_count
            else 0.0,
            embedding_batch_size=getattr(self.embedding_provider, "batch_size", None),
            embedding_num_gpu=getattr(self.embedding_provider, "num_gpu", None),
            chroma_upsert_batch_size=self.upsert_batch_size,
        )

    def _indexed_chunk_ids(self, collection, *, item_id: str | None = None) -> set[str]:
        count = int(collection.count())
        if count <= 0:
            return set()
        kwargs: dict[str, Any] = {"limit": count}
        if item_id:
            kwargs["where"] = {"knowledge_item_id": item_id}
        result = self._collection_get(collection, **kwargs)
        return {str(chunk_id) for chunk_id in result.get("ids", [])}

    def _collection_get(self, collection, **kwargs) -> dict[str, Any]:
        try:
            return collection.get(include=[], **kwargs)
        except (TypeError, ValueError):
            return collection.get(include=["metadatas"], **kwargs)

    def _delete_chunk_ids(
        self,
        collection,
        chunk_ids: list[str],
        *,
        ignore_errors: bool = True,
    ) -> int:
        if not chunk_ids:
            return 0
        deleted = 0
        try:
            for start in range(0, len(chunk_ids), self.upsert_batch_size):
                batch = chunk_ids[start : start + self.upsert_batch_size]
                collection.delete(ids=batch)
                deleted += len(batch)
            return deleted
        except Exception:
            if not ignore_errors:
                raise
            return deleted

    def _delete_knowledge_item(self, collection, item_id: str, *, ignore_errors: bool = True) -> int:
        before_count = int(collection.count())
        try:
            collection.delete(where={"knowledge_item_id": item_id})
            after_count = int(collection.count())
            return max(0, before_count - after_count)
        except Exception:
            if not ignore_errors:
                raise
            return 0

    def collection_metadata(
        self,
        dimensions: int | None = None,
        *,
        include_hnsw: bool = True,
    ) -> dict[str, str | int]:
        known_dimensions = dimensions or self.embedding_provider.dimensions or 0
        metadata: dict[str, str | int] = {
            "embedding_provider": self.embedding_provider.name,
            "embedding_model": self.embedding_provider.model,
            "embedding_dimensions": int(known_dimensions),
        }
        if include_hnsw:
            metadata["hnsw:space"] = "cosine"
        return metadata

    def _update_collection_metadata(self, collection, dimensions: int | None) -> None:
        if dimensions is None:
            return
        collection.modify(metadata=self.collection_metadata(dimensions, include_hnsw=False))

    def _ensure_collection_compatible(self, collection, dimensions: int | None) -> None:
        if int(collection.count()) <= 0:
            return
        metadata = collection.metadata or {}
        expected = self.collection_metadata(dimensions)
        provider_model_mismatches = []
        for key in ("embedding_provider", "embedding_model"):
            if str(metadata.get(key, "")) != str(expected[key]):
                provider_model_mismatches.append(
                    f"{key}: existing={metadata.get(key)!r}, current={expected[key]!r}"
                )
        existing_dimensions = metadata.get("embedding_dimensions")
        if (
            not provider_model_mismatches
            and dimensions is not None
            and str(existing_dimensions) in {"", "0", "None"}
        ):
            self._update_collection_metadata(collection, dimensions)
            return

        mismatches = []
        for key in ("embedding_provider", "embedding_model", "embedding_dimensions"):
            if str(metadata.get(key, "")) != str(expected[key]):
                mismatches.append(
                    f"{key}: existing={metadata.get(key)!r}, current={expected[key]!r}"
                )
        if mismatches:
            raise EmbeddingProviderError(
                "Existing Chroma index was built with a different embedding provider. "
                "请先执行“重建全部索引”，再进行索引或搜索。 "
                + "; ".join(mismatches)
            )

    def _ensure_provider_dimensions(self) -> int | None:
        if self.embedding_provider.dimensions is not None:
            return self.embedding_provider.dimensions
        probe = self.embedding_provider.embed(["MetaOS embedding dimension probe"])
        return len(probe[0]) if probe else None

    def _parse_search_results(self, result: dict[str, Any]) -> list[SearchResult]:
        ids = first_result_list(result.get("ids"))
        documents = first_result_list(result.get("documents"))
        metadatas = first_result_list(result.get("metadatas"))
        distances = first_result_list(result.get("distances"))

        results: list[SearchResult] = []
        for index, chunk_id in enumerate(ids):
            metadata = metadatas[index] if index < len(metadatas) and metadatas[index] else {}
            distance = distances[index] if index < len(distances) else None
            results.append(
                SearchResult(
                    chunk_id=chunk_id,
                    knowledge_item_id=str(metadata.get("knowledge_item_id", "")),
                    text=documents[index] if index < len(documents) else "",
                    heading_path=json.loads(str(metadata.get("heading_path_json", "[]"))),
                    ordinal=metadata.get("ordinal"),
                    score=distance_to_score(distance),
                    distance=distance,
                    source_id=metadata.get("source_id"),
                    asset_id=metadata.get("asset_id"),
                    file_path=metadata.get("file_path"),
                )
            )
        return results


def chunk_metadata(chunk: Chunk) -> dict[str, str | int]:
    citation = chunk.citation
    return {
        "knowledge_item_id": chunk.knowledge_item_id,
        "heading_path": " / ".join(chunk.heading_path),
        "heading_path_json": json.dumps(chunk.heading_path, ensure_ascii=False),
        "ordinal": int(chunk.ordinal),
        "char_count": int(chunk.char_count or len(chunk.text)),
        "source_id": citation.source_id if citation and citation.source_id else "",
        "asset_id": citation.asset_id if citation and citation.asset_id else "",
        "file_path": str(citation.file_path) if citation and citation.file_path else "",
    }


def first_result_list(value: Any) -> list[Any]:
    if not value:
        return []
    first = value[0]
    return first if isinstance(first, list) else value


def distance_to_score(distance: float | None) -> float:
    if distance is None:
        return 0.0
    return max(0.0, min(1.0, 1.0 - float(distance)))
